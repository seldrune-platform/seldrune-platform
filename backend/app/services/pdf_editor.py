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
    visual_fidelity_scores: list[int]

    @property
    def verification_score(self) -> int:
        if self.applied_edits <= 0:
            return 0
        return round((self.verified_operations / self.applied_edits) * 100)

    @property
    def visual_fidelity_score(self) -> int | None:
        if not self.visual_fidelity_scores:
            return None
        return round(sum(self.visual_fidelity_scores) / len(self.visual_fidelity_scores))


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


def _fuzzy_target_is_safe(target_text: str) -> bool:
    normalized = _normalize_text(target_text)
    compact = re.sub(r"\s+", "", normalized)
    if len(compact) < 4:
        return False
    meaningful = [char for char in compact if char.isalnum()]
    if not meaningful:
        return False
    digit_ratio = sum(char.isdigit() for char in meaningful) / len(meaningful)
    # Amounts, IDs, dates, percentages and short numeric cells must match exactly.
    # Fuzzy matching on values such as 0 / 450000 / 2150000 can select the wrong
    # salary row and is unsafe for structured documents.
    return digit_ratio < 0.55


def _locate_text(page: pymupdf.Page, target_text: str) -> tuple[list[pymupdf.Rect], str]:
    exact = list(page.search_for(target_text))
    if exact:
        return exact, "exact"
    if not _fuzzy_target_is_safe(target_text):
        return [], "missing"
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


def _operation_rgb(
    value: Any,
    fallback: tuple[float, float, float],
) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        return fallback
    try:
        channels = tuple(max(0.0, min(1.0, float(item))) for item in value)
    except (TypeError, ValueError):
        return fallback
    return channels  # type: ignore[return-value]


def _visual_font_name(operation: dict[str, Any]) -> str:
    family = str(operation.get("font_family_hint") or "Helvetica")
    weight = str(operation.get("font_weight") or "regular").casefold()
    style = str(operation.get("font_style") or "regular").casefold()
    family_key = _font_key(family)
    bold = weight == "bold" or "bold" in family_key
    italic = style == "italic" or "italic" in family_key or "oblique" in family_key

    if "times" in family_key or "serif" in family_key:
        if bold and italic:
            return "tibi"
        if bold:
            return "tibo"
        if italic:
            return "tiit"
        return "tiro"
    if "courier" in family_key or "mono" in family_key:
        if bold and italic:
            return "cobi"
        if bold:
            return "cobo"
        if italic:
            return "coit"
        return "cour"
    if bold and italic:
        return "hebi"
    if bold:
        return "hebo"
    if italic:
        return "heit"
    return "helv"


def _operation_alignment(operation: dict[str, Any]) -> int:
    value = str(operation.get("alignment") or "left").casefold()
    return {
        "left": pymupdf.TEXT_ALIGN_LEFT,
        "center": pymupdf.TEXT_ALIGN_CENTER,
        "right": pymupdf.TEXT_ALIGN_RIGHT,
    }.get(value, pymupdf.TEXT_ALIGN_LEFT)


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
    fontname: str = "helv",
    align: int = pymupdf.TEXT_ALIGN_LEFT,
    rotate: int = 0,
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
            fontname=fontname,
            color=color,
            align=align,
            rotate=rotate,
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


def _expected_rendered_text_width(
    style: PDFTextStyle,
    text: str,
) -> float:
    document = pymupdf.open()
    page = document.new_page(width=600, height=220)
    fontname = _builtin_font_name(style.font_name)
    if style.font_buffer:
        try:
            page.insert_font(fontname="SELDTEST", fontbuffer=style.font_buffer)
            fontname = "SELDTEST"
        except Exception:
            fontname = _builtin_font_name(style.font_name)
    try:
        page.insert_text(
            pymupdf.Point(100, 120),
            text,
            fontname=fontname,
            fontsize=style.font_size,
            color=style.color,
            rotate=style.rotation,
            overlay=True,
        )
        matches = list(page.search_for(text))
        if matches:
            width = float(matches[0].width)
            document.close()
            return width
    except Exception:
        pass
    document.close()
    return _font_text_length(style, text)


def _font_family_tokens(value: str) -> set[str]:
    key = _font_key(value)
    tokens: set[str] = set()
    for token in (
        "times",
        "helvetica",
        "arial",
        "courier",
        "calibri",
        "cambria",
        "georgia",
        "verdana",
        "serif",
        "sans",
        "mono",
        "bold",
        "italic",
        "oblique",
    ):
        if token in key:
            tokens.add(token)
    return tokens


