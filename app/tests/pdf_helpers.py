"""Build small PDFs in memory for extraction tests."""

from __future__ import annotations

import io


def text_pdf(pages: list[str]) -> bytes:
    """Minimal PDF with a real text layer (Helvetica), one line per page."""
    objects: list[bytes] = []
    n = len(pages)
    font_id = 3 + 2 * n
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, line in enumerate(pages):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {4 + 2 * i} 0 R >>".encode()
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def scanned_pdf(lines: list[str]) -> bytes:
    """Image-only PDF page (no text layer), like a scanner produces."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=56)
    for i, line in enumerate(lines):
        draw.text((120, 200 + i * 110), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=200)
    return buf.getvalue()
