// 개인 레이어 읽개(personal.js)의 시험 — test_manage.py 가 node 로 부른다.
// 실패하면 까닭을 찍고 1 로 끝난다.
const assert = require("assert");
const P = require(process.argv[2]);

// 점 — CSV 와 JSON 이 같은 레이어가 된다
const csv = [
  "#format: gsm-personal-layer",
  "#version: 1",
  "#name: 시료, 2026",
  "#label: name",
  "#column: name | 시료 번호 | string",
  "#column: age | 연대 | number | U-Pb",
  "#column: n | 수 | integer",
  "id,lon,lat,name,age,n",
  'S1,127.1,37.5,"쉼표, ""따옴표""",172.4,3',
  "S2,,,빈 좌표,,",
  "S3,128,36, 앞뒤 공백 ,abc,",
].join("\r\n");
const c = P.parse(csv, "a.csv");
assert.strictEqual(c.kind, "point");
assert.strictEqual(c.name, "시료, 2026");
assert.strictEqual(c.count, 3);
assert.strictEqual(c.drawn, 2);
assert.strictEqual(c.meta.version, 1);
assert.deepStrictEqual(c.features[0].properties, { name: '쉼표, "따옴표"', age: 172.4, n: 3 });
assert.strictEqual(c.features[1].geometry, null);
assert.strictEqual(c.features[2].properties.name, " 앞뒤 공백 ");   // 잃지 않는다
assert.strictEqual(c.features[2].properties.age, "abc");            // 숫자가 아니면 글자 그대로
const j = P.parse(JSON.stringify(P.toGeoJSON(Object.assign({}, c))), "a.json");
assert.deepStrictEqual(j.features, c.features);
assert.deepStrictEqual(j.columns, c.columns);
const c2 = P.parse(P.toCSV(Object.assign({}, j)), "b.csv");
assert.deepStrictEqual(c2.features, c.features);

// 면 — WKT 칸이면 면이다
const poly = P.parse("geometry,name\r\n\"POLYGON ((0 0, 1 0, 1 1, 0 0))\",A\r\n", "p.csv");
assert.strictEqual(poly.kind, "polygon");
assert.strictEqual(poly.warnings.length, 0);
const mp = P.parseWKT("MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((5 5, 6 5, 6 6, 5 5)))");
assert.deepStrictEqual(P.parseWKT(P.wkt(mp)), mp);

// 섞이면 받지 않는다
assert.throws(() => P.parse(JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", geometry: { type: "Point", coordinates: [1, 2] }, properties: {} },
  { type: "Feature", geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }, properties: {} },
] }), "m.json"), /섞였다/);
// 좌표 칸이 없으면 받지 않는다
assert.throws(() => P.parse("a,b\r\n1,2\r\n", "x.csv"), /좌표 칸이 없다/);
// 범위 밖 좌표는 그 행만 문제로 남긴다
const far = P.parse("lon,lat,k\r\n127,37,a\r\n500,37,b\r\n", "f.csv");
assert.strictEqual(far.drawn, 1);
assert.strictEqual(far.problems.length, 1);
// 별명 좌표 칸은 읽되 경고한다
assert.strictEqual(P.parse("경도,위도\r\n127,37\r\n", "k.csv").warnings.length, 1);
// 선은 v1 에서 받지 않는다
assert.throws(() => P.parse(JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] }, properties: {} }] }), "l.json"), /그릴 좌표/);
// EUC-KR 로 저장한 CSV 도 읽는다 (엑셀)
const euckr = Buffer.from([0xc0, 0xa7, 0xb5, 0xb5]);   // "위도"
assert.strictEqual(P.decode(euckr).text, "위도");
console.log("ok");
