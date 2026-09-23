from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import math
import re
from statistics import median
from typing import Any

import pymupdf


class PDFEditorError(ValueError):
    pass


@dataclass(frozen=True)
class PDFInspection:
    page_count: int
    native_text_pages: int
    image_only_pages: int
    form_fields: int
    encrypted: bool
    text_characters: int

    @property
    def document_type(self) -> str:
        if self.form_fields:
            return "interactive_form"
        if self.native_text_pages == self.page_count:
            return "native_text"
        if self.native_text_pages == 0:
            return "scanned_or_image"
        return "hybrid"


@dataclass
class PDFEditResult:
    data: bytes
    applied_edits: int
    warnings: list[str]
    inspection: PDFInspection
    verified_operations: int
    verification_notes: list[str]

    @property
    def verification_score(self) -> int:
        if self.applied_edits <= 0:
            return 0
        return round((self.verified_operations / self.applied_edits) * 100)


def _open_document(pdf_bytes: bytes, password: str | None = None) -> pymupdf.Document:
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFEditorError("Invalid or unreadable PDF") from exc

    if document.needs_pass:
        if not password or not document.authenticate(password):
            document.close()
            raise PDFEditorError(
                "This PDF is password-protected. Enter the document password and retry."
            )
    return document


def prepare_pdf_for_model(
    pdf_bytes: bytes,
    password: str | None = None,
) -> bytes:
    document = _open_document(pdf_bytes, password)
    try:
        return document.tobytes(
            garbage=2,
            deflate=True,
            encryption=pymupdf.PDF_ENCRYPT_NONE,
        )
    finally:
        document.close()


def inspect_pdf(pdf_bytes: bytes, password: str | None = None) -> PDFInspection:
    document = _open_document(pdf_bytes, password)
    native_text_pages = 0
    text_characters = 0
    form_fields = 0
    for page in document:
        text = page.get_text("text").strip()
        text_characters += len(text)
        if len(text) >= 8:
            native_text_pages += 1
        widgets = list(page.widgets() or [])
        form_fields += len(widgets)
    inspection = PDFInspection(
        page_count=document.page_count,
        native_text_pages=native_text_pages,
        image_only_pages=document.page_count - native_text_pages,
        form_fields=form_fields,
        encrypted=bool(document.is_encrypted),
        text_characters=text_characters,
    )
    document.close()
    return inspection


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _union_rect(rectangles: list[pymupdf.Rect]) -> pymupdf.Rect:
    result = pymupdf.Rect(rectangles[0])
    for rectangle in rectangles[1:]:
        result.include_rect(rectangle)
    return result


def _fuzzy_word_rectangles(
    page: pymupdf.Page,
    target_text: str,
    *,
    threshold: float = 0.84,
) -> list[pymupdf.Rect]:
    words = page.get_text("words")
    if not words:
        return []
    target_words = _normalize_text(target_text).split()
    if not target_words:
        return []

    page_words = [str(item[4]) for item in words]
    target_norm = _normalize_text(target_text)
    target_len = len(target_words)
    best: tuple[float, int, int] | None = None

    min_window = max(1, target_len - 2)
    max_window = min(len(page_words), target_len + 3)
    for start in range(len(page_words)):
        for size in range(min_window, max_window + 1):
            end = start + size
            if end > len(page_words):
                break
            candidate = _normalize_text(" ".join(page_words[start:end]))
            ratio = SequenceMatcher(None, target_norm, candidate).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, start, end)

    if best is None or best[0] < threshold:
        return []

    _, start, end = best
    rectangles = [
        pymupdf.Rect(words[index][0], words[index][1], words[index][2], words[index][3])
        for index in range(start, end)
    ]
    return [_union_rect(rectangles)] if rectangles else []


