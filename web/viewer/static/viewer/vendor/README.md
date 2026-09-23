# 담아 둔 것

**OpenLayers 9.2.4** — `ol.js`, `ol.css`

CDN 에서 불러오지 않고 저장소에 담는 까닭은 둘이다.

1. **KOPRI 망이 TLS 를 가로챈다.** 체인 끝이 `CN=KOPRI SSL` 이라, 그 루트를
   안 가진 프로그램은 바깥 CDN 을 못 읽는다. 브라우저는 대개 루트가 깔려 있어
   되지만, 되고 안 되고가 그 컴퓨터의 설정에 달리는 것을 제품에 두지 않는다
2. **형제 저장소(DiaRUGA·ForGIA)에 바깥 링크가 하나도 없다.** 같은 집 규칙이다

받은 자리와 확인값:

```
https://cdn.jsdelivr.net/npm/ol@9.2.4/dist/ol.js
https://cdn.jsdelivr.net/npm/ol@9.2.4/ol.css
```

판을 올릴 때는 두 파일을 같이 받고 이 문서의 판 번호를 고친다.
118c329cf58d41122a4097f9a8abe5f52b56eb80cfc7df83c5ccef8d7b976fbe  ol.js
b46a588ec4f9db4f824ea15ab2b78bd9d1dfb17172a785c69e23fa8953db437f  ol.css
