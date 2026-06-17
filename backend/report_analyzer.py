"""
Medical Report Analyzer
========================
Extracts information from medical test reports using OCR and API-based analysis.
Converts report findings into symptoms for the diagnosis system.
"""

import logging
import os
import re
from typing import Any

LOGGER = logging.getLogger("medcore.report_analyzer")

OPEN_API_BASE_URL = os.getenv("OPEN_API_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPEN_API_KEY = os.getenv("OPEN_API_KEY") or os.getenv("OPENAI_API_KEY", "")
OPEN_API_MODEL = os.getenv("OPEN_API_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

REPORT_ANALYSIS_PROMPT = """You are a medical report analysis expert. Extract structured findings from medical reports, including imaging reports, pathology reports, discharge summaries, and lab reports.

Return ONLY valid JSON with this structure:
{
  "extracted_findings": [
    {"finding": "original finding text", "symptom": "standardized medical term", "severity": "normal|abnormal|critical"}
  ],
  "symptoms_list": ["symptom1", "symptom2"],
  "serious_findings": ["important urgent or critical findings"],
  "abnormal_findings": ["non-normal findings that are not critical"],
  "normal_findings": ["normal or stable findings"],
  "summary": "brief clinical summary"
}

Rules:
- Include serious_findings only when the report supports urgent, critical, severe, clinically significant, or potentially dangerous findings.
- Include normal_findings only when the report explicitly states normal, stable, clear, unremarkable, negative, or no acute findings.
- Include abnormal_findings for positive non-normal findings.
- For imaging reports, preserve clinically meaningful phrases such as pneumonia, pleural effusion, normal cardiac silhouette, no pneumothorax, lungs clear, or no acute osseous abnormality.
- If a category is not supported by the report, return an empty list for that category.
- Do not include patient names, dates, or facility details.
"""

SERIOUS_KEYWORDS = (
    "critical",
    "severe",
    "serious",
    "urgent",
    "emergency",
    "life-threatening",
    "clinically significant",
    "significant active",
    "requiring urgent",
    "requires urgent",
    "requires prompt",
    "prompt medical",
    "prompt physician",
    "urgent physician",
    "urgent clinical",
    "pneumothorax",
    "pneumonia",
    "pleural effusion",
    "hemorrhage",
    "respiratory failure",
    "pulmonary edema",
    "sepsis",
    "obstruction",
    "active infection",
    "active chest infection",
)

NORMAL_KEYWORDS = (
    "normal",
    "within normal",
    "stable",
    "unremarkable",
    "clear",
    "normally expanded",
    "negative for",
    "no acute",
    "no pleural effusion",
    "no pneumothorax",
    "no focal consolidation",
    "without focal air-space opacity",
    "within normal size limits",
    "cardiac size remains within normal limits",
    "cardiomediastinal silhouette is stable",
    "cardiomediastinal silhouette is within normal size limits",
)

ABNORMAL_KEYWORDS = (
    "abnormal",
    "opacity",
    "opacities",
    "consolidation",
    "infection",
    "infective",
    "effusion",
    "bronchitic",
    "pneumonia",
    "mass",
    "nodule",
    "elevated",
    "reduced",
    "decreased",
    "increased",
    "high",
    "low",
    "positive",
    "suspicious",
    "suggestive",
)

SHORT_FINDING_PATTERNS = (
    (r"\bactive chest infection\b|\bserious radiographic abnormality\b", "Serious chest infection"),
    (r"\bpneumonia\b", "Pneumonia"),
    (r"\bpleural effusion\b", "Pleural effusion"),
    (r"\bbronchitic\b|\bbronchovascular markings\b", "Bronchitic change"),
    (r"\bclear\b.*\blung\b|\blung\b.*\bclear\b", "Lungs clear"),
    (r"\bcardiomediastinal silhouette\b|\bcardiac size\b", "Cardiac size normal"),
    (r"\bpneumothorax\b", "No pneumothorax"),
    (r"\bunremarkable\b.*\bbony thorax\b|\bno acute osseous abnormality\b|\bunremarkable for acute abnormality\b", "No acute osseous abnormality"),
    (r"\bconsolidation\b", "Lung consolidation"),
    (r"\bopacity\b|\bopacities\b", "Air-space opacity"),
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        cleaned = _clean_text(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _split_report_sentences(report_text: str) -> list[str]:
    cleaned = _clean_text(report_text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.:;])\s+|\s*[•\-\u2022]\s+", cleaned)
    return [part.strip(" -•\t\r\n") for part in parts if part.strip(" -•\t\r\n")]


def _looks_normal(text: str) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in NORMAL_KEYWORDS)


def _looks_serious(text: str) -> bool:
    lowered = text.casefold()
    if "no " in lowered and any(term in lowered for term in ("pneumothorax", "effusion", "acute", "consolidation")):
        return False
    return any(keyword in lowered for keyword in SERIOUS_KEYWORDS)


def _looks_abnormal(text: str) -> bool:
    lowered = text.casefold()
    if _looks_normal(lowered):
        return False
    return any(keyword in lowered for keyword in ABNORMAL_KEYWORDS)


def _normalize_findings_payload(findings: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not isinstance(findings, list):
        return normalized
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        normalized.append(
            {
                "finding": _clean_text(finding.get("finding", "")),
                "symptom": _clean_text(finding.get("symptom", "")),
                "severity": _clean_text(finding.get("severity", "")).casefold(),
            }
        )
    return normalized


def _short_label(text: str) -> str:
    cleaned = _clean_text(text)
    lowered = cleaned.casefold()
    for pattern, label in SHORT_FINDING_PATTERNS:
        if re.search(pattern, lowered):
            return label
    return cleaned


def _enrich_report_categories(result: dict[str, Any], report_text: str) -> dict[str, Any]:
    findings = _normalize_findings_payload(result.get("findings", []))
    serious_findings = [_short_label(item) for item in result.get("serious_findings", [])]
    abnormal_findings = [_short_label(item) for item in result.get("abnormal_findings", [])]
    normal_findings = [_short_label(item) for item in result.get("normal_findings", [])]
    symptoms = [_clean_text(item) for item in result.get("symptoms", [])]
    summary = _clean_text(result.get("summary", ""))

    candidates: list[tuple[str, str]] = []
    for finding in findings:
        finding_text = finding.get("finding", "")
        symptom_text = finding.get("symptom", "")
        severity = finding.get("severity", "")
        if finding_text:
            candidates.append((finding_text, severity))
        if symptom_text and symptom_text.casefold() != finding_text.casefold():
            candidates.append((symptom_text, severity))

    if summary:
        candidates.append((summary, ""))
    candidates.extend((sentence, "") for sentence in _split_report_sentences(report_text))

    for text, severity in candidates:
        if not text:
            continue
        severity = severity.casefold()
        if severity in {"critical", "serious"} or _looks_serious(text):
            serious_findings.append(_short_label(text))
            if _looks_abnormal(text):
                abnormal_findings.append(_short_label(text))
            continue
        if severity == "normal" or _looks_normal(text):
            normal_findings.append(_short_label(text))
            continue
        if severity == "abnormal" or _looks_abnormal(text):
            abnormal_findings.append(_short_label(text))

    result["findings"] = findings
    result["symptoms"] = _dedupe_keep_order(symptoms)[:12]
    result["summary"] = summary
    result["serious_findings"] = _dedupe_keep_order(serious_findings)[:12]
    result["abnormal_findings"] = _dedupe_keep_order(abnormal_findings)[:12]
    result["normal_findings"] = _dedupe_keep_order(normal_findings)[:12]
    return result


def extract_text_from_image(image_base64: str) -> str:
    """
    Extract text from an image using OCR.
    Falls back to API-based vision if pytesseract is not available.
    """
    try:
        import base64
        import io

        import pytesseract
        from PIL import Image

        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip() if text else ""
    except ImportError:
        LOGGER.warning("pytesseract not available, using API-based OCR")
        return ""
    except Exception as exc:
        LOGGER.error("OCR extraction failed: %s", exc)
        return ""


async def analyze_report_with_api(report_text: str) -> dict[str, Any]:
    """
    Use the OpenAI API to analyze a medical report and extract symptoms.
    """
    if not OPEN_API_KEY:
        return {"error": "API key not configured", "symptoms": [], "findings": []}

    if not report_text or len(report_text.strip()) < 10:
        return {"error": "Report text too short", "symptoms": [], "findings": []}

    try:
        import httpx
        import json

        headers = {
            "Authorization": f"Bearer {OPEN_API_KEY}",
            "Content-Type": "application/json",
        }

        if len(report_text) > 4000:
            report_text = report_text[:4000] + "... [truncated]"

        payload = {
            "model": OPEN_API_MODEL,
            "messages": [
                {"role": "system", "content": REPORT_ANALYSIS_PROMPT},
                {"role": "user", "content": f"Analyze this medical report and extract structured findings:\n\n{report_text}"},
            ],
            "max_tokens": 1000,
            "temperature": 0.1,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPEN_API_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            )

        if response.status_code != 200:
            LOGGER.error("API error: %s - %s", response.status_code, response.text)
            return {"error": f"API error: {response.status_code}", "symptoms": [], "findings": []}

        data = response.json()
        if "choices" not in data or not data["choices"]:
            return {"error": "No response from API", "symptoms": [], "findings": []}

        result_text = data["choices"][0]["message"]["content"].strip()

        try:
            json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
            parsed = json.loads(json_match.group() if json_match else result_text)
            return {
                "symptoms": parsed.get("symptoms_list", []),
                "findings": parsed.get("extracted_findings", []),
                "serious_findings": parsed.get("serious_findings", []),
                "abnormal_findings": parsed.get("abnormal_findings", []),
                "normal_findings": parsed.get("normal_findings", []),
                "summary": parsed.get("summary", ""),
                "raw_response": result_text,
            }
        except (json.JSONDecodeError, AttributeError) as exc:
            LOGGER.warning("Failed to parse API response as JSON: %s", exc)
            return {
                "symptoms": [],
                "findings": [],
                "summary": result_text,
                "raw_response": result_text,
                "parse_error": str(exc),
            }
    except Exception as exc:
        LOGGER.error("Report analysis failed: %s", exc)
        return {"error": str(exc), "symptoms": [], "findings": []}


async def process_report(file_content: bytes, filename: str, mime_type: str) -> dict[str, Any]:
    """
    Process a medical report file and extract symptoms.

    Handles:
    - PDF files (text extraction)
    - Text files
    - Image files (OCR)
    """
    report_text = ""
    suffix = os.path.splitext(filename)[1].lower()

    if suffix == ".pdf":
        from report_parser import extract_text_from_pdf

        report_text = extract_text_from_pdf(file_content)
    elif suffix in (".txt", ".text", ".csv"):
        report_text = file_content.decode("utf-8", errors="replace")
    elif suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        import base64

        image_base64 = base64.b64encode(file_content).decode("ascii")
        report_text = extract_text_from_image(image_base64)
    else:
        try:
            report_text = file_content.decode("utf-8", errors="replace")
        except Exception:
            return {"error": f"Unsupported file type: {suffix}", "symptoms": [], "findings": []}

    if not report_text or len(report_text.strip()) < 10:
        return {"error": "Could not extract text from report", "symptoms": [], "findings": []}

    result = await analyze_report_with_api(report_text)
    result = _enrich_report_categories(result, report_text)
    result["extracted_text"] = report_text[:500]
    return result


def format_report_results(analysis_result: dict[str, Any]) -> str:
    """Format report analysis results for display to user."""
    symptoms = analysis_result.get("symptoms", [])
    findings = analysis_result.get("findings", [])
    summary = analysis_result.get("summary", "")

    lines = []
    if summary:
        lines.append(f"**Report Summary:** {summary}")

    if findings:
        lines.append("\n**Key Findings:**")
        for finding in findings[:5]:
            severity = finding.get("severity", "")
            severity_icon = {"normal": "[OK]", "abnormal": "[!]", "critical": "[!!]"}.get(severity, "-")
            lines.append(f"  {severity_icon} {finding.get('symptom', finding.get('finding', ''))}")

    if symptoms:
        lines.append(f"\n**Extracted Symptoms ({len(symptoms)}):**")
        lines.append(f"  {', '.join(symptoms[:10])}")

    return "\n".join(lines)
