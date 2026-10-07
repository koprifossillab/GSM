# 주간 백업을 월요일 01:10 으로 — 매시 받기(:40)와 비낀다

2026-10-07 · `fix/backup-at-10` · koprifossillab

## 왜

#399·#400(jikhanjung 023·024)을 검토하다 보니, 주간 백업 ① 의 tar 가 `<DB 옆>/fetch_log_host/` 를 그 자리에서 그대로 담는데
#400 부터 매시 일 넷이 매 차례 그 폴더의 오늘 파일에 덧붙이고, #399 는 매시 차례 끝에 그제 파일을 지운다. 주간 백업(월 01:40)과
매시 받기(매시 :40)가 같은 분에 돌아, tar 가 담는 몇 초 사이에 덧붙이거나 지우면 GNU tar 가 "file changed as we read it"·"File removed
before we read it" 로 1 을 내고 그 주의 ① 이 통째로 실패한다.

## 고친 것

**백업을 01:10 으로 옮겼다**(사람, 2026-10-07). 그 분에는 다른 일이 없다 — 매시 :20(DiaRUGA)·:25(ForGIA)·:40(GSM), 02:30(월 WegenersDream).
① 은 첫 몇 분에 끝나므로 :40 의 매시 차례와 만나지 않는다. 운영 crontab 은 바로 고쳤고(`crontab - < 파일` 뒤 `crontab -l` 과 견줘 봤다),
저장소의 조각(`deploy/host/crontab.GSM`)·`weekly_backup.sh` 머리말·`docs/백업.md`·HANDOFF 를 맞췄다.

## 버린 것

- **`fetch_log_host/` 를 먼저 `$STAGE` 로 복사해 담기** — 가장 단단하지만 #399·#400 이 손대는 `weekly_backup.sh` 를 또 고치게 된다. 시각을
  비끼면 겹칠 일 자체가 없다. 매시 차례가 한 시간 넘게 늘어지면(`timeout 3000`) 다시 볼 일이다
- **tar 의 경고를 끄고 1 을 받아들이기** — 담다 만 파일을 성공으로 넘긴다
