import unittest
from unittest.mock import patch
from app import app
from app.services import verification_service as emails


class StyledEmailTests(unittest.TestCase):
    def setUp(self):
        self.context = app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.sender = patch.object(emails.mail, 'send')
        self.send = self.sender.start()
        self.addCleanup(self.sender.stop)

    def test_verification_has_styled_code_and_text_alternative(self):
        self.assertTrue(emails.send_verification_email('candidate@example.invalid', '012345'))
        message = self.send.call_args.args[0]
        self.assertEqual(message.recipients, ['candidate@example.invalid'])
        self.assertIn('012345', message.html)
        self.assertIn('012345', message.body)
        self.assertIn('10 minutes', message.html)
        self.assertIn('Maisha Jobs', message.html)
        self.assertIn('role="presentation"', message.html)
        self.assertIn('Never share', message.body)
        self.assertNotIn('012345', message.subject)

    def test_legacy_email_entry_point_uses_same_design(self):
        self.assertTrue(emails.send_verification_email2('candidate@example.invalid', '654321'))
        self.assertIn('Maisha Jobs', self.send.call_args.args[0].html)
        self.assertTrue(self.send.call_args.args[0].body)

    def test_application_and_interview_have_buttons_and_plain_links(self):
        for sender in [emails.send_application_submission_email, emails.send_interview_invitation_email]:
            with self.subTest(sender=sender.__name__):
                url='https://example.invalid/jobs/1?token=abc&next=interview'
                self.assertTrue(sender('candidate@example.invalid', 'Amina', 'Python Developer', url))
                message=self.send.call_args.args[0]
                self.assertIn('Python Developer', message.html)
                self.assertIn('Hi Amina', message.html)
                self.assertIn(url, message.body)
                self.assertIn('token=abc&amp;next=interview', message.html)
                self.assertIn('If the button does not work', message.html)

    def test_user_supplied_html_is_escaped(self):
        self.assertTrue(emails.send_interview_invitation_email('candidate@example.invalid', '<img src=x onerror=alert(1)>', '<script>bad()</script>', 'https://example.invalid/interview'))
        message=self.send.call_args.args[0]
        self.assertNotIn('<script>bad()</script>', message.html)
        self.assertNotIn('<img src=x', message.html)
        self.assertIn('&lt;script&gt;', message.html)
        self.assertTrue(emails.send_verification_email('candidate@example.invalid', '<script>bad()</script>'))
        self.assertNotIn('<script>bad()</script>', self.send.call_args.args[0].html)

    def test_invalid_links_and_missing_inputs_do_not_send(self):
        for url in ['javascript:alert(1)', '//example.invalid', 'https://user:password@example.invalid', 'https://example.invalid/\nsecret']:
            self.assertFalse(emails.send_application_submission_email('candidate@example.invalid', 'Amina', 'Engineer', url))
        self.assertFalse(emails.send_verification_email('', '123456'))
        self.send.assert_not_called()

    def test_delivery_failure_preserves_false_return_contract(self):
        self.send.side_effect=RuntimeError('Mail unavailable')
        with self.assertLogs(level='ERROR'):
            self.assertFalse(emails.send_verification_email('candidate@example.invalid', '123456'))
