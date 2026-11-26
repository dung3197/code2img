"""Lossless ZIP creation and extraction for source directories."""

import os
import shutil
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from fnmatch import fnmatchcase
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


@dataclass(frozen=True)
class ArchivedEntry:
    name: str
    end: int


def _walk_error(error: OSError) -> None:
    raise error


def write_zip(
    source: Path, destination: BinaryIO, excludes: list[str], include_all: bool
) -> list[ArchivedEntry]:
    def is_excluded(path: Path) -> bool:
        relative = path.relative_to(source).as_posix()
        return any(fnmatchcase(relative, pattern) for pattern in excludes)

    entries = []
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=9, strict_timestamps=False) as archive:
        if source.is_file():
            if not any(fnmatchcase(source.name, pattern) for pattern in excludes):
                archive.write(source, source.name)
                entries.append(ArchivedEntry(source.name, destination.tell()))
            return entries
        for root, directory_names, file_names in os.walk(source, onerror=_walk_error):
            directory = Path(root)
            directory_names[:] = sorted(
                name for name in directory_names
                if (include_all or name not in IGNORED_DIRECTORIES)
                and not (directory / name).is_symlink()
                and not is_excluded(directory / name)
            )
            files = [
                directory / name for name in sorted(file_names)
                if not is_excluded(directory / name)
                and stat.S_ISREG((directory / name).lstat().st_mode)
            ]
            for path in files:
                name = path.relative_to(source).as_posix()
                archive.write(path, name)
                entries.append(ArchivedEntry(name, destination.tell()))
            if directory != source and not (directory_names or files):
                name = directory.relative_to(source).as_posix() + "/"
                archive.write(directory, name)
                entries.append(ArchivedEntry(name, destination.tell()))
    return entries


def zip_members(archive: ZipFile) -> list[tuple[ZipInfo, tuple[str, ...]]]:
    members = []
    seen = set()
    files = set()
    directories = set()
    for entry in archive.infolist():
        name = entry.orig_filename
        path = tuple(name.removesuffix("/").split("/"))
        if (
            "\x00" in name or "\\" in name or ":" in name
            or any(piece in {"", ".", ".."} for piece in path)
            or (os.name == "nt" and any(
                Path(piece).is_reserved() or piece.endswith((" ", ".")) for piece in path
            ))
        ):
            raise ValueError(f"Đường dẫn trong ZIP không hợp lệ: {name!r}.")
        mode = stat.S_IFMT(entry.external_attr >> 16)
        expected = stat.S_IFDIR if entry.is_dir() else stat.S_IFREG
        if mode not in (0, expected) or entry.flag_bits & 1:
            raise ValueError(f"Mục trong ZIP không được hỗ trợ: {name!r}.")
        if path in seen:
            raise ValueError(f"Đường dẫn bị trùng trong ZIP: {name!r}.")
        seen.add(path)
        directories.update(path[:index] for index in range(1, len(path)))
        if entry.is_dir():
            directories.add(path)
        else:
            files.add(path)
        members.append((entry, path))
    if files & directories:
        raise ValueError("ZIP chứa tệp và thư mục có cùng đường dẫn.")
    return members


@contextmanager
def new_directory(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()
    try:
        yield path
    except BaseException:
        shutil.rmtree(path)
        raise


def extract_zip(data: bytes, destination: Path) -> int:
    with ZipFile(BytesIO(data)) as archive:
        members = zip_members(archive)
        file_count = 0
        with new_directory(destination):
            for entry, parts in members:
                path = destination.joinpath(*parts)
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, path.open("xb") as output:
                    shutil.copyfileobj(source, output)
                if os.name != "nt" and stat.S_ISREG(entry.external_attr >> 16):
                    path.chmod((entry.external_attr >> 16) & 0o777)
                file_count += 1
    return file_count
