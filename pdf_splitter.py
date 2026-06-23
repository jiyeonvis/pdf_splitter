"""
PDF & 오디오 도구
실행: python3.13 pdf_splitter.py
의존성: pip install pymupdf
ffmpeg: 앱 폴더 또는 시스템에 설치 필요
"""

import os
import sys
import shutil
import tempfile
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import fitz  # PyMuPDF
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf"])
    import fitz


# ── ffmpeg 경로 ────────────────────────────────────────────────

def get_ffmpeg():
    """번들된 ffmpeg 또는 시스템 ffmpeg 경로 반환"""
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "ffmpeg"
        if bundled.exists():
            return str(bundled)
        bundled_exe = Path(sys._MEIPASS) / "ffmpeg.exe"
        if bundled_exe.exists():
            return str(bundled_exe)
    return "ffmpeg"


# ── 공통 유틸 ──────────────────────────────────────────────────

def get_mb(path):
    return Path(path).stat().st_size / (1024 * 1024)


# ── PDF 용량 분할 로직 ─────────────────────────────────────────

def split_pdf_by_size(src, max_mb, output_dir, log):
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
        log(f"    → {out_name}  ({pages}p, {chunk_mb:.1f} MB)\n")
        parts.append(out_path)
        page_idx = end
        part_num += 1
        estimated = pages

    doc.close()
    return parts


# ── PDF 페이지 분할 로직 ───────────────────────────────────────

def split_pdf_by_pages(src, pages_per_chunk, output_dir, log):
    doc = fitz.open(src)
    total = doc.page_count
    parts, page_idx, part_num = [], 0, 1

    while page_idx < total:
        end = min(page_idx + pages_per_chunk, total)
        chunk = fitz.open()
        chunk.insert_pdf(doc, from_page=page_idx, to_page=end - 1)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
        chunk.save(tmp_path, garbage=4, deflate=True)
        chunk.close()
        chunk_mb = get_mb(tmp_path)

        out_name = f"{Path(src).stem}_part{part_num}.pdf"
        out_path = str(Path(output_dir) / out_name)
        shutil.move(tmp_path, out_path)
        log(f"    → {out_name}  ({end - page_idx}p, {chunk_mb:.1f} MB)\n")
        parts.append(out_path)
        page_idx = end
        part_num += 1

    doc.close()
    return parts


# ── GUI ────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF & 오디오 도구")
        self.resizable(False, False)
        self._build_ui()
        self.update_idletasks()
        self.lift()
        self.focus_force()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab1 = PdfSizeTab(notebook)
        self.tab2 = PdfPageTab(notebook)
        self.tab3 = AudioConvertTab(notebook)
        self.tab4 = AudioSplitTab(notebook)

        notebook.add(self.tab1, text="  PDF 용량 분할  ")
        notebook.add(self.tab2, text="  PDF 페이지 분할  ")
        notebook.add(self.tab3, text="  오디오 → m4a  ")
        notebook.add(self.tab4, text="  오디오 용량 분할  ")


# ── 공통 탭 베이스 ─────────────────────────────────────────────

class BaseTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.selected_paths = []
        self.selected_folder = None   # 폴더 선택 시 루트 경로 저장
        self.var_recursive = tk.BooleanVar(value=False)
        self.var_keep_structure = tk.BooleanVar(value=False)
        self._build()

    def _build(self):
        raise NotImplementedError

    def _make_log(self, parent, row):
        frm = ttk.Frame(parent)
        frm.grid(row=row, column=0, padx=12, pady=(0, 12), sticky="ew")
        log_box = tk.Text(frm, height=12, width=54, state="disabled",
                          bg="#1e1e1e", fg="#d4d4d4", font=("Courier", 10))
        sb = ttk.Scrollbar(frm, command=log_box.yview)
        log_box.configure(yscrollcommand=sb.set)
        log_box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return log_box

    def _log(self, log_box, msg, tag=None):
        log_box.config(state="normal")
        if tag:
            log_box.insert("end", msg, tag)
            log_box.tag_config("warn", foreground="#f0a500")
            log_box.tag_config("ok", foreground="#4ec94e")
            log_box.tag_config("err", foreground="#f55")
        else:
            log_box.insert("end", msg)
        log_box.see("end")
        log_box.config(state="disabled")

    def _clear_log(self, log_box):
        log_box.config(state="normal")
        log_box.delete("1.0", "end")
        log_box.config(state="disabled")

    def _pick_folder(self, filetypes=None):
        folder = filedialog.askdirectory()
        if not folder:
            return None, []
        recursive = self.var_recursive.get()
        if filetypes:
            exts = set()
            for _, pattern in filetypes:
                for p in pattern.split():
                    exts.add(p.lstrip("*").lower())
            glob = "**/*" if recursive else "*"
            paths = [str(p) for p in Path(folder).glob(glob)
                     if p.is_file() and p.suffix.lower() in exts]
        else:
            pattern = "**/*.pdf" if recursive else "*.pdf"
            paths = [str(p) for p in Path(folder).glob(pattern) if p.is_file()]
        return folder, paths

    def _pick_files(self, filetypes):
        files = filedialog.askopenfilenames(filetypes=filetypes)
        return list(files)

    def _make_file_buttons(self, parent, row, filetypes, label_var, filetypes_label="PDF"):
        frm = ttk.LabelFrame(parent, text="입력")
        frm.grid(row=row, column=0, sticky="ew", padx=12, pady=6)

        # 파일 목록 리스트박스
        frm_list = ttk.Frame(frm)
        frm_list.grid(row=2, column=0, columnspan=3, padx=6, pady=(0, 6), sticky="ew")
        listbox = tk.Listbox(frm_list, height=5, width=54,
                             bg="#2a2a2a", fg="#d4d4d4", font=("Courier", 10),
                             selectmode="extended", activestyle="none")
        sb_list = ttk.Scrollbar(frm_list, command=listbox.yview)
        listbox.configure(yscrollcommand=sb_list.set)
        listbox.pack(side="left", fill="both", expand=True)
        sb_list.pack(side="right", fill="y")

        def refresh_list(paths):
            listbox.delete(0, "end")
            for p in sorted(paths):
                listbox.insert("end", Path(p).name)

        def on_folder():
            folder, paths = self._pick_folder(filetypes)
            if paths:
                self.selected_paths = paths
                self.selected_folder = folder
                label_var.set(f"폴더 선택됨  ({len(paths)}개 파일)")
                refresh_list(paths)

        def on_files():
            paths = self._pick_files(filetypes)
            if paths:
                self.selected_paths = paths
                self.selected_folder = None
                label_var.set(f"파일 {len(paths)}개 선택됨")
                refresh_list(paths)

        ttk.Button(frm, text="📂 폴더 선택", command=on_folder).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(frm, text="📄 파일 선택", command=on_files).grid(row=0, column=1, padx=6, pady=6)
        ttk.Checkbutton(frm, text="하위 폴더 포함", variable=self.var_recursive).grid(
            row=0, column=2, padx=6, pady=6)
        ttk.Label(frm, textvariable=label_var, foreground="gray").grid(
            row=1, column=0, columnspan=3, padx=6, pady=(0, 2), sticky="w")
        return frm

    def _make_output_row(self, parent, frm_cfg, row, var_out):
        ttk.Label(frm_cfg, text="출력 폴더:").grid(row=row, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm_cfg, textvariable=var_out, width=30).grid(row=row, column=1, pady=4)
        ttk.Button(frm_cfg, text="찾아보기",
                   command=lambda: var_out.set(filedialog.askdirectory() or var_out.get())
                   ).grid(row=row, column=2, padx=6, pady=4)
        ttk.Checkbutton(frm_cfg, text="하위 폴더 구조 유지", variable=self.var_keep_structure).grid(
            row=row + 1, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 2))

    def _make_progress(self, parent, row):
        pb = ttk.Progressbar(parent, length=400, mode="determinate")
        pb.grid(row=row, column=0, padx=12, pady=(0, 4), sticky="ew")
        return pb

    def _resolve_output_dir(self, src, var_out):
        """출력 폴더 결정. 하위 폴더 구조 유지 옵션 반영."""
        out_val = var_out.get()
        if out_val == "(원본과 동일)":
            return Path(src).parent
        out_base = Path(out_val)
        if self.var_keep_structure.get() and self.selected_folder:
            try:
                rel = Path(src).parent.relative_to(self.selected_folder)
                return out_base / rel
            except ValueError:
                pass
        return out_base


# ── 탭 1: PDF 용량 분할 ────────────────────────────────────────

