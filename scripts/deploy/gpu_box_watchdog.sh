#!/bin/bash
# GPU박스 CCOP 앱 watchdog — 앱이 죽으면 재기동 (systemd 없는 환경)
# 기동: setsid nohup bash ~/coop_app/watchdog.sh > ~/coop_app/watchdog.log 2>&1 < /dev/null &
LOG=/home/elicer/coop_app/watchdog.log
while true; do
  if ! curl -sf -m 5 http://localhost:5002/ >/dev/null 2>&1; then
    echo "$(date "+%F %T") [wd] 앱 down -> 재기동" >> "$LOG"
    pkill -9 -f "coop_app/venv/bin/gunicorn" 2>/dev/null; sleep 3
    setsid nohup /home/elicer/coop_app/start_app.sh >> /home/elicer/coop_app/app.log 2>&1 < /dev/null &
    sleep 20
  fi
  sleep 15
done
