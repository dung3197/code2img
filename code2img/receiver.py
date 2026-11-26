"""Serve the local receiver and decode images without storing uploads."""

import json
from base64 import b64decode, b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from PIL import Image

from .archive import zip_members
from .qr import read_qrs
from .transfer import HEADER, MAX_PART_SIZE, MAX_PARTS, MAX_SINGLE_QR_SIZE, Part, Transfer

MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_BASE64_PART = 4 * ((HEADER.size + MAX_SINGLE_QR_SIZE + 2) // 3)
MAX_JSON_BYTES = MAX_PARTS * (4 * ((HEADER.size + MAX_PART_SIZE + 2) // 3) + 4) + 2


class Receiver(BaseHTTPRequestHandler):
    timeout = 30

    def reply(self, status: int, content_type: str, data: bytes, filename: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def reply_json(self, status: int, data: dict) -> None:
        self.reply(status, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode())

    def read_body(self, content_type: str, limit: int) -> bytes:
        if self.headers.get_content_type() != content_type:
            raise ValueError("Định dạng yêu cầu không được hỗ trợ.")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= limit:
            raise ValueError(f"Dữ liệu trống hoặc vượt quá {limit:,} byte.")
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError("Dữ liệu nhận được chưa đầy đủ.")
        return data

    def do_GET(self) -> None:
        if self.path == "/":
            page = files("code2img").joinpath("receiver.html").read_bytes()
            self.reply(200, "text/html; charset=utf-8", page)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path not in {"/scan", "/restore"}:
            self.send_error(404)
            return
        try:
            if self.path == "/scan":
                result = self.scan_image()
            else:
                result = self.restore_zip()
        except (BadZipFile, OSError, ValueError, Image.DecompressionBombError) as error:
            self.reply_json(400, {"error": str(error)})
            return
        if self.path == "/scan":
            self.reply_json(200, {"parts": result})
        else:
            self.reply(200, "application/zip", result, "code2img.zip")

    def scan_image(self) -> list[dict]:
        data = self.read_body("application/octet-stream", MAX_IMAGE_BYTES)
        parts = read_qrs(BytesIO(data))
        if not parts:
            raise ValueError("Không tìm thấy QR của Code2Img. Hãy lấy nét và giữ đủ viền trắng.")
        return [
            {"id": part.digest.hex(), "number": part.number, "total": part.total,
             "payload": b64encode(part.encode()).decode("ascii")}
            for part in parts
        ]

    def restore_zip(self) -> bytes:
        body = self.read_body("application/json", MAX_JSON_BYTES)
        payloads = json.loads(body)
        if not isinstance(payloads, list) or not 1 <= len(payloads) <= MAX_PARTS:
            raise ValueError("Danh sách các phần QR không hợp lệ.")
        transfer = Transfer()
        for payload in payloads:
            if not isinstance(payload, str) or len(payload) > MAX_BASE64_PART:
                raise ValueError("Dữ liệu phần QR không hợp lệ.")
            transfer.add(Part.decode(b64decode(payload, validate=True)))
        data = transfer.assemble()
        with ZipFile(BytesIO(data)) as archive:
            zip_members(archive)
        return data


def serve(host: str, port: int) -> None:
    if not 0 <= port <= 65535:
        raise ValueError("Cổng HTTP phải từ 0 đến 65535.")
    with ThreadingHTTPServer((host, port), Receiver) as server:
        print(f"Giao diện nhận ảnh QR ở http://{host}:{server.server_port}", flush=True)
        server.serve_forever()
