import json
import os
import re
import zipfile
from datetime import datetime
from xml.etree import ElementTree

from flask import current_app

from app.services.ai_interview_service import call_ai


def _resume_file_path(resume_path):
    if not resume_path:
        return None
    if resume_path.startswith("candidate_cvs/"):
        from app.services.candidate_resume_service import cv_directory
        filename = resume_path.split("/", 1)[1]
        if os.path.basename(filename) != filename:
            return None
        return str(cv_directory() / filename)
    return os.path.join(current_app.root_path, "static", resume_path)


def _extract_docx_text(file_path):
    try:
        with zipfile.ZipFile(file_path) as archive:
            with archive.open("word/document.xml") as document_xml:
                root = ElementTree.fromstring(document_xml.read())
                namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                texts = [node.text for node in root.findall(".//w:t", namespaces) if node.text]
                return "\n".join(texts).strip()
    except Exception:
        return ""


def _extract_pdf_text(file_path):
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            PdfReader = None

    if PdfReader:
        try:
            reader = PdfReader(file_path)
            texts = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    texts.append(page_text)
            return "\n".join(texts).strip()
        except Exception:
            pass

    try:
        with open(file_path, "rb") as handle:
            raw = handle.read().decode("latin-1", errors="ignore")
        fragments = re.findall(r"\(([^)]{2,120})\)", raw)
        return "\n".join(fragments).strip()
    except Exception:
        return ""


def _extract_resume_text(file_path):
    if not file_path or not os.path.exists(file_path):
        return ""

    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".docx":
        text = _extract_docx_text(file_path)
        if text:
            return text
    elif extension == ".pdf":
        text = _extract_pdf_text(file_path)
        if text:
            return text

    try:
        with open(file_path, "rb") as handle:
            return handle.read().decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _normalise_list(value):
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [part.strip() for part in re.split(r"[\n,;]+", value) if part.strip()]
    else:
        items = []
    return "\n".join(items[:8])


def _fit_label(score):
    if score >= 85:
        return "Excellent fit"
    if score >= 70:
        return "Strong fit"
    if score >= 55:
        return "Good fit"
    if score >= 40:
        return "Partial fit"
    return "Low fit"


def _keyword_heuristic(job_text, resume_text):
    job_terms = set(re.findall(r"[a-zA-Z]{4,}", job_text.lower()))
    resume_terms = set(re.findall(r"[a-zA-Z]{4,}", resume_text.lower()))
    if not job_terms or not resume_terms:
        return 20, []

    matched = sorted(job_terms & resume_terms)
    coverage = len(matched) / max(len(job_terms), 1)
    score = min(95, max(20, int(coverage * 100)))
    return score, matched[:10]


def _fallback_analysis(job, candidate, resume_text, reason=None):
    job_text = " ".join(
        part for part in [
            job.get("title"),
            job.get("description"),
            job.get("responsibilities"),
            job.get("requirements"),
            job.get("who_should_apply"),
            job.get("skills"),
            job.get("experience_level"),
            job.get("industry_name"),
            job.get("category_name"),
        ] if part
    )
    score, matched_terms = _keyword_heuristic(job_text, resume_text)
    fit_label = _fit_label(score)
    candidate_name = " ".join(
        part for part in [candidate.get("first_name"), candidate.get("last_name")] if part
    ).strip() or "The candidate"
    strengths = [
        f"{candidate_name} shows keyword overlap with the role requirements.",
    ]
    if matched_terms:
        strengths.append(f"Matched terms: {', '.join(matched_terms)}.")
    gaps = [
        "Review the resume manually for depth in the core skills required by the role.",
    ]
    if reason:
        gaps.append(f"AI review fallback was used because: {reason}.")
    recommendation = "Proceed to manual review and compare the resume against the job requirements."
    return {
        "score": score,
        "fit_label": fit_label,
        "summary": (
            f"This resume appears to be a {fit_label.lower()} for {job.get('title') or 'this role'}."
        ),
        "strengths": "\n".join(strengths),
        "gaps": "\n".join(gaps),
        "recommendation": recommendation,
        "source": "heuristic",
    }


def _parse_json_response(text):
    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown code blocks
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Try to parse the entire cleaned text
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try to find JSON between first { and last }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            json_str = cleaned[first_brace:last_brace + 1]
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None


def analyze_resume_fit(job, candidate, resume_path):
    file_path = _resume_file_path(resume_path)
    resume_text = _extract_resume_text(file_path)
    if not resume_text:
        return _fallback_analysis(job, candidate, "", reason="Resume text could not be extracted")

    prompt = f"""
You are an ATS-style resume reviewer for hiring managers.

IMPORTANT: Return ONLY a valid JSON object. No markdown, no code blocks, no extra text.

JSON format:
{{
  "score": integer between 0 and 100,
  "fit_label": one of "Excellent fit", "Strong fit", "Good fit", "Partial fit", "Low fit",
  "summary": 2-3 sentences about overall fit for the role,
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "gaps": ["gap 1", "gap 2", "gap 3"],
  "recommendation": one short sentence for the employer
}}

Job title: {job.get("title") or "N/A"}
Industry: {job.get("industry_name") or "N/A"}
Category: {job.get("category_name") or "N/A"}
Experience level: {job.get("experience_level") or "N/A"}
Skills required: {job.get("skills") or "N/A"}
Overview: {job.get("description") or "N/A"}
What you will do: {job.get("responsibilities") or "N/A"}
Requirements: {job.get("requirements") or "N/A"}
Who should apply: {job.get("who_should_apply") or "N/A"}

Candidate: {candidate.get("first_name") or ""} {candidate.get("last_name") or ""}

Resume text:
{resume_text[:7000]}
"""

    try:
        response = call_ai(prompt, max_tokens=800)
        current_app.logger.info(f"AI Resume Analysis Response: {response[:500]}")
        parsed = _parse_json_response(response)
        if not parsed:
            current_app.logger.error(f"Failed to parse AI response. Full response: {response}")
            return _fallback_analysis(job, candidate, resume_text, reason="AI response could not be parsed")

        score = int(parsed.get("score", 0) or 0)
        score = max(0, min(100, score))
        fit_label = parsed.get("fit_label") or _fit_label(score)
        summary = str(parsed.get("summary") or "").strip()
        strengths = _normalise_list(parsed.get("strengths"))
        gaps = _normalise_list(parsed.get("gaps"))
        recommendation = str(parsed.get("recommendation") or "").strip()

        if not summary:
            summary = f"This resume appears to be a {fit_label.lower()} for the role."
        if not strengths:
            strengths = "The resume matches some of the job requirements."
        if not gaps:
            gaps = "Manual review is recommended to confirm experience depth."
        if not recommendation:
            recommendation = "Proceed to manual review."

        return {
            "score": score,
            "fit_label": fit_label,
            "summary": summary,
            "strengths": strengths,
            "gaps": gaps,
            "recommendation": recommendation,
            "source": "ai",
        }
    except Exception as exc:
        return _fallback_analysis(job, candidate, resume_text, reason=str(exc))


def build_resume_analysis_payload(job, candidate, resume_path):
    analysis = analyze_resume_fit(job, candidate, resume_path)
    analysis["analyzed_at"] = datetime.now()
    return analysis
