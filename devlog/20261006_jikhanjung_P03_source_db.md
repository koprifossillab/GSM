# 데이터소스 명세를 Django DB 로 — 관리 화면에서 고치고 이력을 남긴다 (계획)

2026-10-06 · `main` · jikhanjung

jikhanjung P02 는 데이터소스의 명세를 **`<DB 옆>/sources.json`** 에 두었다 — 사람이 정하는 것(조건·주기·돌리는 곳·명령·산출물)을
코드 PR·시험 없이 고치게 하려는 것이었다. 지금 고치는 길은 **서버에 들어가 그 파일을 손으로 고치는 것뿐**이고, 잘못 고치면 그 줄이
"건너뛴 줄" 로 뜰 뿐이다. 사람이 **"그 명세를 DB 에서 관리하는 게 제일 바람직해 보인다"** 고 했다(2026-10-06). 같은 목적(PR 없이 고친다)을
DB 가 더 잘 이룬다 — 이 문서는 그 길을 정한다.

## 1. 지금 (2026-10-06, 0.71.1 + #379)

| 무엇 | 어디에 | 꼴 |
|---|---|---|
| 명세 49 곳 | `/srv/GSM/db/sources.json` | JSON. 칸은 id·name·org·license·flags·schedule·runs_on·commands·outputs·kind·raw·docs·note |
| 씨앗 | 저장소 `data/sources.seed.json` | 컨테이너가 뜰 때 `sources_seed` 가 운영에 없는 id 만 덧붙인다 |
| 명세의 이력 | `/srv/GSM/db/sources_history/` | 바뀔 때마다 사본 한 장 |
| 받은 차례의 기록 | `/srv/GSM/db/store.sqlite` 의 `fetch_log` | sqlite, 받을 때마다 쌓인다 |
| Django `GSM.db` | `/srv/GSM/db/GSM.db` | 데이터소스 표가 없다 |

명세를 읽는 자리는 `sources.load()` 하나다 — `apps.py`(명령 → 데이터소스)·`fetchlog.sync`·`overview`(화면·healthz)·`sources_log`·
`sources_backfill`·`sources_seed`·`prune_raw`.

## 2. 왜 DB 인가

- **화면에서 고친다** — 서버에 들어가지 않는다. 고칠 때 칸을 검사해 **잘못된 값은 저장되지 않는다**(지금은 저장된 뒤에 "건너뛴 줄" 로 뜬다)
- **이력이 표 하나** — 누가·언제·무엇을(앞뒤 값). 지금의 `sources_history/` 사본 파일보다 찾고 견주기 쉽다
- **같은 틀이 이미 있다** — 레이어 카탈로그가 그렇게 돈다: 씨앗은 `data/*_layers.json`, `seed_catalog` 가 `Layer` 에 넣고, 사람은
  제목만 손질한다. 데이터소스도 `data/sources.seed.json` → `DataSource`. Django 의 폼·마이그레이션을 그대로 쓴다
- **이미 백업된다** — `GSM.db` 는 주간 백업에 든다. 49 줄이라 커질 걱정이 없다
- `store.sqlite` 는 받을 때마다 쌓이는 **기록**이라 성격이 다르다 — 거기에 그대로 둔다(명세는 GSM.db, 기록은 store.sqlite)

## 3. 정할 것 — 사람이