class PdfSizeTab(BaseTab):
    def _build(self):
        pad = dict(padx=12, pady=6)
        self.var_label = tk.StringVar(value="선택된 항목 없음")
        self._make_file_buttons(self, 0, [("PDF", "*.pdf")], self.var_label)

        frm_cfg = ttk.LabelFrame(self, text="설정")
        frm_cfg.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Label(frm_cfg, text="최대 크기 (MB):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_mb = tk.StringVar(value="200")
        ttk.Entry(frm_cfg, textvariable=self.var_mb, width=8).grid(row=0, column=1, sticky="w", pady=4)
        self.var_out = tk.StringVar(value="(원본과 동일)")
        self._make_output_row(self, frm_cfg, 1, self.var_out)
        self.var_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_cfg, text="분할 후 원본 삭제", variable=self.var_delete).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=2, column=0, **pad)
        self.btn_scan = ttk.Button(frm_btn, text="🔍 스캔", command=self.scan, width=14)
        self.btn_scan.grid(row=0, column=0, padx=6)
        self.btn_run = ttk.Button(frm_btn, text="▶ 분할 시작", command=self.run, width=14, state="disabled")
        self.btn_run.grid(row=0, column=1, padx=6)

        self.progress = self._make_progress(self, 3)
        self.log_box = self._make_log(self, 4)

    def scan(self):
        if not self.selected_paths:
            messagebox.showwarning("알림", "먼저 폴더나 파일을 선택하세요.")
            return
        try:
            max_mb = float(self.var_mb.get())
        except ValueError:
            messagebox.showerror("오류", "크기는 숫자로 입력하세요.")
            return
        self._clear_log(self.log_box)
        over, ok = [], []
        for p in self.selected_paths:
            mb = get_mb(p)
            (over if mb > max_mb else ok).append((p, mb))
        over.sort(key=lambda x: x[1])
        ok.sort(key=lambda x: x[1])

        self._log(self.log_box, f"── 스캔 결과 (기준: {max_mb} MB) ──\n")
        if ok:
            self._log(self.log_box, f"✔ 기준 이하 (건너뜀): {len(ok)}개\n", "ok")
            for p, mb in ok:
                self._log(self.log_box, f"  • {Path(p).name}  ({mb:.1f} MB)\n", "ok")
        if over:
            self._log(self.log_box, f"\n⚠️  분할 필요: {len(over)}개\n")
            for p, mb in over:
                self._log(self.log_box, f"  • {Path(p).name}  ({mb:.1f} MB)\n", "warn")
        else:
            self._log(self.log_box, "\n✅ 모든 파일이 기준 이하입니다.\n")
        self.btn_run.config(state="normal" if over else "disabled")

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
                out_dir = self._resolve_output_dir(src, self.var_out)
                out_dir.mkdir(parents=True, exist_ok=True)
                self._log(self.log_box, f"\n[{i+1}/{len(targets)}] {Path(src).name}\n")
                try:
                    parts = split_pdf_by_size(src, max_mb, out_dir,
                                              lambda m: self._log(self.log_box, m))
                    done += 1
                    if self.var_delete.get() and parts:
                        Path(src).unlink()
                        self._log(self.log_box, "    원본 삭제됨\n", "warn")
                except Exception as e:
                    self._log(self.log_box, f"    ❌ 오류: {e}\n", "err")
                    failed += 1
                self.progress["value"] = i + 1
                self.update_idletasks()
            self._log(self.log_box, f"\n── 완료: {done}개 분할, {failed}개 실패 ──\n")
            self.btn_scan.config(state="normal")
            self.btn_run.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()


# ── 탭 2: PDF 페이지 분할 ──────────────────────────────────────

