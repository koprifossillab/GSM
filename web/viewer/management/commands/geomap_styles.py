"""GeoMAP 이 딸려 준 QGIS 스타일(.qml)에서 색을 뽑아 `data/geomap_styles.json` 에 적는다.

    manage.py geomap_styles --qml-dir <GeoMAP>/QGIS/Support/layerFiles

**색을 사람이 옮겨 적지 않는다.** 레이어 카탈로그를 GetCapabilities 에서 씨앗으로
뽑는 것과 같은 까닭이다 (CLAUDE.md "상류의 함정"). GNS 가 GeoMAP 과 함께 낸
스타일이 원본이고, 우리는 그것을 읽을 수 있는 표로 옮길 뿐이다. 판이 오르면
이 명령을 다시 부른다.

평소에는 부르지 않는다 — 뽑아 둔 JSON 이 저장소에 들어 있다. 운영 장비에는
.qml 이 없다.

읽는 것은 QGIS 규칙 렌더러의 좁은 부분뿐이다 — `FIELD = 값`, `FIELD IS NULL`
을 `AND`·`OR` 로 이은 필터, `SimpleFill`·`SimpleLine` 심볼. 그 밖의 것이 나오면
멈춘다. 모르는 식을 대충 넘기면 색이 조용히 틀린다.

**자료 품질(quality) 레이어에는 GNS 의 스타일이 없다.** 그 색만은 여기서 정한다
(`QUALITY_STYLE`). 1–5 등급의 뜻은 gpkg 의 설명(gpkg_contents)을 줄인 것이다.
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

#: 뽑을 스타일 → (.qml 파일, 표, 갈래)
SOURCES = {
    "simple_geology": ("ATA geological units - Simple geology.qml", "units", "fill"),
    "simple_lithology": ("ATA geological units - Simple lithology.qml", "units", "fill"),
    "chronostratigraphic": ("ATA geological units - Chronostratigraphic symbols.qml", "units", "fill"),
    "faults": ("Mapped faults.qml", "faults", "line"),
}

#: 자료 품질의 색. GNS 스타일이 없어 여기서 정한다 — 5(좋다) 초록 ~ 1(나쁘다) 빨강.
#: 0 은 "그릴 지질이 없는 칸" 이라 그리지 않는다.
QUALITY_STYLE = {
    "table": "quality", "kind": "fill", "fields": ["QUALITY"],
    "source": "GSM (GNS 스타일 없음 — 색은 여기서 정했다)",
    "rules": [
        {"label": label, "group": "Data quality",
         "when": [{"QUALITY": q}], "fill": fill + [120], "outline": fill + [200], "width": 1}
        for q, fill, label in (
            (5, [26, 152, 80], "5 — mapped at 1:250 000 or more detailed"),
            (4, [145, 207, 96], "4 — regional-scale maps, cover from imagery"),
            (3, [254, 224, 139], "3 — regional maps > 1:250 000, limited checks"),
            (2, [252, 141, 89], "2 — large-scale interpretation, little review"),
            (1, [215, 48, 39], "1 — little or no information attributed"),
        )
    ],
}

_ATOM = re.compile(
    r"""^\s*"?(?P<field>[A-Za-z_][A-Za-z0-9_]*)"?\s*
        (?:(?P<isnull>IS\s+NULL)|=\s*(?P<value>'(?:[^']|'')*'|-?\d+(?:\.\d+)?))\s*$""",
    re.X | re.I)
#: 한 번의 스타일에서 받는 단위. QGIS 의 "MM" 은 화면 96 dpi 로 픽셀에 옮긴다
_UNIT_PX = {"Pixel": 1.0, "MM": 96 / 25.4, "Point": 96 / 72}


def parse_filter(text: str) -> list:
    """QGIS 필터 → OR 로 묶인 AND 조건들. `[{"FIELD": 값, …}, …]`.

    `IS NULL` 은 값 None 으로 적는다. 괄호·LIKE·IN 은 받지 않는다 — 지금의
    .qml 들에 없고, 대충 읽으면 색이 조용히 틀린다.
    """
    if not text or not text.strip():
        return [{}]
    if "(" in text or ")" in text:
        raise ValueError(f"괄호가 든 필터는 읽지 못한다: {text[:80]}")
    out = []
    for clause in re.split(r"\s+OR\s+", text.strip(), flags=re.I):
        cond = {}
        for atom in re.split(r"\s+AND\s+", clause, flags=re.I):
            m = _ATOM.match(atom)
            if not m:
                raise ValueError(f"모르는 식이다: {atom[:80]}")
            if m.group("isnull"):
                value = None
            else:
                raw = m.group("value")
                if raw.startswith("'"):
                    value = raw[1:-1].replace("''", "'")
                else:
                    value = float(raw) if "." in raw else int(raw)
            cond[m.group("field")] = value
        out.append(cond)
    return out


def _and(a: list, b: list) -> list:
    """(A1 OR A2) AND (B1 OR B2) → 풀어 쓴 OR."""
    return [dict(x, **y) for x in a for y in b]


def _rgba(text: str) -> list:
    parts = [int(float(p)) for p in (text or "0,0,0,255").split(",")[:4]]
    return (parts + [255])[:4]


