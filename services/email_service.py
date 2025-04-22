# services/email_service.py
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_TLS


logger = logging.getLogger(__name__)
class EmailService:
    def __init__(self):
        # Create templates directory if it doesn't exist
        # Use parent directory (project root) when constructing paths
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.templates_dir = os.path.join(self.root_dir, "email_templates")
            
        # Set up Jinja2 environment for email templates
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Check if SMTP is configured
        self.is_configured = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
        if not self.is_configured:
            logger.error("SMTP not fully configured. Emails will not be sent.")

    def send_email(self, to_address, subject, template_name, context=None):
        if not self.is_configured:
            logger.warning(f"Email to {to_address} not sent: SMTP not configured")
            return False
            
        if context is None:
            context = {}
            
        try:
            # Get template and render with context
            template = self.env.get_template(f"{template_name}.html")
            html_content = template.render(**context)
            
            # Create multipart message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = to_address
            
            # Add HTML part
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            # Connect to SMTP and send
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            try:
                if SMTP_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [to_address], msg.as_string())
                logger.info(f"Email sent to {to_address}: {subject}")
                return True
            finally:
                server.quit()
                
        except Exception as e:
            logger.error(f"Failed to send email to {to_address}: {str(e)}")
            return False
            
    def send_welcome_email(self, to_address, first_name):
        subject = "Willkommen bei Kreditbank - Ihr Konto wurde erstellt"
        context = {"first_name": first_name}
        return self.send_email(to_address, subject, "welcome", context)
        
    def send_password_reset_email(self, to_address, first_name, reset_link):
        subject = "Kreditbank - Link zum Zurücksetzen Ihres Passworts"
        context = {"first_name": first_name, "reset_link": reset_link}
        return self.send_email(to_address, subject, "password_reset", context)
        
    def send_password_changed_email(self, to_address, first_name):
        subject = "Kreditbank - Ihr Passwort wurde geändert"
        context = {"first_name": first_name}
        return self.send_email(to_address, subject, "password_changed", context)
        
    def send_loan_status_email(self, to_address, first_name, application_date, loan_type, status, reason=None):
        subject = "Kreditbank - Update zu Ihrem Kreditantrag"
        context = {
            "first_name": first_name,
            "application_date": application_date,
            "loan_type": loan_type,
            "status": status,
            "reason": reason
        }
        return self.send_email(to_address, subject, "loan_status", context)
        
    def send_custom_email(self, to_address, subject, html_content):
        if not self.is_configured:
            logger.error(f"Custom email to {to_address} not sent: SMTP not configured")
            return False
            
        try:
            # Create multipart message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = to_address
            
            # Add HTML part
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            # Connect to SMTP and send
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            try:
                if SMTP_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [to_address], msg.as_string())
                print(f"Custom email sent to {to_address}: {subject}")
                return True
            finally:
                server.quit()
                
        except Exception as e:
            logger.error(f"Failed to send custom email to {to_address}: {str(e)}")
            return False

email_service = EmailService()