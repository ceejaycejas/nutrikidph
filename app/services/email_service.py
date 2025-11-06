from flask import current_app
from flask_mail import Message
import logging

# Import mail instance from app
try:
    from app import mail
    MAIL_AVAILABLE = True
except ImportError:
    mail = None
    MAIL_AVAILABLE = False

class EmailService:
    """Service for handling email notifications"""

    @staticmethod
    def send_email(
        to=None,
        subject=None,
        body=None,
        html_body=None,
        *,
        recipients=None,
        text_body=None,
    ):
        """
        Send an email notification.

        Compatibility:
        - Supports both legacy signature (to, subject, body, html_body)
          and new keyword style (subject=..., recipients=[...], text_body=..., html_body=...).

        Returns True on success, False on failure.
        """
        try:
            # Check if mail service is available
            if not MAIL_AVAILABLE or mail is None:
                # Fallback to logging if mail is not available
                current_app.logger.info("EMAIL SERVICE NOT AVAILABLE - FALLING BACK TO LOGGING")
                return EmailService._log_email(to, subject, body, html_body, recipients, text_body)
            
            # Normalize inputs
            recipient_list = []
            if recipients and isinstance(recipients, (list, tuple)):
                recipient_list = list(recipients)
            elif to:
                recipient_list = [to]
            
            if not recipient_list:
                current_app.logger.error("No recipients specified for email")
                return False
            
            text = text_body if text_body is not None else body
            
            # Log email details for debugging
            current_app.logger.info(f"Preparing to send email to: {', '.join(recipient_list)}")
            current_app.logger.info(f"Subject: {subject}")
            
            # Create message
            msg = Message(
                subject=subject,
                recipients=recipient_list,
                body=text,
                html=html_body
            )
            
            # Send email
            mail.send(msg)
            current_app.logger.info(f"Email sent successfully to {', '.join(recipient_list)}")
            return True
            
        except Exception as e:
            # Try to include a best-effort recipient for error context
            safe_to = to if to else (recipients[0] if isinstance(recipients, (list, tuple)) and recipients else 'unknown')
            current_app.logger.error(f"Failed to send email to {safe_to}: {str(e)}")
            return False
    
    @staticmethod
    def _log_email(to=None, subject=None, body=None, html_body=None, recipients=None, text_body=None):
        """Fallback method to log emails when mail service is not available"""
        try:
            # Normalize inputs
            recipient_list = []
            if recipients and isinstance(recipients, (list, tuple)):
                recipient_list = list(recipients)
            elif to:
                recipient_list = [to]

            text = text_body if text_body is not None else body

            # Log the email
            current_app.logger.info("EMAIL NOTIFICATION:")
            current_app.logger.info(f"To: {', '.join(recipient_list) if recipient_list else 'N/A'}")
            current_app.logger.info(f"Subject: {subject}")
            current_app.logger.info(f"Body: {text}")
            if html_body:
                current_app.logger.info("HTML Body present")

            return True

        except Exception as e:
            # Try to include a best-effort recipient for error context
            safe_to = to if to else (recipients[0] if isinstance(recipients, (list, tuple)) and recipients else 'unknown')
            current_app.logger.error(f"Failed to log email to {safe_to}: {str(e)}")
            return False
    
    @staticmethod
    def send_password_reset_notification(user_email, user_name, reset_token=None):
        """
        Send password reset notification email
        
        Args:
            user_email (str): User's email address
            user_name (str): User's name
            reset_token (str, optional): Password reset token
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset Request - NutriKid"
        
        if reset_token:
            # Direct password reset email (if implementing direct reset)
            body = f"""
Hello {user_name},

You have requested a password reset for your NutriKid account.

If you did not request this reset, please ignore this email.

Best regards,
NutriKid Team
            """
        else:
            # Admin approval required email
            body = f"""
Hello {user_name},

Your password reset request has been submitted and is pending approval from your administrator.

You will receive another notification once your request has been processed.

Best regards,
NutriKid Team
            """
        
        return EmailService.send_email(user_email, subject, body)
    
    @staticmethod
    def send_admin_notification(admin_email, admin_name, user_name, user_role):
        """
        Send notification to admin about password reset request
        
        Args:
            admin_email (str): Admin's email address
            admin_name (str): Admin's name
            user_name (str): User requesting reset
            user_role (str): Role of user requesting reset
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = f"Password Reset Request - {user_name} ({user_role})"
        
        body = f"""
Hello {admin_name},

A password reset request has been submitted by:
- Name: {user_name}
- Role: {user_role.title()}

Please log in to the NutriKid system to review and process this request.

Best regards,
NutriKid System
        """
        
        return EmailService.send_email(admin_email, subject, body)
    
    @staticmethod
    def send_password_reset_approved(user_email, user_name, new_password):
        """
        Send notification when password reset is approved with new password
        
        Args:
            user_email (str): User's email address
            user_name (str): User's name
            new_password (str): New temporary password
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset Approved - NutriKid"
        
        body = f"""
Hello {user_name},

Your password reset request has been approved.

Your new temporary password is: {new_password}

Please log in with this password and change it immediately for security.

Best regards,
NutriKid Team
        """
        
        return EmailService.send_email(user_email, subject, body)
    
    @staticmethod
    def send_password_reset_denied(user_email, user_name, reason=None):
        """
        Send notification when password reset is denied
        
        Args:
            user_email (str): User's email address
            user_name (str): User's name
            reason (str, optional): Reason for denial
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset Request Denied - NutriKid"
        
        body = f"""
Hello {user_name},

Your password reset request has been denied.

{f"Reason: {reason}" if reason else ""}

Please contact your administrator if you need further assistance.

Best regards,
NutriKid Team
        """
        
        return EmailService.send_email(user_email, subject, body)