# Desktop UI layer for the FCM Intake automation app.
# from __future__ import annotations

# import contextlib
# import getpass
# import io
# import os
# import queue
# import threading
# from pathlib import Path

# import customtkinter as ctk
# from tkinter import messagebox

# from fcm_intake.cms import session as cms_session
# from fcm_intake.context import BotContext
# from fcm_intake.config import APP_TITLE, WINDOW_SIZE
# from fcm_intake.runners.fcm import run_fcm

# THEME_PATH = Path(__file__).resolve().parent / "fcm_ctk_theme.json"
# ctk.set_default_color_theme(str(THEME_PATH))
# ctk.set_appearance_mode("dark")

# ALLOWED_USERS = {"MC133061", "KC133062", "BOSLE_S", "MCCLU_M"}


# def resolve_current_user() -> str:
#     candidates = [
#         os.environ.get("USERNAME", ""),
#         os.environ.get("USER", ""),
#         getpass.getuser(),
#     ]
#     for value in candidates:
#         value = (value or "").strip()
#         if value:
#             return value
#     return "Unknown"


# class QueueWriter(io.TextIOBase):
#     def __init__(self, log_queue: queue.Queue):
#         self.log_queue = log_queue

#     def write(self, s):
#         if s:
#             self.log_queue.put(str(s))
#         return len(s)

#     def flush(self):
#         return None


# class FcmBotApp:
#     def __init__(self):
#         self.current_user = resolve_current_user()
#         self.root = ctk.CTk()
#         self.root.title(APP_TITLE)
#         self.root.geometry(WINDOW_SIZE)
#         self.log_queue = queue.Queue()
#         self._build_ui()
#         self._bring_to_front_once()
#         self.root.after(100, self._drain_log_queue)
#         self._apply_access_rule()

#     def _build_ui(self):
#         outer = ctk.CTkFrame(self.root, corner_radius=0)
#         outer.pack(fill="both", expand=True, padx=12, pady=12)

#         header = ctk.CTkFrame(outer)
#         header.pack(fill="x", padx=8, pady=(8, 10))

#         title_row = ctk.CTkFrame(header, fg_color="transparent")
#         title_row.pack(fill="x", padx=12, pady=(12, 4))

#         ctk.CTkLabel(
#             title_row,
#             text="FCM Intake Bot",
#             font=ctk.CTkFont(size=24, weight="bold")
#         ).pack(side="left", anchor="w")

#         self.user_label = ctk.CTkLabel(
#             title_row,
#             text=f'User: "{self.current_user}"',
#             font=ctk.CTkFont(size=13, weight="bold")
#         )
#         self.user_label.pack(side="right", anchor="e")

#         # ctk.CTkLabel(
#         #     header,
#         #     text="Shared CMS login from UI with recovery-aware automation.",
#         #     font=ctk.CTkFont(size=13)
#         # ).pack(anchor="w", padx=12, pady=(0, 12))

#         creds = ctk.CTkFrame(outer)
#         creds.pack(fill="x", padx=8, pady=(0, 10))

#         ctk.CTkLabel(
#             creds,
#             text="CMS Login",
#             font=ctk.CTkFont(size=16, weight="bold")
#         ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

#         ctk.CTkLabel(creds, text="Username").grid(row=1, column=0, sticky="w", padx=14, pady=6)
#         self.username_var = ctk.StringVar()
#         self.username_entry = ctk.CTkEntry(creds, textvariable=self.username_var, width=320)
#         self.username_entry.grid(row=1, column=1, sticky="ew", padx=14, pady=6)

#         ctk.CTkLabel(creds, text="Password").grid(row=2, column=0, sticky="w", padx=14, pady=(6, 14))
#         self.password_var = ctk.StringVar()
#         self.password_entry = ctk.CTkEntry(creds, textvariable=self.password_var, show="*", width=320)
#         self.password_entry.grid(row=2, column=1, sticky="ew", padx=14, pady=(6, 14))
#         creds.grid_columnconfigure(1, weight=1)

#         actions = ctk.CTkFrame(outer)
#         actions.pack(fill="x", padx=8, pady=(0, 10))
#         self.run_btn = ctk.CTkButton(actions, text="Run Full FCM Flow", command=self.run_full_flow, width=180)
#         self.run_btn.pack(side="left", padx=12, pady=12)
#         self.close_btn = ctk.CTkButton(actions, text="Close CMS Browser", command=self.close_browser, width=180)
#         self.close_btn.pack(side="left", padx=8, pady=12)
#         self.clear_btn = ctk.CTkButton(actions, text="Clear Log", command=self.clear_log, width=140)
#         self.clear_btn.pack(side="left", padx=8, pady=12)

