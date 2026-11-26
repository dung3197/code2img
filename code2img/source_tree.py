"""Write a readable index of source paths and their QR part numbers."""

from dataclasses import dataclass, field
from pathlib import Path

from .archive import ArchivedEntry


@dataclass
class Node:
    children: dict[str, "Node"] = field(default_factory=dict)
    parts: range | None = None
    directory: bool = True


def part_label(parts: range) -> str:
    first = f"{parts.start:05d}"
    return first if len(parts) == 1 else f"{first}–{parts.stop - 1:05d}"


def visible_name(name: str) -> str:
    return "".join(char if char.isprintable() else ascii(char)[1:-1] for char in name)


def write_source_tree(output: Path, source: Path, entries: list[ArchivedEntry], sections: list[range]) -> None:
    root = Node()
    number = 1
    for entry, offsets in zip(entries, sections):
        node = root
        for component in entry.name.removesuffix("/").split("/"):
            node = node.children.setdefault(component, Node())
        node.directory = entry.name.endswith("/")
        node.parts = range(number, number + len(offsets))
        number = node.parts.stop

    lines = [visible_name(source.name or source.as_posix()).rstrip("/") + "/"]

    def append_children(parent: Node, prefix: str) -> None:
        children = sorted(parent.children.items(), key=lambda item: (not item[1].directory, item[0]))
        for index, (name, child) in enumerate(children, start=1):
            last = index == len(children)
            branch = "└── " if last else "├── "
            label = visible_name(name) + ("/" if child.directory else "")
            if child.parts is not None:
                label += f" [QR {part_label(child.parts)}]"
            lines.append(prefix + branch + label)
            append_children(child, prefix + ("    " if last else "│   "))

    append_children(root, "")
    index_parts = range(number, number + len(sections[-1]))
    lines.extend(["", f"Chỉ mục ZIP [QR {part_label(index_parts)}]", "Ảnh QR đánh số trong parts/."])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
