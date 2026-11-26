"""Command-line entry point for Code2Img."""

import argparse
import os
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image

from .archive import extract_zip, new_directory, write_zip, zip_members
from .qr import IMAGE_SUFFIXES, OUTPUT_FORMATS, QR_SCALE, grid_image, qr_image, read_qrs, save_image, write_qr
from .receiver import serve
from .source_tree import write_source_tree
from .transfer import (
    DEFAULT_PART_SIZE, MAX_PART_SIZE, MAX_PARTS, MAX_SINGLE_QR_SIZE, MIN_PART_SIZE,
    Part, Transfer, part_offsets, split_zip,
)


def pack(args: argparse.Namespace) -> None:
    source = args.source.resolve(strict=True)
    if not (source.is_dir() or source.is_file()):
        raise ValueError("Đường dẫn nguồn phải là tệp thường hoặc thư mục.")
    if os.path.lexists(args.output):
        raise ValueError(f"Đường dẫn đích đã tồn tại: {args.output}.")
    with tempfile.TemporaryFile() as archive:
        entries = write_zip(source, archive, args.exclude, args.include_all)
        if not entries:
            raise ValueError("Nguồn trống sau khi áp dụng bộ lọc.")
        size = archive.tell()
        ends = tuple(entry.end for entry in entries)
        sections = part_offsets(size, args.part_size, ends)
        total = sum(map(len, sections))
        if total > MAX_PARTS:
            raise ValueError(f"ZIP {size:,} byte vượt quá số ảnh QR tối đa ({MAX_PARTS:,}).")
        archive.seek(0)
        with ZipFile(archive) as zipped:
            zip_members(zipped)
        archive.seek(0)
        data = archive.read()
    suffix = OUTPUT_FORMATS[args.format]
    project_image = args.output / f"project{suffix}"
    use_grid = not args.parts_only and size > MAX_SINGLE_QR_SIZE
    tiles = []
    with new_directory(args.output):
        parts_directory = args.output / "parts"
        parts_directory.mkdir()
        for part in split_zip(data, args.part_size, ends):
            path = parts_directory / f"qr-{part.number:05d}-of-{total:05d}{suffix}"
            if use_grid:
                tile = qr_image(part, scale=1)
                tiles.append(tile)
                size_at_scale = (tile.width * QR_SCALE, tile.height * QR_SCALE)
                save_image(tile.resize(size_at_scale, Image.Resampling.NEAREST), path)
            else:
                write_qr(part, path)
        if not args.parts_only:
            combined = grid_image(tiles) if use_grid else qr_image(Part(sha256(data).digest(), 1, 1, data))
            save_image(combined, project_image)
        tree_root = source if source.is_dir() else source.parent
        write_source_tree(args.output / "source-tree.txt", tree_root, entries, sections)
    count = sum(not entry.name.endswith("/") for entry in entries)
    print(f"Đã chuyển {count} tệp ({size:,} byte ZIP) thành {total} ảnh QR trong {parts_directory}.")
    if not args.parts_only:
        combined_parts = total if use_grid else 1
        print(f"Ảnh tổng hợp ({combined_parts} QR) ở {project_image}.")
    print(f"Cây mã nguồn ở {args.output / 'source-tree.txt'}.")


def unpack(args: argparse.Namespace) -> None:
    if os.path.lexists(args.output):
        raise ValueError(f"Đường dẫn đích đã tồn tại: {args.output}.")
    transfer = Transfer()
    for input_path in args.images:
        if input_path.is_dir():
            paths = images_in(input_path)
            parts_directory = input_path / "parts"
            if not paths and parts_directory.is_dir():
                paths = images_in(parts_directory)
        elif input_path.is_file():
            paths = [input_path]
        else:
            raise ValueError(f"Không tìm thấy ảnh hoặc thư mục: {input_path}.")
        for path in paths:
            try:
                parts = read_qrs(path)
            except (OSError, ValueError, Image.DecompressionBombError) as error:
                print(f"Bỏ qua {path}: {error}", file=sys.stderr)
                continue
            if not parts:
                print(f"Không tìm thấy QR của Code2Img trong {path}.", file=sys.stderr)
            for part in parts:
                transfer.add(part)
    count = extract_zip(transfer.assemble(), args.output)
    print(f"Đã kiểm tra SHA-256 và khôi phục {count} tệp vào {args.output}.")


def images_in(directory: Path) -> list[Path]:
    return sorted(
        path for path in directory.iterdir()
        if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file()
    )


def part_size(value: str) -> int:
    size = int(value)
    if not MIN_PART_SIZE <= size <= MAX_PART_SIZE:
        raise argparse.ArgumentTypeError(f"Chọn từ {MIN_PART_SIZE} đến {MAX_PART_SIZE} byte.")
    return size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chuyển mã nguồn qua ảnh QR và giữ nguyên từng byte.")
    commands = parser.add_subparsers(required=True)

    pack_parser = commands.add_parser("pack", help="Tạo QR từng tệp, ảnh tổng hợp và cây mã nguồn.")
    pack_parser.add_argument("source", type=Path, help="Tệp hoặc thư mục nguồn.")
    pack_parser.add_argument("-o", "--output", type=Path, required=True, help="Thư mục ảnh mới.")
    pack_parser.add_argument("--part-size", type=part_size, default=DEFAULT_PART_SIZE,
                             help="Số byte ZIP tối đa trong mỗi QR riêng. Mặc định %(default)s.")
    pack_parser.add_argument("--format", choices=OUTPUT_FORMATS, default="png",
                             help="Định dạng tệp ảnh. Mặc định %(default)s.")
    pack_parser.add_argument("--parts-only", action="store_true",
                             help="Chỉ xuất ảnh riêng và cây nguồn cho project quá lớn.")
    pack_parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                             help="Bỏ qua mẫu đường dẫn tương đối với nguồn. Có thể lặp lại.")
    pack_parser.add_argument("--include-all", action="store_true",
                             help="Bỏ bộ lọc thư mục mặc định.")
    pack_parser.set_defaults(run=pack)

    unpack_parser = commands.add_parser("unpack", help="Khôi phục từ ảnh tổng hợp hoặc các ảnh QR riêng.")
    unpack_parser.add_argument("images", nargs="+", type=Path, help="Các ảnh hoặc thư mục ảnh.")
    unpack_parser.add_argument("-o", "--output", type=Path, required=True, help="Thư mục giải nén mới.")
    unpack_parser.set_defaults(run=unpack)

    serve_parser = commands.add_parser("serve", help="Mở giao diện nhận ảnh trong trình duyệt.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Địa chỉ lắng nghe. Mặc định %(default)s.")
    serve_parser.add_argument("--port", type=int, default=8765, help="Cổng HTTP. Mặc định %(default)s.")
    serve_parser.set_defaults(run=lambda args: serve(args.host, args.port))

    args = parser.parse_args(argv)
    try:
        args.run(args)
    except (OSError, ValueError, BadZipFile, NotImplementedError, RuntimeError) as error:
        print(f"Lỗi: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
