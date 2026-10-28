from app.repository.verification_repository import VerificationRepository
import secrets
from flask_mail import Mail, Message
from flask import current_app
from datetime import datetime
import logging

mail = Mail()

repo = VerificationRepository()

##### Verification Functions ################

def save_verification_otp(user_email, otp):
    try:
        return repo.save_verification_otp(user_email, otp)
    except Exception as e:
        print(f"Error saving verification OTP: {e}")
        return False


def get_otp(user_email):
    try:
        return repo.get_otp(user_email)
    except Exception as e:
        print(f"Error fetching OTP: {e}")
        return None


def delete_verification_otp(user_email):
    try:
        return repo.delete_verification_otp(user_email)
    except Exception as e:
        print(f"Error deleting verification OTP: {e}")
        return False

# Generate OTP
def generate_otp():
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])




########## Send Email ###################
def _send_styled_email(user_email, subject, body, **context):
    """Render autoescaped, email-client-friendly HTML with a text alternative."""
    from flask import render_template
    msg = Message(
        subject=subject,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user_email],
        body=body,
        html=render_template('emails/notification.html', year=datetime.now().year, **context),
    )
    mail.send(msg)


def _valid_action_url(value):
    from urllib.parse import urlsplit
    if not isinstance(value, str) or any(ord(char) < 32 for char in value) or '\\' in value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme.lower() in {'http', 'https'} and bool(parsed.hostname) and not parsed.username and not parsed.password


def send_verification_email2(user_email, otp):
    """Keep the legacy entry point consistent with the shared sign-in email."""
    return send_verification_email(user_email, otp)


def send_verification_email(user_email: str, otp: str) -> bool:
    """Send a styled one-time sign-in code with a plain-text alternative."""
    try:
        if not all([user_email, otp]):
            logging.error('Empty email or OTP provided')
            return False
        _send_styled_email(
            user_email, 'Your Maisha Jobs verification code',
            f'Your Maisha Jobs verification code is: {otp}\nValid for 10 minutes. Use the most recent code.\n'
            'Enter it on the sign-in page. Never share your code.\nIf you did not request this, ignore this email.',
            heading='Your next step starts here.', eyebrow='SECURE SIGN-IN',
            preheader='Use your verification code to sign in to Maisha Jobs. It expires in 10 minutes.',
            introduction='Use this one-time code to securely access your Maisha Jobs account.',
            otp=otp, footer_note='If you did not request this code, you can safely ignore this email.',
        )
        return True
    except Exception:
        logging.exception('Failed to send verification email')
        return False


def send_interview_invitation_email(user_email: str, candidate_name: str, job_title: str, interview_url: str) -> bool:
    """Send an interview invitation with a direct, styled action button."""
    try:
        if not all([user_email, job_title, interview_url]) or not _valid_action_url(interview_url):
            logging.error('Missing or invalid interview invitation data')
            return False
        name = candidate_name or 'Candidate'
        _send_styled_email(
            user_email, f'Interview invitation for {job_title}',
            f'Hi {name},\n\nYour interview for {job_title} is ready.\n'
            f'Open this link to start: {interview_url}\nReview the role and follow the interview instructions when you are ready.',
            heading='Your interview is ready.', eyebrow='TAKE THE NEXT STEP',
            preheader=f'You are invited to interview for {job_title}.',
            candidate_name=name, introduction='Your interview is ready for', job_title=job_title,
            action_url=interview_url, action_label='Start interview',
            next_step='Review the role and follow the interview instructions when you are ready to begin.',
            footer_note='This invitation relates to a job application on Maisha Jobs. If you did not apply, you can ignore this email.',
        )
        return True
    except Exception:
        logging.exception('Failed to send interview invitation email')
        return False


def send_application_submission_email(user_email: str, candidate_name: str, job_title: str, job_url: str) -> bool:
    """Confirm a submitted application with consistent branding and a job link."""
    try:
        if not all([user_email, job_title, job_url]) or not _valid_action_url(job_url):
            logging.error('Missing or invalid application confirmation data')
            return False
        name = candidate_name or 'Candidate'
        _send_styled_email(
            user_email, f'Application received for {job_title}',
            f'Hi {name},\n\nYour application for {job_title} has been submitted successfully.\n'
            f'View the job here: {job_url}\nSign in to your candidate profile to track your application and next steps.',
            heading='Application received.', eyebrow='ONE STEP CLOSER',
            preheader=f'Your application for {job_title} has been submitted successfully.',
            candidate_name=name, introduction='Your application has been submitted successfully for', job_title=job_title,
            action_url=job_url, action_label='View job',
            next_step='Sign in to your candidate profile to track your application and any interview next steps.',
            footer_note='You are receiving this confirmation because an application was submitted using this email address.',
        )
        return True
    except Exception:
        logging.exception('Failed to send application submission email')
        return False