class PdfPageTab(BaseTab):
    def _build(self):
        pad = dict(padx=12, pady=6)
        self.var_label = tk.StringVar(value="선택된 항목 없음")
        self._make_file_buttons(self, 0, [("PDF", "*.pdf")], self.var_label)

        frm_cfg = ttk.LabelFrame(self, text="설정")
        frm_cfg.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Label(frm_cfg, text="페이지 수 (N):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_pages = tk.StringVar(value="50")
        ttk.Entry(frm_cfg, textvariable=self.var_pages, width=8).grid(row=0, column=1, sticky="w", pady=4)
        self.var_out = tk.StringVar(value="(원본과 동일)")
        self._make_output_row(self, frm_cfg, 1, self.var_out)
        self.var_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_cfg, text="분할 후 원본 삭제", variable=self.var_delete).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=2, column=0, **pad)
        self.btn_run = ttk.Button(frm_btn, text="▶ 분할 시작", command=self.run, width=14)
        self.btn_run.grid(row=0, column=0, padx=6)

        self.progress = self._make_progress(self, 3)
        self.log_box = self._make_log(self, 4)

    def run(self):
        if not self.selected_paths:
            messagebox.showwarning("알림", "먼저 폴더나 파일을 선택하세요.")
            return
        try:
            pages_per_chunk = int(self.var_pages.get())
            if pages_per_chunk < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("오류", "페이지 수는 1 이상의 정수로 입력하세요.")
            return

        out_val = self.var_out.get()
        self.btn_run.config(state="disabled")
        self.progress["maximum"] = len(self.selected_paths)
        self.progress["value"] = 0
        self._clear_log(self.log_box)

        def worker():
            done, failed = 0, 0
            for i, src in enumerate(self.selected_paths):
                out_dir = self._resolve_output_dir(src, self.var_out)
                out_dir.mkdir(parents=True, exist_ok=True)
                total_pages = fitz.open(src).page_count
                self._log(self.log_box, f"\n[{i+1}/{len(self.selected_paths)}] {Path(src).name}  ({total_pages}p)\n")
                try:
                    parts = split_pdf_by_pages(src, pages_per_chunk, out_dir,
                                               lambda m: self._log(self.log_box, m))
                    done += 1
                    if self.var_delete.get() and parts:
                        Path(src).unlink()
                        self._log(self.log_box, "    원본 삭제됨\n", "warn")
                except Exception as e:
                    self._log(self.log_box, f"    ❌ 오류: {e}\n", "err")
                    failed += 1
                self.progress["value"] = i + 1
                self.update_idletasks()
            self._log(self.log_box, f"\n── 완료: {done}개 분할, {failed}개 실패 ──\n")
            self.btn_run.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()


# ── 탭 3: 오디오 → m4a 변환 ────────────────────────────────────

AUDIO_TYPES = [("오디오 파일", "*.mp3 *.wav *.aac *.flac *.ogg *.wma *.m4a")]
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".wma", ".m4a"}

