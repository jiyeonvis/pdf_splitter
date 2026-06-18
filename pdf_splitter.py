"""
PDF 분할 앱
실행: python pdf_splitter.py
패키징: pyinstaller --onefile --windowed pdf_splitter.py
의존성: pip install pymupdf
"""

import os
import shutil
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import fitz  # PyMuPDF
except ImportError:
    import sys
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf"])
    import fitz


# ── 핵심 로직 ──────────────────────────────────────────────────

def get_mb(path):
    return Path(path).stat().st_size / (1024 * 1024)


def split_pdf(src, max_mb, output_dir, log):
    doc = fitz.open(src)
    total = doc.page_count
    src_mb = get_mb(src)
    estimated = max(1, int(total * (max_mb / src_mb) * 0.85))

    parts, page_idx, part_num = [], 0, 1

    while page_idx < total:
        chunk_size = estimated
        while True:
            end = min(page_idx + chunk_size, total)
            chunk = fitz.open()
            chunk.insert_pdf(doc, from_page=page_idx, to_page=end - 1)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name
            chunk.save(tmp_path, garbage=4, deflate=True)
            chunk.close()
            chunk_mb = get_mb(tmp_path)

            if chunk_mb <= max_mb or chunk_size == 1:
                break
            os.unlink(tmp_path)
            chunk_size = max(1, int(chunk_size * (max_mb / chunk_mb) * 0.9))

        out_name = f"{Path(src).stem}_part{part_num}.pdf"
        out_path = str(Path(output_dir) / out_name)
        shutil.move(tmp_path, out_path)
        pages = end - page_idx
        log(f"    → {out_name}  ({pages}p, {chunk_mb:.1f} MB)")
        parts.append(out_path)
        page_idx = end
        part_num += 1
        estimated = pages

    doc.close()
    return parts


