#!/usr/bin/env python3
"""
Markdown 문서 → 인쇄 최적화 HTML → PDF 변환기 (headless Chrome 사용)

사용법:
  python scripts/build_doc_pdf.py docs/PROJECT_OVERVIEW.md
  → docs/PROJECT_OVERVIEW.html + docs/PROJECT_OVERVIEW.pdf 생성

요구사항: pip install markdown, Google Chrome(또는 Chromium/Edge) 설치.
스타일: A4, 한국어 시스템 폰트, 프로젝트 아이덴티티(청록 액센트), 섹션별 페이지 시작.
"""
import pathlib
import re
import subprocess
import sys

import markdown

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
]

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: "Apple SD Gothic Neo", Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif;
  font-size: 10pt; line-height: 1.68; color: #16262a; margin: 0;
  word-break: keep-all; overflow-wrap: break-word;
}
/* ── 표지 헤더 ─────────────────────────────── */
h1 {
  font-size: 23pt; font-weight: 800; letter-spacing: -0.02em; line-height: 1.25;
  color: #0b181c; margin: 4mm 0 3mm;
  padding-bottom: 3mm; border-bottom: 2.5pt solid #0a9d98;
}
h1 + p { color: #5a6e74; font-size: 9pt; line-height: 1.7; margin-top: 2mm; }
h1 + p strong { color: #16262a; }
/* ── 섹션 ─────────────────────────────────── */
h2 {
  break-before: page;
  font-size: 15pt; font-weight: 800; letter-spacing: -0.01em; color: #0b181c;
  margin: 0 0 4mm; padding: 2mm 0 2mm 3.5mm;
  border-left: 3.5pt solid #0a9d98; background: #f2f7f7;
  break-after: avoid;
}
h2.toc-title, h2:first-of-type { break-before: auto; margin-top: 6mm; }
h3 {
  font-size: 11.5pt; font-weight: 700; color: #0a7f7b;
  margin: 6mm 0 2mm; break-after: avoid;
}
p { margin: 0 0 2.6mm; }
strong { color: #0b181c; }
em { color: #445c62; }
hr { display: none; }
a { color: inherit; text-decoration: none; }
/* ── 목차 ─────────────────────────────────── */
ol.toc {
  columns: 2; column-gap: 10mm; font-size: 9.5pt;
  background: #f6f9f9; border: 0.5pt solid #dbe4e5; border-radius: 2mm;
  padding: 4mm 6mm 4mm 12mm; margin: 0 0 4mm;
}
ol.toc li { margin-bottom: 1.2mm; break-inside: avoid; }
ol.toc a { color: #16262a; }
/* ── 목록 ─────────────────────────────────── */
ul, ol { margin: 0 0 2.6mm; padding-left: 6mm; }
li { margin-bottom: 1.1mm; }
li::marker { color: #0a9d98; }
/* ── 코드/다이어그램 ───────────────────────── */
code {
  font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 8.2pt;
  background: #eef3f3; border: 0.5pt solid #dde6e6; border-radius: 1mm;
  padding: 0.2mm 1.2mm; color: #114b49;
}
pre {
  background: #f6f8f8; border: 0.5pt solid #d9e2e3; border-left: 2.5pt solid #0a9d98;
  border-radius: 1.5mm; padding: 3mm 3.5mm; margin: 0 0 3mm;
  break-inside: avoid; overflow: hidden;
}
pre code {
  background: none; border: none; padding: 0;
  font-size: 7.6pt; line-height: 1.42; color: #22383d; white-space: pre;
}
/* ── 표 ───────────────────────────────────── */
table {
  border-collapse: collapse; width: 100%; margin: 0 0 3.5mm; font-size: 8.6pt;
}
th {
  background: #e7f1f1; color: #114b49; font-weight: 700; text-align: left;
  padding: 1.8mm 2.4mm; border: 0.5pt solid #c9d8d9; font-size: 8.2pt;
}
td {
  padding: 1.6mm 2.4mm; border: 0.5pt solid #d9e2e3; vertical-align: top;
}
tr:nth-child(even) td { background: #f7fafa; }
tr { break-inside: avoid; }
thead { display: table-header-group; }   /* 페이지 넘어가면 헤더 반복 */
/* ── 인용/각주성 문단 ─────────────────────── */
blockquote {
  margin: 0 0 3mm; padding: 2mm 4mm; color: #5a6e74;
  border-left: 2.5pt solid #c9d8d9; background: #f8fafa; font-size: 9pt;
}
"""

TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{title}</title><style>{css}</style></head>
<body>{body}</body></html>
"""


def find_chrome():
    for c in CHROME_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    sys.exit("Chrome/Chromium 을 찾지 못했습니다. CHROME_CANDIDATES 를 수정하세요.")


def main():
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs/PROJECT_OVERVIEW.md")
    if not src.exists():
        sys.exit(f"원본 없음: {src}")
    text = src.read_text(encoding="utf-8")

    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    # 목차 리스트에 2단 스타일 클래스 부여
    body = re.sub(r"<h2>목차</h2>\s*<ol>", '<h2 class="toc-title">목차</h2>\n<ol class="toc">',
                  body, count=1)
    m = re.search(r"<h1>(.*?)</h1>", body)
    title = re.sub(r"<.*?>", "", m.group(1)) if m else src.stem

    html_path = src.with_suffix(".html")
    html_path.write_text(TEMPLATE.format(title=title, css=CSS, body=body), encoding="utf-8")
    print(f"✅ HTML: {html_path}")

    pdf_path = src.with_suffix(".pdf")
    chrome = find_chrome()
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={pdf_path.resolve()}", html_path.resolve().as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not pdf_path.exists():
        # 구버전 Chrome 플래그 폴백
        cmd = [chrome, "--headless", "--disable-gpu", "--print-to-pdf-no-header",
               f"--print-to-pdf={pdf_path.resolve()}", html_path.resolve().as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not pdf_path.exists():
        sys.exit(f"PDF 생성 실패:\n{r.stderr[-800:]}")
    print(f"✅ PDF: {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