def _locate_text(page: pymupdf.Page, target_text: str) -> tuple[list[pymupdf.Rect], str]:
    exact = list(page.search_for(target_text))
    if exact:
        return exact, "exact"
    fuzzy = _fuzzy_word_rectangles(page, target_text)
    if fuzzy:
        return fuzzy, "fuzzy"
    return [], "missing"


def _rect_intersection_area(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    intersection = pymupdf.Rect(a)
    intersection.intersect(b)
    if intersection.is_empty:
        return 0.0
    return max(0.0, intersection.width) * max(0.0, intersection.height)


@dataclass(frozen=True)
class PDFTextStyle:
    font_name: str
    font_size: float
    color: tuple[float, float, float]
    origin: tuple[float, float]
    line_rect: pymupdf.Rect
    target_rect: pymupdf.Rect
    alignment: int
    rotation: int
    font_alias: str
    font_buffer: bytes | None
    exact_font_reusable: bool


def _font_key(value: str) -> str:
    cleaned = re.sub(r"^[A-Z]{6}\+", "", value or "")
    return re.sub(r"[^a-z0-9]+", "", cleaned.casefold())


def _builtin_font_name(font_name: str) -> str:
    key = _font_key(font_name)
    bold = "bold" in key or key.endswith("bd")
    italic = "italic" in key or "oblique" in key or key.endswith("it")
    if "courier" in key or "mono" in key:
        if bold and italic:
            return "cobi"
        if bold:
            return "cobo"
        if italic:
            return "coit"
        return "cour"
    if "times" in key or "serif" in key:
        if bold and italic:
            return "tibi"
        if bold:
            return "tibo"
        if italic:
            return "tiit"
        return "tiro"
    if bold and italic:
        return "hebi"
    if bold:
        return "hebo"
    if italic:
        return "heit"
    return "helv"


def _rotation_from_direction(direction: Any) -> int:
    if not isinstance(direction, (list, tuple)) or len(direction) != 2:
        return 0
    try:
        x, y = float(direction[0]), float(direction[1])
    except (TypeError, ValueError):
        return 0
    angle = (math.degrees(math.atan2(-y, x)) + 360.0) % 360.0
    return int(round(angle / 90.0) * 90) % 360


def _infer_alignment(
    page: pymupdf.Page,
    line_rect: pymupdf.Rect,
    target_rect: pymupdf.Rect,
) -> int:
    tolerance = max(2.0, target_rect.height * 0.2)
    at_line_start = abs(target_rect.x0 - line_rect.x0) <= tolerance
    at_line_end = abs(target_rect.x1 - line_rect.x1) <= tolerance

    if at_line_start and at_line_end:
        left_margin = max(0.0, line_rect.x0 - page.rect.x0)
        right_margin = max(0.0, page.rect.x1 - line_rect.x1)
        if abs(left_margin - right_margin) <= max(8.0, page.rect.width * 0.025):
            return pymupdf.TEXT_ALIGN_CENTER
        if right_margin + tolerance < left_margin * 0.35:
            return pymupdf.TEXT_ALIGN_RIGHT
        return pymupdf.TEXT_ALIGN_LEFT

    if at_line_end and not at_line_start:
        return pymupdf.TEXT_ALIGN_RIGHT
    return pymupdf.TEXT_ALIGN_LEFT


def _font_resource_for_span(
    document: pymupdf.Document,
    page_index: int,
    span_font: str,
    replacement_text: str,
) -> tuple[str, bytes | None, bool]:
    target = _font_key(span_font)
    candidates: list[tuple[int, tuple[Any, ...]]] = []
    for item in document.get_page_fonts(page_index, full=True):
        xref, _ext, _kind, basefont, resource_name, _encoding, _referencer = item
        base_key = _font_key(str(basefont))
        score = 0
        if base_key == target:
            score = 100
        elif target and (target in base_key or base_key in target):
            score = 80
        elif target and any(token in base_key for token in ("bold", "italic", "oblique")):
            score = 10
        if score:
            candidates.append((score, item))

    candidates.sort(key=lambda entry: entry[0], reverse=True)
    for _score, item in candidates:
        xref = int(item[0] or 0)
        if xref <= 0:
            continue
        try:
            _name, ext, _kind, content = document.extract_font(xref)
        except Exception:
            continue
        if not content or ext == "n/a":
            continue
        try:
            font = pymupdf.Font(fontbuffer=content)
            if all(char.isspace() or font.has_glyph(ord(char)) for char in replacement_text):
                alias = f"SELD{xref}"
                return alias, content, True
        except Exception:
            continue

    return _builtin_font_name(span_font), None, False


def _capture_text_style(
    document: pymupdf.Document,
    page_index: int,
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    replacement_text: str,
) -> PDFTextStyle:
    best_span: dict[str, Any] | None = None
    best_line: dict[str, Any] | None = None
    best_area = 0.0

    raw = page.get_text("rawdict")
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                area = _rect_intersection_area(span_rect, rect)
                if area > best_area:
                    best_area = area
                    best_span = span
                    best_line = line

    if best_span is None or best_line is None:
        size, color = _style_near_rect(page, rect)
        return PDFTextStyle(
            font_name="Helvetica",
            font_size=size,
            color=color,
            origin=(rect.x0, rect.y1 - max(1.0, rect.height * 0.18)),
            line_rect=pymupdf.Rect(rect),
            target_rect=pymupdf.Rect(rect),
            alignment=pymupdf.TEXT_ALIGN_LEFT,
            rotation=0,
            font_alias="helv",
            font_buffer=None,
            exact_font_reusable=False,
        )

    line_rect = pymupdf.Rect(best_line.get("bbox", rect))
    origin_value = best_span.get("origin", (rect.x0, rect.y1))
    origin = (float(origin_value[0]), float(origin_value[1]))

    for char in best_span.get("chars", []):
        char_rect = pymupdf.Rect(char.get("bbox", (0, 0, 0, 0)))
        if _rect_intersection_area(char_rect, rect) > 0:
            char_origin = char.get("origin")
            if isinstance(char_origin, (list, tuple)) and len(char_origin) == 2:
                origin = (float(char_origin[0]), float(char_origin[1]))
                break

    font_name = str(best_span.get("font") or "Helvetica")
    font_size = float(best_span.get("size") or max(6.0, rect.height * 0.72))
    color_value = best_span.get("color")
    color = _color_tuple(color_value if isinstance(color_value, int) else None)
    alias, font_buffer, exact = _font_resource_for_span(
        document,
        page_index,
        font_name,
        replacement_text,
    )

    return PDFTextStyle(
        font_name=font_name,
        font_size=max(4.0, min(144.0, font_size)),
        color=color,
        origin=origin,
        line_rect=line_rect,
        target_rect=pymupdf.Rect(rect),
        alignment=_infer_alignment(page, line_rect, rect),
        rotation=_rotation_from_direction(best_line.get("dir")),
        font_alias=alias,
        font_buffer=font_buffer,
        exact_font_reusable=exact,
    )


def _font_text_length(
    style: PDFTextStyle,
    text: str,
) -> float:
    try:
        if style.font_buffer:
            font = pymupdf.Font(fontbuffer=style.font_buffer)
        else:
            font = pymupdf.Font(style.font_alias)
        return float(font.text_length(text, fontsize=style.font_size))
    except Exception:
        return max(1.0, len(text) * style.font_size * 0.55)


def _install_style_font(page: pymupdf.Page, style: PDFTextStyle) -> str:
    if style.font_buffer:
        try:
            page.insert_font(fontname=style.font_alias, fontbuffer=style.font_buffer)
            return style.font_alias
        except Exception:
            pass
    return _builtin_font_name(style.font_name)


def _style_preserving_origin(
    style: PDFTextStyle,
    replacement_width: float,
) -> pymupdf.Point:
    x = style.origin[0]
    if style.alignment == pymupdf.TEXT_ALIGN_RIGHT:
        x = style.target_rect.x1 - replacement_width
    elif style.alignment == pymupdf.TEXT_ALIGN_CENTER:
        x = style.target_rect.x0 + (style.target_rect.width - replacement_width) / 2.0
    return pymupdf.Point(x, style.origin[1])


def _write_like_original(
    page: pymupdf.Page,
    style: PDFTextStyle,
    text: str,
) -> tuple[bool, str]:
    if not text:
        return True, "no replacement text required"

    fontname = _install_style_font(page, style)
    width = _font_text_length(style, text)
    point = _style_preserving_origin(style, width)

    # Preserve the original point size and baseline first. This is the highest
    # fidelity path and avoids textbox vertical recentering.
    try:
        page.insert_text(
            point,
            text,
            fontname=fontname,
            fontsize=style.font_size,
            color=style.color,
            rotate=style.rotation,
            overlay=True,
        )
        font_note = (
            f"reused embedded {style.font_name}"
            if style.exact_font_reusable
            else f"matched {style.font_name} with {fontname}"
        )
        return True, (
            f"original-look reconstruction: {font_note}, "
            f"{style.font_size:.2f}pt, baseline/alignment preserved"
        )
    except Exception:
        pass

    # Last resort: keep the captured style and geometry but permit a tiny fit
    # adjustment. This is intentionally much stricter than the old generic box.
    trial_size = style.font_size
    for _ in range(5):
        box = pymupdf.Rect(style.target_rect)
        if style.alignment == pymupdf.TEXT_ALIGN_LEFT:
            box.x1 = min(page.rect.x1, max(box.x1, box.x0 + width + 3))
        elif style.alignment == pymupdf.TEXT_ALIGN_RIGHT:
            box.x0 = max(page.rect.x0, min(box.x0, box.x1 - width - 3))
        result = page.insert_textbox(
            box,
            text,
            fontname=fontname,
            fontsize=trial_size,
            color=style.color,
            align=style.alignment,
            rotate=style.rotation,
            overlay=True,
        )
        if result >= 0:
            return True, (
                "original-look reconstruction used constrained fit at "
                f"{trial_size:.2f}pt"
            )
        trial_size *= 0.98

    return False, "original-look reconstruction could not fit replacement"


def _color_tuple(value: int | None) -> tuple[float, float, float]:
    if value is None:
        return (0.0, 0.0, 0.0)
    return (
        ((value >> 16) & 255) / 255.0,
        ((value >> 8) & 255) / 255.0,
        (value & 255) / 255.0,
    )


def _style_near_rect(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
) -> tuple[float, tuple[float, float, float]]:
    sizes: list[float] = []
    colors: list[int] = []
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                if _rect_intersection_area(span_rect, rect) <= 0:
                    continue
                size = span.get("size")
                if isinstance(size, (int, float)) and size > 0:
                    sizes.append(float(size))
                color = span.get("color")
                if isinstance(color, int):
                    colors.append(color)

    font_size = median(sizes) if sizes else max(6.0, min(14.0, rect.height * 0.72))
    color = _color_tuple(colors[0] if colors else None)
    return max(4.0, min(72.0, font_size)), color


def _estimate_background(page: pymupdf.Page, rect: pymupdf.Rect) -> tuple[float, float, float]:
    expanded = pymupdf.Rect(
        max(page.rect.x0, rect.x0 - 4),
        max(page.rect.y0, rect.y0 - 4),
        min(page.rect.x1, rect.x1 + 4),
        min(page.rect.y1, rect.y1 + 4),
    )
    if expanded.is_empty:
        return (1.0, 1.0, 1.0)

    try:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0), clip=expanded, alpha=False)
    except Exception:
        return (1.0, 1.0, 1.0)
    if pix.width <= 0 or pix.height <= 0 or pix.n < 3:
        return (1.0, 1.0, 1.0)

    samples = pix.samples
    rgb: list[tuple[int, int, int]] = []
    step = max(1, min(pix.width, pix.height) // 18)
    for y in range(0, pix.height, step):
        for x in range(0, pix.width, step):
            if 2 < x < pix.width - 3 and 2 < y < pix.height - 3:
                continue
            offset = y * pix.stride + x * pix.n
            rgb.append((samples[offset], samples[offset + 1], samples[offset + 2]))
    if not rgb:
        return (1.0, 1.0, 1.0)

    return (
        median([item[0] for item in rgb]) / 255.0,
        median([item[1] for item in rgb]) / 255.0,
        median([item[2] for item in rgb]) / 255.0,
    )


def _normalized_bbox(page: pymupdf.Page, bbox: Any) -> pymupdf.Rect | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None
    if not all(isinstance(value, (int, float)) for value in bbox):
        return None
    x0, y0, x1, y1 = [max(0.0, min(1000.0, float(value))) for value in bbox]
    if x1 <= x0 or y1 <= y0:
        return None
    return pymupdf.Rect(
        page.rect.x0 + page.rect.width * (x0 / 1000.0),
        page.rect.y0 + page.rect.height * (y0 / 1000.0),
        page.rect.x0 + page.rect.width * (x1 / 1000.0),
        page.rect.y0 + page.rect.height * (y1 / 1000.0),
    )


def _fit_textbox(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    text: str,
    *,
    font_size: float,
    color: tuple[float, float, float],
) -> bool:
    if not text:
        return True

    trial_size = min(font_size, max(4.0, rect.height * 0.9))
    expanded = pymupdf.Rect(rect)
    for _ in range(14):
        result = page.insert_textbox(
            expanded,
            text,
            fontsize=trial_size,
            color=color,
            align=pymupdf.TEXT_ALIGN_LEFT,
            overlay=True,
        )
        if result >= 0:
            return True
        trial_size *= 0.90
        if trial_size < 4.0:
            if expanded.y1 < page.rect.y1:
                expanded.y1 = min(page.rect.y1, expanded.y1 + max(4.0, rect.height * 0.28))
                trial_size = max(4.0, font_size * 0.72)
                continue
            break
    return False


def _matching_widgets(
    page: pymupdf.Page,
    field_name: str,
) -> list[Any]:
    widgets = list(page.widgets() or [])
    exact = [
        widget
        for widget in widgets
        if _normalize_text(str(widget.field_name or "")) == _normalize_text(field_name)
    ]
    if exact:
        return exact

    scored: list[tuple[float, Any]] = []
    target = _normalize_text(field_name)
    for widget in widgets:
        name = _normalize_text(str(widget.field_name or ""))
        if not name:
            continue
        scored.append((SequenceMatcher(None, target, name).ratio(), widget))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    return [scored[0][1]] if scored[0][0] >= 0.80 else []


def _page_indexes(document: pymupdf.Document, page_number: Any) -> list[int]:
    if page_number is None:
        return list(range(document.page_count))
    if isinstance(page_number, int) and 1 <= page_number <= document.page_count:
        return [page_number - 1]
    return []


def _verify_text_change(
    page: pymupdf.Page,
    *,
    target_text: str,
    replacement_text: str,
    action: str,
) -> tuple[bool, str]:
    text = _normalize_text(page.get_text("text"))
    target_present = _normalize_text(target_text) in text if target_text else False
    replacement_present = (
        _normalize_text(replacement_text) in text if replacement_text else True
    )
    if action == "redact_text":
        ok = not target_present
        return ok, "redacted source text is absent" if ok else "source text still detected"
    ok = not target_present and replacement_present
    if ok:
        return True, "replacement text verified in extracted page text"
    if replacement_present:
        return True, "replacement text verified; original may remain elsewhere on page"
    return False, "replacement could not be verified from extracted page text"


def apply_pdf_edit_plan(
    pdf_bytes: bytes,
    plan: dict[str, Any],
    *,
    password: str | None = None,
) -> PDFEditResult:
    document = _open_document(pdf_bytes, password)
    inspection = inspect_pdf(pdf_bytes, password)
    applied = 0
    verified = 0
    warnings: list[str] = []
    verification_notes: list[str] = []

    operations = plan.get("operations")
    if not isinstance(operations, list):
        document.close()
        raise PDFEditorError("Invalid PDF edit plan")

    for op_index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            warnings.append(f"Operation {op_index} was ignored because it was malformed.")
            continue

        action = str(operation.get("action") or "")
        page_number = operation.get("page")
        indexes = _page_indexes(document, page_number)

        if action == "set_metadata":
            metadata = operation.get("metadata")
            if not isinstance(metadata, dict):
                warnings.append(f"Operation {op_index}: metadata must be an object.")
                continue
            current = dict(document.metadata or {})
            for key in ("title", "author", "subject", "keywords", "creator", "producer"):
                value = metadata.get(key)
                if isinstance(value, str):
                    current[key] = value
            document.set_metadata(current)
            applied += 1
            verified += 1
            verification_notes.append(f"Operation {op_index}: metadata updated.")
            continue

        if action == "rotate_page":
            if len(indexes) != 1:
                warnings.append(f"Operation {op_index}: rotate_page requires one valid page.")
                continue
            degrees = operation.get("degrees")
            if degrees not in {0, 90, 180, 270}:
                warnings.append(f"Operation {op_index}: rotation must be 0/90/180/270.")
                continue
            page = document[indexes[0]]
            page.set_rotation(int(degrees))
            applied += 1
            verified += 1
            verification_notes.append(
                f"Operation {op_index}: page {indexes[0] + 1} rotation updated."
            )
            continue

        if not indexes:
            warnings.append(f"Operation {op_index}: invalid page {page_number}.")
            continue

        if action == "fill_form":
            field_name = str(operation.get("field_name") or "").strip()
            value = operation.get("value")
            if not field_name:
                warnings.append(f"Operation {op_index}: form field name is missing.")
                continue
            matched = False
            for page_index in indexes:
                page = document[page_index]
                for widget in _matching_widgets(page, field_name):
                    matched = True
                    if isinstance(value, bool):
                        widget.field_value = "Yes" if value else "Off"
                    else:
                        widget.field_value = "" if value is None else str(value)
                    widget.update()
                    applied += 1
                    verified += 1
                    verification_notes.append(
                        f"Operation {op_index}: form field '{field_name}' updated."
                    )
            if not matched:
                warnings.append(
                    f"Operation {op_index}: form field '{field_name}' was not found."
                )
            continue

        if action in {"replace_text", "redact_text"}:
            target_text = str(operation.get("target_text") or "").strip()
            replacement_text = (
                str(operation.get("replacement_text") or "")
                if action == "replace_text"
                else ""
            )
            bbox = operation.get("bbox")
            occurrence = operation.get("occurrence")
            operation_applied = False

            for page_index in indexes:
                page = document[page_index]
                rectangles: list[pymupdf.Rect] = []
                match_mode = "visual_bbox"
                if target_text:
                    rectangles, match_mode = _locate_text(page, target_text)
                if not rectangles:
                    visual_rect = _normalized_bbox(page, bbox)
                    if visual_rect is not None:
                        rectangles = [visual_rect]
                        match_mode = "visual_bbox"

                if not rectangles:
                    continue

                if isinstance(occurrence, int) and occurrence >= 1:
                    rectangles = rectangles[occurrence - 1 : occurrence]

                prepared: list[
                    tuple[pymupdf.Rect, PDFTextStyle | None, tuple[float, float, float]]
                ] = []
                for rectangle in rectangles:
                    if match_mode == "visual_bbox":
                        background = _estimate_background(page, rectangle)
                        prepared.append((rectangle, None, background))
                        page.add_redact_annot(rectangle, fill=background)
                    else:
                        style = _capture_text_style(
                            document,
                            page_index,
                            page,
                            rectangle,
                            replacement_text,
                        )
                        prepared.append((rectangle, style, (1.0, 1.0, 1.0)))
                        # Native text is removed without repainting the background,
                        # so vector lines, fills, logos and design elements survive.
                        page.add_redact_annot(rectangle, fill=False)

                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_NONE,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                )

                for rectangle, style, _background in prepared:
                    if action == "replace_text":
                        if style is not None:
                            inserted, style_note = _write_like_original(
                                page,
                                style,
                                replacement_text,
                            )
                            verification_notes.append(
                                f"Operation {op_index}, page {page_index + 1}: {style_note}."
                            )
                        else:
                            font_size, color = _style_near_rect(page, rectangle)
                            inserted = _fit_textbox(
                                page,
                                rectangle,
                                replacement_text,
                                font_size=font_size,
                                color=color,
                            )
                        if not inserted:
                            warnings.append(
                                f"Operation {op_index}: replacement text did not fit cleanly "
                                f"on page {page_index + 1}."
                            )
                    applied += 1
                    operation_applied = True

                if target_text and match_mode != "visual_bbox":
                    ok, note = _verify_text_change(
                        page,
                        target_text=target_text,
                        replacement_text=replacement_text,
                        action=action,
                    )
                    if ok:
                        verified += len(prepared)
                    verification_notes.append(
                        f"Operation {op_index}, page {page_index + 1}: {note} "
                        f"({match_mode} match)."
                    )
                else:
                    verification_notes.append(
                        f"Operation {op_index}, page {page_index + 1}: visual-region edit "
                        "applied; text-level verification is unavailable for image-only content."
                    )

            if not operation_applied:
                warnings.append(
                    f"Operation {op_index}: target was not found. For scanned/image PDFs, "
                    "the edit plan must include a normalized visual bbox."
                )
            continue

        if action in {"add_text", "add_note"}:
            text = str(operation.get("text") or "").strip()
            if not text:
                warnings.append(f"Operation {op_index}: text is missing.")
                continue
            page_index = indexes[0]
            page = document[page_index]
            rect = _normalized_bbox(page, operation.get("bbox"))
            if rect is None:
                rect = pymupdf.Rect(
                    36,
                    max(36, page.rect.height - 112),
                    max(72, page.rect.width - 36),
                    max(72, page.rect.height - 36),
                )
            font_size = float(operation.get("font_size") or 10.0)
            color = (0.0, 0.0, 0.0)
            if _fit_textbox(page, rect, text, font_size=font_size, color=color):
                applied += 1
                if _normalize_text(text) in _normalize_text(page.get_text("text")):
                    verified += 1
                verification_notes.append(
                    f"Operation {op_index}: inserted text on page {page_index + 1}."
                )
            else:
                warnings.append(
                    f"Operation {op_index}: inserted text could not fit in the requested region."
                )
            continue

        warnings.append(f"Operation {op_index}: unsupported action '{action}'.")

    if applied == 0:
        document.close()
        raise PDFEditorError(
            "No PDF edits could be applied. The document may require a visual-region "
            "edit plan, a password, or a more specific instruction."
        )

    output = document.tobytes(
        garbage=4,
        deflate=True,
        clean=True,
    )
    original_pages = inspection.page_count
    document.close()

    try:
        verification_doc = pymupdf.open(stream=output, filetype="pdf")
        if verification_doc.page_count != original_pages:
            verification_doc.close()
            raise PDFEditorError("Edited PDF failed page-count integrity validation.")
        verification_doc.close()
    except PDFEditorError:
        raise
    except Exception as exc:
        raise PDFEditorError("Edited PDF failed integrity validation.") from exc

    return PDFEditResult(
        data=output,
        applied_edits=applied,
        warnings=warnings,
        inspection=inspection,
        verified_operations=verified,
        verification_notes=verification_notes,
    )
