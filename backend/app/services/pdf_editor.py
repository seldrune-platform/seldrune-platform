from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import pymupdf
from fastapi import HTTPException

from backend.app.core.modeling import ModelImageInput


@dataclass(frozen=True)
class PDFVisualContext:
    images: tuple[ModelImageInput, ...]
    profile_text: str
    scanned_pages: tuple[int, ...]
    rendered_pages: tuple[int, ...]


def _open_document(pdf_bytes: bytes) -> pymupdf.Document:
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid or unreadable PDF") from exc
    if document.needs_pass:
        document.close()
        raise HTTPException(
            status_code=422,
            detail="Password-protected PDFs must be unlocked before editing",
        )
    return document


def _page_text_and_style_summary(page: pymupdf.Page) -> tuple[str, list[str]]:
    text = page.get_text("text").strip()
    style_lines: list[str] = []
    try:
        data = page.get_text("dict")
    except Exception:
        return text, style_lines
    seen: set[tuple[str, int, int]] = set()
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                font = str(span.get("font") or "unknown")[:40]
                size = int(round(float(span.get("size") or 0)))
                color = int(span.get("color") or 0)
                key = (font, size, color)
                if key in seen:
                    continue
                seen.add(key)
                style_lines.append(f"{font}/{size}pt/#{color:06x}")
                if len(style_lines) >= 8:
                    return text, style_lines
    return text, style_lines


def build_pdf_visual_context(
    pdf_bytes: bytes,
    *,
    max_rendered_pages: int = 24,
) -> PDFVisualContext:
    document = _open_document(pdf_bytes)
    page_profiles: list[str] = []
    scanned_pages: list[int] = []
    candidates: list[tuple[int, int]] = []

    for index, page in enumerate(document):
        page_number = index + 1
        text, styles = _page_text_and_style_summary(page)
        text_chars = len(text)
        image_count = len(page.get_images(full=True))
        if text_chars < 24:
            scanned_pages.append(page_number)
        candidates.append((page_number, text_chars))
        excerpt = " ".join(text.split())[:900]
        page_profiles.append(
            " | ".join(
                [
                    f"page={page_number}",
                    f"size={page.rect.width:.1f}x{page.rect.height:.1f}pt",
                    f"text_chars={text_chars}",
                    f"images={image_count}",
                    f"styles={','.join(styles) if styles else 'unknown'}",
                    f"excerpt={excerpt!r}",
                ]
            )
        )

    # Visual fallback is most valuable for scanned / image-heavy pages. If room
    # remains, include the lowest-text pages so difficult layouts are also visible.
    render_order: list[int] = []
    for page_number in scanned_pages:
        if page_number not in render_order:
            render_order.append(page_number)
    for page_number, _text_chars in sorted(candidates, key=lambda item: item[1]):
        if page_number not in render_order:
            render_order.append(page_number)
        if len(render_order) >= max_rendered_pages:
            break
    render_order = render_order[:max_rendered_pages]

    images: list[ModelImageInput] = []
    for page_number in render_order:
        page = document[page_number - 1]
        scale = min(2.0, max(1.0, 1400.0 / max(page.rect.width, page.rect.height)))
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image_bytes = pixmap.tobytes("jpeg", jpg_quality=68)
        images.append(
            ModelImageInput(
                media_type="image/jpeg",
                data_base64=base64.b64encode(image_bytes).decode("ascii"),
                name=f"pdf-page-{page_number}.jpg",
            )
        )

    document.close()
    profile_text = "\n".join(page_profiles)
    return PDFVisualContext(
        images=tuple(images),
        profile_text=profile_text,
        scanned_pages=tuple(scanned_pages),
        rendered_pages=tuple(render_order),
    )


def _rgb_int_to_tuple(value: int | None) -> tuple[float, float, float]:
    raw = int(value or 0)
    return (
        ((raw >> 16) & 0xFF) / 255.0,
        ((raw >> 8) & 0xFF) / 255.0,
        (raw & 0xFF) / 255.0,
    )


