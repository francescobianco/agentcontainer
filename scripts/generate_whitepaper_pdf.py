from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "WHITEPAPER.md"
TARGET = ROOT / "WHITEPAPER.pdf"


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_lines(text: str, width: int = 92) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        raw = raw.rstrip()
        if not raw:
            lines.append("")
            continue
        current = ""
        for word in raw.split():
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def make_pdf(lines: list[str]) -> bytes:
    objects: list[bytes] = []

    page_height = 792
    start_y = 760
    line_height = 14
    lines_per_page = 48

    pages = [lines[index : index + lines_per_page] for index in range(0, len(lines), lines_per_page)]
    if not pages:
        pages = [[]]

    font_object = 1
    page_tree_object = 2
    page_object_ids = []
    content_object_ids = []
    next_object_id = 3

    for _ in pages:
        page_object_ids.append(next_object_id)
        content_object_ids.append(next_object_id + 1)
        next_object_id += 2

    catalog_object = next_object_id

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    kids = " ".join(f"{object_id} 0 R" for object_id in page_object_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("utf-8"))

    for page_object_id, content_object_id, page_lines in zip(page_object_ids, content_object_ids, pages):
        text_lines = ["BT", "/F1 10 Tf"]
        current_y = start_y
        for line in page_lines:
            escaped = escape_pdf_text(line)
            text_lines.append(f"1 0 0 1 72 {current_y} Tm")
            text_lines.append(f"({escaped}) Tj")
            current_y -= line_height
        text_lines.append("ET")
        stream = "\n".join(text_lines).encode("utf-8")
        objects.append(
            f"<< /Type /Page /Parent {page_tree_object} 0 R /MediaBox [0 0 612 {page_height}] /Resources << /Font << /F1 {font_object} 0 R >> >> /Contents {content_object_id} 0 R >>".encode(
                "utf-8"
            )
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
    lines = wrap_lines(SOURCE.read_text(encoding="utf-8"))
    TARGET.write_bytes(make_pdf(lines))
    print(f"generated {TARGET}")


if __name__ == "__main__":
    main()
