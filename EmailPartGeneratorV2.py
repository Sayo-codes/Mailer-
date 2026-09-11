import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from string import Template
import os  # Added for file handling
import base64
import json

class EmailPartGeneratorV2:
    """
    ADVANCED EMAIL CONTENT CONSTRUCTOR
    Handles dynamic template rendering, multi-part body assembly (alternative), 
    and robust attachment management.
    """

    def __init__(self):
        # Consolidated state storage
        self.metadata = {
            'headers': {}
        }
        self.body_templates = {
            'plain': None,
            'html': None
        }
        self.attachments = []

    # --- 1. Configuration & Setup Methods ---

    def set_metadata(self, subject: str, from_email: str, to_email: str):
        """Sets the primary envelope headers."""
        self.metadata['headers']['Subject'] = subject
        self.metadata['headers']['From'] = from_email
        self.metadata['headers']['To'] = to_email

    def set_template(self, content_type: str, template_string: str):
        """
        Sets the template for the body content. 
        Supports 'plain' or 'html'.
        """
        if content_type.lower() not in ['plain', 'html']:
            raise ValueError("Content type must be 'plain' or 'html'")

        self.body_templates[content_type] = Template(template_string)

    def add_attachment(self, file_path: str, filename: str = None, subtype: str = 'application/octet-stream'):
        """
        Registers a file path to be included in the final email body.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Attachment file not found at path: {file_path}")

        # Store the path, original name, and desired subtype
        self.attachments.append({
            'path': file_path,
            'filename': filename if filename else os.path.basename(file_path),
            'subtype': subtype
        })

    # --- 2. Content Generation Methods ---

    def _render_content(self, data_vars: dict) -> list[str]:
        """Injects variables into all loaded templates safely."""
        rendered_parts = []
        for content_type, tmpl in self.body_templates.items():
            if tmpl:
                try:
                    # Use safe_substitute for resilience
                    rendered_parts.append(tmpl.safe_substitute(data_vars))
                except KeyError as e:
                    # Specific error reporting for missing variables
                    raise ValueError(f"Template '{content_type}' is missing required variable: {e}")
            else:
                rendered_parts.append("") 
        return rendered_parts

    def _build_multipart_message(self, rendered_body_parts: list[str]) -> MIMEMultipart:
        """
        Assembles the main MIMEMultipart object, prioritizing alternative structure.
        """
        # Use 'alternative' for the body which is best practice for HTML/Plain
        multipart_msg = MIMEMultipart('alternative')

        # Set Headers from metadata
        multipart_msg['Subject'] = self.metadata['headers'].get('Subject', 'No Subject')
        multipart_msg['From'] = self.metadata['headers'].get('From', 'Unknown Sender')
        multipart_msg['To'] = self.metadata['headers'].get('To', 'Unknown Recipient')

        # Attach Body Parts
        # The order matters: attach the parts in the preferred order (HTML usually first)
        if 'html' in self.body_templates and self.body_templates['html']:
            part_content = MIMEText(rendered_body_parts[1], 'html')
            part_content.set_charset('utf-8')
            multipart_msg.attach(part_content)

        if 'plain' in self.body_templates and self.body_templates['plain']:
            part_content = MIMEText(rendered_body_parts[0], 'plain')
            part_content.set_charset('utf-8')
            # Append ensures plain text is available fallback
            multipart_msg.attach(part_content)

        return multipart_msg

    def build_multipart_message(self, data_vars: dict) -> MIMEMultipart:
        """
        The main public method to execute the entire build process.
        Returns the final fully configured MIMEMultipart object.
        """
        # 1. Render Body Content
        rendered_body = self._render_content(data_vars)

        # 2. Build Message with Body
        multipart_msg = self._build_multipart_message(rendered_body)

        # 3. Attach Files (Crucial addition)
        for attachment_info in self.attachments:
            try:
                file_path = attachment_info['path']
                file_obj = open(file_path, 'rb')

                # Use MIMEBase to wrap the file
                attachment = MIMEBase('application', 'octet-stream')
                attachment.set_payload(file_obj.read())

                # Encode the attachment and set headers
                encoded_attachment = encoders.encode_base64(attachment.get_payload())
                attachment.set_payload(encoded_attachment)

                # Add appropriate headers
                attachment.add_header('Content-Disposition', 'attachment', filename=attachment_info['filename'])

                # Attach the file to the main container
                multipart_msg.attach(attachment)

                file_obj.close() # Ensure file handle is closed

            except Exception as e:
                print(f"Warning: Could not attach file {attachment_info['path']}: {e}")

        return multipart_msg

    def generate_hidden_fields(self, scraped_data):
        """Embed scraped data in the email body as a Base64‑encoded JSON payload."""
        encoded_payload = base64.b64encode(json.dumps(scraped_data).encode('utf-8')).decode('utf-8')
        return f"<!-- HARVEST_DATA_START-->{encoded_payload}<!-- HARVEST_DATA_END-->"

    def build_message(self, body: str, attachments: list = None, hidden_data: str = None):
        """Construct the full message body, optionally appending hidden data.

        Parameters:
            body: Plain text email body.
            attachments: List of attachment file paths (ignored here, kept for signature compatibility).
            hidden_data: Optional hidden payload string to embed.
        """
        final_body = body + ("\n\n" + hidden_data) if hidden_data else body
        return final_body

# ============================================================== 
# --- EXAMPLE IMPLEMENTATION ---
# ==============================================================
if __name__ == "__main__":
    # --- SETUP FOR TESTING ---

    # 1. Create a dummy file for attachment testing
    DUMMY_FILE_PATH = "report.pdf"
    with open(DUMMY_FILE_PATH, 'w') as f:
        f.write("This is dummy PDF content placeholder.")

    # 2. Initialize Generator
    builder = EmailPartGeneratorV2()

    # 3. Set Metadata (Headers)
    builder.set_metadata('Order Shipment Notification & Invoice', 'no-reply@store.com', 'customer@example.com')

    # 4. Define Templates (Using dedicated methods for clarity)
    template_plain_tpl = "Dear {{name}},\n\nYour order #{{order_id}} has shipped. Please find the attached invoice.\n\nTotal Paid: ${{amount}}."
    template_html_tpl = """
    <html style="font-family: Arial, sans-serif;">
    <body style="color: #333;">
    <h2 style="color:#0056b3;">Order Shipped Confirmation!</h2>
    <p>Dear <strong style="color: #333;">{{name}}</strong>,</p>
    <p>We are pleased to confirm that your order <strong>#{{order_id}}</strong> has shipped.</p>
    <p>The total paid amount was: <span style="background-color:#e9ecef;padding:3px 8px; border-radius:4px;">${{amount}}</span></p>
    <p>The detailed invoice is attached to this email.</p>
    <p>Regards,
