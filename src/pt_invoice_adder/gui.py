"""Apple-inspired GUI for PT Invoice List Adder (CustomTkinter preferred)."""

from __future__ import annotations

import json
import threading
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any


CONFIG_NAME = "config.json"
HOME_CONFIG = ".pt_invoice_adder.json"

# Soft light palette (Apple-ish)
BG = "#F5F5F7"
CARD = "#FFFFFF"
TEXT = "#1D1D1F"
MUTED = "#86868B"
ACCENT = "#0071E3"
ACCENT_HOVER = "#0077ED"
BORDER = "#D2D2D7"
SUCCESS = "#34C759"


def _config_paths() -> list[Path]:
    from pt_invoice_adder.paths import app_dir

    return [
        app_dir() / CONFIG_NAME,
        Path.cwd() / CONFIG_NAME,
        Path.home() / HOME_CONFIG,
    ]


def load_config() -> dict[str, Any]:
    for p in _config_paths():
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


def save_config(cfg: dict[str, Any]) -> None:
    from pt_invoice_adder.paths import app_dir

    for primary in (app_dir() / CONFIG_NAME, Path.cwd() / CONFIG_NAME):
        try:
            primary.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            return
        except OSError:
            continue
    home = Path.home() / HOME_CONFIG
    home.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _fmt_row(row: dict[str, Any]) -> str:
    d = row.get("invoice_date")
    if isinstance(d, datetime):
        ds = d.date().isoformat()
    elif isinstance(d, date):
        ds = d.isoformat()
    else:
        ds = str(d)
    return (
        f"{row.get('invoice_no')}  ·  {ds}  ·  {row.get('country')}  ·  "
        f"{row.get('shipment_type')}  ·  {row.get('total_pkg')} pcs  ·  "
        f"{row.get('gross_weight')} kg"
    )


