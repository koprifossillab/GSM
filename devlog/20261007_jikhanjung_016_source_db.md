# 데이터소스 명세와 기록을 `GSM.db` 로 (P03 1 단계)

2026-10-07 · `feature/source-db` · jikhanjung

jikhanjung P03 의 1 단계. 명세(`<DB 옆>/sources.json`)를 `DataSource` 로, 받은 차례의 기록(`store.sqlite` 의 `fetch_log`)을 `FetchRun` 으로
옮겼다. 명세는 Django admin 에서 고치고 고칠 때마다 `DataSourceChange` 에 앞뒤 줄이 남는다. 받은 판의 정보(`manifest.json`)는 원본 폴더에
그대로다. 사람이 정한 셋(호스트는 `GSM.db` 를 읽는다·staff 계정·admin 다음 탭)대로다.

## 1. 무엇을 정했나

1. **바깥 꼴을 지켰다** — `sources.load()` 는 여전히 `Spec`(줄의 dict 목록)을, `fetchlog` 의 `latest`·`history_many`·`write`·`sync` 는 같은
   이름·같은 dict 를 준다(`started_at` 은 이 서버 시간대의 ISO 글). 부르는 자리(`apps.py`·화면·healthz·`sources_log`·`sources_backfill`·`prune_raw`)를
   고치지 않았다. 속만 ORM 이다
