"""HYROX Seoul 티켓 카테고리 상태 모니터 (Playwright).

브라우저를 실제로 띄워서 '티켓 구매' 모달의 카테고리 상태
(매진 / 매진 임박 / 구매 가능) 라벨 변화를 감지.
타겟 카테고리가 매진에서 풀리면 macOS 모달 알림.

사용법:
    pip install playwright && python3 -m playwright install chromium
    python3 scripts/hyrox_playwright_watch.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "https://korea.hyrox.com/event/hyrox-seoul-season-26-27-vthaza"
STATE_PATH = os.path.join(os.path.dirname(__file__), ".hyrox_playwright_state.json")
INTERVAL = 300  # 5분
TARGET_CATEGORIES = ["Doubles"]  # PRO DOUBLES MEN은 Doubles 안에 있음
CATEGORIES = ["Singles", "Doubles", "Relay", "Spectator"]


def notify_modal(title: str, msg: str) -> None:
    print(f"[ALERT] {title}: {msg}", flush=True)
    if sys.platform != "darwin":
        return
    safe = msg.replace('"', '\\"').replace("\n", " / ")
    script = (
        f'display alert "{title}" message "{safe}" '
        f'as critical buttons {{"확인"}} default button "확인"'
    )
    try:
        subprocess.Popen(["osascript", "-e", script])
    except Exception as e:
        print(f"알림 실패: {e}", file=sys.stderr)


def open_buy_modal(page) -> None:
    """초기 페이지에서 쿠키 dismiss + '티켓 구매' 클릭으로 모달 오픈."""
    page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    time.sleep(3)
    try:
        page.locator("button:has-text('필요한 것만')").click(timeout=3000)
        time.sleep(1)
    except Exception:
        pass
    # 보이는 버튼 중 마지막 것이 sticky footer CTA — 더 안정적으로 클릭됨
    buy_buttons = page.locator("button:visible:has-text('티켓 구매')")
    cnt = buy_buttons.count()
    if cnt == 0:
        raise RuntimeError("'티켓 구매' 버튼 미발견")
    buy_buttons.nth(cnt - 1).scroll_into_view_if_needed(timeout=3000)
    buy_buttons.nth(cnt - 1).click(timeout=10000)
    # checkout iframe이 나타날 때까지 폴링 대기 (최대 20초)
    deadline = time.time() + 20
    while time.time() < deadline:
        if any("/checkout/" in f.url for f in page.frames):
            time.sleep(3)  # 내용 렌더 추가 대기
            return
        time.sleep(0.5)


def scrape_categories(page) -> dict[str, str]:
    """iframe(sellmodal-anchor)에서 카테고리별 상태 추출.

    iframe body 텍스트 패턴:
        ...카테고리 선택하기\n[STATUS]\n[NAME]\n[STATUS]\n[NAME]...
    """
    target_frame = None
    for f in page.frames:
        if "/checkout/" in f.url:
            target_frame = f
            break
    if target_frame is None:
        return {c: "missing" for c in CATEGORIES}

    try:
        txt = target_frame.inner_text("body", timeout=5000)
    except PWTimeout:
        return {c: "missing" for c in CATEGORIES}

    result: dict[str, str] = {}
    # 카테고리명 직전 라인이 상태 라벨
    lines = [ln.strip() for ln in txt.splitlines()]
    for cat in CATEGORIES:
        try:
            idx = lines.index(cat)
            status_line = lines[idx - 1] if idx > 0 else ""
            # '티켓 구매 가능' / '매진' / '매진 임박' 등 정규화
            if "매진 임박" in status_line or "Almost" in status_line:
                result[cat] = "almost_sold_out"
            elif "구매 가능" in status_line or "available" in status_line.lower():
                result[cat] = "available"
            elif "매진" in status_line or "Sold" in status_line:
                result[cat] = "sold_out"
            else:
                result[cat] = f"unknown({status_line!r})"
        except ValueError:
            result[cat] = "missing"
    return result


def diff_state(prev: dict[str, str], curr: dict[str, str]) -> list[str]:
    return [
        f"{cat}: {prev.get(cat, '-')} → {curr[cat]}"
        for cat in TARGET_CATEGORIES
        if prev.get(cat) != curr.get(cat)
    ]


def should_alert(curr: dict[str, str]) -> bool:
    """타겟 카테고리가 매진이 아닌 상태면 알림."""
    return any(
        curr.get(cat) in ("almost_sold_out", "available")
        for cat in TARGET_CATEGORIES
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="1회 스크랩 후 종료")
    ap.add_argument("--headless", action="store_true", help="브라우저 숨김 모드")
    args = ap.parse_args()

    prev: dict[str, str] = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            prev = json.load(f)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        try:
            while True:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                try:
                    open_buy_modal(page)
                    curr = scrape_categories(page)
                    if all(v == "missing" for v in curr.values()):
                        time.sleep(5)
                        curr = scrape_categories(page)
                except Exception as e:
                    print(f"[{ts}] 페이지 처리 실패: {e}", file=sys.stderr, flush=True)
                    if args.once:
                        return 1
                    time.sleep(INTERVAL)
                    continue

                print(f"[{ts}] {curr}", flush=True)

                # 모든 카테고리가 missing이면 일시적 실패 — 상태 저장/알림 스킵
                if all(v == "missing" for v in curr.values()):
                    print("  [skip] 전체 missing → 재시도", flush=True)
                    if args.once:
                        break
                    time.sleep(INTERVAL)
                    continue

                changes = diff_state(prev, curr)
                if changes and prev and should_alert(curr):
                    notify_modal(
                        "🎫 HYROX 티켓 구매 가능!",
                        "\n".join(changes) + "\n바로 브라우저로 가서 구매하세요.",
                    )
                elif changes and prev:
                    print(f"  변화(매진 유지): {changes}", flush=True)

                with open(STATE_PATH, "w", encoding="utf-8") as f:
                    json.dump(curr, f, ensure_ascii=False, indent=2)
                prev = curr

                if args.once:
                    break
                time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\n중지됨.")
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
