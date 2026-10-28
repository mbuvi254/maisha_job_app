"""Private profile CV storage and transparent text-based job suggestions."""
from pathlib import Path
import re
import uuid
import zipfile
from xml.etree import ElementTree

from flask import current_app
from werkzeug.utils import secure_filename

MAX_CV_BYTES = 5 * 1024 * 1024
STOP_WORDS = set('about after also and are been build can company experience for from have into job looking our role should skills strong team that the their this through will with work years your you'.split())


def cv_directory():
    directory = Path(current_app.root_path) / 'private' / 'candidate_resumes'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_cv_text(path):
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if len(reader.pages) > 50:
            raise ValueError('Please upload a CV with no more than 50 pages.')
        return '\n'.join((page.extract_text() or '') for page in reader.pages)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('word/document.xml')
        if info.file_size > 10 * 1024 * 1024:
            raise ValueError('This document is too large to read. Please upload a smaller CV.')
        root = ElementTree.fromstring(archive.read(info))
        return '\n'.join(node.text for node in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text)


def save_profile_cv(upload):
    name = secure_filename(upload.filename or '')
    extension = Path(name).suffix.lower()
    if extension not in {'.pdf', '.docx'}:
        raise ValueError('Upload a PDF or DOCX resume / CV.')
    content = upload.stream.read(MAX_CV_BYTES + 1)
    if not content or len(content) > MAX_CV_BYTES:
        raise ValueError('Your CV must be a non-empty file of 5 MB or less.')
    if (extension == '.pdf' and not content.startswith(b'%PDF-')) or (extension == '.docx' and not content.startswith(b'PK')):
        raise ValueError('The file does not match its format. Upload a valid PDF or DOCX.')
    path = cv_directory() / (str(uuid.uuid4()) + extension)
    path.write_bytes(content)
    try:
        text = read_cv_text(path).strip()
        if len(text) < 30:
            raise ValueError('We could not read enough text from this CV. Upload a text-based PDF or DOCX; scanned images cannot be matched.')
        return dict(cv_filename=path.name, cv_name=name, cv_text=text[:100000])
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, ValueError):
            raise
        raise ValueError('We could not read this CV. Upload a valid, unencrypted PDF or DOCX.') from exc


def _terms(value):
    # Keep short technical skills such as SQL, Go, C++, C#, and R.
    return set(re.findall(r'[a-z0-9]+(?:[+#]+|\.[a-z0-9]+)?', str(value or '').casefold())) - STOP_WORDS


def match_open_jobs(cv_text, jobs, applied_job_ids=(), limit=6):
    resume_terms = _terms(cv_text)
    if not resume_terms:
        return []
    applied = {str(ident) for ident in applied_job_ids}
    matches = []
    for job in jobs:
        if str(job['id']) in applied:
            continue
        skills = [skill.strip() for skill in str(job.get('skills') or '').split(',') if skill.strip()]
        matched_skills = [skill for skill in skills if _terms(skill) and _terms(skill) <= resume_terms]
        role_terms = _terms(' '.join(str(job.get(field) or '') for field in ('title', 'description', 'responsibilities', 'requirements', 'who_should_apply')))
        shared = role_terms & resume_terms
        if not matched_skills and len(shared) < 2:
            continue
        skill_coverage = len(matched_skills) / len(skills) if skills else 0
        context_coverage = len(shared) / max(len(role_terms), 1)
        score = round(100 * (0.75 * skill_coverage + 0.25 * context_coverage)) if skills else round(100 * context_coverage)
        # These are text overlaps, not a suitability decision or hiring prediction.
        matches.append(dict(job=job, match_score=score, matched_skills=matched_skills[:8],
                            matched_terms=sorted(shared)[:6]))
    matches.sort(key=lambda row: (row['match_score'], len(row['matched_skills'])), reverse=True)
    return matches[:limit]