2. **`started_at` 은 `DateTimeField`** — UTC 로 적혀 시간대가 섞여도 때의 순서가 맞다(#375 의 `julianday` 가 하던 일). 시간대만 다르고 같은 때인
   두 줄은 하나가 된다(`fetch_run_once`). 때를 못 읽는 줄은 버린다 — 파일 시절에는 아무 글이나 들어갔다
3. **명세의 순서는 `order` 칸** — 파일 시절 줄의 차례를 지킨다. 씨앗이 덧붙이는 것은 끝에
4. **씨앗과의 견주기는 빈 칸을 채워서**(`_normal`) — 씨앗은 빈 칸(`flags`·`org` …)을 적지 않고 표는 모든 칸을 가진다. 그대로 견주면 49 곳이
   다 "씨앗과 다름" 으로 뜬다
5. **옮기기는 `sources_import` 한 명령, 표가 비었을 때만** — `entrypoint-web.sh` 가 `migrate` 뒤·`sources_seed` 앞에 부른다. 사람이 서버에서 고친
   명세가 씨앗보다 먼저 들어가야 한다. 파일이 깨졌으면 마지막으로 떠 둔 판(`sources_history/`)을. 명세가 바뀐 것을 적던 `_spec` 기록 줄은
   옮기지 않는다 — 그 몫은 `DataSourceChange` 다. 호스트 기록을 읽은 자리(`host_offset`)도 옮긴다(`FetchRunMark`)
6. **"명세를 고친 때" 에 옮겨 온 것은 넣지 않는다** — 배포 직후 탭 머리에 옮긴 때가 "고친 때" 로 뜨면 사람이 고친 줄 안다
7. **admin** — 명세는 고치고(id 는 만든 뒤 못 바꾼다 — 기록이 글로 가리킨다), 갈래·주기·돌리는 곳은 고르는 칸(검사와 같은 표), 저장 전에 같은
   검사(`DataSource.clean` → `problems_of`). 저장·지우기마다 이력. 이력과 받은 차례는 읽기만
8. **호스트는 `GSM.db` 를 열지 않는다** (사람, 같은 날 — "호스트가 DB 를 건드려야 할 필요가 있으면 컨테이너를 통해"). 계획은 "호스트가
   `GSM.db` 를 읽는다" 였다 — 매시 일이 이미 `UpstreamDay` 에 쓰고 있었으니 새로 여는 길이 없다고 봤다. 사람은 읽기도 위험하다고 봤고, 그 말이
   맞다 — 읽기만이어도 두 계정(호스트 paleoadmin·컨테이너)이 한 파일의 잠금과 스키마에 묶이고, 판을 올리는 사이 호스트의 앱 사본이 DB 보다
   앞서거나 뒤처질 수 있다
   - 호스트에서는 명세를 읽지 않고(`apps.py`) **명령 이름을 데이터소스 자리에** 적는다 — 컨테이너가 옮겨 적을 때(`fetchlog.sync`) 데이터소스로 바꾼다
   - 이미 있던 쓰기도 뗐다 — 호스트의 상류 호출 수는 `upstream_host.jsonl` 에 남기고 컨테이너가 같은 차례에 `UpstreamDay` 에 더한다(`usage.sync_host`).
     jsonl 을 읽은 자리를 기억하는 틀은 기록과 함께 쓴다(`fetchlog.new_lines`)
   - **호스트의 설정은 DB 엔진이 dummy 다**(`GSM_RUN_PLACE=host`) — 실수로 열면 곧장 깨진다. DB 를 여는 명령(`sources_log`·`sources_import`·
     `sources_seed`·`sources_backfill`·`prune_raw`)은 호스트에서 부르면 "컨테이너 안에서 부른다" 며 멈춘다
   - **주간 백업은 아직 호스트가 `GSM.db` 를 읽는다**(`weekly_backup.sh` 의 sqlite backup, 읽기 전용) — 이 규칙대로라면 컨테이너를 거쳐야 한다.
     백업 스크립트라 따로 고친다(TODOs)
   - WAL 은 지금 바꾸지 않는다(사람) — 사용자 트랜잭션이 있는 것이 아니다. 호스트가 DB 를 열지 않게 되어 바꿀 때는 컨테이너만 보면 된다
9. 관리 화면 탭의 안내를 "admin 에서 고친다" 로 바꾸고 admin 의 명세 목록으로 가는 링크를 달았다

## 2. 버린 것

- **매니페스트도 DB 로** — P03 §3 E. 원본 폴더가 스스로를 설명해야 하고 `prune_raw` 의 안전장치가 그것을 본다
- **`started_at` 을 글로 두기** — 정렬마다 `julianday` 를 거치고, 시간대만 다른 같은 때가 두 줄이 된다
- **`load()` 에 캐시** — 파일 시절에는 mtime 으로 들고 있었다. 49 줄 SELECT 하나라 두지 않았다 — admin 에서 고친 것이 곧 보인다
- 파일·`store.sqlite` 를 지우기 — 한 판 동안 남긴다(P03 §6). 판을 되돌려도 읽힌다

## 3. 확인

- 시험 — `test_sources`(씨앗이 표를 오가도 같다·비었을 때만 옮긴다·씨앗보다 먼저·`_spec` 은 빼고·시간대만 다른 줄은 하나·admin 에서 고치면
  이력과 고친 사람·틀린 값은 저장되지 않는다·지우면 뒤가 빈 줄·기록은 읽기만), `test_fetchlog`(호스트는 DB 를 열지 않는다 — 질의 0·명세를 읽지 않음·DB 명령은 멈춤,
  호스트 설정의 엔진은 dummy, 명령 이름을 데이터소스로, 상류 호출 수를 한 번만 더한다, 쓰기가 깨져도 명령은 돈다, 때를 못 읽는 줄, 관리 화면의 질의 수가
  데이터소스 수와 상관없다), `test_rawstore`. 전체 2 109 개 통과
- **옮기는 날을 미리** — 운영의 `GSM.db`·`store.sqlite`·`sources.json` 사본에 `migrate` → `sources_import` → `sources_seed`. 명세 49 곳이 차례·칸까지
  파일과 같고, 기록 95 줄이 다 옮겨지고(데이터소스 35 곳), 화면의 수(전체 49·기록 없음 14)가 앞과 같다. `prune_raw --dry-run` 도
  돈다. admin 의 목록·고치기 화면을 찍어 봤다
- **호스트로 진짜 한 차례** — `GSM_RUN_PLACE=host` 로 매시 일 하나(`fetch_recent_quakes`, USGS 한 번)를 빈 자리에서: 일은 끝나고, 남은 것은
  `fetch_log_host.jsonl`·`upstream_host.jsonl` 두 줄, `GSM.db` 는 생기지도 않았다. 호스트의 `sources_log` 는 "컨테이너 안에서" 로 멈춘다

## 4. 배포 뒤 (판 세션)

- **staff 계정을 만든다** — 운영 `auth_user` 가 0 명이다. 계정이 없으면 admin 으로도 못 고친다(`manage.py createsuperuser`, 사람마다 하나)
- 컨테이너 기록에 `sources_import` 의 두 줄("명세 — 49 곳을 옮겼다"·"기록 — n 줄을 옮겼다")이 떴는지 본다
