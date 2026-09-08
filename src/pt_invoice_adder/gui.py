"""GUI for PT Invoice List Adder (CustomTkinter if available, else tkinter)."""

from __future__ import annotations

import json
import threading
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any


CONFIG_NAME = "config.json"
HOME_CONFIG = ".pt_invoice_adder.json"


def _config_paths() -> list[Path]:
    return [
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
    primary = Path.cwd() / CONFIG_NAME
    try:
        primary.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    except OSError:
        pass
    home = Path.home() / HOME_CONFIG
    home.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _fmt_row(row: dict[str, Any]) -> str:
    d = row.get("invoice_date")
    if isinstance(d, (date, datetime)):
        ds = d.isoformat() if isinstance(d, date) and not isinstance(d, datetime) else (
            d.date().isoformat() if isinstance(d, datetime) else str(d)
        )
    else:
        ds = str(d)
    return (
        f"{row.get('invoice_no')}\t{ds}\t{row.get('country')}\t"
        f"{row.get('shipment_type')}\t{row.get('total_pkg')}\t{row.get('gross_weight')}\t"
        f"{row.get('source_file')}"
    )


def run_gui() -> None:
    """Launch GUI; requires tkinter (and optionally customtkinter / tkinterdnd2)."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext, ttk
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "GUI 需要 tkinter（此環境未安裝）。請用 CLI：\n"
            "  python -m pt_invoice_adder --files ... --list ...\n"
            f"原始錯誤：{exc}"
        ) from exc

    use_ctk = False
    try:
        import customtkinter as ctk  # noqa: F401

        use_ctk = True
    except Exception:
        ctk = None  # type: ignore

    has_dnd = False
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD

        has_dnd = True
    except Exception:
        DND_FILES = None  # type: ignore
        TkinterDnD = None  # type: ignore

    class App:
        def __init__(self) -> None:
            self.cfg = load_config()
            self.paths: list[str] = list(self.cfg.get("last_files") or [])
            self._build()

        def _make_root(self):
            if has_dnd:
                root = TkinterDnD.Tk()
            elif use_ctk:
                ctk.set_appearance_mode("System")
                ctk.set_default_color_theme("blue")
                root = ctk.CTk()
            else:
                root = tk.Tk()
            root.title("PT 發票清單加入工具")
            root.geometry("900x640")
            return root

        def _build(self) -> None:
            self.root = self._make_root()
            pad = {"padx": 8, "pady": 4}

            frm_list = ttk.Frame(self.root)
            frm_list.pack(fill="x", **pad)
            ttk.Label(frm_list, text="PT INV LIST 路徑：").pack(side="left")
            self.list_var = tk.StringVar(value=self.cfg.get("list_path") or "")
            self.list_entry = ttk.Entry(frm_list, textvariable=self.list_var)
            self.list_entry.pack(side="left", fill="x", expand=True, padx=4)
            ttk.Button(frm_list, text="瀏覽…", command=self._browse_list).pack(side="left")

            frm_drop = ttk.LabelFrame(
                self.root, text="拖放區域（PDF / MSG / 資料夾）— DnD 為選用依賴"
            )
            frm_drop.pack(fill="both", expand=False, **pad)
            self.drop_label = ttk.Label(
                frm_drop,
                text="將檔案拖放到此處，或使用下方按鈕選擇",
                anchor="center",
                padding=24,
            )
            self.drop_label.pack(fill="x", padx=8, pady=8)

            if has_dnd:
                try:
                    self.drop_label.drop_target_register(DND_FILES)
                    self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
                except Exception:
                    pass

            frm_btns = ttk.Frame(self.root)
            frm_btns.pack(fill="x", **pad)
            ttk.Button(frm_btns, text="選擇檔案", command=self._pick_files).pack(
                side="left", padx=4
            )
            ttk.Button(frm_btns, text="選擇資料夾", command=self._pick_folder).pack(
                side="left", padx=4
            )
            ttk.Button(frm_btns, text="清除清單", command=self._clear_paths).pack(
                side="left", padx=4
            )
            ttk.Button(frm_btns, text="處理 / 寫入", command=self._process).pack(
                side="right", padx=4
            )
            ttk.Button(
                frm_btns,
                text="僅預覽（不寫入）",
                command=lambda: self._process(dry_run=True),
            ).pack(side="right", padx=4)

            frm_paths = ttk.LabelFrame(self.root, text="已選路徑")
            frm_paths.pack(fill="both", expand=False, **pad)
            self.paths_box = scrolledtext.ScrolledText(frm_paths, height=6, wrap="none")
            self.paths_box.pack(fill="both", expand=True, padx=4, pady=4)
            self._refresh_paths_box()

            frm_prev = ttk.LabelFrame(
                self.root, text="預覽（發票號 / 日期 / 國別 / 運送 / 件數 / 毛重 / 來源）"
            )
            frm_prev.pack(fill="both", expand=True, **pad)
            self.preview = scrolledtext.ScrolledText(frm_prev, height=8, wrap="none")
            self.preview.pack(fill="both", expand=True, padx=4, pady=4)

            frm_log = ttk.LabelFrame(self.root, text="日誌")
            frm_log.pack(fill="both", expand=True, **pad)
            self.log = scrolledtext.ScrolledText(frm_log, height=8, wrap="word")
            self.log.pack(fill="both", expand=True, padx=4, pady=4)

            dnd_note = "已啟用" if has_dnd else "未安裝（仍可用按鈕）"
            toolkit = "CustomTkinter" if use_ctk and not has_dnd else "tkinter"
            self._log(f"介面：{toolkit}；拖放：{dnd_note}")

        def _log(self, msg: str) -> None:
            self.log.insert("end", msg + "\n")
            self.log.see("end")

        def _refresh_paths_box(self) -> None:
            self.paths_box.delete("1.0", "end")
            for p in self.paths:
                self.paths_box.insert("end", p + "\n")

        def _add_paths(self, new_paths: list[str]) -> None:
            for p in new_paths:
                p = p.strip().strip("{}")
                if p and p not in self.paths:
                    self.paths.append(p)
            self._refresh_paths_box()
            self._persist()

        def _clear_paths(self) -> None:
            self.paths.clear()
            self._refresh_paths_box()
            self._persist()

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
            self._log(f"拖放加入 {len(parts)} 項")

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
                self._log(f"設定儲存失敗：{exc}")

        def _process(self, dry_run: bool = False) -> None:
            self._persist()
            list_path = self.list_var.get().strip()
            if not self.paths:
                messagebox.showwarning("提示", "請先選擇 PDF / MSG 檔案或資料夾")
                return
            if not dry_run and not list_path:
                messagebox.showwarning("提示", "請指定 PT INV LIST.xlsx 路徑")
                return

            self.preview.delete("1.0", "end")
            self._log("開始處理…" + ("（預覽）" if dry_run else ""))

            def work() -> None:
                try:
                    from pt_invoice_adder.extract import collect_pdfs, rows_from_pdfs
                    from pt_invoice_adder.list_writer import append_rows
                    from pt_invoice_adder.lookups import load_lookups

                    lookups = load_lookups()
                    pdfs = collect_pdfs(self.paths)
                    rows = rows_from_pdfs(pdfs, lookups)

                    def ui_update() -> None:
                        for r in rows:
                            self.preview.insert("end", _fmt_row(r) + "\n")
                        if dry_run or not list_path:
                            added, skipped = (len(rows), 0)
                            if list_path:
                                added, skipped = append_rows(
                                    list_path, rows, dry_run=True
                                )
                            self._log(
                                f"完成：PDF={len(pdfs)} 列={len(rows)} "
                                f"新增={added} 略過={skipped} [dry-run]"
                            )
                        else:
                            added, skipped = append_rows(
                                list_path, rows, dry_run=False
                            )
                            self._log(
                                f"完成：PDF={len(pdfs)} 列={len(rows)} "
                                f"新增={added} 略過={skipped}"
                            )
                            messagebox.showinfo(
                                "完成", f"新增 {added} 筆，略過重複 {skipped} 筆"
                            )

                    self.root.after(0, ui_update)
                except Exception:
                    err = traceback.format_exc()
                    self.root.after(0, lambda: self._log(err))
                    self.root.after(
                        0, lambda: messagebox.showerror("錯誤", err[-500:])
                    )

            threading.Thread(target=work, daemon=True).start()

        def run(self) -> None:
            self.root.mainloop()

    App().run()


if __name__ == "__main__":
    run_gui()