def _rgb_channels(value: int | None) -> tuple[int, int, int] | None:
    if not isinstance(value, int):
        return None
    return (
        (value >> 16) & 255,
        (value >> 8) & 255,
        value & 255,
    )


def _replacement_visual_fidelity(
    page: pymupdf.Page,
    replacement_text: str,
    style: PDFTextStyle,
) -> tuple[int, str]:
    matches = list(page.search_for(replacement_text))
    if not matches:
        return 0, "replacement style could not be visually inspected"

    target = min(
        matches,
        key=lambda item: abs(item.y0 - style.target_rect.y0)
        + abs(item.x0 - style.target_rect.x0),
    )
    best_span: dict[str, Any] | None = None
    best_area = 0.0
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                area = _rect_intersection_area(span_rect, target)
                if area > best_area:
                    best_area = area
                    best_span = span

    if best_span is None:
        return 0, "replacement span could not be inspected"

    expected_advance = _font_text_length(style, replacement_text)
    expected_visual_width = _expected_rendered_text_width(
        style,
        replacement_text,
    )
    width_tolerance = max(
        1.25,
        style.font_size * 0.08,
        expected_visual_width * 0.035,
    )
    width_match = (
        abs(target.width - expected_visual_width)
        <= width_tolerance
    )

    output_font = str(best_span.get("font") or "")
    source_key = _font_key(style.font_name)
    output_key = _font_key(output_font)
    source_tokens = _font_family_tokens(style.font_name)
    output_tokens = _font_family_tokens(output_font)
    family_tokens = source_tokens & {
        "times",
        "helvetica",
        "arial",
        "courier",
        "calibri",
        "cambria",
        "georgia",
        "verdana",
        "serif",
        "sans",
        "mono",
    }
    style_tokens = source_tokens & {"bold", "italic", "oblique"}

    name_match = (
        source_key == output_key
        or source_key in output_key
        or output_key in source_key
    )
    semantic_font_match = (
        bool(family_tokens)
        and bool(family_tokens & output_tokens)
        and all(
            token in output_tokens
            or (token == "italic" and "oblique" in output_tokens)
            or (token == "oblique" and "italic" in output_tokens)
            for token in style_tokens
        )
    )
    embedded_metric_match = style.exact_font_reusable and width_match
    font_match = name_match or semantic_font_match or embedded_metric_match

    output_size = float(best_span.get("size") or 0.0)
    size_match = abs(output_size - style.font_size) <= max(
        0.25,
        style.font_size * 0.015,
    )

    output_rgb = _rgb_channels(best_span.get("color"))
    expected_rgb = tuple(round(channel * 255) for channel in style.color)
    color_match = bool(
        output_rgb
        and all(
            abs(output_rgb[index] - expected_rgb[index]) <= 2
            for index in range(3)
        )
    )

    output_origin = best_span.get("origin")
    # PyMuPDF can merge newly inserted text into the surrounding line span.
    # In that case span.origin is the beginning of the whole line, not the
    # replacement. Resolve the first character that actually intersects the
    # replacement search rectangle and use its origin for geometry checks.
    try:
        raw = page.get_text("rawdict")
    except Exception:
        raw = {}
    replacement_char_origin: tuple[float, float] | None = None
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    char_rect = pymupdf.Rect(char.get("bbox", (0, 0, 0, 0)))
                    intersection = _rect_intersection_area(char_rect, target)
                    char_area = max(1.0, char_rect.width * char_rect.height)
                    if (
                        intersection < 0.5
                        or intersection / char_area < 0.10
                    ):
                        continue
                    char_origin = char.get("origin")
                    if (
                        isinstance(char_origin, (list, tuple))
                        and len(char_origin) == 2
                    ):
                        replacement_char_origin = (
                            float(char_origin[0]),
                            float(char_origin[1]),
                        )
                        break
                if replacement_char_origin is not None:
                    break
            if replacement_char_origin is not None:
                break
        if replacement_char_origin is not None:
            break

    if replacement_char_origin is not None:
        output_origin = replacement_char_origin

    baseline_match = False
    anchor_match = False
    if isinstance(output_origin, (list, tuple)) and len(output_origin) == 2:
        output_x = float(output_origin[0])
        output_y = float(output_origin[1])
        baseline_match = abs(output_y - style.origin[1]) <= max(
            1.0,
            style.font_size * 0.06,
        )
        expected_origin = _style_preserving_origin(style, expected_advance)
        anchor_match = abs(output_x - expected_origin.x) <= max(
            1.2,
            style.font_size * 0.07,
        )

    # Internal PDF font names are not a visual property. A subset font can be
    # exposed as ABCDEF+FontName or a generated resource alias even when the
    # exact same font bytes are reused. Fidelity therefore requires matching
    # glyph metrics plus size/color/baseline/anchor; the name is only supporting
    # evidence unless it directly matches.
    checks = {
        "font": font_match,
        "width": width_match,
        "size": size_match,
        "color": color_match,
        "baseline": baseline_match,
        "anchor": anchor_match,
    }
    score = round(
        (sum(1 for item in checks.values() if item) / len(checks)) * 100
    )
    return score, (
        f"visual fidelity {score}% "
        f"(font={'yes' if checks['font'] else 'no'}, "
        f"width={'yes' if checks['width'] else 'no'}, "
        f"size={'yes' if checks['size'] else 'no'}, "
        f"color={'yes' if checks['color'] else 'no'}, "
        f"baseline={'yes' if checks['baseline'] else 'no'}, "
        f"anchor={'yes' if checks['anchor'] else 'no'})"
    )


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


