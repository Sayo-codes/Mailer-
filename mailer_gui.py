import tkinter as tk
from tkinter import ttk, messagebox, filedialog  # Using ttk for modern widgets
import os
from SMTPTransporter import SMTPTransporter
from EmailPartGeneratorV2 import EmailPartGeneratorV2
import re
import logging
import threading
import csv
from datetime import datetime, timedelta
from tkinter import simpledialog
from tkinter.scrolledtext import ScrolledText
# Email MIME imports for custom header handling
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailMailerApp:
    def __init__(self, master):
        self.master = master
        master.title("🚀 Professional Mass Emailer")
        master.geometry("850x650")
        # Allow window to be resized and maximized
        master.resizable(True, True)

        # Configure a modern theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Accent.TButton', font=('Arial', 11, 'bold'), foreground='#1a5276')
        style.configure('TLabelframe.Label', font=('Arial', 10, 'bold'))

        # Logger for UI actions
        self.logger = logging.getLogger('EmailMailerApp')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler('mailer_ui.log')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # --- 1. VARIABLE SETUP (CRITICAL FIX) ---
        # Initialize all variables at the top to ensure they exist before widgets are built
        self.sender_email_var = tk.StringVar()
        self.sender_pass_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.body_var = tk.StringVar()
        self.recipients_var = tk.StringVar()
        # Brand configuration variables (constants for the email brand)
        self.brand_name_var = tk.StringVar(value="Google")  # big display name
        self.brand_email_var = tk.StringVar(value="no-reply@google.com")  # technical reply address
        self.subject_prefix_var = tk.StringVar(value="[Google]")
        self.status_text_var = tk.StringVar(value="Ready")
        # Transporter will be lazily created after credentials are provided
        self.transporter = None
        self.generator = EmailPartGeneratorV2()
        self.attachments = []  # List of absolute file paths for attachments
        # State management
        self.send_log = []  # List of (recipient, status, error_msg)
        self.sending_state = "idle"  # idle, sending, scheduled
        self.scheduled_time = None
        self.progress_var = tk.DoubleVar()
        self.sending_thread = None
        self.skip_preview_var = tk.BooleanVar(value=False)

        # --- 2. UI SCROLLING SETUP ---
        # Create a canvas with a vertical scrollbar to allow scrolling of the content
        self.canvas = tk.Canvas(master)
        self.scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        # Update scrollregion when the size of the frame changes
        self.scrollable_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        # Smooth mousewheel scrolling — works on Windows, macOS and Linux
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)          # Windows / macOS
        self.canvas.bind_all("<Button-4>", _on_mousewheel_linux)       # Linux scroll up
        self.canvas.bind_all("<Button-5>", _on_mousewheel_linux)       # Linux scroll down

        # Setup widgets inside the scrollable frame
        self.setup_widgets(self.scrollable_frame)

        # Status bar at the bottom (outside the scrollable area)
        self.status_bar = ttk.Label(master, textvariable=self.status_text_var, relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(fill='x', side='bottom')

    def setup_widgets(self, master):
        # Using ttk.LabelFrame gives a more structured, 'card-like' appearance
        main_frame = ttk.LabelFrame(master, text="Email Campaign Setup", padding="20 20 20 20")
        main_frame.pack(padx=20, pady=20, fill="x")

        # --- SECTION 1: Sender Credentials ---
        sender_frame = ttk.LabelFrame(main_frame, text="Sender Authentication (SMTP)", padding="15")
        sender_frame.pack(fill="x", pady=10)

        # Using Label + Entry structure for cleaner look
        ttk.Label(sender_frame, text="Sender Email:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ttk.Entry(sender_frame, textvariable=self.sender_email_var, width=40).grid(row=0, column=1, padx=10, pady=5, sticky="w")

        ttk.Label(sender_frame, text="SMTP Password:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        ttk.Entry(sender_frame, textvariable=self.sender_pass_var, show="*").grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # Brand configuration UI (editable fields)
        ttk.Label(sender_frame, text="Brand Name:").grid(row=0, column=2, padx=5, pady=5, sticky='e')
        ttk.Entry(sender_frame, textvariable=self.brand_name_var, width=20).grid(row=0, column=3, padx=5, pady=5, sticky='ew')

        ttk.Label(sender_frame, text="Brand Email:").grid(row=1, column=2, padx=5, pady=5, sticky='e')
        ttk.Entry(sender_frame, textvariable=self.brand_email_var, width=25).grid(row=1, column=3, padx=5, pady=5, sticky='ew')

        ttk.Label(sender_frame, text="Subject Prefix:").grid(row=0, column=4, padx=5, pady=5, sticky='e')
        ttk.Entry(sender_frame, textvariable=self.subject_prefix_var, width=20).grid(row=0, column=5, padx=5, pady=5, sticky='ew')

        # --- SECTION 2: Campaign Details ---
        detail_frame = ttk.LabelFrame(main_frame, text="Campaign Content", padding="15")
        detail_frame.pack(fill="x", pady=10)

        # Subject & Recipient List (The most visible change)
        ttk.Label(detail_frame, text="Subject Line:").grid(row=0, column=0, padx=10, pady=5, sticky="nw")
        ttk.Entry(detail_frame, textvariable=self.subject_var, width=50).grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # *** CRITICAL NEW COMPONENT: RECIPIENTS AREA ***
        ttk.Label(detail_frame, text="Recipients (One per line, separated by , or list):").grid(row=1, column=0, padx=10, pady=5, sticky="nw")
        # Use a Text widget for better multi-line pasting than Entry
        self.recipient_text = tk.Text(detail_frame, height=8, width=45)
        self.recipient_text.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Body Content - use ScrolledText for multiline input
        ttk.Label(detail_frame, text="Email Body:").grid(row=2, column=0, padx=10, pady=5, sticky="nw")
        self.body_text = ScrolledText(detail_frame, height=6, width=45)
        self.body_text.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # ==== Attachments UI ====
        ttk.Label(detail_frame, text="Attachments:").grid(row=3, column=0, padx=10, pady=5, sticky="nw")
        attach_btn_frame = ttk.Frame(detail_frame)
        attach_btn_frame.grid(row=3, column=1, padx=10, pady=5, sticky="ew")
        self.attach_button = ttk.Button(attach_btn_frame, text="Add Attachments", command=self.add_attachments)
        self.attach_button.pack(side="left")
        self.remove_attach_button = ttk.Button(attach_btn_frame, text="Remove Selected", command=self.remove_selected_attachment)
        self.remove_attach_button.pack(side="left", padx=5)
        self.attachment_listbox = tk.Listbox(detail_frame, height=4)
        self.attachment_listbox.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

        # --- SECTION 3: Execution ---
        self.launch_button = ttk.Button(main_frame, text="🚀 Launch Mass Campaign", command=self.send_mass_campaign, style='Accent.TButton')
        self.launch_button.pack(pady=10)
        self.schedule_button = ttk.Button(main_frame, text="Schedule Campaign", command=self.schedule_campaign, style='Accent.TButton')
        self.schedule_button.pack(pady=10)
        self.export_button = ttk.Button(main_frame, text="Export Log", command=self.export_log, style='Accent.TButton')
        self.export_button.pack(pady=10)
        self.skip_preview_checkbox = ttk.Checkbutton(main_frame, text="Skip preview", variable=self.skip_preview_var)
        self.skip_preview_checkbox.pack(pady=5)
        # Progress bar
        ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100, mode='determinate').pack(fill='x', padx=20, pady=5)
        # Status list (Treeview)
        self.status_tree = ttk.Treeview(main_frame, columns=("recipient", "status"), show='headings', height=5)
        self.status_tree.heading('recipient', text='Recipient')
        self.status_tree.heading('status', text='Status')
        self.status_tree.column('recipient', width=200)
        self.status_tree.column('status', width=100)
        self.status_tree.pack(fill='both', padx=20, pady=5)


    # =============================================================
    # CORE LOGIC METHOD (This replaces the single send function)
    # =============================================================
    def send_mass_campaign(self):
        # 1. Gather Data
        sender_email = self.sender_email_var.get().strip()
        smtp_pass = self.sender_pass_var.get().strip()
        # Original subject entered by user
        raw_subject = self.subject_var.get().strip()
        # Brand configuration
        brand_name = self.brand_name_var.get().strip()
        brand_email = self.brand_email_var.get().strip()
        subject_prefix = self.subject_prefix_var.get().strip()
        # Build final subject with prefix
        subject = f"{subject_prefix} {raw_subject}" if subject_prefix else raw_subject
        body = self.body_text.get("1.0", "end-1c").strip()

        # Validate fields
        if not sender_email or not smtp_pass:
            messagebox.showerror("Error", "Sender Email and Password must be provided.")
            return
        if not subject:
            messagebox.showerror("Error", "Subject cannot be empty.")
            return
        if not body:
            messagebox.showerror("Error", "Email body cannot be empty.")
            return

        # Extract recipients from the Text widget
        raw_recipients = self.recipient_text.get("1.0", "end-1c").strip()
        if not raw_recipients:
            messagebox.showerror("Error", "Please enter at least one recipient email address.")
            return

        # Split by comma, semicolon, or newline
        recipient_list = [r.strip() for r in re.split(r'[,;\n]+', raw_recipients) if r.strip()]

        # Validate email format
        email_regex = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
        valid = []
        invalid = []
        for r in recipient_list:
            if email_regex.match(r):
                valid.append(r)
            else:
                invalid.append(r)
        if invalid:
            messagebox.showwarning("Invalid Emails",
                f"The following addresses are invalid and will be skipped:\n" + "\n".join(invalid))
            self.logger.warning(f"Invalid recipients skipped: {invalid}")
        if not valid:
            messagebox.showerror("No Valid Recipients", "No valid email addresses found.")
            return
        recipient_list = valid

        if self.sending_state != "idle":
            messagebox.showerror("Error", "A campaign is already in progress or scheduled.")
            return

        # Preview step (unless skipped)
        if not self.skip_preview_var.get():
            if not self.preview_email(sender_email, smtp_pass, subject, body, recipient_list):
                self.logger.info("User cancelled email preview.")
                return

        # Lazily create transporter
        os.environ["SMTP_USER"] = sender_email
        os.environ["SMTP_PASSWORD"] = smtp_pass
        if self.transporter is None:
            try:
                self.transporter = SMTPTransporter()
            except Exception as e:
                messagebox.showerror("SMTP Error", f"Failed to initialise SMTP transporter:\n{e}")
                self.logger.error(f"SMTP init error: {e}")
                return

        # Prepare UI for sending
        self.sending_state = "sending"
        self.send_log.clear()
        self.status_tree.delete(*self.status_tree.get_children())
        self.progress_var.set(0)
        self.status_text_var.set(f"Sending to {len(recipient_list)} recipients…")
        self.launch_button.config(state="disabled")
        self.schedule_button.config(state="disabled")
        self.export_button.config(state="disabled")
        self.logger.info(f"Starting campaign to {len(recipient_list)} recipients.")

        # Launch background thread
        self.sending_thread = threading.Thread(
            target=self._send_campaign_worker,
            args=(sender_email, smtp_pass, subject, body, recipient_list),
            daemon=True
        )
        self.sending_thread.start()

    def reset_fields(self):
        """Clear all input fields after a successful send."""
        self.sender_email_var.set("")
        self.sender_pass_var.set("")
        self.subject_var.set("")
        self.body_var.set("")
        self.recipient_text.delete("1.0", tk.END)
        # Clear attachments UI and list
        self.attachments.clear()
        self.attachment_listbox.delete(0, tk.END)
        # Reset progress and status UI
        self.progress_var.set(0)
        self.status_tree.delete(*self.status_tree.get_children())
        self.send_log.clear()
        self.sending_state = "idle"
        self.scheduled_time = None

        # Re‑enable UI buttons after reset
        self.launch_button.config(state="normal")
        self.schedule_button.config(state="normal")
        self.export_button.config(state="disabled")

    def add_attachments(self):
        files = filedialog.askopenfilenames(title="Select attachment files")
        for f in files:
            self.attachments.append(f)
            self.attachment_listbox.insert(tk.END, os.path.basename(f))
        if self.attachments:
            self.remove_attach_button.config(state="normal")
        else:
            self.remove_attach_button.config(state="disabled")

    def remove_selected_attachment(self):
        selected = list(self.attachment_listbox.curselection())
        for idx in reversed(selected):
            self.attachment_listbox.delete(idx)
            del self.attachments[idx]
        if not self.attachments:
            self.remove_attach_button.config(state="disabled")

    def _update_ui_progress(self, recipient, success, current, total):
        status = "Success" if success else "Failure"
        self.status_tree.insert("", tk.END, values=(recipient, status))
        progress = int((current / total) * 100)
        self.progress_var.set(progress)
        self.status_text_var.set(f"{current}/{total} processed")

    def _finalize_send(self):
        self.sending_state = "idle"
        self.launch_button.config(state="normal")
        self.schedule_button.config(state="normal")
        self.export_button.config(state="normal")
        successes = sum(1 for _,s,_ in self.send_log if s == "Success")
        failures = len(self.send_log) - successes
        msg = f"Successfully sent to {successes}/{len(self.send_log)} recipients."
        if failures:
            msg += f" {failures} failures occurred."
        messagebox.showinfo("Send Completed", msg)
        self.logger.info("Campaign completed: " + msg)
        self.status_text_var.set("Completed")
        # Reset fields after a short pause
        self.master.after(2000, self.reset_fields)

    def send_email(self, recipient):
        """Construct and send a single email using brand UI values.
        Returns (success: bool, error_msg: str)."""
        try:
            # Build the MIME message
            msg = MIMEMultipart()

            # Brand From header
            brand_name = self.brand_name_var.get().strip()
            brand_email = self.brand_email_var.get().strip()
            msg['From'] = f"{brand_name} <{brand_email}>"
            msg['Reply-To'] = brand_email
            msg['To'] = recipient

            # Subject with prefix
            base_subject = self.subject_var.get().strip()
            prefix = self.subject_prefix_var.get().strip()
            msg['Subject'] = f"{prefix} {base_subject}" if prefix else base_subject

            # Body (plain text)
            body_text = self.body_text.get("1.0", tk.END).strip()
            msg.attach(MIMEText(body_text, 'plain'))

            # Ensure transporter exists
            if self.transporter is None:
                self.transporter = SMTPTransporter()
            spoofed_from_header = f"{brand_name} <{brand_email}>"
            self.transporter.send(msg, recipient, from_header=spoofed_from_header)
            self.logger.info(f"Email sent to {recipient} as {brand_name}")
            return True, ""
        except Exception as e:
            self.logger.error(f"Error sending to {recipient}: {e}")
            self.master.after(0, messagebox.showerror, "Send Error",
                              f"Could not send to {recipient}:\n{e}")
            return False, str(e)

    def _send_campaign_worker(self, sender_email, smtp_pass, subject, body, recipient_list):
        total = len(recipient_list)
        for idx, recipient in enumerate(recipient_list, 1):
            # Use the new helper to send each email
            success, error_msg = self.send_email(recipient)
            self.send_log.append((recipient, "Success" if success else "Failure", error_msg))
            self.master.after(0, self._update_ui_progress, recipient, success, idx, total)
        self.master.after(0, self._finalize_send)

    def schedule_campaign(self):
        """Prompt user for a future datetime and schedule the campaign."""
        dt_str = simpledialog.askstring("Schedule Campaign", "Enter date & time (YYYY-MM-DD HH:MM):")
        if not dt_str:
            return
        try:
            schedule_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Invalid format", "Please use YYYY-MM-DD HH:MM")
            return
        now = datetime.now()
        delay = (schedule_time - now).total_seconds()
        if delay <= 0:
            messagebox.showerror("Invalid time", "Scheduled time must be in the future.")
            return
        self.scheduled_time = schedule_time
        self.schedule_button.config(state="disabled")
        self.launch_button.config(state="disabled")
        threading.Timer(delay, self.send_mass_campaign).start()
        messagebox.showinfo("Scheduled", f"Campaign scheduled for {schedule_time}")

    def export_log(self):
        if not self.send_log:
            messagebox.showwarning("No log", "No send log to export.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", title="Save Log As", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return
        with open(file_path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Recipient", "Status", "ErrorMessage"])
            writer.writerows(self.send_log)
        messagebox.showinfo("Exported", f"Log saved to {file_path}")

    def preview_email(self, sender_email, smtp_pass, subject, body, recipient_list):
        """Show a modal preview of the email for the first recipient."""
        if not recipient_list:
            messagebox.showerror("Error", "No recipients to preview.")
            return False
        first_recipient = recipient_list[0]
        # Build the message for preview
        # Use brand variables for preview as well
        brand_name = self.brand_name_var.get().strip()
        brand_email = self.brand_email_var.get().strip()
        subject_prefix = self.subject_prefix_var.get().strip()
        raw_subject = self.subject_var.get().strip()
        preview_subject = f"{subject_prefix} {raw_subject}" if subject_prefix else raw_subject
        from_header = f"{brand_name} <{brand_email}>"
        self.generator.set_metadata(preview_subject, from_header, first_recipient)
        self.generator.set_template('plain', body)
        for att in self.attachments:
            self.generator.add_attachment(att)
        try:
            msg_obj = self.generator.build_multipart_message({})
            preview_content = msg_obj.as_string()
        except Exception as e:
            messagebox.showerror("Preview Error", f"Failed to build preview: {e}")
            return False

        # Create preview window
        preview_win = tk.Toplevel(self.master)
        preview_win.title("Email Preview")
        preview_win.transient(self.master)
        preview_win.grab_set()

        # Scrolled text for content
        txt = ScrolledText(preview_win, width=100, height=30)
        txt.pack(padx=10, pady=10, fill='both', expand=True)
        txt.insert(tk.END, preview_content)
        txt.config(state='disabled')

        # Button frame
        btn_frame = ttk.Frame(preview_win)
        btn_frame.pack(pady=5)

        result = {"confirmed": False}

        def confirm():
            result["confirmed"] = True
            preview_win.destroy()

        def cancel():
            preview_win.destroy()

        ttk.Button(btn_frame, text="Confirm", command=confirm).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side='left', padx=5)

        self.master.wait_window(preview_win)
        return result["confirmed"]

# --- EXECUTION BLOCK ---
if __name__ == "__main__":
    root = tk.Tk()
    app = EmailMailerApp(root)
    root.mainloop()