def _props(layer) -> dict:
    out = {p.get("k"): p.get("v") for p in layer.findall("prop")}
    # QGIS 3.26 부터는 <Option name=… value=…> 로 적는다
    for opt in layer.iter("Option"):
        if opt.get("name") and opt.get("value") is not None:
            out.setdefault(opt.get("name"), opt.get("value"))
    return out


def _width(props, key, unit_key) -> float:
    return round(float(props.get(key) or 1) * _UNIT_PX.get(props.get(unit_key, "Pixel"), 1.0), 2)


def parse_symbol(symbol) -> dict:
    fills, strokes = [], []
    for layer in symbol.findall("layer"):
        if layer.get("enabled", "1") == "0":
            continue
        cls, p = layer.get("class"), _props(layer)
        if cls == "SimpleFill":
            fills.append({
                "fill": _rgba(p.get("color")) if p.get("style", "solid") != "no" else None,
                "outline": _rgba(p.get("outline_color")) if p.get("outline_style") != "no" else None,
                "width": _width(p, "outline_width", "outline_width_unit"),
                "pattern": p.get("style", "solid"),
            })
        elif cls == "SimpleLine":
            dash = None
            if p.get("use_custom_dash") == "1" and p.get("customdash"):
                scale = _UNIT_PX.get(p.get("customdash_unit", "Pixel"), 1.0)
                dash = [round(float(v) * scale, 2) for v in p["customdash"].split(";")]
            strokes.append({"color": _rgba(p.get("line_color")),
                            "width": _width(p, "line_width", "line_width_unit"),
                            "dash": dash})
        else:
            raise ValueError(f"모르는 심볼 갈래다: {cls}")
    if fills:
        f = fills[0]
        return {"fill": f["fill"], "outline": f["outline"], "width": f["width"],
                "pattern": f["pattern"]}
    return {"strokes": strokes}


def parse_qml(path: Path, table: str, kind: str) -> dict:
    root = ET.parse(path).getroot()
    renderer = root.find(".//renderer-v2")
    if renderer is None or renderer.get("type") != "RuleRenderer":
        raise ValueError(f"규칙 렌더러가 아니다: {path.name}")
    symbols = {s.get("name"): parse_symbol(s) for s in renderer.find("symbols")}

    rules, fields = [], []

    def walk(node, cond, group):
        for rule in node.findall("rule"):
            if rule.get("checkstate") == "0":
                continue
            here = _and(cond, parse_filter(rule.get("filter", "")))
            label = (rule.get("label") or "").strip()
            if rule.get("symbol") is not None:
                for clause in here:
                    for f in clause:
                        if f not in fields:
                            fields.append(f)
                rules.append(dict({"label": label, "group": group, "when": here},
                                  **symbols[rule.get("symbol")]))
            walk(rule, here, label if rule.get("symbol") is None else group)

    walk(renderer.find("rules"), [{}], "")
    return {"table": table, "kind": kind, "fields": fields, "source": path.name, "rules": rules}


def dumps(out: dict) -> str:
    """규칙 하나를 한 줄에. 사람이 diff 로 읽기 좋게 하려는 것이다."""
    lines = ["{"]
    head = [k for k in out if k != "styles"]
    for k in head:
        lines.append(f" {json.dumps(k, ensure_ascii=False)}: {json.dumps(out[k], ensure_ascii=False)},")
    lines.append(' "styles": {')
    names = list(out["styles"])
    for i, name in enumerate(names):
        style = out["styles"][name]
        lines.append(f"  {json.dumps(name)}: {{")
        for k in [k for k in style if k != "rules"]:
            lines.append(f"   {json.dumps(k)}: {json.dumps(style[k], ensure_ascii=False)},")
        lines.append('   "rules": [')
        rules = style["rules"]
        for j, rule in enumerate(rules):
            comma = "," if j < len(rules) - 1 else ""
            lines.append(f"    {json.dumps(rule, ensure_ascii=False)}{comma}")
        lines.append("   ]")
        lines.append("  }" + ("," if i < len(names) - 1 else ""))
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


class Command(BaseCommand):
    help = "GeoMAP 의 QGIS 스타일(.qml)에서 색을 뽑아 data/geomap_styles.json 에 적는다"

    def add_arguments(self, parser):
        parser.add_argument("--qml-dir", required=True,
                            help="GeoMAP 의 QGIS/Support/layerFiles")
        parser.add_argument("--out", default=str(settings.GEOMAP_STYLES))

    def handle(self, *args, **options):
        qml_dir = Path(options["qml_dir"])
        styles = {}
        for name, (fname, table, kind) in SOURCES.items():
            path = qml_dir / fname
            if not path.exists():
                raise CommandError(f"스타일이 없다: {path}")
            try:
                styles[name] = parse_qml(path, table, kind)
            except ValueError as exc:
                raise CommandError(f"{fname}: {exc}") from exc
            self.stdout.write(f"{name}: 규칙 {len(styles[name]['rules'])}")
        styles["quality"] = QUALITY_STYLE

        from django.utils import timezone
        out = {
            "_주석": "GeoMAP v2022-08 과 함께 온 QGIS 스타일(.qml)에서 manage.py geomap_styles 로 "
                     "뽑았다. 손으로 고치지 않는다 — 다시 뽑으면 덮인다. quality 만은 GNS 스타일이 "
                     "없어 그 명령 안에서 정했다.",
            "_뽑은날": timezone.localdate().isoformat(),
            "styles": styles,
        }
        Path(options["out"]).write_text(dumps(out), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"적었다: {options['out']}"))
