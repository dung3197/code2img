"""Split and reassemble a ZIP using versioned, independently scannable parts."""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise
from struct import Struct

MAGIC = b"C2I\x01"
HEADER = Struct(">4s32sHH")
DEFAULT_PART_SIZE = 512
MIN_PART_SIZE = 64
MAX_PART_SIZE = 800
MAX_SINGLE_QR_SIZE = 1600
MAX_PARTS = 65535


@dataclass(frozen=True)
class Part:
    digest: bytes
    number: int
    total: int
    data: bytes

    def encode(self) -> bytes:
        return HEADER.pack(MAGIC, self.digest, self.number, self.total) + self.data

    @classmethod
    def decode(cls, payload: bytes) -> "Part":
        if not HEADER.size < len(payload) <= HEADER.size + MAX_SINGLE_QR_SIZE:
            raise ValueError("Phần QR có độ dài không hợp lệ.")
        magic, digest, number, total = HEADER.unpack_from(payload)
        if magic != MAGIC or not 1 <= number <= total:
            raise ValueError("Phần QR có định dạng hoặc số thứ tự không hợp lệ.")
        if total > 1 and len(payload) > HEADER.size + MAX_PART_SIZE:
            raise ValueError("Phần QR có độ dài không hợp lệ.")
        return cls(digest, number, total, payload[HEADER.size :])


def part_offsets(size: int, part_size: int, entry_ends: tuple[int, ...] = ()) -> list[range]:
    if not MIN_PART_SIZE <= part_size <= MAX_PART_SIZE:
        raise ValueError(f"Kích thước phần QR phải từ {MIN_PART_SIZE} đến {MAX_PART_SIZE} byte.")
    return [range(start, end, part_size) for start, end in pairwise((0, *entry_ends, size))]


def split_zip(archive: bytes, part_size: int, entry_ends: tuple[int, ...] = ()) -> Iterator[Part]:
    sections = part_offsets(len(archive), part_size, entry_ends)
    total = sum(map(len, sections))
    if not 1 <= total <= MAX_PARTS:
        raise ValueError(f"ZIP phải chia được thành từ 1 đến {MAX_PARTS} ảnh QR.")
    digest = hashlib.sha256(archive).digest()
    number = 1
    for offsets in sections:
        for offset in offsets:
            end = min(offset + part_size, offsets.stop)
            yield Part(digest, number, total, archive[offset:end])
            number += 1


class Transfer:
    def __init__(self):
        self.digest: bytes | None = None
        self.total = 0
        self.parts: dict[int, bytes] = {}

    def add(self, part: Part) -> None:
        if self.digest is None:
            self.digest = part.digest
            self.total = part.total
        if (part.digest, part.total) != (self.digest, self.total):
            raise ValueError("Ảnh QR thuộc bộ truyền khác.")
        previous = self.parts.setdefault(part.number, part.data)
        if previous != part.data:
            raise ValueError(f"Ảnh QR số {part.number} có nội dung mâu thuẫn.")

    def assemble(self) -> bytes:
        if self.digest is None:
            raise ValueError("Chưa có ảnh QR nào của Code2Img.")
        if len(self.parts) != self.total:
            missing = [number for number in range(1, self.total + 1) if number not in self.parts]
            numbers = ", ".join(map(str, missing[:12]))
            if len(missing) > 12:
                numbers += ", …"
            raise ValueError(f"Thiếu {len(missing)}/{self.total} ảnh QR. Số còn thiếu: {numbers}.")
        archive = b"".join(self.parts[number] for number in range(1, self.total + 1))
        if hashlib.sha256(archive).digest() != self.digest:
            raise ValueError("SHA-256 không khớp. Hãy chụp lại bộ ảnh QR.")
        return archive
