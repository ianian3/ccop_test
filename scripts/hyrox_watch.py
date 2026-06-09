"""HYROX Seoul 티켓 상태 모니터 — vivenu __NEXT_DATA__ 폴링.

사용법:
    python3 scripts/hyrox_watch.py              # 5분 간격 폴링
    python3 scripts/hyrox_watch.py --once       # 1회만 확인

알림: 상태가 직전 스냅샷과 달라지면 macOS terminal-notifier (있으면)와
표준출력으로 보고. .state 파일로 상태 캐싱.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

URL = "https://korea.hyrox.com/event/hyrox-seoul-season-26-27-vthaza"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
STATE_PATH = os.path.join(os.path.dirname(__file__), ".hyrox_state.json")
MIN_INTERVAL = 60  # 서버 부담 방지 하한 (초)


def fetch_status() -> dict[str, bool]:
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'__NEXT_DATA__[^>]*>([^<]+)<', html, re.S)
    if not m:
        raise RuntimeError("__NEXT_DATA__ 미발견 — 페이지 구조 변경 가능")
    data = json.loads(m.group(1))
    tickets = data["props"]["pageProps"]["event"]["tickets"]
    return {t["name"]: bool(t.get("active")) for t in tickets}


def notify(title: str, msg: str, sticky: bool = False) -> None:
    print(f"[ALERT] {title}: {msg}", flush=True)
    if sys.platform != "darwin":
        return
    try:
        if sticky:
            # 사용자가 닫기 전까지 사라지지 않는 모달 알림
            safe = msg.replace('"', '\\"')
            script = (
                f'display alert "{title}" message "{safe}" '
                f'as critical buttons {{"확인"}} default button "확인"'
            )
            subprocess.Popen(["osascript", "-e", script])  # non-blocking
        else:
            subprocess.run(
                ["osascript", "-e", f'display notification "{msg}" with title "{title}"'],
                check=False, timeout=5,
            )
    except Exception:
        pass


def diff_state(prev: dict, curr: dict) -> list[str]:
    changes = []
    for name, active in curr.items():
        was = prev.get(name)
        if was is None:
            changes.append(f"NEW [{('판매중' if active else '비활성')}] {name}")
        elif was != active:
            changes.append(f"CHANGED [{('비활성→판매중' if active else '판매중→비활성')}] {name}")
    for name in prev:
        if name not in curr:
            changes.append(f"REMOVED {name}")
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=300, help="폴링 간격(초), 최소 60")
    ap.add_argument("--once", action="store_true", help="1회만 확인 후 종료")
    ap.add_argument("--filter", action="append", default=[],
                    help="티켓 이름에 포함되어야 할 부분 문자열(여러 번 지정 시 AND). 대소문자 무시.")
    ap.add_argument("--sticky", action="store_true",
                    help="알림을 모달 다이얼로그로 띄워 사용자가 닫을 때까지 유지")
    args = ap.parse_args()

    interval = max(MIN_INTERVAL, args.interval)
    prev: dict = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            prev = json.load(f)

    while True:
        try:
            curr = fetch_status()
            if args.filter:
                needles = [f.lower() for f in args.filter]
                curr = {n: v for n, v in curr.items() if all(x in n.lower() for x in needles)}
                if not curr:
                    print("[경고] 필터에 맞는 티켓 없음 — --filter 값을 확인하세요", file=sys.stderr, flush=True)
            active_n = sum(1 for v in curr.values() if v)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] 총 {len(curr)}종 / 판매중 {active_n}종 / 비활성 {len(curr) - active_n}종", flush=True)

            changes = diff_state(prev, curr)
            if changes and prev:  # 최초 실행 시는 알림 X
                detail = "\n".join(changes[:5]) + (f"\n... (+{len(changes)-5})" if len(changes) > 5 else "")
                notify("HYROX 티켓 상태 변경", detail, sticky=args.sticky)
                for c in changes:
                    print("  -", c, flush=True)

            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(curr, f, ensure_ascii=False, indent=2)
            prev = curr
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 오류: {e}", file=sys.stderr, flush=True)

        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