# ── GUI ────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF 분할기")
        self.resizable(False, False)
        self.selected_paths = []   # 선택된 파일 목록
        self._build_ui()
        self.update_idletasks()
        self.lift()
        self.focus_force()

    def _build_ui(self):
        pad = dict(padx=12, pady=6)

        # ── 입력 섹션 ──
        frm_input = ttk.LabelFrame(self, text="입력")
        frm_input.grid(row=0, column=0, sticky="ew", **pad)

        ttk.Button(frm_input, text="📂 폴더 선택", command=self.pick_folder).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(frm_input, text="📄 파일 선택", command=self.pick_files).grid(row=0, column=1, padx=6, pady=6)

        self.lbl_selected = ttk.Label(frm_input, text="선택된 항목 없음", foreground="gray")
        self.lbl_selected.grid(row=1, column=0, columnspan=2, padx=6, pady=(0, 6), sticky="w")

        # ── 설정 섹션 ──
        frm_cfg = ttk.LabelFrame(self, text="설정")
        frm_cfg.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Label(frm_cfg, text="최대 크기 (MB):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_mb = tk.StringVar(value="200")
        ttk.Entry(frm_cfg, textvariable=self.var_mb, width=8).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(frm_cfg, text="출력 폴더:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.var_out = tk.StringVar(value="(원본과 동일)")
        ttk.Entry(frm_cfg, textvariable=self.var_out, width=34).grid(row=1, column=1, pady=4)
        ttk.Button(frm_cfg, text="찾아보기", command=self.pick_output).grid(row=1, column=2, padx=6, pady=4)

        self.var_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_cfg, text="분할 후 원본 삭제", variable=self.var_delete).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        # ── 버튼 ──
        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=2, column=0, **pad)

        self.btn_scan = ttk.Button(frm_btn, text="🔍 스캔", command=self.scan, width=14)
        self.btn_scan.grid(row=0, column=0, padx=6)
        self.btn_run = ttk.Button(frm_btn, text="▶ 분할 시작", command=self.run, width=14, state="disabled")
        self.btn_run.grid(row=0, column=1, padx=6)

        # ── 진행률 ──
        self.progress = ttk.Progressbar(self, length=400, mode="determinate")
        self.progress.grid(row=3, column=0, padx=12, pady=(0, 4), sticky="ew")

        # ── 로그 ──
        frm_log = ttk.Frame(self)
        frm_log.grid(row=4, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.log_box = tk.Text(frm_log, height=12, width=54, state="disabled",
                               bg="#1e1e1e", fg="#d4d4d4", font=("Courier", 10))
        scrollbar = ttk.Scrollbar(frm_log, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scrollbar.set)
        self.log_box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ── 파일/폴더 선택 ──

    def pick_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.selected_paths = [str(p) for p in Path(folder).glob("*.pdf")]
        self._update_label(f"폴더: {Path(folder).name}  ({len(self.selected_paths)}개 PDF)")
        self.btn_run.config(state="disabled")
        self._clear_log()

    def pick_files(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF 파일", "*.pdf")])
        if not files:
            return
        self.selected_paths = list(files)
        self._update_label(f"파일 {len(files)}개 선택됨")
        self.btn_run.config(state="disabled")
        self._clear_log()

    def pick_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.var_out.set(folder)

    # ── 스캔 ──

    def scan(self):
        if not self.selected_paths:
            messagebox.showwarning("알림", "먼저 폴더나 파일을 선택하세요.")
            return
        try:
            max_mb = float(self.var_mb.get())
        except ValueError:
            messagebox.showerror("오류", "크기는 숫자로 입력하세요.")
            return

        self._clear_log()
        over, ok = [], []
        for p in self.selected_paths:
            mb = get_mb(p)
            if mb > max_mb:
                over.append((p, mb))
            else:
                ok.append((p, mb))

        over.sort(key=lambda x: x[1])
        ok.sort(key=lambda x: x[1])

        self._log(f"── 스캔 결과 (기준: {max_mb} MB) ──\n")
        if ok:
            self._log(f"✔ 기준 이하 (건너뜀): {len(ok)}개\n", "ok")
            for p, mb in ok:
                self._log(f"  • {Path(p).name}  ({mb:.1f} MB)\n", "ok")

        if over:
            self._log(f"\n⚠️  분할 필요: {len(over)}개\n")
            for p, mb in over:
                self._log(f"  • {Path(p).name}  ({mb:.1f} MB)\n", "warn")
        else:
            self._log("\n✅ 모든 파일이 기준 이하입니다.\n")

        self.btn_run.config(state="normal" if over else "disabled")

    # ── 분할 실행 ──

    def run(self):
        try:
            max_mb = float(self.var_mb.get())
        except ValueError:
            messagebox.showerror("오류", "크기는 숫자로 입력하세요.")
            return

        out_val = self.var_out.get()
        targets = [p for p in self.selected_paths if get_mb(p) > max_mb]

        self.btn_scan.config(state="disabled")
        self.btn_run.config(state="disabled")
        self.progress["maximum"] = len(targets)
        self.progress["value"] = 0

        def worker():
            done, failed = 0, 0
            for i, src in enumerate(targets):
                out_dir = Path(out_val) if out_val != "(원본과 동일)" else Path(src).parent
                out_dir.mkdir(parents=True, exist_ok=True)
                self._log(f"\n[{i+1}/{len(targets)}] {Path(src).name}\n")
                try:
                    parts = split_pdf(src, max_mb, out_dir, self._log)
                    done += 1
                    if self.var_delete.get() and parts:
                        Path(src).unlink()
                        self._log(f"    원본 삭제됨\n", "warn")
                except Exception as e:
                    self._log(f"    ❌ 오류: {e}\n", "err")
                    failed += 1
                self.progress["value"] = i + 1
                self.update_idletasks()

            self._log(f"\n── 완료: {done}개 분할, {failed}개 실패 ──\n")
            self.btn_scan.config(state="normal")
            self.btn_run.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    # ── 헬퍼 ──

    def _update_label(self, text):
        self.lbl_selected.config(text=text, foreground="black")

    def _log(self, msg, tag=None):
        self.log_box.config(state="normal")
        if tag == "warn":
            self.log_box.insert("end", msg, "warn")
            self.log_box.tag_config("warn", foreground="#f0a500")
        elif tag == "ok":
            self.log_box.insert("end", msg, "ok")
            self.log_box.tag_config("ok", foreground="#4ec94e")
        elif tag == "err":
            self.log_box.insert("end", msg, "err")
            self.log_box.tag_config("err", foreground="#f55")
        else:
            self.log_box.insert("end", msg)
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()