def _normalize_rgb(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        return default
    try:
        values = tuple(max(0.0, min(1.0, float(item))) for item in value)
    except (TypeError, ValueError):
        return default
    return values  # type: ignore[return-value]


def _rect_from_normalized(page: pymupdf.Page, value: Any) -> pymupdf.Rect | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    if not all(0.0 <= item <= 1.0 for item in (x0, y0, x1, y1)):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return pymupdf.Rect(
        page.rect.x0 + page.rect.width * x0,
        page.rect.y0 + page.rect.height * y0,
        page.rect.x0 + page.rect.width * x1,
        page.rect.y0 + page.rect.height * y1,
    )


def _best_span_style(page: pymupdf.Page, target: pymupdf.Rect) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_overlap = 0.0
    try:
        data = page.get_text("dict")
    except Exception:
        return best
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox")
                if not bbox:
                    continue
                span_rect = pymupdf.Rect(bbox)
                overlap = (span_rect & target).get_area()
                if overlap > best_overlap:
                    best_overlap = overlap
                    best = span
    return best


def _fit_textbox(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    text: str,
    *,
    initial_font_size: float,
    color: tuple[float, float, float],
    align: int,
) -> bool:
    size = max(4.5, min(72.0, initial_font_size))
    expanded = pymupdf.Rect(
        rect.x0,
        rect.y0 - min(2.0, rect.height * 0.08),
        min(page.rect.x1, rect.x1 + max(4.0, rect.width * 0.35)),
        min(page.rect.y1, rect.y1 + max(3.0, rect.height * 0.12)),
    )
    while size >= 4.5:
        result = page.insert_textbox(
            expanded,
            text,
            fontname="helv",
            fontsize=size,
            color=color,
            align=align,
            overlay=True,
        )
        if result >= 0:
            return True
        size -= 0.5
    return False


def _sample_background(page: pymupdf.Page, rect: pymupdf.Rect) -> tuple[float, float, float]:
    expanded = pymupdf.Rect(
        max(page.rect.x0, rect.x0 - 3),
        max(page.rect.y0, rect.y0 - 3),
        min(page.rect.x1, rect.x1 + 3),
        min(page.rect.y1, rect.y1 + 3),
    )
    try:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(0.35, 0.35), clip=expanded, alpha=False)
        samples = pix.samples
        if not samples:
            return (1.0, 1.0, 1.0)
        channels = pix.n
        pixels = len(samples) // channels
        if pixels <= 0:
            return (1.0, 1.0, 1.0)
        step = max(1, pixels // 64)
        rs: list[int] = []
        gs: list[int] = []
        bs: list[int] = []
        for pixel_index in range(0, pixels, step):
            base = pixel_index * channels
            rs.append(samples[base])
            gs.append(samples[base + 1])
            bs.append(samples[base + 2])
            if len(rs) >= 64:
                break
        rs.sort()
        gs.sort()
        bs.sort()
        mid = len(rs) // 2
        return (rs[mid] / 255.0, gs[mid] / 255.0, bs[mid] / 255.0)
    except Exception:
        return (1.0, 1.0, 1.0)


def _page_indexes(document: pymupdf.Document, page_number: Any) -> list[int]:
    if page_number is None:
        return list(range(document.page_count))
    if isinstance(page_number, int) and 1 <= page_number <= document.page_count:
        return [page_number - 1]
    return []


def apply_advanced_pdf_edit_plan(
    pdf_bytes: bytes,
    plan: dict[str, Any],
) -> tuple[bytes, int, int, list[str], list[dict[str, Any]]]:
    document = _open_document(pdf_bytes)
    warnings: list[str] = []
    verification: list[dict[str, Any]] = []
    applied = 0

    operations = plan.get("operations")
    if not isinstance(operations, list):
        document.close()
        raise HTTPException(status_code=502, detail="Invalid PDF edit plan")

    for operation_index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            continue
        action = str(operation.get("action") or "")
        indexes = _page_indexes(document, operation.get("page"))
        if not indexes:
            warnings.append(
                f"Operation {operation_index} skipped because its page is invalid."
            )
            continue

        operation_applied = 0
        target_text = str(operation.get("target_text") or "").strip()
        replacement = str(operation.get("replacement_text") or "")
        note_text = str(operation.get("text") or "")
        alignment = str(operation.get("alignment") or "left")
        align = {"left": 0, "center": 1, "right": 2}.get(alignment, 0)

        if action in {"replace_text", "redact_text"}:
            if not target_text:
                warnings.append(f"Operation {operation_index} has no target text.")
                continue
            for page_index in indexes:
                page = document[page_index]
                matches = page.search_for(target_text)
                for rect in matches:
                    style = _best_span_style(page, rect)
                    font_size = float(
                        operation.get("font_size")
                        or style.get("size")
                        or max(6.0, rect.height * 0.72)
                    )
                    color = _normalize_rgb(
                        operation.get("text_color"),
                        _rgb_int_to_tuple(style.get("color")),
                    )
                    page.add_redact_annot(rect, fill=None)
                    page.apply_redactions()
                    if action == "replace_text" and replacement:
                        if not _fit_textbox(
                            page,
                            rect,
                            replacement,
                            initial_font_size=font_size,
                            color=color,
                            align=align,
                        ):
                            warnings.append(
                                f"Replacement text did not fit cleanly on page {page_index + 1}."
                            )
                            continue
                    operation_applied += 1

        elif action in {"visual_replace", "place_text"}:
            for page_index in indexes:
                page = document[page_index]
                rect = _rect_from_normalized(page, operation.get("rect_norm"))
                if rect is None:
                    warnings.append(
                        f"Operation {operation_index} needs a valid normalized rectangle."
                    )
                    continue
                text = replacement or note_text
                if not text:
                    warnings.append(f"Operation {operation_index} has no replacement text.")
                    continue
                if action == "visual_replace":
                    background = _normalize_rgb(
                        operation.get("background_color"),
                        _sample_background(page, rect),
                    )
                    page.draw_rect(rect, color=None, fill=background, overlay=True)
                font_size = float(
                    operation.get("font_size")
                    or max(6.0, min(18.0, rect.height * 0.6))
                )
                color = _normalize_rgb(
                    operation.get("text_color"),
                    (0.0, 0.0, 0.0),
                )
                if _fit_textbox(
                    page,
                    rect,
                    text,
                    initial_font_size=font_size,
                    color=color,
                    align=align,
                ):
                    operation_applied += 1
                else:
                    warnings.append(
                        f"Text did not fit the requested region on page {page_index + 1}."
                    )

        elif action == "set_form_field":
            field_name = str(operation.get("field_name") or "").strip()
            field_value = str(operation.get("field_value") or "")
            if not field_name:
                warnings.append(f"Operation {operation_index} has no form field name.")
                continue
            for page_index in indexes:
                page = document[page_index]
                widget = page.first_widget
                while widget:
                    if (widget.field_name or "").strip().casefold() == field_name.casefold():
                        widget.field_value = field_value
                        widget.update()
                        operation_applied += 1
                    widget = widget.next

        elif action == "rotate_page":
            rotation = int(operation.get("rotation") or 0)
            if rotation not in {0, 90, 180, 270}:
                warnings.append(f"Operation {operation_index} has an invalid rotation.")
                continue
            for page_index in indexes:
                document[page_index].set_rotation(rotation)
                operation_applied += 1

        else:
            warnings.append(f"Unsupported PDF edit action: {action}")
            continue

        applied += operation_applied
        verification.append(
            {
                "operation": operation_index,
                "action": action,
                "page": operation.get("page"),
                "applied": operation_applied,
                "verified": operation_applied > 0,
            }
        )

    if applied == 0:
        document.close()
        raise HTTPException(
            status_code=422,
            detail=(
                "No requested PDF edits could be applied. The document was left unchanged."
            ),
        )

    output = document.tobytes(garbage=4, deflate=True, clean=True)
    document.close()

    # Re-open the produced file and verify the operations against the actual output.
    verified = 0
    output_document = _open_document(output)
    for item, operation in zip(verification, operations, strict=False):
        if not isinstance(operation, dict) or not item.get("verified"):
            continue
        action = item["action"]
        indexes = _page_indexes(output_document, operation.get("page"))
        target = str(operation.get("target_text") or "").strip()
        replacement = str(operation.get("replacement_text") or "")
        field_name = str(operation.get("field_name") or "").strip()
        field_value = str(operation.get("field_value") or "")

        valid = True
        if action == "replace_text" and replacement:
            valid = any(
                replacement in output_document[index].get_text("text")
                for index in indexes
            )
        elif action == "redact_text" and target:
            valid = all(
                target not in output_document[index].get_text("text")
                for index in indexes
            )
        elif action in {"visual_replace", "place_text"}:
            expected = replacement or str(operation.get("text") or "")
            valid = bool(expected) and any(
                expected in output_document[index].get_text("text")
                for index in indexes
            )
        elif action == "set_form_field":
            valid = False
            for index in indexes:
                widget = output_document[index].first_widget
                while widget:
                    if (
                        (widget.field_name or "").strip().casefold()
                        == field_name.casefold()
                        and str(widget.field_value or "") == field_value
                    ):
                        valid = True
                        break
                    widget = widget.next
                if valid:
                    break

        item["verified"] = bool(valid)
        if valid:
            verified += int(item.get("applied") or 0)
        else:
            warnings.append(
                f"Verification failed for operation {item['operation']} ({action})."
            )

    output_document.close()
    return output, applied, verified, warnings, verification
