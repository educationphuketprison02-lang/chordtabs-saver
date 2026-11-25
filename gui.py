"""หน้าต่างโปรแกรม Chordtabs Saver ธีมมืดแบบ Claude (customtkinter)"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from chord_saver import DEFAULT_OUTPUT_DIR, parse_song_lines, run_batch

# โทนสีแบบ Claude dark mode
BG = "#262624"
SURFACE = "#30302E"
SURFACE_HOVER = "#3A3A37"
BORDER = "#3E3E38"
TEXT = "#F5F4EF"
MUTED = "#A6A39A"
ACCENT = "#D97757"
ACCENT_HOVER = "#C6613F"
SUCCESS = "#7FB77E"
ERROR = "#E5736B"
FONT_FAMILY = "Leelawadee UI"  # มีทั้งไทยและอังกฤษในตัว Windows ทุกเครื่อง
PLACEHOLDER = "ฝนตกไหม Three Man Down\nสิให้จ้างหมอลำบ่\nhttps://chordtabs.in.th/51250/"


def font(size: int = 14, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


class ChordSaverApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=BG)
        self.title("Chordtabs Saver")
        self.geometry("720x760")
        self.minsize(560, 620)
        self._has_placeholder = False

        self.folder_var = ctk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.web_title_var = ctk.BooleanVar(value=False)
        self.label_var = ctk.BooleanVar(value=False)
        self.show_var = ctk.BooleanVar(value=False)

        self._build_header()
        self._build_song_input()
        self._build_options()
        self._build_actions()
        self._build_log()

    # ------------------------------------------------------------ layout
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(24, 4))
        ctk.CTkLabel(header, text="✳", font=font(26), text_color=ACCENT).pack(side="left", padx=(0, 10))
        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="Chordtabs Saver", font=font(22, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            titles, text="ค้นหาคอร์ดเพลงแล้วเซฟเป็นรูปให้อัตโนมัติ", font=font(13), text_color=MUTED
        ).pack(anchor="w")

    def _build_song_input(self) -> None:
        ctk.CTkLabel(
            self,
            text="ชื่อเพลง (บรรทัดละ 1 เพลง ใส่ชื่อศิลปินต่อท้ายจะค้นเจอแม่นขึ้น)",
            font=font(13),
            text_color=MUTED,
        ).pack(anchor="w", padx=28, pady=(16, 6))
        self.songs_box = ctk.CTkTextbox(
            self,
            height=190,
            font=font(15),
            fg_color=SURFACE,
            border_color=BORDER,
            border_width=1,
            corner_radius=14,
            text_color=TEXT,
            wrap="none",
        )
        self.songs_box.pack(fill="both", expand=True, padx=28)
        self._show_placeholder()
        self.songs_box.bind("<FocusIn>", lambda _e: self._hide_placeholder())
        self.songs_box.bind("<FocusOut>", lambda _e: self._show_placeholder())

    def _build_options(self) -> None:
        card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=14, border_color=BORDER, border_width=1)
        card.pack(fill="x", padx=28, pady=(14, 0))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(row, text="เซฟไว้ที่", font=font(13), text_color=MUTED).pack(side="left", padx=(0, 10))
        ctk.CTkEntry(
            row,
            textvariable=self.folder_var,
            font=font(13),
            fg_color=BG,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=10,
            height=34,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row,
            text="เลือก…",
            width=74,
            height=34,
            font=font(13),
            corner_radius=10,
            fg_color=SURFACE_HOVER,
            hover_color=BORDER,
            text_color=TEXT,
            command=self._choose_folder,
        ).pack(side="left", padx=(8, 0))

        switches = [
            ("ใส่ชื่อไฟล์ไว้ที่มุมขวาล่างของรูป", self.label_var),
            ("ตั้งชื่อไฟล์ตามชื่อเพลง + ศิลปินจากเว็บ", self.web_title_var),
            ("แสดงหน้าต่างเบราว์เซอร์ระหว่างทำงาน", self.show_var),
        ]
        for text, var in switches:
            ctk.CTkSwitch(
                card,
                text=text,
                variable=var,
                font=font(13),
                text_color=TEXT,
                progress_color=ACCENT,
                button_color=TEXT,
                button_hover_color="#FFFFFF",
                fg_color=BORDER,
            ).pack(anchor="w", padx=16, pady=4)
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _build_actions(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=28, pady=(16, 0))
        self.start_btn = ctk.CTkButton(
            row,
            text="เริ่มค้นหาและเซฟ",
            height=44,
            font=font(15, "bold"),
            corner_radius=12,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            command=self._start,
        )
        self.start_btn.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row,
            text="เปิดโฟลเดอร์",
            width=120,
            height=44,
            font=font(13),
            corner_radius=12,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
            command=self._open_folder,
        ).pack(side="left", padx=(10, 0))

        self.progress = ctk.CTkProgressBar(self, height=6, progress_color=ACCENT, fg_color=SURFACE, corner_radius=3)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=28, pady=(14, 0))

    def _build_log(self) -> None:
        self.log_box = ctk.CTkTextbox(
            self,
            height=170,
            font=font(13),
            fg_color="#1F1E1D",
            border_color=BORDER,
            border_width=1,
            corner_radius=14,
            text_color=MUTED,
            state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=28, pady=(12, 24))
        self.log_box.tag_config("ok", foreground=SUCCESS)
        self.log_box.tag_config("err", foreground=ERROR)
        self.log_box.tag_config("head", foreground=TEXT)

    # ------------------------------------------------------------ placeholder
    def _show_placeholder(self) -> None:
        if self.songs_box.get("1.0", "end").strip():
            return
        self.songs_box.insert("1.0", PLACEHOLDER)
        self.songs_box.configure(text_color="#6E6C66")
        self._has_placeholder = True

    def _hide_placeholder(self) -> None:
        if self._has_placeholder:
            self.songs_box.delete("1.0", "end")
            self.songs_box.configure(text_color=TEXT)
            self._has_placeholder = False

    # ------------------------------------------------------------ actions
    def _choose_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get())
        if chosen:
            self.folder_var.set(chosen)

    def _open_folder(self) -> None:
        folder = Path(self.folder_var.get())
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # noqa: S606 - เปิดโฟลเดอร์ที่ผู้ใช้เลือกเองใน Explorer

    def _log(self, msg: str) -> None:
        tag = "ok" if "✔" in msg else "err" if ("✘" in msg or "ผิดพลาด" in msg) else "head"
        if msg.lstrip().startswith("[") or msg.startswith("\n"):
            tag = "head"

        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n", tag)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, append)

    def _set_progress(self, done: int, total: int) -> None:
        self.after(0, lambda: self.progress.set(done / total if total else 0))

    def _start(self) -> None:
        text = "" if self._has_placeholder else self.songs_box.get("1.0", "end")
        songs = parse_song_lines(text.splitlines())
        if not songs:
            self._log("✘ กรุณาใส่ชื่อเพลงอย่างน้อย 1 เพลง")
            return
        self.start_btn.configure(state="disabled", text="กำลังทำงาน…")
        self.progress.set(0)
        options = (
            Path(self.folder_var.get()),
            self.web_title_var.get(),
            self.show_var.get(),
            self.label_var.get(),
        )
        threading.Thread(target=self._work, args=(songs, *options), daemon=True).start()

    def _work(self, songs: list[str], out_dir: Path, web_title: bool, show: bool, label: bool) -> None:
        try:
            run_batch(songs, out_dir, self._log, web_title, show, label, on_progress=self._set_progress)
        except Exception as exc:  # noqa: BLE001 - แสดงข้อผิดพลาดให้ผู้ใช้เห็น
            self._log(f"✘ ผิดพลาด: {exc}")
        finally:
            self.after(0, lambda: self.start_btn.configure(state="normal", text="เริ่มค้นหาและเซฟ"))


def run_gui() -> None:
    ctk.set_appearance_mode("dark")
    ChordSaverApp().mainloop()


if __name__ == "__main__":
    run_gui()
