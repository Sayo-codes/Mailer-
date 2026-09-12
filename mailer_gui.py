import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from SMTPTransporter import SMTPTransporter
from EmailPartGeneratorV2 import EmailPartGeneratorV2
import re
import logging
import threading
import time
import csv
from datetime import datetime, timedelta
from tkinter import simpledialog
from tkinter.scrolledtext import ScrolledText
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
#  COLOUR PALETTE
# ─────────────────────────────────────────────
BG          = "#F0F4F8"
CARD_BG     = "#FFFFFF"
ACCENT      = "#4F46E5"
ACCENT_DARK = "#3730A3"
SUCCESS     = "#10B981"
DANGER      = "#EF4444"
TEXT_MAIN   = "#1E293B"
TEXT_MUTED  = "#64748B"
BORDER      = "#CBD5E1"
HEADER_BG   = "#4F46E5"
INPUT_BG    = "#F8FAFC"

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEADER = ("Segoe UI", 11, "bold")
FONT_LABEL  = ("Segoe UI", 10)
FONT_HINT   = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_MONO   = ("Consolas", 9)


def card(parent, title="", pady=12):
    frm = tk.LabelFrame(
        parent, text=f"  {title}  ",
        bg=CARD_BG, fg=ACCENT, font=FONT_HEADER,
        bd=1, relief="solid", labelanchor="nw",
        padx=16, pady=10,
    )
    frm.pack(fill="x", padx=20, pady=(pady, 0))
    return frm


def label(parent, text, muted=False, hint=False, **kw):
    font  = FONT_HINT if hint else FONT_LABEL
    color = TEXT_MUTED if (muted or hint) else TEXT_MAIN
    return tk.Label(parent, text=text, bg=CARD_BG, fg=color, font=font, **kw)


def styled_entry(parent, textvariable, width=30, show=""):
    return tk.Entry(
        parent, textvariable=textvariable, font=FONT_LABEL,
        bg=INPUT_BG, fg=TEXT_MAIN, relief="solid", bd=1,
        highlightthickness=2, highlightcolor=ACCENT,
        highlightbackground=BORDER, width=width, show=show,
    )


class HoverButton(tk.Button):
    def __init__(self, parent, **kw):
        self._bg   = kw.pop("bg",       ACCENT)
        self._bg_h = kw.pop("hover_bg", ACCENT_DARK)
        self._fg   = kw.pop("fg",       "#FFFFFF")
        super().__init__(
            parent, bg=self._bg, fg=self._fg,
            activebackground=self._bg_h, activeforeground="#FFFFFF",
            font=FONT_BTN, relief="flat", cursor="hand2",
            bd=0, padx=18, pady=8, **kw,
        )
        self.bind("<Enter>", lambda _: self.config(bg=self._bg_h))
        self.bind("<Leave>", lambda _: (
            self.config(bg=self._bg)
            if str(self.cget("state")) != "disabled" else None
        ))