class AudioConvertTab(BaseTab):
    def _build(self):
        pad = dict(padx=12, pady=6)
        self.var_label = tk.StringVar(value="선택된 항목 없음")
        self._make_file_buttons(self, 0, AUDIO_TYPES, self.var_label)

        frm_cfg = ttk.LabelFrame(self, text="설정")
        frm_cfg.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Label(frm_cfg, text="비트레이트:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_bitrate = tk.StringVar(value="128k")
        cb = ttk.Combobox(frm_cfg, textvariable=self.var_bitrate, width=8,
                          values=["64k", "96k", "128k", "192k", "256k"], state="readonly")
        cb.grid(row=0, column=1, sticky="w", pady=4)
        self.var_out = tk.StringVar(value="(원본과 동일)")
        self._make_output_row(self, frm_cfg, 1, self.var_out)
        self.var_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_cfg, text="변환 후 원본 삭제", variable=self.var_delete).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=2, column=0, **pad)
        self.btn_run = ttk.Button(frm_btn, text="▶ 변환 시작", command=self.run, width=14)
        self.btn_run.grid(row=0, column=0, padx=6)

        self.progress = self._make_progress(self, 3)
        self.log_box = self._make_log(self, 4)

    def run(self):
        if not self.selected_paths:
            messagebox.showwarning("알림", "먼저 폴더나 파일을 선택하세요.")
            return
        out_val = self.var_out.get()
        ffmpeg = get_ffmpeg()
        self.btn_run.config(state="disabled")
        self.progress["maximum"] = len(self.selected_paths)
        self.progress["value"] = 0
        self._clear_log(self.log_box)

        def worker():
            done, failed, skipped = 0, 0, 0
            for i, src in enumerate(self.selected_paths):
                out_dir = self._resolve_output_dir(src, self.var_out)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / (Path(src).stem + ".m4a")

                if Path(src).suffix.lower() == ".m4a":
                    self._log(self.log_box, f"[건너뜀] {Path(src).name}  (이미 m4a)\n", "ok")
                    skipped += 1
                    self.progress["value"] = i + 1
                    self.update_idletasks()
                    continue

                self._log(self.log_box, f"\n[{i+1}/{len(self.selected_paths)}] {Path(src).name}\n")
                try:
                    result = subprocess.run(
                        [ffmpeg, "-y", "-i", src, "-c:a", "aac",
                         "-b:a", self.var_bitrate.get(), str(out_path)],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        out_mb = get_mb(out_path)
                        self._log(self.log_box, f"    → {out_path.name}  ({out_mb:.1f} MB)\n")
                        done += 1
                        if self.var_delete.get():
                            Path(src).unlink()
                            self._log(self.log_box, "    원본 삭제됨\n", "warn")
                    else:
                        self._log(self.log_box, f"    ❌ 오류: {result.stderr[-200:]}\n", "err")
                        failed += 1
                except FileNotFoundError:
                    self._log(self.log_box, "    ❌ ffmpeg을 찾을 수 없습니다.\n", "err")
                    failed += 1
                self.progress["value"] = i + 1
                self.update_idletasks()
            self._log(self.log_box, f"\n── 완료: {done}개 변환, {skipped}개 건너뜀, {failed}개 실패 ──\n")
            self.btn_run.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()


# ── 탭 4: 오디오 용량 분할 ────────────────────────────────────

class AudioSplitTab(BaseTab):
    def _build(self):
        pad = dict(padx=12, pady=6)
        self.var_label = tk.StringVar(value="선택된 항목 없음")
        self._make_file_buttons(self, 0, AUDIO_TYPES, self.var_label)

        frm_cfg = ttk.LabelFrame(self, text="설정")
        frm_cfg.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Label(frm_cfg, text="최대 크기 (MB):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_mb = tk.StringVar(value="100")
        ttk.Entry(frm_cfg, textvariable=self.var_mb, width=8).grid(row=0, column=1, sticky="w", pady=4)
        self.var_out = tk.StringVar(value="(원본과 동일)")
        self._make_output_row(self, frm_cfg, 1, self.var_out)
        self.var_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_cfg, text="분할 후 원본 삭제", variable=self.var_delete).grid(
            row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=2, column=0, **pad)
        self.btn_run = ttk.Button(frm_btn, text="▶ 분할 시작", command=self.run, width=14)
        self.btn_run.grid(row=0, column=0, padx=6)

        self.progress = self._make_progress(self, 3)
        self.log_box = self._make_log(self, 4)

    def run(self):
        if not self.selected_paths:
            messagebox.showwarning("알림", "먼저 폴더나 파일을 선택하세요.")
            return
        try:
            max_mb = float(self.var_mb.get())
        except ValueError:
            messagebox.showerror("오류", "크기는 숫자로 입력하세요.")
            return

        out_val = self.var_out.get()
        ffmpeg = get_ffmpeg()
        targets = [p for p in self.selected_paths if get_mb(p) > max_mb]

        if not targets:
            messagebox.showinfo("알림", "분할이 필요한 파일이 없습니다.")
            return

        self.btn_run.config(state="disabled")
        self.progress["maximum"] = len(targets)
        self.progress["value"] = 0
        self._clear_log(self.log_box)

        def get_duration(src):
            result = subprocess.run(
                [ffmpeg, "-i", src],
                capture_output=True, text=True
            )
            for line in result.stderr.split("\n"):
                if "Duration" in line:
                    t = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = t.split(":")
                    return float(h) * 3600 + float(m) * 60 + float(s)
            return None

        def worker():
            done, failed = 0, 0
            for i, src in enumerate(targets):
                out_dir = self._resolve_output_dir(src, self.var_out)
                out_dir.mkdir(parents=True, exist_ok=True)
                src_mb = get_mb(src)
                self._log(self.log_box, f"\n[{i+1}/{len(targets)}] {Path(src).name}  ({src_mb:.1f} MB)\n")
                try:
                    duration = get_duration(src)
                    if not duration:
                        raise ValueError("재생 시간을 읽을 수 없습니다.")

                    # 청크당 시간 추정
                    seconds_per_chunk = int(duration * (max_mb / src_mb) * 0.9)
                    ext = Path(src).suffix.lower()
                    part_num = 1
                    start = 0

                    while start < duration:
                        end = min(start + seconds_per_chunk, duration)
                        out_name = f"{Path(src).stem}_part{part_num}{ext}"
                        out_path = str(out_dir / out_name)
                        subprocess.run(
                            [ffmpeg, "-y", "-i", src,
                             "-ss", str(start), "-to", str(end),
                             "-c", "copy", out_path],
                            capture_output=True
                        )
                        chunk_mb = get_mb(out_path)
                        self._log(self.log_box, f"    → {out_name}  ({chunk_mb:.1f} MB)\n")
                        start = end
                        part_num += 1

                    done += 1
                    if self.var_delete.get():
                        Path(src).unlink()
                        self._log(self.log_box, "    원본 삭제됨\n", "warn")
                except FileNotFoundError:
                    self._log(self.log_box, "    ❌ ffmpeg을 찾을 수 없습니다.\n", "err")
                    failed += 1
                except Exception as e:
                    self._log(self.log_box, f"    ❌ 오류: {e}\n", "err")
                    failed += 1
                self.progress["value"] = i + 1
                self.update_idletasks()
            self._log(self.log_box, f"\n── 완료: {done}개 분할, {failed}개 실패 ──\n")
            self.btn_run.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
