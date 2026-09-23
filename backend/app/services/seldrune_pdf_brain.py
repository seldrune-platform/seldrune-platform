from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import random
import re
from typing import Any

import pymupdf

from backend.app.services.pdf_local_ocr import locate_text_with_ocr
from backend.app.services.pdf_editor import (
    PDFEditAssessment,
    PDFEditResult,
    PDFEditorError,
    apply_pdf_edit_plan,
    assess_pdf_edit_candidate,
    inspect_pdf,
    validate_pdf_edit_plan,
)

MODEL_VERSION = "seldrune-pdf-brain-v0.3.1"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_QUOTE = r'(?:"([^"]+)"|\'([^\']+)\'|“([^”]+)”|‘([^’]+)’)'
_PAGE_RE = re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE)
_OCCURRENCE_RE = re.compile(
    r"\b(?:occurrence|instance|match)\s+(\d+)\b", re.IGNORECASE
)

_TRAINING_TEMPLATES: dict[str, tuple[str, ...]] = {
    "replace_text": (
        "replace {a} with {b}",
        "change {a} to {b}",
        "update {a} to {b}",
        "edit {a} and make it {b}",
        "modify {a} into {b}",
        "correct {a} to {b}",
        "swap {a} for {b}",
        "set {a} as {b}",
        "make {a} read {b}",
        "in the pdf replace {a} with {b}",
        "change the value {a} into {b}",
    ),
    "redact_text": (
        "redact {a}",
        "remove {a}",
        "hide {a}",
        "black out {a}",
        "erase {a}",
        "delete the text {a}",
        "mask {a}",
        "cover {a}",
        "remove sensitive text {a}",
    ),
    "fill_form": (
        "fill field {a} with {b}",
        "set field {a} to {b}",
        "enter {b} in {a}",
        "put {b} in the {a} field",
        "complete {a} as {b}",
        "update form field {a} to {b}",
    ),
    "add_text": (
        "add text {b} on page {p}",
        "insert {b} on page {p}",
        "write {b} on page {p}",
        "add a note {b} to page {p}",
        "place {b} on page {p}",
        "append {b} on page {p}",
    ),
    "rotate_page": (
        "rotate page {p} {d} degrees",
        "turn page {p} by {d} degrees",
        "rotate the page {p} {d} degrees",
        "make page {p} rotated {d}",
    ),
}

_TRAINING_A = (
    "OLD",
    "2025-01-01",
    "450000",
    "John Smith",
    "Draft",
    "Acme Corp",
    "Pending",
    "0",
)
_TRAINING_B = (
    "NEW",
    "2026-01-01",
    "500000",
    "Jane Doe",
    "Final",
    "Seldrune Labs",
    "Approved",
    "1",
)
_TRAINING_PAGES = ("1", "2", "3", "5")
_TRAINING_DEGREES = ("90", "180", "270")


@dataclass(frozen=True)
class _NBClass:
    documents: int
    total_tokens: int
    token_counts: Counter[str]


@dataclass(frozen=True)
class PDFBrainModel:
    classes: dict[str, _NBClass]
    vocab: frozenset[str]
    documents: int
    fingerprint: str


@dataclass(frozen=True)
class PDFBrainPrediction:
    model_version: str
    model_fingerprint: str
    intent: str | None
    confidence: float
    plan: dict[str, Any] | None
    fallback_reason: str | None

    @property
    def usable(self) -> bool:
        return self.plan is not None and self.fallback_reason is None


@dataclass(frozen=True)
class LocalPDFEdit:
    prediction: PDFBrainPrediction
    result: PDFEditResult
    assessment: PDFEditAssessment
    ocr_used: bool = False


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.casefold())


def _training_examples() -> list[tuple[str, str]]:
    rng = random.Random(7)
    examples: list[tuple[str, str]] = []
    for label, templates in _TRAINING_TEMPLATES.items():
        for template in templates:
            for _ in range(15):
                examples.append(
                    (
                        template.format(
                            a=rng.choice(_TRAINING_A),
                            b=rng.choice(_TRAINING_B),
                            p=rng.choice(_TRAINING_PAGES),
                            d=rng.choice(_TRAINING_DEGREES),
                        ),
                        label,
                    )
                )
    return examples