#         # note = ctk.CTkFrame(outer)
#         # note.pack(fill="x", padx=8, pady=(0, 10))
#         # self.note_label = ctk.CTkLabel(
#         #     note,
#         #     text="Allowed users only. Launcher uses one shared CMS login session from this UI.",
#         #     wraplength=980,
#         #     justify="left"
#         # )
#         # self.note_label.pack(anchor="w", padx=14, pady=12)

#         log_frame = ctk.CTkFrame(outer)
#         log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
#         ctk.CTkLabel(log_frame, text="Log", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))
#         self.log_widget = ctk.CTkTextbox(log_frame, wrap="word")
#         self.log_widget.pack(fill="both", expand=True, padx=14, pady=(0, 14))

#     def _bring_to_front_once(self):
#         try:
#             self.root.deiconify()
#         except Exception:
#             pass
#         self.root.lift()
#         self.root.focus_force()
#         self.root.attributes("-topmost", True)
#         self.root.after(400, lambda: self.root.attributes("-topmost", False))

#     def _apply_access_rule(self):
#         normalized_user = self.current_user.strip().upper()
#         if normalized_user not in ALLOWED_USERS:
#             self.log(f'[ACCESS] User "{self.current_user}" is not allowed to run this tool.')
#             self.run_btn.configure(state="disabled")
#             self.username_entry.configure(state="disabled")
#             self.password_entry.configure(state="disabled")
#             self.note_label.configure(
#                 text=f'Access denied for User: "{self.current_user}". Allowed users: {", ".join(sorted(ALLOWED_USERS))}'
#             )
#         else:
#             self.log(f'[ACCESS] User "{self.current_user}" is allowed.')

#     def close_browser(self):
#         cms_session.close_shared_driver()
#         self.log("[INFO] Shared CMS browser closed.")

#     def get_context(self):
#         return BotContext(
#             cms_username=self.username_var.get().strip(),
#             cms_password=self.password_var.get(),
#         )

#     def show_info(self, title: str, text: str):
#         messagebox.showinfo(title, text, parent=self.root)

#     def clear_log(self):
#         self.log_widget.delete("1.0", "end")

#     def log(self, message: str):
#         self.log_queue.put(message.rstrip("\n") + "\n")

#     def _drain_log_queue(self):
#         try:
#             while True:
#                 item = self.log_queue.get_nowait()
#                 self.log_widget.insert("end", item)
#                 self.log_widget.see("end")
#         except queue.Empty:
#             pass
#         self.root.after(100, self._drain_log_queue)

#     def _run_with_redirect(self, target, *args):
#         writer = QueueWriter(self.log_queue)
#         try:
#             with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
#                 target(*args)
#         except Exception as exc:
#             self.log(f"[ERROR] {exc}")
#         finally:
#             self.root.after(0, lambda: self.run_btn.configure(state="normal"))

#     def run_full_flow(self):
#         if self.current_user.strip().upper() not in ALLOWED_USERS:
#             self.log("[ACCESS] Run blocked.")
#             return
#         context = self.get_context()
#         self.run_btn.configure(state="disabled")
#         threading.Thread(target=self._run_with_redirect, args=(run_fcm, self, context), daemon=True).start()

#     def run(self):
#         self.root.mainloop()


from __future__ import annotations

import contextlib
import getpass
import io
import os
import queue
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from fcm_intake.cms import session as cms_session
from fcm_intake.context import BotContext
from fcm_intake.config import APP_TITLE, WINDOW_SIZE
from fcm_intake.runners.fcm import run_fcm

THEME_PATH = Path(__file__).resolve().parent / "fcm_ctk_theme.json"
ctk.set_default_color_theme(str(THEME_PATH))
ctk.set_appearance_mode("dark")

ALLOWED_USERS = {"MC133061", "KC133062", "BOSLE_S", "MCCLU_M"}


def resolve_current_user() -> str:
    candidates = [
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        getpass.getuser(),
    ]
    for value in candidates:
        value = (value or "").strip()
        if value:
            return value
    return "Unknown"


class QueueWriter(io.TextIOBase):
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def write(self, s):
        if s:
            self.log_queue.put(str(s))
        return len(s)

    def flush(self):
        return None


