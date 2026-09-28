# tests/test_airgap_build_inputs.py
"""
F09 (감사 2026-09-17): 폐쇄망 빌드 입력과 의존성 선언 충돌.

- Dockerfile.airgap 이 COPY 하는 파일을 .dockerignore 가 제외하면 빌드 실패
- app/ 의 필수 서드파티 import 가 requirements.airgap.txt 에 없으면 폐쇄망 이미지에서 기능 실패
"""
import ast
import fnmatch
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 지연 import + 미설치 시 기능 강등이 설계된 선택 의존성 (requirements-vector.txt 등)
OPTIONAL = {"chromadb", "pypdf", "olefile"}
# pip 패키지명 ≠ import 이름
PIP_NAME = {"flask_cors": "flask-cors", "psycopg2": "psycopg2-binary", "dotenv": "python-dotenv"}
# 다른 패키지가 끌고 오는 전이 의존성 (numpy ← pandas)
TRANSITIVE = {"numpy", "werkzeug"}


def _dockerignore_patterns():
    pats = []
    for line in (ROOT / ".dockerignore").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("!"):
            pats.append(line.lstrip("/"))
    return pats


def test_airgap_copy_sources_not_dockerignored():
    pats = _dockerignore_patterns()
    for line in (ROOT / "Dockerfile.airgap").read_text().splitlines():
        m = re.match(r"\s*COPY\s+(?!--)(\S+)\s+\S+", line)
        if not m or m.group(1) == ".":
            continue
        src = m.group(1)
        hit = [p for p in pats if fnmatch.fnmatch(src, p)]
        assert not hit, f"Dockerfile.airgap COPY {src} 가 .dockerignore {hit} 로 제외됨"


def _airgap_requirements():
    names = set()
    for line in (ROOT / "requirements.airgap.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(re.split(r"[<>=~!\[]", line, 1)[0].strip().lower())
    return names


def _third_party_imports():
    import sys
    import importlib.util
    mods = set()
    for p in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods.add(n.module.split(".")[0])
    out = set()
    for m in mods - {"app", "config"}:
        if m in sys.builtin_module_names:
            continue
        spec = importlib.util.find_spec(m)
        origin = (getattr(spec, "origin", None) or "") if spec else ""
        # 설치 안 된 모듈(spec None)도 서드파티로 간주 — 선언 누락을 놓치지 않도록
        if spec is None or "site-packages" in origin:
            out.add(m)
    return out


def test_airgap_requirements_cover_runtime_imports():
    reqs = _airgap_requirements()
    missing = []
    for m in sorted(_third_party_imports() - OPTIONAL - TRANSITIVE):
        if PIP_NAME.get(m, m).lower() not in reqs:
            missing.append(m)
    assert missing == [], f"requirements.airgap.txt 누락: {missing}"