| 물음 | 갈래 | 권하는 것 |
|---|---|---|
| **A. 호스트가 명세를 어떻게 읽나** — 매시 cron(`run.sh`)이 명령 이름으로 데이터소스를 찾는다 | ① 호스트가 `GSM.db` 를 읽는다 ② DB 가 바뀔 때마다 `sources.json` 을 내보내고 호스트는 그 파일을 읽는다 | **①**. 호스트는 이미 `GSM_DB_PATH=/srv/GSM/db/GSM.db` 로 돌고, 매시 일이 **이미 `GSM.db` 에 쓴다**(`usage.record` → `UpstreamDay`). 새로 여는 길이 없다. ② 는 한 명세가 두 벌이 된다 |
| **B. 누가 고칠 수 있나** — 관리 화면은 계정을 묻지 않는다(지금은 읽기만이라 괜찮았다) | ① Django 계정(staff) 로그인 ② nginx 의 basic auth ③ 연구소 망에서만 열기 | **①**. `/GSM/admin/` 이 이미 붙어 있고 이력에 "누가" 가 남는다. **운영 `auth_user` 는 지금 0 명**이다 — 계정을 만드는 일(`createsuperuser`, 사람마다 하나)이 먼저다 |
| **C. 어디서 고치나** | ① 관리 화면의 "데이터소스" 탭에 고치기 ② Django admin(`/GSM/admin/`) | **① 을 목표로, ② 를 먼저** — admin 은 거의 공짜로 서지만 낯설다. 1 단계 뒤 바로 admin 으로 고칠 수 있게 하고, 2 단계에서 탭에 고치기를 들인다 |
| D. 씨앗을 운영에 어떻게 | 지금처럼 **없는 id 만 덧붙인다** — 사람이 고친 줄을 덮지 않는다 | 그대로. "씨앗과 다른 줄" 표시(#379)도 그대로 |

## 4. 꼴

```
DataSource                     ← 명세 한 줄 (pk = id 글, `^[a-z][a-z0-9_]*$`)
  name_ko · name_en · org · kind · runs_on · schedule · license · raw · note
  flags · commands · outputs · docs           JSONField (글의 목록)
  updated_at · updated_by(→ User, null)
DataSourceChange               ← 이력. 고칠 때마다 한 줄
  source(id 글 — 지운 줄도 남게 FK 가 아니다) · at · by(→ User, null) · origin(admin·tab·seed·import)
  before · after               JSONField (줄 전체)
```

- 검사는 지금의 `sources.problems_of` 를 모델의 `clean()` 으로 옮긴다 — 화면·admin·명령이 같은 검사를 지난다
- `sources.load()` 는 **이름과 돌려주는 꼴(`Spec`)을 지킨다** — 부르는 자리 일곱을 고치지 않으려고. 속만 DB 를 읽는다
- `sources.coverage()`(명령·구운 파일이 빠짐없이 든다) 시험은 **씨앗**을 본다 — 그대로
- 명세가 DB 에 없으면(새 설치) 씨앗을 넣는다 — `seed_catalog` 처럼 컨테이너가 뜰 때

## 5. 차례

한 단계마다 브랜치·PR·devlog 하나. 병합·판은 판 세션이 한다.

| 단계 | 브랜치 | 담는 것 |
|---|---|---|
| 1 | `feature/source-db` | 모델·마이그레이션, `sources.load()` 의 속을 DB 로, `sources_seed` 가 DB 에(없는 id 만), **운영 `sources.json` 을 한 번 DB 로 옮기는 마이그레이션 명령**(`sources_import`, 이력에 `import` 한 줄), admin 등록(읽기·고치기 — B·C 의 ② 로), healthz·화면은 그대로 |
| 2 | `feature/source-edit` | 관리 화면 "데이터소스" 탭에 고치기(로그인한 staff 만, 줄을 펼친 자리의 폼), 이력을 펼친 줄에, `sources.json`·`sources_history/` 를 읽는 길을 지운다 |

1 단계가 끝나면 **서버에서 파일을 고칠 일이 없다**(admin 으로). 2 단계는 쓰기 편하게 하는 것이다.

## 6. 옮기는 날

1. 1 단계가 나간 판에서 컨테이너가 뜨면 `sources_import` 가 운영의 `sources.json`(사람이 고친 것까지)을 DB 로 — **DB 가 비었을 때만**.
   이미 차 있으면 아무것도 하지 않는다(두 번 옮겨 덮지 않게)
2. `sources.json`·`sources_history/` 는 지우지 않고 남긴다 — 한 판 동안 둘이 같은지 `sources_log` 로 본다. 2 단계에서 읽는 길을 지우고, 파일은
   사람이 치운다
3. 주간 백업의 `sources.json`·`sources_history/` 줄은 2 단계에서 뺀다(GSM.db 에 든다)

## 7. 넣지 않은 것

- **"지금 받기" 단추** — P02 와 같다. 고치기가 서고 계정이 생기면 그때 다시 본다
- **기록 표(`fetch_log`)를 GSM.db 로** — 받을 때마다 쌓여 백업이 부푼다. `store.sqlite` 에 둔다(뒤의 적재 ② 도 거기다)
- 레이어 카탈로그를 이 틀로 — 이미 DB 다
- 중계 상류 여든 남짓의 조건(`상류_조건표.md`)을 이 표로 — P02 와 같다

## 8. 위험

- **호스트와 컨테이너가 같은 `GSM.db` 를 연다** — 지금도 그렇다(`UpstreamDay`). `GSM.db` 는 `journal_mode=delete` 라 쓰기가 겹치면 잠깐 막힌다.
  명세 읽기는 짧은 SELECT 하나라 늘지 않는다. 문제가 되면 WAL 로 바꾸는 것은 따로
- **계정이 없는 채로 2 단계가 나가면** 아무도 못 고친다 — B 의 계정 만들기를 1 단계 배포 뒤 할 일에 적는다
- 옮기는 날 운영의 `sources.json` 이 깨져 있으면 — `sources_import` 는 떠 둔 판(`sources_history/` 의 끝)을 쓴다. 지금 `load()` 와 같다
- 판을 되돌리면(0.71 로) 명세가 다시 파일에서 읽힌다 — 1 단계 동안 파일을 지우지 않는 까닭이다

## 9. 확인하는 법

- 1 단계 뒤 — 운영 `sources.json` 의 49 줄이 DB 에 그대로(`sources_log` 의 목록이 같다), 화면·healthz 의 수가 앞과 같다, admin 에서 한 줄을
  고치면 화면에 곧 뜨고 `DataSourceChange` 에 한 줄
- 2 단계 뒤 — 로그인하지 않으면 고치기가 안 보인다, 틀린 값(없는 주기)은 저장되지 않고 까닭이 뜬다, 고친 줄의 펼친 자리에 이력