class FcmBotApp:
    def __init__(self):
        self.current_user = resolve_current_user()
        self.root = ctk.CTk()
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.log_queue = queue.Queue()
        self._build_ui()
        self._bring_to_front_once()
        self.root.after(100, self._drain_log_queue)
        self._apply_access_rule()

    def _build_ui(self):
        outer = ctk.CTkFrame(self.root, corner_radius=0)
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        header = ctk.CTkFrame(outer)
        header.pack(fill="x", padx=8, pady=(8, 10))

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkLabel(
            title_row,
            text="FCM Intake Bot",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left", anchor="w")

        self.user_label = ctk.CTkLabel(
            title_row,
            text=f'User: "{self.current_user}"',
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.user_label.pack(side="right", anchor="e")

        # ctk.CTkLabel(
        #     header,
        #     text="Shared CMS login from UI with recovery-aware automation.",
        #     font=ctk.CTkFont(size=13)
        # ).pack(anchor="w", padx=12, pady=(0, 12))

        creds = ctk.CTkFrame(outer)
        creds.pack(fill="x", padx=8, pady=(0, 10))

        ctk.CTkLabel(
            creds,
            text="CMS Login",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        ctk.CTkLabel(creds, text="Username").grid(row=1, column=0, sticky="w", padx=14, pady=6)
        self.username_var = ctk.StringVar()
        self.username_entry = ctk.CTkEntry(creds, textvariable=self.username_var, width=320)
        self.username_entry.grid(row=1, column=1, sticky="ew", padx=14, pady=6)

        ctk.CTkLabel(creds, text="Password").grid(row=2, column=0, sticky="w", padx=14, pady=(6, 14))
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(creds, textvariable=self.password_var, show="*", width=320)
        self.password_entry.grid(row=2, column=1, sticky="ew", padx=14, pady=(6, 14))
        creds.grid_columnconfigure(1, weight=1)

        actions = ctk.CTkFrame(outer)
        actions.pack(fill="x", padx=8, pady=(0, 10))
        self.run_btn = ctk.CTkButton(actions, text="Run Full FCM Flow", command=self.run_full_flow, width=180)
        self.run_btn.pack(side="left", padx=12, pady=12)
        self.close_btn = ctk.CTkButton(actions, text="Close CMS Browser", command=self.close_browser, width=180)
        self.close_btn.pack(side="left", padx=8, pady=12)
        self.clear_btn = ctk.CTkButton(actions, text="Clear Log", command=self.clear_log, width=140)
        self.clear_btn.pack(side="left", padx=8, pady=12)

        # note = ctk.CTkFrame(outer)
        # note.pack(fill="x", padx=8, pady=(0, 10))
        # self.note_label = ctk.CTkLabel(
        #     note,
        #     text="Allowed users only. Launcher uses one shared CMS login session from this UI.",
        #     wraplength=980,
        #     justify="left"
        # )
        # self.note_label.pack(anchor="w", padx=14, pady=12)

        log_frame = ctk.CTkFrame(outer)
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        ctk.CTkLabel(log_frame, text="Log", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))
        self.log_widget = ctk.CTkTextbox(log_frame, wrap="word")
        self.log_widget.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _bring_to_front_once(self):
        try:
            self.root.deiconify()
        except Exception:
            pass
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))

    def _apply_access_rule(self):
        normalized_user = self.current_user.strip().upper()
        if normalized_user not in ALLOWED_USERS:
            self.log(f'[ACCESS] User "{self.current_user}" is not allowed to run this tool.')
            self.run_btn.configure(state="disabled")
            self.username_entry.configure(state="disabled")
            self.password_entry.configure(state="disabled")
            self.note_label.configure(
                text=f'Access denied for User: "{self.current_user}". Allowed users: {", ".join(sorted(ALLOWED_USERS))}'
            )
        else:
            self.log(f'[ACCESS] User "{self.current_user}" is allowed.')

    def close_browser(self):
        cms_session.close_shared_driver()
        self.log("[INFO] Shared CMS browser closed.")

    def get_context(self):
        return BotContext(
            cms_username=self.username_var.get().strip(),
            cms_password=self.password_var.get(),
        )

    def show_info(self, title: str, text: str):
        messagebox.showinfo(title, text, parent=self.root)

    def clear_log(self):
        self.log_widget.delete("1.0", "end")

    def log(self, message: str):
        self.log_queue.put(message.rstrip("\n") + "\n")

    def _drain_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self.log_widget.insert("end", item)
                self.log_widget.see("end")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log_queue)

    def _run_with_redirect(self, target, *args):
        writer = QueueWriter(self.log_queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                target(*args)
        except Exception as exc:
            self.log(f"[ERROR] {exc}")
        finally:
            self.root.after(0, lambda: self.run_btn.configure(state="normal"))

    def run_full_flow(self):
        if self.current_user.strip().upper() not in ALLOWED_USERS:
            self.log("[ACCESS] Run blocked.")
            return
        context = self.get_context()
        self.run_btn.configure(state="disabled")
        threading.Thread(target=self._run_with_redirect, args=(run_fcm, self, context), daemon=True).start()

    def run(self):
        self.root.mainloop()




