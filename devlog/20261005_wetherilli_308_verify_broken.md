# 대조에서 깨진 레이어 고치기

2026-10-05 · `fix/verify-broken` · wetherilli

운영의 `verify_layers --redo` 가 오류·빈 그림으로 적은 레이어를 하나씩 본다.

## 카메룬 IRGM 단층 — 스타일을 우리가 보낸다

- 증상: `GetMap` 이 예외 XML — `msLoadMSRasterBufferFromFile(): unable to open file /carto/wxs/1GG/THRUSTFAULT`. BRGM 의 MapServer 가
  단층 기본 스타일의 기호 파일을 잃었다. 스타일 이름은 `default` 하나뿐이라 다른 이름으로 고를 수 없다
- 고친 것: 그 레이어를 부를 때만 `SLD_BODY` 로 검은 선 하나(1.2 px)를 보낸다(`brgm.IRGM_SLD`). MapServer 가 받아 그린다(19 KB, 카메룬 전체).
  역단층·정단층을 가르던 기호는 잃지만 선은 다 선다. 상류가 기호 파일을 되살리면 `IRGM_SLD` 에서 지운다
- 버린 것: 레이어를 내리기 — 그릴 길이 있는데 내릴 까닭이 없다