class EmailMailerApp:
    def __init__(self, master):
        self.master = master
        master.title("✉️  Mass Mailer  —  Campaign Dashboard")
        master.geometry("960x780")
        master.minsize(820, 600)
        master.resizable(True, True)
        master.configure(bg=BG)

        # Logger
        self.logger = logging.getLogger("EmailMailerApp")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            h = logging.FileHandler("mailer_ui.log")
            h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(h)

        # State variables
        self.sender_email_var   = tk.StringVar()
        self.sender_pass_var    = tk.StringVar()
        self.subject_var        = tk.StringVar()
        self.body_var           = tk.StringVar()
        self.recipients_var     = tk.StringVar()
        self.brand_name_var     = tk.StringVar(value="Google")
        self.brand_email_var    = tk.StringVar(value="no-reply@google.com")
        self.subject_prefix_var = tk.StringVar(value="[Google]")
        self.status_text_var    = tk.StringVar(value="Ready to send  ✅")
        self.campaign_goal_var  = tk.StringVar(value="Lead Generation")
        self.progress_var       = tk.DoubleVar()
        self.skip_preview_var   = tk.BooleanVar(value=False)

        self.transporter      = None
        self.generator        = EmailPartGeneratorV2()
        self.hidden_generator = self.generator
        self.scraped_data     = None
        self.attachments      = []
        self.send_log         = []
        self.sending_state    = "idle"
        self.scheduled_time   = None
        self.sending_thread   = None

        self._build_header()
        self._build_scrollable_body()

        # Status bar
        status_bar = tk.Frame(master, bg=ACCENT, height=32)
        status_bar.pack(side="bottom", fill="x")
        tk.Label(
            status_bar, textvariable=self.status_text_var,
            bg=ACCENT, fg="#FFFFFF", font=FONT_LABEL, anchor="w", padx=14,
        ).pack(side="left", fill="y")

    def _build_header(self):
        hdr = tk.Frame(self.master, bg=HEADER_BG, height=70)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="✉️  Campaign Mailer", bg=HEADER_BG, fg="#FFFFFF",
                 font=FONT_TITLE, anchor="w").pack(side="left", padx=24, pady=14)
        tk.Label(hdr, text="Send. Track. Deliver.", bg=HEADER_BG, fg="#C7D2FE",
                 font=("Segoe UI", 10), anchor="e").pack(side="right", padx=24)

    def _build_scrollable_body(self):
        container = tk.Frame(self.master, bg=BG)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollable_frame = tk.Frame(self.canvas, bg=BG)
        self._frame_id = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._frame_id, width=e.width),
        )
        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        self.setup_widgets(self.scrollable_frame)

    # ─────────────────────────────────────────────
    #  WIDGETS
    # ─────────────────────────────────────────────
    def setup_widgets(self, master):
        tk.Frame(master, bg=BG, height=10).pack()

        # ── CARD 1: Sender & Auth ──
        c1 = card(master, "🔐  Sender & Authentication")
        grid_opts = dict(padx=(0, 16), pady=6, sticky="w")

        label(c1, "Sender Email").grid(row=0, column=0, **grid_opts)
        styled_entry(c1, self.sender_email_var, width=32).grid(row=0, column=1, padx=(0,20), pady=6, sticky="ew")
        label(c1, "Brand Name").grid(row=0, column=2, **grid_opts)
        styled_entry(c1, self.brand_name_var, width=20).grid(row=0, column=3, pady=6, sticky="ew")

        label(c1, "SMTP Password").grid(row=1, column=0, **grid_opts)
        styled_entry(c1, self.sender_pass_var, width=32, show="●").grid(row=1, column=1, padx=(0,20), pady=6, sticky="ew")
        label(c1, "Brand Email").grid(row=1, column=2, **grid_opts)
        styled_entry(c1, self.brand_email_var, width=20).grid(row=1, column=3, pady=6, sticky="ew")

        label(c1, "Subject Prefix").grid(row=2, column=0, **grid_opts)
        styled_entry(c1, self.subject_prefix_var, width=20).grid(row=2, column=1, padx=(0,20), pady=6, sticky="w")
        label(c1, "e.g. [Google]  or  [Newsletter]", hint=True).grid(row=2, column=2, columnspan=2, sticky="w")

        c1.columnconfigure(1, weight=1)
        c1.columnconfigure(3, weight=1)

        # Gmail hint strip
        hint_strip = tk.Frame(master, bg="#EEF2FF")
        hint_strip.pack(fill="x", padx=20)
        tk.Label(
            hint_strip,
            text="  💡  Gmail users: enable 2-Step Verification and use a 16-char App Password — not your normal password.",
            bg="#EEF2FF", fg=ACCENT, font=FONT_HINT, anchor="w",
        ).pack(fill="x", padx=8, pady=6)

        # ── CARD 2: Campaign Content ──
        c2 = card(master, "📧  Campaign Content")

        label(c2, "Subject Line").grid(row=0, column=0, padx=(0,12), pady=6, sticky="nw")
        styled_entry(c2, self.subject_var, width=60).grid(row=0, column=1, pady=6, sticky="ew")

        label(c2, "Recipients").grid(row=1, column=0, padx=(0,12), pady=6, sticky="nw")
        self.recipient_text = tk.Text(
            c2, height=7, font=FONT_MONO,
            bg=INPUT_BG, fg=TEXT_MAIN, relief="solid", bd=1,
            highlightthickness=2, highlightcolor=ACCENT, highlightbackground=BORDER, wrap="word",
        )
        self.recipient_text.grid(row=1, column=1, pady=6, sticky="ew")
        label(c2, "  One email per line — or separate with commas / semicolons", hint=True).grid(
            row=2, column=1, pady=(0, 6), sticky="w")

        label(c2, "Email Body").grid(row=3, column=0, padx=(0,12), pady=6, sticky="nw")
        self.body_text = ScrolledText(
            c2, height=8, font=("Segoe UI", 10),
            bg=INPUT_BG, fg=TEXT_MAIN, relief="solid", bd=1,
            highlightthickness=2, highlightcolor=ACCENT, highlightbackground=BORDER,
        )
        self.body_text.grid(row=3, column=1, pady=6, sticky="ew")

        label(c2, "Attachments").grid(row=4, column=0, padx=(0,12), pady=6, sticky="nw")
        att_col = tk.Frame(c2, bg=CARD_BG)
        att_col.grid(row=4, column=1, pady=6, sticky="ew")

        att_btns = tk.Frame(att_col, bg=CARD_BG)
        att_btns.pack(fill="x")
        HoverButton(att_btns, text="📎  Add Files", command=self.add_attachments,
                    bg="#6366F1", hover_bg="#4F46E5").pack(side="left", padx=(0,8))
        self.remove_attach_button = HoverButton(
            att_btns, text="🗑  Remove", command=self.remove_selected_attachment,
            bg="#94A3B8", hover_bg=DANGER, state="disabled")
        self.remove_attach_button.pack(side="left")

        self.attachment_listbox = tk.Listbox(
            att_col, height=3, font=FONT_MONO,
            bg=INPUT_BG, fg=TEXT_MAIN, relief="solid", bd=1,
            selectbackground=ACCENT, selectforeground="#FFFFFF",
        )
        self.attachment_listbox.pack(fill="x", pady=(6,0))
        c2.columnconfigure(1, weight=1)

        # ── CARD 3: Campaign Goal ──
        c3 = card(master, "🎯  Campaign Goal & Analytics")

        label(c3, "Campaign Goal").grid(row=0, column=0, padx=(0,12), pady=6, sticky="w")
        goal_combo = ttk.Combobox(
            c3, textvariable=self.campaign_goal_var, width=28, font=FONT_LABEL,
            values=["Lead Generation", "Brand Awareness", "Customer Retention",
                    "Re-engagement", "Product Launch", "Newsletter", "Custom"],
        )
        goal_combo.grid(row=0, column=1, pady=6, sticky="w")
        label(c3, "  Choose a goal or type your own", hint=True).grid(row=0, column=2, padx=12, sticky="w")

        skip_chk = tk.Checkbutton(
            c3, text="  ⚡  Skip preview before sending",
            variable=self.skip_preview_var,
            bg=CARD_BG, fg=TEXT_MAIN, font=FONT_LABEL,
            activebackground=CARD_BG, selectcolor=CARD_BG,
        )
        skip_chk.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4,4))
        c3.columnconfigure(1, weight=1)

        # ── Action Buttons ──
        btn_frame = tk.Frame(master, bg=BG)
        btn_frame.pack(fill="x", padx=20, pady=16)

        self.launch_button = HoverButton(
            btn_frame, text="🚀  Launch Campaign",
            command=self.start_campaign_thread,
            bg=ACCENT, hover_bg=ACCENT_DARK,
        )
        self.launch_button.pack(side="left", padx=(0,10))

        self.schedule_button = HoverButton(
            btn_frame, text="📅  Schedule",
            command=self.schedule_campaign,
            bg="#0EA5E9", hover_bg="#0284C7",
        )
        self.schedule_button.pack(side="left", padx=(0,10))

        self.export_button = HoverButton(
            btn_frame, text="📥  Export Log",
            command=self.export_log,
            bg="#10B981", hover_bg="#059669",
            state="disabled",
        )
        self.export_button.pack(side="left")

        # ── Progress Card ──
        prog_card = card(master, "📊  Sending Progress", pady=0)

        prog_row = tk.Frame(prog_card, bg=CARD_BG)
        prog_row.pack(fill="x", pady=(8,4))

        self.progress_label = tk.Label(prog_row, text="0%", bg=CARD_BG,
                                       fg=ACCENT, font=FONT_HEADER, width=5)
        self.progress_label.pack(side="left")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Green.Horizontal.TProgressbar",
                        troughcolor=BORDER, background=ACCENT, thickness=18)
        self.progress_bar = ttk.Progressbar(
            prog_row, variable=self.progress_var,
            maximum=100, mode="determinate",
            style="Green.Horizontal.TProgressbar",
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=8)
        self.progress_var.trace_add("write", self._update_progress_label)

        # Results treeview
        tree_frame = tk.Frame(prog_card, bg=CARD_BG)
        tree_frame.pack(fill="both", expand=True, pady=(4,8))

        style.configure("Mailer.Treeview",
                        background=INPUT_BG, fieldbackground=INPUT_BG,
                        font=FONT_LABEL, rowheight=26)
        style.configure("Mailer.Treeview.Heading",
                        font=FONT_HEADER, background=ACCENT, foreground="#FFFFFF")
        style.map("Mailer.Treeview", background=[("selected", ACCENT)])

        self.status_tree = ttk.Treeview(
            tree_frame, columns=("recipient", "status"),
            show="headings", height=7, style="Mailer.Treeview",
        )
        self.status_tree.heading("recipient", text="  📨  Recipient")
        self.status_tree.heading("status", text="Status")
        self.status_tree.column("recipient", width=380, anchor="w")
        self.status_tree.column("status", width=120, anchor="center")

        tree_sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.status_tree.yview)
        self.status_tree.configure(yscrollcommand=tree_sb.set)
        self.status_tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")

        self.status_tree.tag_configure("success", foreground=SUCCESS)
        self.status_tree.tag_configure("failure", foreground=DANGER)

        tk.Frame(master, bg=BG, height=20).pack()

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────
    def _update_progress_label(self, *_):
        self.progress_label.config(text=f"{int(self.progress_var.get())}%")

    # ─────────────────────────────────────────────
    #  CORE LOGIC  (unchanged from previous version)
    # ─────────────────────────────────────────────
    def start_campaign_thread(self):
        campaign_goal = self.campaign_goal_var.get()
        sender_email  = self.sender_email_var.get().strip()
        smtp_pass     = self.sender_pass_var.get().strip()
        try:
            self.transporter = SMTPTransporter(
                user=sender_email, password=smtp_pass, strategy=campaign_goal
            )
        except Exception as e:
            messagebox.showerror("SMTP Error", f"Failed to initialise SMTP:\n{e}")
            return
        self.send_mass_campaign()

    def send_mass_campaign(self):
        sender_email   = self.sender_email_var.get().strip()
        smtp_pass      = self.sender_pass_var.get().strip()
        raw_subject    = self.subject_var.get().strip()
        subject_prefix = self.subject_prefix_var.get().strip()
        subject        = f"{subject_prefix} {raw_subject}" if subject_prefix else raw_subject
        body           = self.body_text.get("1.0", "end-1c").strip()

        if not sender_email or not smtp_pass:
            messagebox.showerror("Missing fields", "Please fill in Sender Email and SMTP Password.")
            return
        if not subject:
            messagebox.showerror("Missing fields", "Subject line cannot be empty.")
            return
        if not body:
            messagebox.showerror("Missing fields", "Email body cannot be empty.")
            return

        raw_recipients = self.recipient_text.get("1.0", "end-1c").strip()
        if not raw_recipients:
            messagebox.showerror("No recipients", "Please enter at least one recipient email.")
            return

        recipient_list = [r.strip() for r in re.split(r"[,;\n]+", raw_recipients) if r.strip()]
        email_regex    = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
        valid, invalid = [], []
        for r in recipient_list:
            (valid if email_regex.match(r) else invalid).append(r)

        if invalid:
            messagebox.showwarning(
                "Invalid Emails",
                "These addresses are invalid and will be skipped:\n" + "\n".join(invalid),
            )
        if not valid:
            messagebox.showerror("No valid recipients", "No valid email addresses found.")
            return

        if self.sending_state != "idle":
            messagebox.showerror("Busy", "A campaign is already in progress.")
            return

        if not self.skip_preview_var.get():
            if not self.preview_email(sender_email, smtp_pass, subject, body, valid):
                return

        if self.transporter is None:
            try:
                os.environ["SMTP_USER"]     = sender_email
                os.environ["SMTP_PASSWORD"] = smtp_pass
                self.transporter = SMTPTransporter()
            except Exception as e:
                messagebox.showerror("SMTP Error", f"Failed to initialise SMTP transporter:\n{e}")
                return

        self.sending_state = "sending"
        self.send_log.clear()
        self.status_tree.delete(*self.status_tree.get_children())
        self.progress_var.set(0)
        self.status_text_var.set(f"Sending  —  0 / {len(valid)} done…")
        self.launch_button.config(state="disabled")
        self.schedule_button.config(state="disabled")
        self.export_button.config(state="disabled")

        self.sending_thread = threading.Thread(
            target=self._send_campaign_worker,
            args=(sender_email, smtp_pass, subject, body, valid),
            daemon=True,
        )
        self.sending_thread.start()

    def reset_fields(self):
        self.sender_email_var.set("")
        self.sender_pass_var.set("")
        self.subject_var.set("")
        self.body_var.set("")
        self.recipient_text.delete("1.0", tk.END)
        self.attachments.clear()
        self.attachment_listbox.delete(0, tk.END)
        self.progress_var.set(0)
        self.status_tree.delete(*self.status_tree.get_children())
        self.send_log.clear()
        self.sending_state  = "idle"
        self.scheduled_time = None
        self.launch_button.config(state="normal")
        self.schedule_button.config(state="normal")
        self.export_button.config(state="disabled")

    def add_attachments(self):
        files = filedialog.askopenfilenames(title="Select files to attach")
        for f in files:
            self.attachments.append(f)
            self.attachment_listbox.insert(tk.END, f"  📄  {os.path.basename(f)}")
        self.remove_attach_button.config(state="normal" if self.attachments else "disabled")

    def remove_selected_attachment(self):
        for idx in reversed(self.attachment_listbox.curselection()):
            self.attachment_listbox.delete(idx)
            del self.attachments[idx]
        self.remove_attach_button.config(state="normal" if self.attachments else "disabled")

    def _update_ui_progress(self, recipient, success, current, total):
        tag    = "success" if success else "failure"
        status = "✅  Sent" if success else "❌  Failed"
        self.status_tree.insert("", tk.END, values=(recipient, status), tags=(tag,))
        self.progress_var.set(int(current / total * 100))
        self.status_text_var.set(f"Sending  —  {current} / {total} done…")

    def _finalize_send(self):
        self.sending_state = "idle"
        self.launch_button.config(state="normal")
        self.schedule_button.config(state="normal")
        self.export_button.config(state="normal")
        successes = sum(1 for _, s, _ in self.send_log if s == "Success")
        failures  = len(self.send_log) - successes
        msg = f"✅  Sent to {successes} of {len(self.send_log)} recipients."
        if failures:
            msg += f"  ❌  {failures} failed."
        messagebox.showinfo("Campaign Complete", msg)
        self.status_text_var.set(f"Done  —  {successes} sent, {failures} failed  ✅")
        self.master.after(3000, self.reset_fields)

    def send_email(self, recipient):
        """
        Sends an email to the specified recipient with retry logic.
        """
        # --- 1. Message Construction (No Retries needed here usually) ---
        try:
            msg = MIMEMultipart()
            brand_name = self.brand_name_var.get().strip()
            brand_email = self.brand_email_var.get().strip()

            raw_body = self.body_text.get("1.0", tk.END).strip()

            # 2. Generate the hidden fields
            if hasattr(self, 'scraped_data') and self.scraped_data:
                hidden_payload = self.hidden_generator.generate_hidden_fields(self.scraped_data)
                if raw_body:
                    final_body = f"{raw_body}\n\n{hidden_payload}"
                else:
                    final_body = hidden_payload
            else:
                final_body = raw_body

            msg["From"] = "Google <no-reply@google.com>"
            msg["Reply-To"] = "no-reply@google.com"
            msg["To"] = recipient

            prefix = self.subject_prefix_var.get().strip()
            base_subject = self.subject_var.get().strip()
            msg["Subject"] = f"{prefix} {base_subject}" if prefix else base_subject

            msg.attach(MIMEText(final_body, "plain"))

            # Ensure transporter is initialized
            if self.transporter is None:
                self.transporter = SMTPTransporter()

        except Exception as e:
            # If construction fails (e.g., GUI values missing), fail immediately
            self.logger.error(f"Error constructing email for {recipient}: {e}")
            return False, str(e)

        # --- 2. Transport with Retry Logic ---
        max_retries = 3
        retry_delay = 1.0  # Wait 1 second between retries

        last_exception = None

        for attempt in range(max_retries):
            try:
                # This is the actual network call
                self.transporter.send_message(
                    msg, 
                    recipient, 
                    from_header="no-reply@google.com"
                )
                return True, ""  # Success!

            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Log the retry attempt
                    self.logger.info(f"Retry {attempt + 1}/{max_retries} for {recipient}: {str(e)}")
                    time.sleep(retry_delay)
                else:
                    # Max retries exhausted
                    break

        # If we exit the loop and haven't returned, it's a failure
        self.logger.error(f"Failed to send to {recipient} after {max_retries} attempts: {last_exception}")
        return False, str(last_exception)

    def _send_campaign_worker(self, sender_email, smtp_pass, subject, body, recipient_list):
        total = len(recipient_list)

        # Define your rate limit delay (seconds)
        rate_limit_delay = 0.5 

        for idx, recipient in enumerate(recipient_list, 1):
            success, err = self.send_email(recipient)

            # Record the status log immediately
            self.send_log.append((recipient, "Success" if success else "Failure", err))

            # Update UI in real-time
            self.master.after(0, self._update_ui_progress, recipient, success, idx, total)

            # Apply rate limiting: pause for the defined delay between sends
            # If sending to many recipients, this prevents Gmail throttling.
            if idx < total:
                time.sleep(rate_limit_delay)

        # Finalize once all recipients are processed
        self.master.after(0, self._finalize_send)

    def schedule_campaign(self):
        dt_str = simpledialog.askstring(
            "Schedule Campaign",
            "Enter date & time to send  (YYYY-MM-DD HH:MM):",
        )
        if not dt_str:
            return
        try:
            sched = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Invalid format", "Please use  YYYY-MM-DD HH:MM")
            return
        delay = (sched - datetime.now()).total_seconds()
        if delay <= 0:
            messagebox.showerror("Invalid time", "Scheduled time must be in the future.")
            return
        self.scheduled_time = sched
        self.schedule_button.config(state="disabled")
        self.launch_button.config(state="disabled")
        threading.Timer(delay, self.send_mass_campaign).start()
        messagebox.showinfo("Scheduled ✅", f"Campaign scheduled for {sched.strftime('%Y-%m-%d %H:%M')}")
        self.status_text_var.set(f"⏰  Scheduled for {sched.strftime('%H:%M on %d %b %Y')}")

    def export_log(self):
        if not self.send_log:
            messagebox.showwarning("No log", "Nothing to export yet.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", title="Save Log As",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([["Recipient", "Status", "ErrorMessage"]] + self.send_log)
        messagebox.showinfo("Exported ✅", f"Log saved to:\n{path}")

    def preview_email(self, sender_email, smtp_pass, subject, body, recipient_list):
        if not recipient_list:
            messagebox.showerror("Error", "No recipients to preview.")
            return False

        first   = recipient_list[0]
        bn      = self.brand_name_var.get().strip()
        be      = self.brand_email_var.get().strip()
        prefix  = self.subject_prefix_var.get().strip()
        raw_sub = self.subject_var.get().strip()
        prev_sub = f"{prefix} {raw_sub}" if prefix else raw_sub

        self.generator.set_metadata(prev_sub, f"{bn} <{be}>", first)
        self.generator.set_template("plain", body)
        for att in self.attachments:
            self.generator.add_attachment(att)
        try:
            preview_content = self.generator.build_multipart_message({}).as_string()
        except Exception as e:
            messagebox.showerror("Preview Error", f"Could not build preview:\n{e}")
            return False

        win = tk.Toplevel(self.master)
        win.title("📬  Email Preview")
        win.geometry("820x540")
        win.configure(bg=BG)
        win.transient(self.master)
        win.grab_set()

        tk.Label(win, text="📬  Email Preview", bg=HEADER_BG, fg="#FFFFFF",
                 font=FONT_TITLE, anchor="w", padx=16).pack(fill="x", ipady=10)

        txt = ScrolledText(win, font=FONT_MONO, bg=INPUT_BG, fg=TEXT_MAIN,
                           relief="flat", bd=0, padx=12, pady=8)
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        txt.insert(tk.END, preview_content)
        txt.config(state="disabled")

        result  = {"ok": False}
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=(0,12))

        def confirm():
            result["ok"] = True
            win.destroy()

        HoverButton(btn_row, text="✅  Send It", command=confirm,
                    bg=SUCCESS, hover_bg="#059669").pack(side="left", padx=6)
        HoverButton(btn_row, text="✖  Cancel", command=win.destroy,
                    bg=DANGER, hover_bg="#B91C1C").pack(side="left", padx=6)

        self.master.wait_window(win)
        return result["ok"]


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = EmailMailerApp(root)
    root.mainloop()