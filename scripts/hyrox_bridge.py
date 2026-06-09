"""HYROX Discord 알림 브릿지.

changedetection.io 가 보낸 raw snapshot 텍스트를 파싱해
카테고리별 상태를 이모지로 재포맷한 뒤 Discord webhook 으로 송신.

환경변수:
    DISCORD_WEBHOOK_URL  Discord webhook 전체 URL (필수)
    TARGET_CATEGORY      ⭐ 마커를 붙일 카테고리명 (default: Doubles)
    PORT                 리슨 포트 (default: 5051)
"""
import os
import sys
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
DISCORD = os.environ.get("DISCORD_WEBHOOK_URL")
TARGET = os.environ.get("TARGET_CATEGORY", "Doubles")
PORT = int(os.environ.get("PORT", "5051"))

if not DISCORD:
    print("ERROR: DISCORD_WEBHOOK_URL 환경변수 필요", file=sys.stderr)
    sys.exit(1)

CATEGORIES = ["Singles", "Doubles", "Relay", "Spectator"]
STATUS_EMOJI = {
    "almost sold out": "🔴",
    "sold out": "⚫",
    "tickets available": "🟢",
    "available": "🟢",
}


def parse_categories(text: str) -> dict[str, str]:
    """Snapshot 에서 [상태]\\n[카테고리명] 패턴 추출."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        if line in CATEGORIES and i > 0:
            out[line] = lines[i - 1].lower()
    return out


def build_discord_message(snapshot: str, watch_url: str) -> str:
    statuses = parse_categories(snapshot)
    lines = ["🎫 **HYROX Seoul 티켓 상태 변경 감지!**", ""]
    for cat in CATEGORIES:
        s = statuses.get(cat, "unknown")
        emoji = STATUS_EMOJI.get(s, "⚪")
        marker = "  ⭐ **내 타겟**" if cat == TARGET else ""
        lines.append(f"{emoji} **{s.upper()}** — {cat}{marker}")
    lines.append("")
    if watch_url:
        lines.append(f"🔗 {watch_url}")
    return "\n".join(lines)


@app.route("/notify", methods=["POST"])
def notify():
    data = request.get_json(silent=True) or {}
    # Apprise json:// 페이로드 구조: {version, title, message, type}
    # message 필드에 snapshot+url 을 미리 결합해 보냄 (changedetection body 설정)
    message = data.get("message", "")
    title = data.get("title", "")

    # Body 템플릿에서 SNAPSHOT/URL 마커로 분리
    m_snap = re.search(r"<<SNAPSHOT>>(.*?)<<END>>", message, re.DOTALL)
    m_url = re.search(r"<<URL>>(.*?)<<URLEND>>", message, re.DOTALL)
    snapshot = m_snap.group(1).strip() if m_snap else message
    url = m_url.group(1).strip() if m_url else ""

    body = build_discord_message(snapshot, url)

    try:
        r = requests.post(DISCORD, json={"content": body}, timeout=10)
        return jsonify({"discord_status": r.status_code, "body": body}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"ok": True, "target": TARGET})


@app.route("/preview", methods=["POST"])
def preview():
    """디버그용: 실제 Discord 전송 없이 결과 미리보기."""
    data = request.get_json(silent=True) or {}
    snapshot = data.get("snapshot", "")
    url = data.get("url", "")
    return jsonify({"body": build_discord_message(snapshot, url)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
