# PDF & 오디오 도구 — 프로젝트 문서

## 개요

PDF·오디오 파일을 처리하는 PyQt6 기반 데스크톱 앱. 비개발자도 쓸 수 있도록 PyInstaller로 패키징해 배포한다.

---

## 실행 / 개발 환경

```bash
# 의존성 설치
pip3.13 install pymupdf pyqt6

# 실행
python3.13 pdf_splitter.py
```

- Python **3.13** (python.org 설치판) — 시스템 Python 3.9는 Tk deprecated로 흑화면 발생
- 패키지: `pymupdf` (PyMuPDF / fitz), `pyqt6`
- ffmpeg은 앱 내부에 번들 (사용자가 별도 설치 불필요)

---

## 파일 구조

```
pdf_splitter/
├── pdf_splitter.py          # 앱 본체 (단일 파일)
├── icon_generated.png       # 아이콘 원본
├── icon.icns                # macOS 아이콘
├── icon.ico                 # Windows 아이콘
├── README.md                # 사용자용 배포 설명서
├── CLAUDE.md                # 이 문서
└── .github/workflows/
    └── build.yml            # GitHub Actions 빌드 워크플로
```

---

## 코드 구조 (`pdf_splitter.py`)

```
utils (get_ffmpeg, get_mb)
  ↓
PDF 로직 (split_pdf_by_size, split_pdf_by_pages)
  ↓
WorkerSignals(QObject)  ← 스레드 → Qt UI 통신용 pyqtSignal
  ↓
BaseTab(QWidget)        ← 4개 탭 공통 베이스 클래스
  ├── PdfSizeTab        탭 1: PDF 용량 기준 분할
  ├── PdfPageTab        탭 2: PDF 페이지 수 기준 분할
  ├── AudioConvertTab   탭 3: 오디오 → m4a 변환 (ffmpeg)
  └── AudioSplitTab     탭 4: 오디오 용량 기준 분할 (ffmpeg)
  ↓
MainWindow(QMainWindow) ← QTabWidget으로 4탭 구성
```

### BaseTab 주요 메서드

| 메서드 | 역할 |
|---|---|
| `_input_group(ext_filter)` | 폴더/파일 선택 UI + 파일 목록 위젯 |
| `_output_group()` | 출력 폴더 + 옵션 체크박스 |
| `_log_widget()` | 로그 출력 QTextEdit |
| `_progress_widget()` | 진행률 QProgressBar |
| `_pick_folder(ext)` | 폴더 선택 → 파일 목록 갱신, 경로 표시 |
| `_pick_files(ext)` | 파일 직접 선택 |
| `_rescan_folder()` | 체크박스 변경 시 백그라운드 재스캔 |
| `_resolve_out(src)` | 출력 경로 결정 (하위 폴더 구조 유지 포함) |
| `_append_log(widget, msg, tag)` | 색상 태그로 로그 추가 |
| `_launch(signals, fn, *btns)` | 백그라운드 스레드 실행 + 버튼 비활성화 |

### 스레드 안전성

Qt UI는 메인 스레드에서만 업데이트해야 한다. `WorkerSignals(QObject)`에 `pyqtSignal`을 정의하고, 백그라운드 `threading.Thread`에서 `signals.xxx.emit()`으로만 통신한다.

```python
class WorkerSignals(QObject):
    log      = pyqtSignal(str, str)   # (메시지, 색상태그)
    progress = pyqtSignal(int)
    finished = pyqtSignal()
```

### ffmpeg 번들 경로

```python
def get_ffmpeg():
    if hasattr(sys, "_MEIPASS"):          # PyInstaller 패키징 환경
        for name in ("ffmpeg", "ffmpeg.exe"):
            p = Path(sys._MEIPASS) / name
            if p.exists():
                return str(p)
    return "ffmpeg"                        # 개발 환경
```

---

## 주요 설계 결정

| 항목 | 선택 | 이유 |
|---|---|---|
| PDF 라이브러리 | PyMuPDF (fitz) | pypdf는 malformed PDF에서 "Could not read Boolean object" 오류 발생 |
| GUI 프레임워크 | PyQt6 | QSS 스타일링 지원이 목표; Tkinter는 QSS 불가 |
| ffmpeg 배포 | 앱 내 번들 | 사용자가 별도 설치 불필요 |
| macOS 패키징 | `--onedir` | `--onefile`은 macOS에서 windowed 모드와 충돌 |
| Windows 패키징 | `--onefile` | 단일 exe 배포 편의성 |
| 파일 이동 | `shutil.move()` | `os.replace()`는 크로스 디바이스 이동 시 오류 |

---

## 탭별 기본값

| 탭 | 설정 | 기본값 |
|---|---|---|
| PDF 용량 분할 | 최대 크기 | 200 MB |
| PDF 페이지 분할 | 페이지 수 | 50 페이지 |
| 오디오 → m4a | 비트레이트 | 128k |
| 오디오 용량 분할 | 최대 크기 | 100 MB |

---

## 빌드 (GitHub Actions)

`.github/workflows/build.yml` — `workflow_dispatch`로 수동 트리거

- **macOS**: `--onedir --windowed --icon=icon.icns` + ffmpeg 번들
- **Windows**: `--onefile --windowed --icon=icon.ico` + ffmpeg.exe 번들
- Python 3.12 사용 (CI 환경)
- 빌드 결과물: Actions 탭 → 완료된 워크플로 → Artifacts

### 로컬 빌드

```bash
# macOS
python3.13 -m PyInstaller --onedir --windowed --icon=icon.icns \
  --add-binary "ffmpeg:." -y pdf_splitter.py

# Windows
python -m PyInstaller --onefile --windowed --icon=icon.ico \
  --add-binary "ffmpeg.exe;." -y pdf_splitter.py
```

---

## 향후 작업 (TODO)

- QSS 스타일 시트 적용 (현재 최소 스타일만 적용됨)
- 앱 아이콘 개선
