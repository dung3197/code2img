"""Read and write Code2Img parts as images."""

from itertools import pairwise
from math import dist, isqrt
from pathlib import Path
from typing import BinaryIO

import zxingcpp
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from pillow_heif import register_heif_opener

from .transfer import MAGIC, Part

register_heif_opener()

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".gif", ".avif"}
OUTPUT_FORMATS = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp"}
MAX_IMAGE_PIXELS = 50_000_000
MAX_GRID_PIXELS = 25_000_000
QR_SCALE = 8
GRID_COLOR = (26, 117, 190)


def qr_image(part: Part, scale: int = QR_SCALE) -> Image.Image:
    barcode = zxingcpp.create_barcode(part.encode(), zxingcpp.BarcodeFormat.QRCode, ec_level="Q")
    return Image.fromarray(zxingcpp.write_barcode_to_image(barcode, scale=scale))


def save_image(image: Image.Image, output: Path) -> None:
    if output.suffix == ".jpg":
        image.save(output, quality=95, subsampling=0)
    elif output.suffix == ".webp":
        image.save(output, lossless=True)
    else:
        image.save(output)


def write_qr(part: Part, output: Path) -> None:
    save_image(qr_image(part), output)


def grid_image(tiles: list[Image.Image]) -> Image.Image:
    columns = 1 + isqrt(len(tiles) - 1)
    rows = (len(tiles) + columns - 1) // columns
    rule = 4
    stride = max(tile.width for tile in tiles) + 8
    width = columns * stride + rule
    height = rows * stride + rule
    scale = min(QR_SCALE, isqrt(MAX_GRID_PIXELS // (width * height)))
    if not scale:
        raise ValueError("Lưới QR quá lớn cho một ảnh. Dùng --parts-only để xuất riêng từng phần.")
    sheet = Image.new("RGB", (width, height), GRID_COLOR)
    draw = ImageDraw.Draw(sheet)
    for index in range(columns * rows):
        row, column = divmod(index, columns)
        x, y = column * stride, row * stride
        draw.rectangle((x + rule, y + rule, x + stride - 1, y + stride - 1), fill="white")
        if index < len(tiles):
            tile = tiles[index]
            padding = (stride + rule - tile.width) // 2
            sheet.paste(tile, (x + padding, y + padding))
    return sheet.resize((width * scale, height * scale), Image.Resampling.NEAREST)


def _grid_bands(image: Image.Image, vertical: bool) -> list[tuple[int, int]]:
    pixels = image.load()
    length, span = image.size if vertical else image.size[::-1]
    samples = [span * step // 16 for step in range(1, 16)]
    bands = []
    start = None
    for position in range(length):
        votes = 0
        for across in samples:
            red, green, blue = pixels[position, across] if vertical else pixels[across, position]
            votes += blue - red >= 60 and blue - green >= 35 and green - red >= 25
        if votes >= 10 and start is None:
            start = position
        if votes < 10 and start is not None:
            bands.append((start, position))
            start = None
    if start is not None:
        bands.append((start, length))
    gaps = [((right[0] + right[1]) - (left[0] + left[1])) / 2 for left, right in pairwise(bands)]
    if not gaps or min(gaps) < 25 or max(gaps) - min(gaps) > max(4, min(gaps) * 0.08):
        return []
    return bands


def _read_parts(image: Image.Image, *, pure: bool = False) -> list[Part]:
    barcodes = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode, is_pure=pure)
    return [Part.decode(barcode.bytes) for barcode in barcodes if barcode.bytes.startswith(MAGIC)]


def _read_grid(image: Image.Image) -> list[Part]:
    columns = _grid_bands(image, vertical=True)
    rows = _grid_bands(image, vertical=False)
    if not columns or not rows or len(columns) + len(rows) <= 4:
        return []
    parts = []
    for top, bottom in pairwise(rows):
        for left, right in pairwise(columns):
            tile = image.crop((left[1], top[1], right[0], bottom[0])).convert("L")
            decoded = _read_parts(tile, pure=True) or _read_parts(tile)
            if not decoded and min(tile.size) < 300:
                enlarged = tile.resize((tile.width * 2, tile.height * 2), Image.Resampling.BILINEAR)
                decoded = _read_parts(enlarged)
            parts.extend(decoded)
    return parts


def _rectify_grid(image: Image.Image) -> Image.Image | None:
    preview = image.copy()
    preview.thumbnail((1600, 1600))
    red, green, blue = preview.split()
    mask = ImageChops.darker(
        ImageChops.subtract(blue, red).point(lambda value: 255 if value >= 60 else 0),
        ImageChops.subtract(blue, green).point(lambda value: 255 if value >= 35 else 0),
    ).filter(ImageFilter.MedianFilter(3))
    bounds = mask.getbbox()
    if bounds is None:
        return None
    endpoints = []
    for y in range(bounds[1], bounds[3]):
        band = mask.crop((bounds[0], y, bounds[2], y + 1)).getbbox()
        if band:
            endpoints.extend(((bounds[0] + band[0], y), (bounds[0] + band[2] - 1, y)))
    tl = min(endpoints, key=lambda point: point[0] + point[1])
    tr = max(endpoints, key=lambda point: point[0] - point[1])
    br = max(endpoints, key=lambda point: point[0] + point[1])
    bl = min(endpoints, key=lambda point: point[0] - point[1])
    x_scale, y_scale = image.width / preview.width, image.height / preview.height
    tl, tr, br, bl = [(x * x_scale, y * y_scale) for x, y in (tl, tr, br, bl)]
    width = round(max(dist(tl, tr), dist(bl, br)))
    height = round(max(dist(tl, bl), dist(tr, br)))
    if min(width, height) < 50 or width * height > MAX_IMAGE_PIXELS:
        return None

    # Map the output rectangle back to the four corners of the photographed grid.
    x0, y0 = tl
    x1, y1 = tr
    x2, y2 = br
    x3, y3 = bl
    dx1, dx2, dx3 = x1 - x2, x3 - x2, x0 - x1 + x2 - x3
    dy1, dy2, dy3 = y1 - y2, y3 - y2, y0 - y1 + y2 - y3
    determinant = dx1 * dy2 - dx2 * dy1
    if abs(determinant) < 1:
        return None
    g = (dx3 * dy2 - dx2 * dy3) / determinant
    h = (dx1 * dy3 - dx3 * dy1) / determinant
    coefficients = (
        (x1 - x0 + g * x1) / width, (x3 - x0 + h * x3) / height, x0,
        (y1 - y0 + g * y1) / width, (y3 - y0 + h * y3) / height, y0,
        g / width, h / height,
    )
    return image.transform((width, height), Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BILINEAR)


def _complete(parts: list[Part]) -> bool:
    return bool(parts) and len({part.number for part in parts}) == parts[0].total


def read_qrs(source: Path | BinaryIO) -> list[Part]:
    with Image.open(source) as original:
        if original.width * original.height > MAX_IMAGE_PIXELS:
            raise ValueError("Ảnh vượt quá 50 megapixel.")
        image = ImageOps.exif_transpose(original)
    parts = []
    if image.mode not in {"1", "L", "LA"}:
        color = image if image.mode == "RGB" else image.convert("RGB")
        parts = _read_grid(color)
        if not _complete(parts):
            rectified = _rectify_grid(color)
            if rectified is not None:
                parts.extend(_read_grid(rectified))
    if not _complete(parts):
        parts.extend(_read_parts(image.convert("L")))
    return list(dict.fromkeys(parts))