@dataclass(frozen=True)
class PDFPlanValidation:
    valid: bool
    issues: tuple[str, ...]


def _rect_overlap_ratio(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    intersection = _rect_intersection_area(a, b)
    if intersection <= 0:
        return 0.0
    smaller = max(1.0, min(a.width * a.height, b.width * b.height))
    return intersection / smaller


def _nearby_text_context(page: pymupdf.Page, rect: pymupdf.Rect) -> str:
    region = _expanded_rect(
        page,
        rect,
        x_pad=max(30.0, rect.width * 2.0),
        y_pad=max(10.0, rect.height * 1.4),
    )
    return " ".join(page.get_textbox(region).split())[:220]


def validate_pdf_edit_plan(
    pdf_bytes: bytes,
    plan: dict[str, Any],
    *,
    password: str | None = None,
) -> PDFPlanValidation:
    document = _open_document(pdf_bytes, password)
    operations = plan.get("operations")
    if not isinstance(operations, list):
        document.close()
        return PDFPlanValidation(False, ("edit plan operations are invalid",))

    issues: list[str] = []
    resolved: list[tuple[int, int, pymupdf.Rect, str]] = []

    for op_index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            issues.append(f"operation {op_index}: malformed operation")
            continue
        action = str(operation.get("action") or "")
        if action not in {"replace_text", "redact_text"}:
            continue

        indexes = _page_indexes(document, operation.get("page"))
        if not indexes:
            issues.append(f"operation {op_index}: invalid page")
            continue

        target_text = str(operation.get("target_text") or "").strip()
        occurrence = operation.get("occurrence")
        bbox = operation.get("bbox")

        for page_index in indexes:
            page = document[page_index]
            rectangles: list[pymupdf.Rect] = []
            mode = "visual_bbox"
            if target_text:
                rectangles, mode = _locate_text(page, target_text)
            if not rectangles:
                visual_rect = _normalized_bbox(page, bbox)
                if visual_rect is not None:
                    rectangles = [visual_rect]
                    mode = "visual_bbox"

            if not rectangles:
                issues.append(
                    f"operation {op_index}: target {target_text!r} was not found "
                    f"on original page {page_index + 1}; use the exact source value "
                    "or a precise bbox"
                )
                continue

            if isinstance(occurrence, int) and occurrence >= 1:
                if occurrence > len(rectangles):
                    issues.append(
                        f"operation {op_index}: occurrence {occurrence} exceeds "
                        f"{len(rectangles)} match(es) on page {page_index + 1}"
                    )
                    continue
                rectangles = rectangles[occurrence - 1 : occurrence]
            elif len(rectangles) > 1 and mode != "visual_bbox":
                contexts = [
                    _nearby_text_context(page, rectangle)
                    for rectangle in rectangles[:4]
                ]
                issues.append(
                    f"operation {op_index}: target {target_text!r} is ambiguous with "
                    f"{len(rectangles)} matches on page {page_index + 1}; choose an "
                    f"occurrence or bbox. Nearby contexts: {' || '.join(contexts)}"
                )
                continue

            for rectangle in rectangles:
                resolved.append(
                    (
                        op_index,
                        page_index,
                        pymupdf.Rect(rectangle),
                        target_text or mode,
                    )
                )

    for left_index in range(len(resolved)):
        op_a, page_a, rect_a, label_a = resolved[left_index]
        for right_index in range(left_index + 1, len(resolved)):
            op_b, page_b, rect_b, label_b = resolved[right_index]
            if page_a != page_b or op_a == op_b:
                continue
            ratio = _rect_overlap_ratio(rect_a, rect_b)
            if ratio >= 0.20:
                issues.append(
                    f"operations {op_a} and {op_b} overlap on page {page_a + 1} "
                    f"({label_a!r} vs {label_b!r}); combine or target them separately"
                )

    document.close()
    unique = tuple(dict.fromkeys(issues))
    return PDFPlanValidation(valid=not unique, issues=unique)


@dataclass(frozen=True)
class PDFEditAssessment:
    safe_to_return: bool
    layout_integrity_score: int
    issues: tuple[str, ...]


def _expanded_rect(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    *,
    x_pad: float,
    y_pad: float,
) -> pymupdf.Rect:
    return pymupdf.Rect(
        max(page.rect.x0, rect.x0 - x_pad),
        max(page.rect.y0, rect.y0 - y_pad),
        min(page.rect.x1, rect.x1 + x_pad),
        min(page.rect.y1, rect.y1 + y_pad),
    )


def _nearest_rect(
    rectangles: list[pymupdf.Rect],
    target: pymupdf.Rect,
) -> pymupdf.Rect | None:
    if not rectangles:
        return None
    return min(
        rectangles,
        key=lambda item: abs((item.x0 + item.x1) / 2 - (target.x0 + target.x1) / 2)
        + abs((item.y0 + item.y1) / 2 - (target.y0 + target.y1) / 2),
    )


def _local_replacement_rect(
    page: pymupdf.Page,
    rectangles: list[pymupdf.Rect],
    target: pymupdf.Rect,
) -> pymupdf.Rect | None:
    if not rectangles:
        return None
    local_region = _expanded_rect(
        page,
        target,
        x_pad=max(20.0, target.width * 1.5),
        y_pad=max(8.0, target.height * 1.2),
    )
    local = [
        rectangle
        for rectangle in rectangles
        if _rect_intersection_area(rectangle, local_region) > 0
    ]
    return _nearest_rect(local, target)


def _protected_word_rectangles(
    page: pymupdf.Page,
    target: pymupdf.Rect,
) -> list[pymupdf.Rect]:
    protected: list[pymupdf.Rect] = []
    target_pad = _expanded_rect(
        page,
        target,
        x_pad=max(1.0, target.height * 0.08),
        y_pad=max(1.0, target.height * 0.08),
    )
    for word in page.get_text("words"):
        rect = pymupdf.Rect(word[0], word[1], word[2], word[3])
        if _rect_intersection_area(rect, target_pad) > 0:
            continue
        protected.append(rect)
    return protected


def assess_pdf_edit_candidate(
    original_pdf: bytes,
    edited_pdf: bytes,
    plan: dict[str, Any],
    *,
    password: str | None = None,
    visual_fidelity_score: int | None = None,
) -> PDFEditAssessment:
    original = _open_document(original_pdf, password)
    edited = _open_document(edited_pdf)
    issues: list[str] = []

    if original.page_count != edited.page_count:
        original.close()
        edited.close()
        return PDFEditAssessment(
            safe_to_return=False,
            layout_integrity_score=0,
            issues=("page count changed unexpectedly",),
        )

    operations = plan.get("operations")
    if not isinstance(operations, list):
        original.close()
        edited.close()
        return PDFEditAssessment(
            safe_to_return=False,
            layout_integrity_score=0,
            issues=("invalid edit plan",),
        )

    edited_pages: set[int] = set()
    for op_index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            continue
        action = str(operation.get("action") or "")
        if action not in {"replace_text", "redact_text"}:
            continue

        indexes = _page_indexes(original, operation.get("page"))
        target_text = str(operation.get("target_text") or "").strip()
        replacement_text = str(operation.get("replacement_text") or "")
        occurrence = operation.get("occurrence")

        for page_index in indexes:
            edited_pages.add(page_index)
            source_page = original[page_index]
            output_page = edited[page_index]
            target_rectangles: list[pymupdf.Rect] = []
            if target_text:
                target_rectangles, _mode = _locate_text(source_page, target_text)
            if not target_rectangles:
                visual_rect = _normalized_bbox(source_page, operation.get("bbox"))
                if visual_rect is not None:
                    target_rectangles = [visual_rect]

            if isinstance(occurrence, int) and occurrence >= 1:
                target_rectangles = target_rectangles[occurrence - 1 : occurrence]

            if not target_rectangles:
                issues.append(
                    f"operation {op_index}: original target region could not be located"
                )
                continue

            for target_rect in target_rectangles:
                check_region = _expanded_rect(
                    output_page,
                    target_rect,
                    x_pad=max(2.0, target_rect.height * 0.18),
                    y_pad=max(2.0, target_rect.height * 0.18),
                )
                region_text = _normalize_text(output_page.get_textbox(check_region))
                if target_text and _normalize_text(target_text) in region_text:
                    issues.append(
                        f"operation {op_index}: old text remains in its original region"
                    )

                if action == "redact_text":
                    continue

                replacement_matches = list(output_page.search_for(replacement_text))
                replacement_rect = _local_replacement_rect(
                    output_page,
                    replacement_matches,
                    target_rect,
                )
                if replacement_rect is None:
                    issues.append(
                        f"operation {op_index}: replacement text is not detectable "
                        "near the original target region"
                    )
                    continue

                vertical_drift = abs(
                    (replacement_rect.y0 + replacement_rect.y1) / 2
                    - (target_rect.y0 + target_rect.y1) / 2
                )
                max_vertical_drift = max(2.5, target_rect.height * 0.35)
                if vertical_drift > max_vertical_drift:
                    issues.append(
                        f"operation {op_index}: replacement drifted vertically "
                        f"{vertical_drift:.1f}pt"
                    )

                for protected in _protected_word_rectangles(source_page, target_rect):
                    intersection = _rect_intersection_area(replacement_rect, protected)
                    if intersection <= 0:
                        continue
                    protected_area = max(1.0, protected.width * protected.height)
                    replacement_area = max(
                        1.0,
                        replacement_rect.width * replacement_rect.height,
                    )
                    if (
                        intersection / protected_area >= 0.08
                        or intersection / replacement_area >= 0.05
                    ):
                        issues.append(
                            f"operation {op_index}: replacement overlaps unrelated text"
                        )
                        break

    for page_index in edited_pages:
        source_drawings = len(original[page_index].get_drawings())
        output_drawings = len(edited[page_index].get_drawings())
        if output_drawings < source_drawings:
            issues.append(
                f"page {page_index + 1}: vector lines or shapes were removed"
            )

    original.close()
    edited.close()

    if visual_fidelity_score is not None and visual_fidelity_score < 95:
        issues.append(
            f"native typography fidelity is only {visual_fidelity_score}%"
        )

    unique_issues = tuple(dict.fromkeys(issues))
    penalty = min(100, len(unique_issues) * 25)
    score = max(0, 100 - penalty)
    return PDFEditAssessment(
        safe_to_return=not unique_issues,
        layout_integrity_score=score,
        issues=unique_issues,
    )


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
    visual_fidelity_scores: list[int] = []

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
                        background = _operation_rgb(
                            operation.get("background_color"),
                            _estimate_background(page, rectangle),
                        )
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
                            if inserted:
                                fidelity, fidelity_note = _replacement_visual_fidelity(
                                    page,
                                    replacement_text,
                                    style,
                                )
                                visual_fidelity_scores.append(fidelity)
                                verification_notes.append(
                                    f"Operation {op_index}, page {page_index + 1}: "
                                    f"{fidelity_note}."
                                )
                                if fidelity < 95:
                                    warnings.append(
                                        f"Operation {op_index}: original-look visual fidelity "
                                        f"is {fidelity}% on page {page_index + 1}."
                                    )
                        else:
                            inferred_size, inferred_color = _style_near_rect(page, rectangle)
                            font_size = float(
                                operation.get("font_size") or inferred_size
                            )
                            color = _operation_rgb(
                                operation.get("text_color"),
                                inferred_color,
                            )
                            inserted = _fit_textbox(
                                page,
                                rectangle,
                                replacement_text,
                                font_size=font_size,
                                color=color,
                                fontname=_visual_font_name(operation),
                                align=_operation_alignment(operation),
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
        visual_fidelity_scores=visual_fidelity_scores,
    )
