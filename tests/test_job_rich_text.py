import unittest
from unittest.mock import patch

from app import app
from app.services.job_content_service import clean_job_html, render_job_html, editor_job_html, plain_job_text
from app.services.job_service import create_job, update_job
from app.services.candidate_resume_service import match_open_jobs


class JobRichTextTests(unittest.TestCase):
    def test_formatting_is_preserved_and_active_content_is_removed(self):
        source = '<h2>Role</h2><p><strong>Python</strong></p><ul><li>Build APIs</li></ul><a href="https://example.org" onclick="bad()">Details</a><script>alert(1)</script><img src=x onerror=bad()><iframe src="https://bad.invalid"></iframe>'
        cleaned = clean_job_html(source)
        for expected in ('<h2>Role</h2>', '<strong>Python</strong>', '<ul><li>Build APIs</li></ul>', 'href="https://example.org"'):
            self.assertIn(expected, cleaned)
        for unsafe in ('onclick', 'onerror', '<script', '<img', '<iframe', 'alert(1)'):
            self.assertNotIn(unsafe, cleaned)
        self.assertEqual(clean_job_html(cleaned), cleaned)

    def test_unsafe_link_schemes_and_css_are_removed(self):
        value = clean_job_html('<a href="javascript:alert(1)">Bad</a><span style="position:fixed" class="overlay">Text</span>')
        self.assertNotIn('javascript:', value)
        self.assertNotIn('style=', value)
        self.assertNotIn('class=', value)
        self.assertIn('Text', value)

    def test_plain_existing_jobs_keep_linebreaks_and_escape_angle_brackets(self):
        self.assertEqual(str(render_job_html('First line\nSecond line & more')), 'First line\nSecond line &amp; more')
        self.assertIn('\n', editor_job_html('First\nSecond'))
        self.assertEqual(plain_job_text('<p>Python</p><p>SQL &amp; Flask</p>').split(), ['Python', 'SQL', '&', 'Flask'])

    def test_create_and_edit_sanitize_before_repository_write(self):
        data = dict(employer_id='employer',title='Developer',category_id='category',description='<p>Build <b>APIs</b></p><script>bad()</script>')
        with patch('app.services.job_service.repo.insert', return_value='job') as insert:
            self.assertEqual(create_job(data)['id'], 'job')
            self.assertEqual(insert.call_args.args[0]['description'],'<p>Build <b>APIs</b></p>')
        with patch('app.services.job_service.repo.update', return_value=True) as update:
            update_job('job', data)
            self.assertNotIn('<script>', update.call_args.args[1]['description'])

    def test_html_tags_do_not_add_match_terms(self):
        jobs = [dict(id='job', title='Engineer', skills='Python, SQL', description='<p>Flask API development</p>')]
        matches = match_open_jobs('Python SQL Flask API developer', jobs)
        self.assertEqual(matches[0]['job']['id'], 'job')
        self.assertNotIn('p', matches[0]['matched_terms'])

    def test_editor_fields_render_and_old_values_are_safe(self):
        from flask import render_template
        with app.test_request_context('/employers/jobs/new'):
            output=render_template('employer/employer_job_form.html',job={'description':'<p>Safe</p><script>bad()</script>'},form_data=None,industries=[],grouped_categories=[],selected_industry_id=None,selected_category_id=None)
        self.assertEqual(output.count('job-rich-editor'),5)
        self.assertIn('summernote-lite.min.js',output)
        self.assertIn('&lt;p&gt;Safe&lt;/p&gt;',output)
        self.assertNotIn('<script>bad()',output)
