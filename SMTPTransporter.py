import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mailer_error.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class SMTPTransporter:
    """
    Handles the physical connection and sending of composed email messages.

    Supports two connection modes automatically based on port:
      - Port 465 → SMTP_SSL  (implicit TLS)
      - Port 587 → SMTP + STARTTLS (explicit TLS)

    Credentials can be supplied directly via constructor args or via env vars:
      SMTP_HOST     (default: smtp.gmail.com)
      SMTP_PORT     (default: 587)
      SMTP_USER     (required: your real login email address)
      SMTP_PASSWORD (required: Gmail App Password or account password)

    Direct args always take priority over env vars.
    """

    def __init__(self, user: str = None, password: str = None):
        self.server_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.port = int(os.getenv('SMTP_PORT', '587'))  # 587=STARTTLS, 465=SSL

        # Direct args take priority; fall back to env vars
        # Strip whitespace to avoid invisible-character auth failures
        self.sender_email = (user or os.getenv('SMTP_USER') or '').strip()
        self.sender_password = (password or os.getenv('SMTP_PASSWORD') or '').strip()

        if not self.sender_email or not self.sender_password:
            raise ValueError(
                "SMTP credentials not set! "
                "Please provide 'SMTP_USER' and 'SMTP_PASSWORD' (env vars) "
                "or pass user/password directly to SMTPTransporter()."
            )

        logger.info(
            f"SMTPTransporter ready — host={self.server_host}, "
            f"port={self.port}, user={self.sender_email}, "
            f"mode={'SMTP_SSL' if self.port == 465 else 'STARTTLS'}"
        )

    def _connect(self) -> smtplib.SMTP:
        """
        Open and authenticate an SMTP connection.
        Uses SMTP_SSL for port 465, SMTP+STARTTLS for port 587.
        """
        if self.port == 465:
            # Implicit TLS — wrap the socket from the start
            server = smtplib.SMTP_SSL(self.server_host, self.port, timeout=10)
        else:
            # Explicit TLS — connect plain, then upgrade
            server = smtplib.SMTP(self.server_host, self.port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(self.sender_email, self.sender_password)
        return server

    def send_message(self, message_obj: MIMEMultipart, receiver_email: str, from_header: str = None) -> bool:
        """
        Connect, authenticate, and send one message.
        If from_header is provided, it overrides the envelope sender.
        Returns True on success, False on failure.
        Raises Exception with a descriptive message on auth or connection errors.
        """
        sender_identity = from_header if from_header else self.sender_email
        try:
            with self._connect() as server:
                server.sendmail(
                    sender_identity,
                    receiver_email,
                    message_obj.as_string()
                )
            logger.info(
                f"Sent to {receiver_email} | subject='{message_obj['Subject']}'"
            )
            return True

        except smtplib.SMTPAuthenticationError as e:
            msg = (
                f"SMTP Authentication Failed.\n"
                f"  User  : {self.sender_email}\n"
                f"  Host  : {self.server_host}:{self.port}\n"
                f"  Mode  : {'SMTP_SSL' if self.port == 465 else 'STARTTLS'}\n"
                f"  Detail: {e}\n\n"
                f"For Gmail: make sure 2-Step Verification is ON and you are using\n"
                f"a 16-character App Password (not your normal Gmail password).\n"
                f"Generate one at: myaccount.google.com/apppasswords"
            )
            logger.error(msg)
            raise Exception(msg)

        except smtplib.SMTPConnectError as e:
            msg = f"Could not connect to {self.server_host}:{self.port} — {e}"
            logger.error(msg)
            raise Exception(msg)

        except smtplib.SMTPRecipientsRefused as e:
            msg = f"Recipient refused by server: {receiver_email} — {e}"
            logger.error(msg)
            raise Exception(msg)

        except Exception as e:
            logger.error(f"Unexpected SMTP error sending to {receiver_email}: {e}", exc_info=True)
            raise

    def send(self, message_obj: MIMEMultipart, receiver_email: str, from_header: str = None) -> bool:
        """Send an email with optional spoofed From header.
        If from_header is provided, it overrides the message's 'From' header and envelope sender.
        """
        if from_header:
            message_obj['From'] = from_header
        return self.send_message(message_obj, receiver_email, from_header)