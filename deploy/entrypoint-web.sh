#!/bin/bash
# 뷰어 컨테이너 시작.
set -e

cd /app/web

# 이미 적용돼 있으면 아무 일도 하지 않는다. 새 장비에 올릴 때를 위해 둔다.
python manage.py migrate --noinput

# 카탈로그가 비어 있으면 저장소에 든 씨앗으로 채운다. 상류를 타지 않는다.
python manage.py seed_catalog || echo "씨앗을 넣지 못했다 — 화면은 뜬다"

exec gunicorn gsmweb.wsgi:application \
    --bind 0.0.0.0:9310 \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
