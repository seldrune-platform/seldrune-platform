from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass

import pymupdf

MAX_PDF_CONTENT_CHARACTERS = 100_000
MAX_PDF_PAGES = 60
MAX_PDF_BYTES = 20 * 1024 * 1024


class PDFCreationError(ValueError):
    """The requested document could not be rendered as a PDF."""


@dataclass(frozen=True)
class CreatedPDF:
    data: bytes
    page_count: int


def _inline_markdown(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def _markdown_body(content: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_kind = ""
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{'<br/>'.join(_inline_markdown(line) for line in paragraph)}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            rendered_items = "".join(f"<li>{item}</li>" for item in list_items)
            blocks.append(f"<{list_kind}>{rendered_items}</{list_kind}>")
            list_items.clear()
        list_kind = ""

    def flush_code() -> None:
        if code_lines:
            rendered_code = html.escape("\n".join(code_lines), quote=False)
            blocks.append(f"<pre><code>{rendered_code}</code></pre>")
            code_lines.clear()

    for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(raw_line)
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{_inline_markdown(heading.group(2))}</h{level}>")
            continue
        unordered = re.match(r"^[-*+]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        match = unordered or ordered
        if match:
            flush_paragraph()
            next_kind = "ul" if unordered else "ol"
            if list_kind and list_kind != next_kind:
                flush_list()
            list_kind = next_kind
            list_items.append(_inline_markdown(match.group(1)))
            continue
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if list_kind:
            flush_list()
        paragraph.append(raw_line)

    flush_paragraph()
    flush_list()
    if in_code:
        flush_code()
    return "".join(blocks) or "<p></p>"


def create_text_pdf(title: str, content: str) -> CreatedPDF:
    clean_title = " ".join(str(title or "").split())
    clean_content = str(content or "").strip()
    if not clean_title:
        raise PDFCreationError("Enter a document title before creating the PDF.")
    if not clean_content:
        raise PDFCreationError("Add document text before creating the PDF.")
    if len(clean_content) > MAX_PDF_CONTENT_CHARACTERS:
        raise PDFCreationError(
            f"PDF content is limited to {MAX_PDF_CONTENT_CHARACTERS:,} characters."
        )

    document_html = (
        '<html><head><meta charset="utf-8"></head><body>'
        '<p class="brand">SELDRUNE · DOCUMENT STUDIO</p>'
        f"<h1>{_inline_markdown(clean_title)}</h1>"
        f"<main>{_markdown_body(clean_content)}</main>"
        "</body></html>"
    )
    css = """
        body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.38; color: #18283d; }
        .brand { font-size: 8pt; font-weight: bold; letter-spacing: 1.2pt; color: #087e83; }
        h1 { color: #10233d; font-size: 23pt; line-height: 1.14; margin: 0 0 20pt; }
        h2 { color: #123e56; font-size: 16pt; margin: 18pt 0 7pt; }
        h3, h4, h5, h6 { color: #123e56; margin: 14pt 0 6pt; }
        p { margin: 0 0 8pt; }
        ul, ol { margin: 3pt 0 10pt; }
        li { margin: 0 0 4pt; }
        pre { font-family: monospace; white-space: pre-wrap; background: #f0f4f8; padding: 8pt; }
        code { font-family: monospace; background: #eef3f7; }
        strong { color: #10233d; }
    """

    output = io.BytesIO()
    writer = pymupdf.DocumentWriter(output)
    paper = pymupdf.paper_rect("a4")
    content_rect = pymupdf.Rect(48, 48, paper.width - 48, paper.height - 48)
    story = pymupdf.Story(html=document_html, user_css=css)
    page_count = 0
    try:
        while True:
            device = writer.begin_page(paper)
            more, _filled = story.place(content_rect)
            story.draw(device)
            writer.end_page()
            page_count += 1
            if not more:
                break
            if page_count >= MAX_PDF_PAGES:
                raise PDFCreationError(f"PDF creation is limited to {MAX_PDF_PAGES} pages.")
        writer.close()
    except Exception as exc:
        try:
            writer.close()
        except Exception:
            pass
        if isinstance(exc, PDFCreationError):
            raise
        raise PDFCreationError("Seldrune could not render this content as a PDF.") from exc

    data = output.getvalue()
    if not data.startswith(b"%PDF-"):
        raise PDFCreationError("PDF renderer returned an invalid file.")
    if len(data) > MAX_PDF_BYTES:
        raise PDFCreationError("The generated PDF is larger than Seldrune accepts.")
    return CreatedPDF(data=data, page_count=page_count)