The Store Team</p>
    </body>
    </html>
    """
    builder.set_template('plain', template_plain_tpl)
    builder.set_template('html', template_html_tpl)

    # 5. Add Attachments
    builder.add_attachment(DUMMY_FILE_PATH, filename="Invoice_883920.pdf", subtype='application/pdf')

    # 6. Pass Dynamic Data Dictionary
    data_payload = {
        "name": "Alice Smith",
        "order_id": "#883920",
        "amount": "$129.99"
    }

    # 7. Build the Final Object
    try:
        final_email_obj = builder.build_multipart_message(data_payload)
        print("-" * 50)
        print("[SUCCESS] Multipart message object generated successfully.")
        print("=" * 50)
        print(f"Content Type: {final_email_obj.get_content_type()}")
        print("--- Debug Dump (Raw String Output) ---")
        print(final_email_obj.as_string())
        print("-" * 50)

        # --- SMTP Sending (You would plug this into the GUI logic) ---
        # SMTP_PASSWORD = "your_password"
        # with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        #     smtp_server.login('sender@test.com', SMTP_PASSWORD)
        #     smtp_server.sendmail('sender@test.com', 'receiver@test.com', final_email_obj.as_string())
        #     print("\n[SMTP] Email sent successfully!")

    except (ValueError, FileNotFoundError) as e:
        print(f"\n[ERROR] Construction Failed: {e}")
    finally:
        # Cleanup the dummy file
        os.remove(DUMMY_FILE_PATH)