from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "WHITEPAPER.md"
TARGET = ROOT / "WHITEPAPER.pdf"

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 54
TOP_MARGIN = 740
BOTTOM_MARGIN = 52


@dataclass(frozen=True)
class StyledLine:
    text: str
    font: str
    size: int
    indent: int = 0
    gap_after: int = 0


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def estimate_width(text: str, size: int) -> float:
    return max(1.0, len(text) * size * 0.52)


def wrap_text(text: str, width: int, size: int, prefix: str = "", continuation: str = "") -> list[str]:
    words = text.split()
    if not words:
        return [prefix.rstrip()]

    lines: list[str] = []
    current = prefix
    current_limit = width
    for word in words:
        candidate = word if not current.strip() else f"{current}{word}" if current.endswith((" ", "-")) else f"{current} {word}"
        if estimate_width(candidate, size) <= current_limit:
            current = candidate
        else:
            if current.strip():
                lines.append(current.rstrip())
            current = f"{continuation}{word}" if continuation else word
    if current.strip():
        lines.append(current.rstrip())
    return lines


def markdown_to_lines(markdown: str) -> list[StyledLine]:
    lines: list[StyledLine] = []
    in_code_block = False

    for raw in markdown.splitlines():
        line = raw.rstrip()

        if line.startswith("```"):
            in_code_block = not in_code_block
            if not in_code_block:
                lines.append(StyledLine("", "Helvetica", 11, gap_after=6))
            continue

        if in_code_block:
            content = line or " "
            lines.append(StyledLine(content, "Courier", 9, indent=18))
            continue

        if not line:
            lines.append(StyledLine("", "Helvetica", 11, gap_after=4))
            continue

        if line.startswith("# "):
            title = line[2:].strip()
            lines.extend(StyledLine(item, "Helvetica-Bold", 22, gap_after=6) for item in wrap_text(title, PAGE_WIDTH - 2 * LEFT_MARGIN, 22))
            lines.append(StyledLine("", "Helvetica", 11, gap_after=8))
            continue

        if line.startswith("## "):
            title = line[3:].strip()
            lines.extend(StyledLine(item, "Helvetica-Bold", 16, gap_after=3) for item in wrap_text(title, PAGE_WIDTH - 2 * LEFT_MARGIN, 16))
            lines.append(StyledLine("", "Helvetica", 11, gap_after=4))
            continue

        if line.startswith("### "):
            title = line[4:].strip()
            lines.extend(StyledLine(item, "Helvetica-Bold", 13, gap_after=2) for item in wrap_text(title, PAGE_WIDTH - 2 * LEFT_MARGIN, 13))
            continue

        bullet = re.match(r"^-\s+(.*)$", line)
        if bullet:
            body = bullet.group(1).strip()
            available = PAGE_WIDTH - 2 * LEFT_MARGIN - 24
            wrapped = wrap_text(body, available, 11, prefix="• ", continuation="  ")
            lines.extend(StyledLine(item, "Helvetica", 11, indent=12) for item in wrapped)
            continue

        numbered = re.match(r"^(\d+)\.\s+(.*)$", line)
        if numbered:
            prefix = f"{numbered.group(1)}. "
            body = numbered.group(2).strip()
            available = PAGE_WIDTH - 2 * LEFT_MARGIN - 24
            wrapped = wrap_text(body, available, 11, prefix=prefix, continuation=" " * len(prefix))
            lines.extend(StyledLine(item, "Helvetica", 11, indent=12) for item in wrapped)
            continue

        paragraph = line.replace("`", "")
        wrapped = wrap_text(paragraph, PAGE_WIDTH - 2 * LEFT_MARGIN, 11)
        lines.extend(StyledLine(item, "Helvetica", 11) for item in wrapped)

    return lines


def paginate(lines: list[StyledLine]) -> list[list[StyledLine]]:
    pages: list[list[StyledLine]] = [[]]
    current_height = TOP_MARGIN

    for line in lines:
        line_height = max(line.size + 4, 12) + line.gap_after
        if current_height - line_height < BOTTOM_MARGIN:
            pages.append([])
            current_height = TOP_MARGIN
        pages[-1].append(line)
        current_height -= line_height

    return pages


def make_pdf(pages: list[list[StyledLine]]) -> bytes:
    objects: list[bytes] = []

    font_map = {
        "Helvetica": 1,
        "Helvetica-Bold": 2,
        "Courier": 3,
    }
    page_tree_object = 4
    page_object_ids = []
    content_object_ids = []
    next_object_id = 5

    for _ in pages:
        page_object_ids.append(next_object_id)
        content_object_ids.append(next_object_id + 1)
        next_object_id += 2

    catalog_object = next_object_id

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    kids = " ".join(f"{object_id} 0 R" for object_id in page_object_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("utf-8"))

    for page_object_id, content_object_id, page_lines in zip(page_object_ids, content_object_ids, pages):
        text_lines = ["BT"]
        current_y = TOP_MARGIN
        for line in page_lines:
            font_id = font_map[line.font]
            text_lines.append(f"/F{font_id} {line.size} Tf")
            text_lines.append(f"1 0 0 1 {LEFT_MARGIN + line.indent} {current_y} Tm")
            text_lines.append(f"({escape_pdf_text(line.text)}) Tj")
            current_y -= max(line.size + 4, 12) + line.gap_after
        text_lines.append("ET")
        stream = "\n".join(text_lines).encode("utf-8")
        objects.append(
            (
                f"<< /Type /Page /Parent {page_tree_object} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 1 0 R /F2 2 0 R /F3 3 0 R >> >> "
                f"/Contents {content_object_id} 0 R >>"
            ).encode("utf-8")
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("utf-8") + stream + b"\nendstream")

    objects.append(f"<< /Type /Catalog /Pages {page_tree_object} 0 R >>".encode("utf-8"))

    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode("utf-8"))
        payload.extend(obj)
        payload.extend(b"\nendobj\n")

    xref_start = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))

    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_object} 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "utf-8"
        )
    )
    return bytes(payload)


def main() -> None:
    styled_lines = markdown_to_lines(SOURCE.read_text(encoding="utf-8"))
    TARGET.write_bytes(make_pdf(paginate(styled_lines)))
    print(f"generated {TARGET}")


if __name__ == "__main__":
    main()
