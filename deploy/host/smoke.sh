#!/bin/bash
# 올린 뒤 살아 있는지 본다. 돌아가는 장비에서 돌린다.
#
#   deploy/host/smoke.sh [주소]      기본 http://127.0.0.1:9310/GSM/
#
# 상류를 타는 것(타일·속성)은 인증키가 있어야 하므로, 키가 없으면 그 둘은
# 건너뛰고 화면과 카탈로그만 본다.
set -uo pipefail

BASE="${1:-http://127.0.0.1:9310/GSM/}"
BASE="${BASE%/}"
fail=0

check() {
    local name="$1" url="$2" want="$3"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$url")
    if [[ "$code" == "$want" ]]; then
        printf '  %-22s %s\n' "$name" "$code"
    else
        printf '  %-22s %s  (바란 것 %s)\n' "$name" "$code" "$want" >&2
        fail=1
    fi
}

echo "== $BASE =="
check "화면"      "$BASE/"          200
check "카탈로그"  "$BASE/catalog/"  200
check "점묶음"    "$BASE/pointsets/" 200
check "좌표"      "$BASE/coords/parse/?q=37.5,127.0" 200

echo "== 카탈로그에 든 레이어 =="
curl -s -m 20 "$BASE/catalog/" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  레이어군", len(d["groups"]), "· 레이어", sum(len(g["layers"]) for g in d["groups"]))' \
  || { echo "  카탈로그를 읽지 못했다" >&2; fail=1; }

if [[ $fail -eq 0 ]]; then
    echo "== 다 돈다 =="
else
    echo "== 멈춘 것이 있다 ==" >&2
fi
exit $fail
