import smtplib
from email.mime.multipart import MIMEMultipart
import os
import logging
class SMTPTransporter:
    # Configure logger (once per module)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('mailer_error.log'),
            logging.StreamHandler()
        ]
    )
    """
    Handles the physical connection and sending of the composed message.
    This class abstracts away the smtplib details.
    """
    def __init__(self):
        # Read credentials from environment variables (with sensible defaults)
        self.server_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.port = int(os.getenv('SMTP_PORT', '465'))
        self.sender_email = os.getenv('SMTP_USER')
        self.sender_password = os.getenv('SMTP_PASSWORD')

        # Validate required credentials
        if not self.sender_email or not self.sender_password:
            raise ValueError(
                "SMTP credentials not set! Please set the environment variables 'SMTP_USER' and 'SMTP_PASSWORD'."
            )

    def send_message(self, message_obj: MIMEMultipart, receiver_email: str) -> bool:
        """
        Connects, logs in, and attempts to send the message object.
        Returns True on success, False otherwise.
        """
        try:
            with smtplib.SMTP_SSL(self.server_host, self.port) as smtp_server:
                smtp_server.login(self.sender_email, self.sender_password)
                smtp_server.sendmail(self.sender_email, receiver_email, message_obj.as_string())
                logging.info(f"Successfully sent email to {receiver_email}. Subject: {message_obj['Subject']}")
                return True
        except smtplib.SMTPAuthenticationError:
            logging.error("SMTP Authentication Failed. Check email/App Password.")
            return False
        except smtplib.SMTPConnectError:
            logging.error(f"Could not connect to {self.server_host}.")
            return False
        except Exception as e:
            logging.error(f"Generic sending failure: {e}", exc_info=True)
            return False