def train_pdf_brain() -> PDFBrainModel:
    examples = _training_examples()
    counts: dict[str, Counter[str]] = {}
    class_documents: Counter[str] = Counter()
    class_total_tokens: Counter[str] = Counter()
    vocab: set[str] = set()

    for text, label in examples:
        tokens = _tokens(text)
        class_documents[label] += 1
        class_total_tokens[label] += len(tokens)
        counts.setdefault(label, Counter()).update(tokens)
        vocab.update(tokens)

    classes = {
        label: _NBClass(
            documents=class_documents[label],
            total_tokens=class_total_tokens[label],
            token_counts=counts[label],
        )
        for label in sorted(counts)
    }
    serializable = {
        "version": MODEL_VERSION,
        "documents": len(examples),
        "vocab": sorted(vocab),
        "classes": {
            label: {
                "documents": item.documents,
                "total_tokens": item.total_tokens,
                "token_counts": dict(sorted(item.token_counts.items())),
            }
            for label, item in classes.items()
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(serializable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return PDFBrainModel(
        classes=classes,
        vocab=frozenset(vocab),
        documents=len(examples),
        fingerprint=fingerprint,
    )


MODEL = train_pdf_brain()


def _predict_intent(instruction: str) -> tuple[str, float]:
    tokens = _tokens(instruction)
    vocabulary_size = max(1, len(MODEL.vocab))
    scores: dict[str, float] = {}
    for label, item in MODEL.classes.items():
        score = math.log(item.documents / MODEL.documents)
        denominator = item.total_tokens + vocabulary_size
        for token in tokens:
            score += math.log((item.token_counts.get(token, 0) + 1) / denominator)
        scores[label] = score

    maximum = max(scores.values())
    exponentials = {label: math.exp(value - maximum) for label, value in scores.items()}
    total = sum(exponentials.values())
    probabilities = {label: value / total for label, value in exponentials.items()}
    label = max(probabilities, key=probabilities.get)
    return label, probabilities[label]


_FIELD_VALUE_PREFIX_RE = re.compile(
    r"^(?:the\s+)?(?:"
    r"joining\s+date|last\s+working\s+date|invoice\s+date|offer\s+date|"
    r"effective\s+date|start\s+date|end\s+date|date\s+of\s+birth|dob|date|"
    r"annual\s+salary|monthly\s+salary|gross\s+salary|net\s+salary|"
    r"basic\s+salary|basic\s+pay|fixed\s+pay|variable\s+pay|salary|"
    r"total\s+ctc|ctc|hra|amount|total|"
    r"employee\s+name|candidate\s+name|name|"
    r"employee\s+id|employee\s+number|id|"
    r"designation|department|location|address|phone|email|status|notice\s+period"
    r")\s*(?::|-)?\s+(.+)$",
    re.IGNORECASE,
)

_FIELD_LABEL_ONLY_RE = re.compile(
    r"^(?:the\s+)?(?:"
    r"joining\s+date|last\s+working\s+date|invoice\s+date|offer\s+date|"
    r"effective\s+date|start\s+date|end\s+date|date\s+of\s+birth|dob|date|"
    r"annual\s+salary|monthly\s+salary|gross\s+salary|net\s+salary|"
    r"basic\s+salary|basic\s+pay|fixed\s+pay|variable\s+pay|salary|"
    r"total\s+ctc|ctc|hra|amount|total|"
    r"employee\s+name|candidate\s+name|name|"
    r"employee\s+id|employee\s+number|id|"
    r"designation|department|location|address|phone|email|status|notice\s+period"
    r")\s*:?[\s]*$",
    re.IGNORECASE,
)


def _clean_slot(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"\'“”‘’').strip()
    cleaned = re.sub(
        r"\s+(?:in|on)\s+(?:this|the)\s+(?:pdf|document)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"\s+(?:on|in)\s+page\s+\d+\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"\s+(?:please|thanks?|thank\s+you)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" ,;")
    return cleaned or None


def _strip_field_value_prefix(value: str | None) -> str | None:
    cleaned = _clean_slot(value)
    if not cleaned:
        return None
    match = _FIELD_VALUE_PREFIX_RE.match(cleaned)
    if match:
        candidate = _clean_slot(match.group(1))
        if candidate:
            return candidate
    return cleaned


def _field_label_only(value: str | None) -> str | None:
    cleaned = _clean_slot(value)
    if not cleaned or not _FIELD_LABEL_ONLY_RE.match(cleaned):
        return None
    return re.sub(r"^the\s+", "", cleaned, flags=re.IGNORECASE).rstrip(":").strip()


def _candidate_matches_replacement_shape(candidate: str, replacement: str) -> bool:
    replacement_digits = re.findall(r"\d[\d,./-]*", replacement)
    if not replacement_digits:
        return True
    candidate_digits = re.findall(r"\d[\d,./-]*", candidate)
    return len(candidate_digits) == 1


def _native_value_after_label(
    pdf_bytes: bytes,
    label: str,
    *,
    password: str | None,
    page_number: int | None,
) -> tuple[int, str] | None:
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    if document.needs_pass:
        if not password or not document.authenticate(password):
            document.close()
            return None

    indexes = (
        [page_number - 1]
        if isinstance(page_number, int) and 1 <= page_number <= document.page_count
        else list(range(document.page_count))
    )
    candidates: list[tuple[int, str]] = []
    label_pattern = re.compile(
        rf"^\s*{re.escape(label)}\s*[:\-]?\s+(.+?)\s*$",
        re.IGNORECASE,
    )
    try:
        for page_index in indexes:
            page = document[page_index]
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    spans = [
                        str(span.get("text") or "").strip()
                        for span in line.get("spans", [])
                        if str(span.get("text") or "").strip()
                    ]
                    if not spans:
                        continue
                    line_text = " ".join(spans)
                    match = label_pattern.match(line_text)
                    if not match:
                        continue
                    candidate = _clean_slot(match.group(1))
                    if not candidate or candidate.casefold() == label.casefold():
                        continue
                    candidates.append((page_index + 1, candidate))
    finally:
        document.close()

    unique: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    for candidate in candidates:
        key = (candidate[0], candidate[1].casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique[0] if len(unique) == 1 else None


def _resolve_native_field_targets(
    pdf_bytes: bytes,
    plan: dict[str, Any],
    *,
    password: str | None,
) -> dict[str, Any] | None:
    updated = deepcopy(plan)
    operations = updated.get("operations")
    if not isinstance(operations, list):
        return None

    for operation in operations:
        if not isinstance(operation, dict):
            return None
        if str(operation.get("action") or "") != "replace_text":
            continue
        label = _field_label_only(str(operation.get("target_text") or ""))
        if label is None:
            continue
        replacement = str(operation.get("replacement_text") or "").strip()
        if not replacement:
            return None
        resolved = _native_value_after_label(
            pdf_bytes,
            label,
            password=password,
            page_number=(
                operation.get("page")
                if isinstance(operation.get("page"), int)
                else None
            ),
        )
        if resolved is None:
            return None
        page, old_value = resolved
        if not _candidate_matches_replacement_shape(old_value, replacement):
            return None
        operation["page"] = page
        operation["target_text"] = old_value

    return updated


def _page(instruction: str) -> int | None:
    match = _PAGE_RE.search(instruction)
    return int(match.group(1)) if match else None


def _occurrence(instruction: str) -> int | None:
    match = _OCCURRENCE_RE.search(instruction)
    return int(match.group(1)) if match else None


def _empty_operation(action: str, *, page: int | None) -> dict[str, Any]:
    return {
        "action": action,
        "page": page,
        "target_text": None,
        "replacement_text": None,
        "text": None,
        "bbox": None,
        "occurrence": None,
        "field_name": None,
        "value": None,
        "degrees": None,
        "font_size": None,
        "font_family_hint": None,
        "font_weight": None,
        "font_style": None,
        "alignment": None,
        "text_color": None,
        "background_color": None,
    }


def _quoted_values(text: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(_QUOTE, text):
        for group in match.groups():
            if group is not None:
                values.append(group.strip())
                break
    return values


def _replace_operation(instruction: str) -> dict[str, Any] | None:
    quoted = _quoted_values(instruction)
    target: str | None = None
    replacement: str | None = None
    if len(quoted) >= 2:
        target, replacement = quoted[0], quoted[1]
    else:
        from_match = re.search(
            r"\b(?:replace|change|update|correct|modify|set|edit)\b"
            r".*?\bfrom\s+(.+?)\s+(?:to|with|into|as)\s+(.+?)"
            r"(?=\s+(?:on|in)\s+page\s+\d+\b|$)",
            instruction,
            re.IGNORECASE,
        )
        if from_match:
            target = _clean_slot(from_match.group(1))
            replacement = _clean_slot(from_match.group(2))
        else:
            patterns = (
                r"\b(?:replace|change|update|correct|modify|set)\s+(.+?)\s+(?:with|to|into|as)\s+(.+)$",
                r"\bswap\s+(.+?)\s+for\s+(.+)$",
                r"\bmake\s+(.+?)\s+read\s+(.+)$",
                r"\bedit\s+(.+?)\s+and\s+make\s+it\s+(.+)$",
            )
            for pattern in patterns:
                match = re.search(pattern, instruction, re.IGNORECASE)
                if match:
                    target = _strip_field_value_prefix(match.group(1))
                    replacement = _clean_slot(match.group(2))
                    break
    target, replacement = _clean_slot(target), _clean_slot(replacement)
    if not target or replacement is None:
        return None
    operation = _empty_operation("replace_text", page=_page(instruction))
    operation["target_text"] = target
    operation["replacement_text"] = replacement
    operation["occurrence"] = _occurrence(instruction)
    return operation


def _redact_operation(instruction: str) -> dict[str, Any] | None:
    quoted = _quoted_values(instruction)
    target = quoted[0] if quoted else None
    if target is None:
        match = re.search(
            r"\b(?:redact|remove|hide|erase|mask|cover|delete(?:\s+the\s+text)?|black\s+out)"
            r"\s+(.+)$",
            instruction,
            re.IGNORECASE,
        )
        if match:
            target = _clean_slot(match.group(1))
    target = _clean_slot(target)
    if not target:
        return None
    operation = _empty_operation("redact_text", page=_page(instruction))
    operation["target_text"] = target
    operation["occurrence"] = _occurrence(instruction)
    return operation


def _fill_form_operation(instruction: str) -> dict[str, Any] | None:
    quoted = _quoted_values(instruction)
    field: str | None = None
    value: str | None = None
    if len(quoted) >= 2:
        field, value = quoted[0], quoted[1]
    else:
        patterns = (
            r"\b(?:fill|set|update)\s+(?:form\s+)?field\s+(.+?)\s+(?:with|to|as)\s+(.+)$",
            r"\benter\s+(.+?)\s+in\s+(?:the\s+)?(.+?)\s+field\b",
            r"\bput\s+(.+?)\s+in\s+(?:the\s+)?(.+?)\s+field\b",
        )
        for index, pattern in enumerate(patterns):
            match = re.search(pattern, instruction, re.IGNORECASE)
            if not match:
                continue
            if index == 0:
                field, value = match.group(1), match.group(2)
            else:
                value, field = match.group(1), match.group(2)
            break
    field, value = _clean_slot(field), _clean_slot(value)
    if not field or value is None:
        return None
    operation = _empty_operation("fill_form", page=_page(instruction))
    operation["field_name"] = field
    operation["value"] = value
    return operation


def _add_text_operation(instruction: str) -> dict[str, Any] | None:
    page = _page(instruction)
    if page is None:
        return None
    quoted = _quoted_values(instruction)
    value = quoted[0] if quoted else None
    if value is None:
        match = re.search(
            r"\b(?:add(?:\s+(?:text|a\s+note))?|insert|write|place|append)\s+(.+?)"
            r"\s+(?:on|to)\s+page\s+\d+\b",
            instruction,
            re.IGNORECASE,
        )
        if match:
            value = match.group(1)
    value = _clean_slot(value)
    if not value:
        return None
    operation = _empty_operation("add_text", page=page)
    operation["text"] = value
    return operation


def _rotate_operation(instruction: str) -> dict[str, Any] | None:
    page = _page(instruction)
    if page is None:
        return None
    degree_match = re.search(r"\b(0|90|180|270)\s*(?:degrees?)?\b", instruction)
    if not degree_match:
        return None
    operation = _empty_operation("rotate_page", page=page)
    operation["degrees"] = int(degree_match.group(1))
    return operation


_PARSERS = {
    "replace_text": _replace_operation,
    "redact_text": _redact_operation,
    "fill_form": _fill_form_operation,
    "add_text": _add_text_operation,
    "rotate_page": _rotate_operation,
}

_DETERMINISTIC_HINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rotate_page",
        re.compile(r"\b(?:rotate|turn)\b.*\bpage\s+\d+\b", re.IGNORECASE),
    ),
    (
        "fill_form",
        re.compile(
            r"\b(?:fill|set|update|enter|put)\b.*\bfield\b",
            re.IGNORECASE,
        ),
    ),
    (
        "redact_text",
        re.compile(
            r"\b(?:redact|remove|hide|erase|mask|cover|black\s+out)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "add_text",
        re.compile(
            r"\b(?:add|insert|write|place|append)\b.*\bpage\s+\d+\b",
            re.IGNORECASE,
        ),
    ),
    (
        "replace_text",
        re.compile(
            r"\b(?:replace|change|update|correct|modify|swap|make|edit|set)\b",
            re.IGNORECASE,
        ),
    ),
)


def _batch_replace_operations(
    instruction: str,
) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"\b(?:replace|change|update|correct|modify)\s+(.+?)"
        r"\s+(?:with|to|into)\s+(.+?)"
        r"(?=(?:\s+(?:and|,)\s+"
        r"(?:replace|change|update|correct|modify)\b)|[;\n]|$)",
        re.IGNORECASE,
    )
    operations: list[dict[str, Any]] = []
    for match in pattern.finditer(instruction):
        target = _clean_slot(match.group(1))
        replacement_text = _clean_slot(match.group(2))
        if not target or replacement_text is None:
            continue
        operation = _empty_operation(
            "replace_text",
            page=_page(instruction),
        )
        operation["target_text"] = target
        operation["replacement_text"] = replacement_text
        operation["occurrence"] = _occurrence(instruction)
        operations.append(operation)
    return operations if len(operations) > 1 else []


def _deterministic_operation(
    instruction: str,
) -> tuple[str, dict[str, Any]] | None:
    for intent, pattern in _DETERMINISTIC_HINTS:
        if not pattern.search(instruction):
            continue
        parser = _PARSERS[intent]
        operation = parser(instruction)
        if operation is not None:
            return intent, operation
    return None


def _plan_with_local_ocr(
    pdf_bytes: bytes,
    plan: dict[str, Any],
    *,
    password: str | None,
) -> tuple[dict[str, Any] | None, bool]:
    updated = deepcopy(plan)
    operations = updated.get("operations")
    if not isinstance(operations, list):
        return None, False

    ocr_used = False
    for operation in operations:
        if not isinstance(operation, dict):
            return None, ocr_used
        action = str(operation.get("action") or "")
        if action not in {"replace_text", "redact_text"}:
            continue
        if operation.get("bbox") is not None:
            continue

        target = str(operation.get("target_text") or "").strip()
        if not target:
            return None, ocr_used
        page = operation.get("page")
        page_numbers = [page] if isinstance(page, int) else None
        matches = locate_text_with_ocr(
            pdf_bytes,
            target,
            password=password,
            page_numbers=page_numbers,
        )
        if not matches:
            return None, ocr_used

        occurrence = operation.get("occurrence")
        if isinstance(occurrence, int) and occurrence >= 1:
            if occurrence > len(matches):
                return None, ocr_used
            chosen = matches[occurrence - 1]
        elif len(matches) == 1:
            chosen = matches[0]
        else:
            return None, ocr_used

        operation["page"] = chosen.page
        operation["bbox"] = chosen.bbox
        ocr_used = True

    return updated, ocr_used


def predict_pdf_plan(
    instruction: str,
    *,
    minimum_confidence: float = 0.78,
) -> PDFBrainPrediction:
    batch_replacements = _batch_replace_operations(instruction)
    if batch_replacements:
        return PDFBrainPrediction(
            model_version=MODEL_VERSION,
            model_fingerprint=MODEL.fingerprint,
            intent="replace_text",
            confidence=1.0,
            plan={
                "summary": (
                    f"Local {MODEL_VERSION} deterministic batch replacement plan"
                ),
                "operations": batch_replacements,
            },
            fallback_reason=None,
        )

    deterministic = _deterministic_operation(instruction)
    if deterministic is not None:
        intent, operation = deterministic
        return PDFBrainPrediction(
            model_version=MODEL_VERSION,
            model_fingerprint=MODEL.fingerprint,
            intent=intent,
            confidence=1.0,
            plan={
                "summary": f"Local {MODEL_VERSION} deterministic {intent} plan",
                "operations": [operation],
            },
            fallback_reason=None,
        )

    intent, confidence = _predict_intent(instruction)
    if confidence < minimum_confidence:
        return PDFBrainPrediction(
            model_version=MODEL_VERSION,
            model_fingerprint=MODEL.fingerprint,
            intent=intent,
            confidence=confidence,
            plan=None,
            fallback_reason="local intent confidence below threshold",
        )

    parser = _PARSERS.get(intent)
    operation = parser(instruction) if parser else None
    if operation is None:
        return PDFBrainPrediction(
            model_version=MODEL_VERSION,
            model_fingerprint=MODEL.fingerprint,
            intent=intent,
            confidence=confidence,
            plan=None,
            fallback_reason="local slot parser could not safely resolve the instruction",
        )

    return PDFBrainPrediction(
        model_version=MODEL_VERSION,
        model_fingerprint=MODEL.fingerprint,
        intent=intent,
        confidence=confidence,
        plan={
            "summary": f"Local {MODEL_VERSION} {intent} plan",
            "operations": [operation],
        },
        fallback_reason=None,
    )


def try_local_pdf_edit(
    pdf_bytes: bytes,
    instruction: str,
    *,
    password: str | None = None,
    minimum_confidence: float = 0.78,
    allow_ocr: bool = True,
) -> LocalPDFEdit | None:
    prediction = predict_pdf_plan(
        instruction,
        minimum_confidence=minimum_confidence,
    )
    if not prediction.usable or prediction.plan is None:
        return None

    inspect_pdf(pdf_bytes, password)
    plan = deepcopy(prediction.plan)
    resolved_plan = _resolve_native_field_targets(
        pdf_bytes,
        plan,
        password=password,
    )
    if resolved_plan is None:
        return None
    plan = resolved_plan
    ocr_used = False
    validation = validate_pdf_edit_plan(
        pdf_bytes,
        plan,
        password=password,
    )

    if not validation.valid and allow_ocr:
        ocr_plan, ocr_used = _plan_with_local_ocr(
            pdf_bytes,
            plan,
            password=password,
        )
        if ocr_plan is not None:
            plan = ocr_plan
            validation = validate_pdf_edit_plan(
                pdf_bytes,
                plan,
                password=password,
            )

    if not validation.valid:
        return None

    prediction = PDFBrainPrediction(
        model_version=prediction.model_version,
        model_fingerprint=prediction.model_fingerprint,
        intent=prediction.intent,
        confidence=prediction.confidence,
        plan=plan,
        fallback_reason=None,
    )

    try:
        result = apply_pdf_edit_plan(
            pdf_bytes,
            plan,
            password=password,
        )
    except PDFEditorError:
        return None

    assessment = assess_pdf_edit_candidate(
        pdf_bytes,
        result.data,
        plan,
        password=password,
        visual_fidelity_score=result.visual_fidelity_score,
    )
    if not assessment.safe_to_return or result.verification_score < 100:
        return None
    return LocalPDFEdit(
        prediction=prediction,
        result=result,
        assessment=assessment,
        ocr_used=ocr_used,
    )


def training_summary() -> dict[str, Any]:
    return {
        "model_version": MODEL_VERSION,
        "algorithm": (
            "deterministic parser + multinomial-naive-bayes + local OCR fallback"
        ),
        "trained_examples": MODEL.documents,
        "vocabulary_size": len(MODEL.vocab),
        "intents": sorted(MODEL.classes),
        "fingerprint": MODEL.fingerprint,
    }
