"""A narrow rich-text format for employer-authored job content."""
import html
import re

import nh3
from markupsafe import Markup, escape

RICH_FIELDS = ('description', 'responsibilities', 'requirements', 'who_should_apply', 'salary_insight')
TAGS = {'p', 'br', 'div', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'h2', 'h3', 'h4',
        'ul', 'ol', 'li', 'blockquote', 'a', 'hr', 'pre', 'code', 'span', 'sub', 'sup'}


def clean_job_html(value):
    return nh3.clean(str(value or ''), tags=TAGS, attributes={'a': {'href', 'title'}},
                     url_schemes={'http', 'https', 'mailto'})


def editor_job_html(value):
    value = str(value or '')
    return clean_job_html(value) if nh3.is_html(value) else str(escape(value))


def render_job_html(value):
    return Markup(editor_job_html(value))


def plain_job_text(value):
    return html.unescape(re.sub(r'<[^>]*>', ' ', clean_job_html(value)))


def clean_job_data(data):
    return {key: clean_job_html(value) if key in RICH_FIELDS else value for key, value in data.items()}
