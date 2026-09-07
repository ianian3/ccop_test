#!/bin/bash
cd /home/elicer/coop_app
# gunicorn — debug 비활성(Werkzeug 디버거는 임의 코드 실행 위험) + 0.0.0.0 바인딩(터널 접근)
exec ./venv/bin/gunicorn -w 4 -b 0.0.0.0:5002 --timeout 180 --access-logfile - run:app
