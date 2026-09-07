#!/bin/bash
# C-8 watchdog — 2026-09-07 개편
#  · 이 서버의 gunicorn 은 더 이상 쓰지 않는다(DB 미승인 IP .62 로 차단). 대신
#    엘리스 HTTPS 터널이 보는 5001 을 GPU박스(.61, 승인 IP)의 5002 로 포워딩해
#    URL 변경 없이 GPU박스 앱을 노출한다.
#  · vLLM 터널(8000)은 기존대로 유지.
LOG=~/c8_watchdog.log
while true; do
  # ① 앱 포워딩: 5001 → GPU박스 5002
  if ! curl -sf -m 5 -o /dev/null http://127.0.0.1:5001/ 2>/dev/null; then
    echo "$(date "+%F %T") [wd] 앱 포워딩 down -> 재기동" >> "$LOG"
    pkill -9 -f "5001:localhost:5002" 2>/dev/null; sleep 3
    setsid ssh -L 0.0.0.0:5001:localhost:5002 -p 18349 -i /home/elicer/gpu.pem \
      -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
      -o ExitOnForwardFailure=yes -o BatchMode=yes -o GatewayPorts=yes \
      elicer@central-02.tcp.tunnel.elice.io sleep infinity > /dev/null 2>&1 < /dev/null &
    sleep 8
  fi
  # ② vLLM 터널(8000) — 기존 유지
  if ! curl -sf -m 5 http://localhost:8000/v1/models >/dev/null 2>&1; then
    echo "$(date "+%F %T") [wd] vLLM 터널 down -> 재기동" >> "$LOG"
    pkill -9 -f "8000:localhost:8000" 2>/dev/null; sleep 3
    setsid bash -c "ssh -L 127.0.0.1:8000:localhost:8000 -p 18349 -i /home/elicer/gpu.pem -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o BatchMode=yes elicer@central-02.tcp.tunnel.elice.io sleep infinity" >/dev/null 2>&1 < /dev/null &
    sleep 8
  fi
  sleep 15
done
