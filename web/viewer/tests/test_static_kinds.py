"""정적 판의 극지 상류 — `static_tables.py` 와 `static-kinds.js` (wetherilli 161). 상류를 부르지 않는다.

JS 는 문자열과 꼴로 지킨다. node 가 있으면 JS 의 손질(지질시대 옮기기·NPI·EMODnet·GEUS 이름 표)을 파이썬의 것과 같은 입력으로
대조한다 — 두 벌이 갈라지면 깨진다. node 가 없으면(CI) 그 대조만 건너뛴다.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from viewer import emodnet, geus, i18n, kopri, npolar, static_tables, views

JS = Path(__file__).resolve().parents[1] / "static" / "viewer" / "static-kinds.js"


class Tables(SimpleTestCase):
    def setUp(self):
        self.t = static_tables.tables()

    def test_JSON_으로_뜬다(self):
        self.assertLess(len(json.dumps(self.t, ensure_ascii=False)), 200_000)

    def test_문의_표를_그대로(self):
        self.assertEqual(self.t["npolar"]["tiles"], npolar.TILES)
        self.assertEqual(self.t["npolar"]["friendly"], list(npolar.FRIENDLY.items()))
        self.assertEqual(self.t["geus"]["friendly"], geus.FRIENDLY)
        self.assertEqual(self.t["emodnet"]["friendly"], [list(p) for p in emodnet.FRIENDLY]
                         if isinstance(self.t["emodnet"]["friendly"][0], list) else list(emodnet.FRIENDLY))
        self.assertEqual(self.t["age"]["words"], i18n.AGE_WORDS_KO)
        self.assertEqual(self.t["maxFeatures"], views.MAX_FEATURES)

    def test_KPDC_지도_서버는_싣고_연구실_것은_싣지_않는다(self):
        self.assertEqual(set(self.t["kopri"]["wms"]), set(kopri.WMS))
        # 이름 표(`propEn`)는 글자뿐이다 — 레이어·주소가 든 자리만 본다
        text = json.dumps({k: v for k, v in self.t.items() if k not in ("propEn", "linkEn")}, ensure_ascii=False)
        for lab in ("geo3al", "phyloserver", "peninsula"):
            self.assertNotIn(lab, text)

    def test_점_명세에_주소와_열이_있다(self):
        portal = self.t["grportal"]["points"]["grportal:geochron"]
        self.assertTrue(portal["url"].endswith("/FeatureServer/0/query"))
        self.assertEqual(portal["fields"]["age"]["from"], "age_num")
        rock = self.t["npolar"]["points"]["npolar:rock_archive"]
        self.assertEqual((rock["oid"], rock["style"]), ("ObjectId", "rock"))


class Script(SimpleTestCase):
    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")
        # 주석을 뺀 코드 — 주석은 서버 판과 견주느라 서버 주소를 적는다
        self.code = re.sub(r"/\*.*?\*/|//[^\n]*", "", self.js, flags=re.S)

    def test_꼴(self):
        self.assertIn("window.GSM_STATIC_KINDS = KINDS", self.js)
        for up in ("geus", "npolar", "grportal", "pgc", "emodnet", "kopri"):
            self.assertIn(f"KINDS.{up} =", self.js)

    def test_서버를_부르지_않는다(self):
        for path in ('BASE + "wms"', "featureinfo/", "/GSM/", 'BASE + "points'):
            self.assertNotIn(path, self.code)

    def test_상류_주소를_박지_않는다(self):
        # 주소는 빌드가 서버의 문에서 떠 싣는 표에서 읽는다 — 상류가 바뀌면 문 하나만 고친다
        for host in ("geodata.npolar.no", "data.geus.dk", "arcgis.com", "emodnet-geology", "kpdcgeo"):
            self.assertNotIn(host, self.code)

    def test_GEUS_는_화면_한_장으로_정사각을_피해(self):
        self.assertIn("ol.source.ImageWMS", self.js)
        self.assertIn("imageLoadFunction: notSquare", self.js)
        self.assertIn('stored("gsm.key.geus")', self.js)

    def test_저장소는_try_로(self):
        self.assertIn("try { return localStorage.getItem(key)", self.js)


class SameAsPython(SimpleTestCase):
    """JS 와 파이썬이 같은 입력에 같은 답을 내는지 — node 가 있을 때만"""

    def test_손질이_같다(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 가 없다")
        ages = ["late Paleocene", "Early - Middle Triassic", "Carboniferous - Permian", "Neoproterozoic (?)",
                "Palaeoproterozoic", "Early Palaeozoic", "Cambrian and/or Ordovician", "Middle Jurassic ?",
                "Statherian 1 (1800-1770 Ma)", "? Oligocene - Miocene", "Early"]
        npi = [{"NAME": "Hecla Hoek", "AGE_PERIOD": "Neoproterozoic", "AGE_BASE": "Early Palaeozoic",
                "URL": "https://example.org/x", "Date": "20230910", "Length_km": "3,595676", "GEO_CODE": "  "},
               {"Stratigraphic Unit": "Billefjorden Group", "URL": "javascript:alert(1)", "AGE_TOP": "late Paleocene"}]
        emo = [{"label_litho": "limestone", "label_age": "Pennsylvanian - Permian", "scale": 5000000,
                "reference": "Reference: Asch 2005", "name": None},
               {"folk_7cl_txt": "4. Mixed sediment", "fault_name": "n/a", "scale": "2000000"}]
        plain = "Layer 'grl'\n  Feature 733: \n    gu_name = 'Rapakivi Suite'\n    ics_min_age_num = '1600.000000'\n    rgb = '1'\n"
        expected = {"ages": [i18n.age_ko(a) for a in ages], "npi": [npolar.friendly(p, "ko") for p in npi],
                    "emo": [emodnet.friendly(p, "ko") for p in emo],
                    "plain": [geus.friendly(f["properties"]) for f in geus.parse_plain(plain)]}
        harness = """
const fs = require('fs'); const inp = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
global.window = {GSM_STATIC_TABLES: inp.tables}; global.document = {documentElement: {lang: 'ko'}};
global.localStorage = {getItem: () => null}; global.sessionStorage = {getItem: () => null}; global.ol = {};
eval(fs.readFileSync(process.argv[3], 'utf8')); const H = window.GSM_STATIC_HELPERS;
console.log(JSON.stringify({ages: inp.ages.map(H.ageKo), npi: inp.npi.map(H.npiFriendly), emo: inp.emo.map(H.emodFriendly),
  plain: H.parsePlain(inp.plain).map(f => H.geusFriendly(f.properties))}));
"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "in.json").write_text(json.dumps({"tables": static_tables.tables(), "ages": ages, "npi": npi,
                                                        "emo": emo, "plain": plain}, ensure_ascii=False), "utf-8")
            Path(tmp, "h.js").write_text(harness, "utf-8")
            out = subprocess.run([node, str(Path(tmp, "h.js")), str(Path(tmp, "in.json")), str(JS)],
                                 capture_output=True, text=True, timeout=60, check=True).stdout
        self.assertEqual(json.loads(out), json.loads(json.dumps(expected, ensure_ascii=False)))