def run_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "GUI 需要 tkinter。請用 CLI：\n"
            "  python -m pt_invoice_adder --files ... --list ...\n"
            f"原始錯誤：{exc}"
        ) from exc

    try:
        import customtkinter as ctk
    except Exception as exc:
        raise SystemExit(
            "此版本介面需要 customtkinter。\n"
            "請安裝：pip install customtkinter\n"
            f"或使用免安裝可攜包。\n原始錯誤：{exc}"
        ) from exc

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    class App(ctk.CTk):
        def __init__(self) -> None:
            super().__init__()
            self.cfg = load_config()
            self.paths: list[str] = list(self.cfg.get("last_files") or [])
            self.title("PT Invoice")
            self.geometry("820x700")
            self.minsize(720, 600)
            self.configure(fg_color=BG)
            self._busy = False
            self._build()
            self._hook_dnd()

        def _card(self, parent, **kwargs) -> ctk.CTkFrame:
            return ctk.CTkFrame(
                parent,
                fg_color=CARD,
                corner_radius=16,
                border_width=1,
                border_color=BORDER,
                **kwargs,
            )

        def _build(self) -> None:
            outer = ctk.CTkFrame(self, fg_color=BG)
            outer.pack(fill="both", expand=True, padx=28, pady=24)

            # Header
            ctk.CTkLabel(
                outer,
                text="PT Invoice",
                font=ctk.CTkFont(size=28, weight="bold"),
                text_color=TEXT,
                anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                outer,
                text="從 MSG / PDF 擷取發票，寫入 PT INV LIST",
                font=ctk.CTkFont(size=13),
                text_color=MUTED,
                anchor="w",
            ).pack(fill="x", pady=(4, 18))

            # List path card
            card_list = self._card(outer)
            card_list.pack(fill="x", pady=(0, 12))
            inner = ctk.CTkFrame(card_list, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=14)
            ctk.CTkLabel(
                inner, text="PT INV LIST", font=ctk.CTkFont(size=12, weight="bold"), text_color=MUTED
            ).pack(anchor="w")
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=(8, 0))
            self.list_var = tk.StringVar(value=self.cfg.get("list_path") or "")
            self.list_entry = ctk.CTkEntry(
                row,
                textvariable=self.list_var,
                height=36,
                corner_radius=10,
                border_color=BORDER,
                fg_color="#FAFAFA",
                text_color=TEXT,
                placeholder_text="選擇或貼上 PT INV LIST.xlsx 路徑",
            )
            self.list_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkButton(
                row,
                text="瀏覽",
                width=88,
                height=36,
                corner_radius=10,
                fg_color="#E8E8ED",
                hover_color="#DCDCE0",
                text_color=TEXT,
                command=self._browse_list,
            ).pack(side="left")

            # Drop / files card
            card_drop = self._card(outer)
            card_drop.pack(fill="x", pady=(0, 12))
            drop_inner = ctk.CTkFrame(card_drop, fg_color="transparent")
            drop_inner.pack(fill="x", padx=16, pady=16)
            self.drop_zone = ctk.CTkFrame(
                drop_inner,
                fg_color="#FAFAFA",
                corner_radius=12,
                border_width=1,
                border_color=BORDER,
                height=88,
            )
            self.drop_zone.pack(fill="x")
            self.drop_zone.pack_propagate(False)
            ctk.CTkLabel(
                self.drop_zone,
                text="將 PDF / MSG 拖到這裡，或用下方按鈕加入",
                font=ctk.CTkFont(size=14),
                text_color=MUTED,
            ).place(relx=0.5, rely=0.5, anchor="center")

            btn_row = ctk.CTkFrame(drop_inner, fg_color="transparent")
            btn_row.pack(fill="x", pady=(12, 0))
            for text, cmd in (
                ("選擇檔案", self._pick_files),
                ("選擇資料夾", self._pick_folder),
                ("清除", self._clear_paths),
            ):
                ctk.CTkButton(
                    btn_row,
                    text=text,
                    width=100,
                    height=32,
                    corner_radius=10,
                    fg_color="#E8E8ED",
                    hover_color="#DCDCE0",
                    text_color=TEXT,
                    command=cmd,
                ).pack(side="left", padx=(0, 8))

            # Selected paths
            card_paths = self._card(outer)
            card_paths.pack(fill="x", pady=(0, 12))
            pi = ctk.CTkFrame(card_paths, fg_color="transparent")
            pi.pack(fill="both", expand=True, padx=16, pady=12)
            ctk.CTkLabel(
                pi, text="已選檔案", font=ctk.CTkFont(size=12, weight="bold"), text_color=MUTED
            ).pack(anchor="w")
            self.paths_box = ctk.CTkTextbox(
                pi,
                height=72,
                corner_radius=10,
                fg_color="#FAFAFA",
                border_color=BORDER,
                border_width=1,
                text_color=TEXT,
                font=ctk.CTkFont(size=12),
            )
            self.paths_box.pack(fill="x", pady=(8, 0))
            self._refresh_paths_box()

            # Preview
            card_prev = self._card(outer)
            card_prev.pack(fill="both", expand=True, pady=(0, 12))
            pvi = ctk.CTkFrame(card_prev, fg_color="transparent")
            pvi.pack(fill="both", expand=True, padx=16, pady=12)
            ctk.CTkLabel(
                pvi, text="預覽", font=ctk.CTkFont(size=12, weight="bold"), text_color=MUTED
            ).pack(anchor="w")
            self.preview = ctk.CTkTextbox(
                pvi,
                corner_radius=10,
                fg_color="#FAFAFA",
                border_color=BORDER,
                border_width=1,
                text_color=TEXT,
                font=ctk.CTkFont(size=12),
            )
            self.preview.pack(fill="both", expand=True, pady=(8, 0))

            # Actions + status
            actions = ctk.CTkFrame(outer, fg_color="transparent")
            actions.pack(fill="x", pady=(4, 0))
            self.status = ctk.CTkLabel(
                actions, text="就緒", font=ctk.CTkFont(size=12), text_color=MUTED, anchor="w"
            )
            self.status.pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                actions,
                text="僅預覽",
                width=100,
                height=40,
                corner_radius=12,
                fg_color="#E8E8ED",
                hover_color="#DCDCE0",
                text_color=TEXT,
                command=lambda: self._process(dry_run=True),
            ).pack(side="right", padx=(8, 0))
            self.btn_run = ctk.CTkButton(
                actions,
                text="處理並寫入",
                width=128,
                height=40,
                corner_radius=12,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda: self._process(dry_run=False),
            )
            self.btn_run.pack(side="right")

        def _set_status(self, msg: str, *, ok: bool = False) -> None:
            self.status.configure(text=msg, text_color=SUCCESS if ok else MUTED)

        def _hook_dnd(self) -> None:
            """Windows: windnd; else try tkinterdnd2 on underlying tk."""
            try:
                import windnd

                def _dropped(files):
                    paths = [
                        f.decode("utf-8") if isinstance(f, bytes) else str(f) for f in files
                    ]
                    self.after(0, lambda: self._add_paths(paths))

                windnd.hook_dropfiles(self, func=_dropped)
                self._set_status("就緒 · 可拖放檔案")
                return
            except Exception:
                pass
            try:
                from tkinterdnd2 import DND_FILES

                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop)
                self._set_status("就緒 · 可拖放檔案")
            except Exception:
                self._set_status("就緒 · 請用按鈕選擇檔案")

        def _on_drop(self, event) -> None:
            raw = event.data
            parts: list[str] = []
            cur = ""
            in_brace = False
            for ch in raw:
                if ch == "{":
                    in_brace = True
                    cur = ""
                elif ch == "}":
                    in_brace = False
                    parts.append(cur)
                    cur = ""
                elif ch == " " and not in_brace:
                    if cur:
                        parts.append(cur)
                        cur = ""
                else:
                    cur += ch
            if cur:
                parts.append(cur)
            self._add_paths(parts)

        def _refresh_paths_box(self) -> None:
            self.paths_box.delete("1.0", "end")
            if not self.paths:
                self.paths_box.insert("end", "尚未選擇檔案")
                return
            for p in self.paths:
                self.paths_box.insert("end", p + "\n")

        def _add_paths(self, new_paths: list[str]) -> None:
            n = 0
            for p in new_paths:
                p = p.strip().strip("{}")
                if p and p not in self.paths:
                    self.paths.append(p)
                    n += 1
            self._refresh_paths_box()
            self._persist()
            if n:
                self._set_status(f"已加入 {n} 項")

        def _clear_paths(self) -> None:
            self.paths.clear()
            self._refresh_paths_box()
            self._persist()
            self._set_status("已清除清單")

        def _pick_files(self) -> None:
            files = filedialog.askopenfilenames(
                title="選擇 PDF / MSG",
                filetypes=[
                    ("Invoice files", "*.pdf *.PDF *.msg *.MSG"),
                    ("PDF", "*.pdf *.PDF"),
                    ("Outlook MSG", "*.msg *.MSG"),
                    ("All", "*.*"),
                ],
            )
            if files:
                self._add_paths(list(files))

        def _pick_folder(self) -> None:
            folder = filedialog.askdirectory(title="選擇資料夾")
            if folder:
                self._add_paths([folder])

        def _browse_list(self) -> None:
            path = filedialog.askopenfilename(
                title="選擇 PT INV LIST.xlsx",
                filetypes=[("Excel", "*.xlsx *.xlsm"), ("All", "*.*")],
            )
            if path:
                self.list_var.set(path)
                self._persist()

        def _persist(self) -> None:
            self.cfg["list_path"] = self.list_var.get().strip()
            self.cfg["last_files"] = list(self.paths)
            try:
                save_config(self.cfg)
            except Exception as exc:
                self._set_status(f"設定儲存失敗：{exc}")

        def _process(self, dry_run: bool = False) -> None:
            if self._busy:
                return
            self._persist()
            list_path = self.list_var.get().strip()
            if not self.paths:
                messagebox.showwarning("提示", "請先選擇 PDF / MSG 檔案或資料夾")
                return
            if not dry_run and not list_path:
                messagebox.showwarning("提示", "請指定 PT INV LIST.xlsx 路徑")
                return

            self.preview.delete("1.0", "end")
            self._busy = True
            self.btn_run.configure(state="disabled")
            self._set_status("處理中…")

            def work() -> None:
                try:
                    from pt_invoice_adder.extract import collect_pdfs, rows_from_pdfs
                    from pt_invoice_adder.list_writer import append_rows
                    from pt_invoice_adder.lookups import load_lookups

                    lookups = load_lookups()
                    pdfs = collect_pdfs(self.paths)
                    rows = rows_from_pdfs(pdfs, lookups)

                    def ui_update() -> None:
                        self.preview.delete("1.0", "end")
                        if not rows:
                            self.preview.insert("end", "沒有擷取到發票列")
                        else:
                            for r in rows:
                                self.preview.insert("end", _fmt_row(r) + "\n")
                        try:
                            if dry_run or not list_path:
                                added, skipped = append_rows(
                                    list_path, rows, dry_run=True
                                ) if list_path else (len(rows), 0)
                                self._set_status(
                                    f"預覽完成 · 將新增 {added} · 略過 {skipped}", ok=True
                                )
                            else:
                                added, skipped = append_rows(
                                    list_path,
                                    rows,
                                    dry_run=False,
                                    open_after=True,
                                )
                                msg = f"完成 · 新增 {added} · 略過 {skipped}"
                                if added:
                                    msg += " · 已開啟清單"
                                self._set_status(msg, ok=True)
                                messagebox.showinfo(
                                    "完成",
                                    f"新增 {added} 筆，略過重複 {skipped} 筆"
                                    + ("\n已開啟 PT INV LIST 供檢視" if added else ""),
                                )
                        finally:
                            self._busy = False
                            self.btn_run.configure(state="normal")

                    self.after(0, ui_update)
                except Exception:
                    err = traceback.format_exc()

                    def fail() -> None:
                        self._busy = False
                        self.btn_run.configure(state="normal")
                        self._set_status("發生錯誤")
                        self.preview.insert("end", err)
                        messagebox.showerror("錯誤", err[-500:])

                    self.after(0, fail)

            threading.Thread(target=work, daemon=True).start()

    App().mainloop()


if __name__ == "__main__":
    run_gui()
