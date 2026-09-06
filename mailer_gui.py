import smtplib
import tkinter as tk
from tkinter import ttk, messagebox
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from string import Template

# --- Configuration & Credentials ---
# NOTE: It is highly recommended to use environment variables or a secure vault 
# for production, but for a simple GUI, placing them in the script is fine.
GMAIL_SMTP_SERVER = 'smtp.gmail.com'
GMAIL_SMTP_PORT = 465

class EmailMailerApp:
    def __init__(self, master):
        self.master = master
        master.title("Secure Email Sender (Gmail SMTP)")

        # --- GUI Setup ---
        self.setup_widgets(master)

        # --- Variables to hold input data ---
        self.sender_email_var = tk.StringVar()
        self.sender_password_var = tk.StringVar()
        self.receiver_email_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.body_content_var = tk.StringVar()
        self.plain_text_var = tk.StringVar()
        self.html_body_var = tk.StringVar()

    def setup_widgets(self, master):
        """Sets up all the input fields and labels in the GUI."""

        main_frame = ttk.Frame(master, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 1. Credentials Section (Top)
        ttk.Label(main_frame, text="--- Credentials ---", font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky=tk.W)

        ttk.Label(main_frame, text="Sender Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.sender_email_var, width=50).grid(row=1, column=1, pady=5, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="App Password:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.sender_password_var, show='*' ).grid(row=2, column=1, pady=5, sticky=(tk.W, tk.E))

        # 2. Destination & Content
        ttk.Label(main_frame, text="\n--- Content ---", font=('Arial', 12, 'bold')).grid(row=3, column=0, columnspan=2, pady=(15, 5), sticky=tk.W)

        # Receiver Email
        ttk.Label(main_frame, text="To Email:").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.receiver_email_var, width=50).grid(row=4, column=1, pady=5, sticky=(tk.W, tk.E))

        # Subject Line
        ttk.Label(main_frame, text="Subject:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.subject_var, width=50).grid(row=5, column=1, pady=5, sticky=(tk.W, tk.E))

        # Body Content (Using Text widget for better multi-line input)
        ttk.Label(main_frame, text="Plain Text Body (Fallback):").grid(row=6, column=0, sticky=tk.N+tk.W, pady=5)
        self.plain_text_widget = tk.Text(main_frame, height=8, width=40)
        self.plain_text_widget.grid(row=6, column=1, pady=5, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="HTML Body (Preferred):").grid(row=7, column=0, sticky=tk.N+tk.W, pady=5)
        self.html_widget = tk.Text(main_frame, height=8, width=40)
        self.html_widget.grid(row=7, column=1, pady=5, sticky=(tk.W, tk.E))

        # 3. Action Button
        style = ttk.Style()
        # style.theme_use('clam')  # Uncomment to change theme
        style.configure('TButton', font=('Arial', 10, 'bold'), padding=10)
        ttk.Button(main_frame, text="SEND EMAIL", command=self.send_email_handler, style='TButton', padding=10).grid(row=8, column=0, columnspan=2, pady=20, sticky=(tk.W, tk.E))

        # Configure grid weight so widgets expand nicely
        master.columnconfigure(0, weight=1)
        master.columnconfigure(1, weight=1)
        main_frame.columnconfigure(1, weight=1)


    def create_message_parts(self):
        """
        Gathers content from Text widgets and creates the MIME structure.
        """
        # Gather data from the Text widgets
        plain_text = self.plain_text_widget.get("1.0", tk.END).strip()
        html_content = self.html_widget.get("1.0", tk.END).strip()

        # Create MIME objects
        plain_part = MIMEText(plain_text, 'plain')
        html_part = MIMEText(html_content, 'html')

        # Create the main container
        msg = MIMEMultipart()
        msg['From'] = self.sender_email_var.get()
        msg['To'] = self.receiver_email_var.get()
        msg['Subject'] = self.subject_var.get()

        # Attach parts
        msg.attach(plain_part)
        msg.attach(html_part)

        return msg

    def _validate_content(self, plain_text: str, html_content: str) -> tuple[bool, str]:
        """
        Analyzes the content body to score its spam risk and provides coaching feedback.
        Returns: (is_valid_flag, coaching_message)
        """
        if not plain_text and not html_content:
            return False, "Error: Both Plain Text and HTML bodies cannot be left empty. Please add content."

        # --- 1. Basic Length Check ---
        min_length = 30
        combined_length = len(plain_text) + len(html_content)
        if combined_length < min_length:
            return False, f"Warning: Content is very short ({combined_length} characters). To improve deliverability, try to write at least {min_length} words of substance."

        def calculate_capital_ratio(text):
            if not text:
                return 0.0
            capital_count = sum(1 for char in text if char.isupper() and char.isalpha())
            total_alpha = sum(1 for char in text if char.isalpha())
            if total_alpha == 0:
                return 0.0
            return capital_count / total_alpha

        capital_ratio = calculate_capital_ratio(plain_text)
        exclamation_count = plain_text.count('!')
        question_count = plain_text.count('?')
        is_over_punctuation = exclamation_count > 3 or question_count > 5

        feedback_list = []
        is_valid = True

        if capital_ratio > 0.4:
            feedback_list.append(f"🚨 HIGH CAPS ALERT: {capital_ratio:.1%} of your text is in ALL CAPS. Try using mixed case for a more natural, less spammy look.")
            is_valid = False

        if is_over_punctuation:
            feedback_list.append("❗ PUNCTUATION WARNING: You used too many !!! or ???. Try varying your punctuation marks.")
            is_valid = False

        if combined_length < min_length:
            return False, "ERROR: Content is too sparse. Please elaborate on your message."

        coaching_message = "\n".join(feedback_list)
        if not coaching_message:
            coaching_message = "✅ Content looks solid! Good balance of words and punctuation."
        return True, coaching_message

    def send_email_handler(self):
        """Handles the entire sending process when the button is clicked."""

        # 1. Input Validation
        sender = self.sender_email_var.get()
        password = self.sender_password_var.get()
        receiver = self.receiver_email_var.get()
        subject = self.subject_var.get()

        if not all([sender, password, receiver, subject]):
            messagebox.showerror("Input Error", "Please fill in Sender Email, App Password, Receiver Email, and Subject.")
            return

        # 2. Content Validation
        plain_text = self.plain_text_widget.get("1.0", tk.END).strip()
        html_content = self.html_widget.get("1.0", tk.END).strip()
        is_valid, feedback = self._validate_content(plain_text, html_content)
        if not is_valid:
            messagebox.showwarning("Content Validation", feedback)
            return

        # 3. Message Composition
        try:
            message_to_send = self.create_message_parts()
        except Exception as e:
            messagebox.showerror("Composition Error", f"Error building the email: {e}")
            return

        # 4. Sending Logic
        try:
            with smtplib.SMTP_SSL(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT) as smtp_server:
                smtp_server.login(sender, password)
                smtp_server.sendmail(sender, receiver, message_to_send.as_string())

            messagebox.showinfo("Success", "Email sent successfully!\nCheck your recipient's inbox.")

            # Clear fields on success
            self.reset_fields()

        except smtplib.SMTPAuthenticationError:
            messagebox.showerror("Authentication Failed", "Invalid Email or App Password. Did you generate an App Password for Gmail?")
        except smtplib.SMTPConnectError:
            messagebox.showerror("Connection Error", f"Could not connect to {GMAIL_SMTP_SERVER}. Check your network or firewall settings.")
        except Exception as e:
            messagebox.showerror("Sending Error", f"An unexpected error occurred: {e}")

    def reset_fields(self):
        """Clears the form fields after successful sending."""
        self.sender_email_var.set("")
        self.sender_password_var.set("")
        self.receiver_email_var.set("")
        self.subject_var.set("")
        self.plain_text_widget.delete("1.0", tk.END)
        self.html_widget.delete("1.0", tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    # Optional: Set a minimum size for better appearance
    root.geometry("700x700") 
    app = EmailMailerApp(root)
    root.mainloop()