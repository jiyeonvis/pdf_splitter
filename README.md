# PDF 분할기

용량이 큰 PDF 파일을 지정한 크기 이하로 자동 분할하는 데스크톱 앱입니다.
notebookLM는 용량이 200MB를 넘는 pdf를 받아주지 않습니다.. notebookLM에 올리기 전에 pdf 용량 괜찮은지 확인하는 과정이 필요합니다.

---

## 다운로드

| 운영체제 | 파일               |
| -------- | ------------------ |
| Windows  | `pdf_splitter.exe` |
| macOS    | `pdf_splitter.app` |

→ [최신 버전 다운로드](https://github.com/jiyeonvis/pdf_splitter/actions) (Actions 탭 → 가장 최근 완료된 워크플로 → 하단 Artifacts)

---

## 사용법

### 1단계: 파일 선택

- **폴더 선택**: 폴더 안의 PDF 전체를 처리
- **파일 선택**: 특정 PDF 파일만 골라서 처리

### 2단계: 설정

- **최대 크기**: 분할 기준 용량 입력 (기본값 200MB)
- **출력 폴더**: 분할된 파일을 저장할 위치 선택 (기본값: 원본과 같은 폴더)
- **분할 후 원본 삭제**: 체크하면 분할 완료 후 원본 파일 삭제

### 3단계: 스캔

**🔍 스캔** 버튼을 누르면 기준을 초과하는 파일 목록을 미리 확인할 수 있습니다.

### 4단계: 분할

**▶ 분할 시작** 버튼을 누르면 자동으로 분할됩니다.

분할된 파일명은 `원본파일명_part1.pdf`, `_part2.pdf` 형식으로 저장됩니다.

---

## 처음 실행할 때 보안 경고 해제

### Windows

"Windows가 PC를 보호했습니다" 창이 뜨면:

1. **추가 정보** 클릭
2. **실행** 클릭

### macOS

"개발자를 확인할 수 없습니다" 창이 뜨면:

1. **시스템 설정** → **개인정보 보호 및 보안** 이동
2. 하단 "확인 없이 열기" 클릭

---

## 개발 환경에서 실행하기

```bash
pip3.13 install pymupdf
python3.13 pdf_splitter.py
```

## 실행 파일 직접 빌드하기

```bash
pip install pymupdf pyinstaller

# macOS
pyinstaller --onedir --windowed -y pdf_splitter.py

# Windows
pyinstaller --onefile --windowed -y pdf_splitter.py
```
