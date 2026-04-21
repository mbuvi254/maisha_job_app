from app.repository.verification_repository import VerificationRepository
import secrets
from flask_mail import Mail, Message
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
# Send Email
def send_verification_email2(user_email, otp):
    try:
        msg = Message(
            subject='Cybermaisha OTP Verification',
            sender='accounts@cm.co.ke',
            recipients=[user_email],
            body=f"Your OTP code is {otp}. It is valid for 10 minutes."
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error while sending verification email: {e}")
        return False
    
    


def send_verification_email(user_email: str, otp: str) -> bool:
    """
    Send OTP verification email to user.
    
    Args:
        user_email (str): Recipient's email address
        otp (str): One-Time Password to send
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate inputs
        if not all([user_email, otp]):
            logging.error("Empty email or OTP provided")
            return False
            
        # Create email message
        msg = Message(
            subject='Your Verification Code for Cybermaisha',
            sender='accounts@cm.co.ke',
            recipients=[user_email],
            html=f"""
            <html>
                <body>
                    <h2>Cybermaisha Account Verification</h2>
                    <p>Your verification code is:</p>
                    <h3 style="font-size: 24px; letter-spacing: 3px;">{otp}</h3>
                    <p>This code will expire in 10 minutes.</p>
                    <hr>
                    <p>If you didn't request this, please ignore this email.</p> 
                    <p>© {datetime.now().year} Cybermaisha. All rights reserved.</p>
                </body>
            </html>
            """
        )
        
        # Add text fallback
        msg.body = f"Your Cybermaisha verification code is: {otp}\nValid for 10 minutes."
        
        # Send email
        mail.send(msg)
        logging.info(f"Verification email sent to {user_email}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send verification email to {user_email}: {str(e)}", exc_info=True)
        return False