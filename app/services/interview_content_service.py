"""Keep interview formatting separate from the plain answer sent for evaluation."""
from html.parser import HTMLParser
from markupsafe import escape
from app.services.job_content_service import clean_job_html


class AnswerText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'p', 'div', 'br', 'li', 'h2', 'h3', 'h4', 'pre', 'blockquote'}:
            self.parts.append('\n')
        if tag == 'li':
            self.parts.append('• ')

    def handle_endtag(self, tag):
        if tag in {'p', 'div', 'li', 'h2', 'h3', 'h4', 'pre', 'blockquote'}:
            self.parts.append('\n')

    def handle_data(self, value):
        self.parts.append(value)


def rich_answer(value):
    safe_html = clean_job_html(value)
    parser = AnswerText()
    parser.feed(safe_html)
    text = '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip()).strip()
    return text, safe_html


def coding_answer_html(language, code, explanation_html):
    return f'<p><strong>Language: {escape(language)}</strong></p><pre><code>{escape(code)}</code></pre><h4>Explanation and tests</h4>{explanation_html}'
