#!/usr/bin/env python3
"""
CCOP OSINT 제출물 검증기 — 온톨로지 V4.0 연동 규격 대비 자동 검사 (표준 라이브러리만)

사용법:
  python scripts/validate_osint_submission.py <파일.json|파일.ndjson>
  python scripts/validate_osint_submission.py <파일> --strict   # 경고도 실패로 처리
  python scripts/validate_osint_submission.py --selftest        # 내장 자체 테스트

검사 항목:
  구조({manifest,nodes,edges}) · manifest 건수 일치 · 노드 라벨/식별자/id_format/필수속성
  · Provenance 메타(source_domain=osint, source_id, reliability_tier=4, collected_at)
  · 식별자 정규화(URL/전화/해시/IP/시각 — sameAs 매칭 무결성) · 엣지 타입/양끝 라벨/참조무결성
종료코드: 오류 0건이면 0, 있으면 1 (--strict 는 경고도 1)
"""
import argparse
import ipaddress
import json
import re
import sys

# ── 규격 상수 (OSINT 연동 규격 V4.0) ──────────────────────────
NODE_SPECS = {
    "vt_src":       ("src_id",     {"plain"},                     ["src_name", "src_type", "reliability_tier"]),
    "vt_site":      ("url_addr",   {"normalized_url"},            ["site_type", "is_malicious"]),
    "site_cluster": ("cluster_id", {"plain", "sc"},              ["html_fingerprint", "phishing_type"]),
    "vt_ip":        ("ip_addr",    {"ipv4_dotted", "ipv6"},       ["country"]),
    "vt_file":      ("hash_val",   {"md5", "sha1", "sha256"},     []),
    "vt_id":        ("id_val",     {"plain"},                     ["platform"]),
    "vt_msg":       ("msg_id",     {"plain"},                     ["msg_type", "content_hash"]),
    "vt_bacnt":     ("account_no", {"plain_dash", "md5", "sha256"}, ["bank_cd"]),
    "vt_telno":     ("telno",      {"no_hyphen_e164", "md5"},     []),
    "vt_transfer":  ("transfer_id", {"plain"},                    ["dlng_amt", "dlng_dt"]),
    "vt_org":       ("org_id",     {"plain"},                     ["org_name", "org_category"]),
    "vt_psn":       ("psn_id",     {"plain"},                     []),  # registered_to 대상 등
}
ANY = None
EDGE_SPECS = {
    "belongs_to_campaign": ({"vt_site"},                {"site_cluster"}),
    "resolves_to":         ({"vt_site"},                {"vt_ip"}),
    "hosts":               ({"vt_ip"},                  {"vt_site"}),
    "communicated_with":   ({"vt_ip"},                  {"vt_ip"}),
    "contains_file":       ({"vt_site", "vt_msg", "vt_id"}, {"vt_file"}),
    "mentions_account":    ({"vt_msg"},                 {"vt_bacnt"}),
    "operates":            ({"vt_id", "vt_org", "vt_psn"}, {"vt_site", "vt_id"}),
    "registered_to":       ({"vt_telno"},               {"vt_psn"}),
    "sameAs":              (ANY,                        ANY),
}
ISO8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
HEXLEN = {"md5": 32, "sha1": 40, "sha256": 64}


class Report:
    def __init__(self):
        self.errors, self.warns = [], []
    def err(self, loc, msg):  self.errors.append((loc, msg))
    def warn(self, loc, msg): self.warns.append((loc, msg))


# ── 값 검증기 ────────────────────────────────────────────────
def check_iso8601(rep, loc, val):
    if not isinstance(val, str) or not ISO8601.match(val):
        rep.err(loc, f"시각은 ISO8601 UTC 형식이어야 함(예: 2026-07-10T09:00:00Z) — got {val!r}")
        return
    if not (val.endswith("Z") or val.endswith("+00:00")):
        rep.warn(loc, f"UTC(Z 또는 +00:00) 권장 — got {val!r}")


def check_normalized(rep, loc, id_format, value):
    """식별자 정규화 검증 — sameAs 교차매칭의 생명."""
    if not isinstance(value, str) or not value.strip():
        rep.err(loc, "식별자 value 가 비어 있음"); return
    v = value
    if id_format == "normalized_url":
        if not re.match(r"^https?://", v):
            rep.err(loc, f"URL은 스킴(http/https) 포함 필요 — {v!r}")
        host = re.sub(r"^https?://", "", v).split("/")[0]
        if host != host.lower():
            rep.err(loc, f"URL 호스트는 소문자여야 함 — {host!r}")
        if "#" in v:
            rep.warn(loc, "URL fragment(#…) 제거 권장")
        if " " in v:
            rep.err(loc, "URL에 공백 불가")
    elif id_format == "ipv4_dotted":
        try:
            ip = ipaddress.IPv4Address(v)
            if any(len(o) > 1 and o[0] == "0" for o in v.split(".")):
                rep.err(loc, f"IPv4 zero-padding 금지 — {v!r}")
        except ValueError:
            rep.err(loc, f"유효한 IPv4 아님 — {v!r}")
    elif id_format == "ipv6":
        try: ipaddress.IPv6Address(v)
        except ValueError: rep.err(loc, f"유효한 IPv6 아님 — {v!r}")
    elif id_format == "no_hyphen_e164":
        if not re.fullmatch(r"\+?\d+", v):
            rep.err(loc, f"전화번호는 숫자만(선택적 +), 하이픈·공백 금지 — {v!r}")
    elif id_format in ("md5", "sha1", "sha256"):
        h = v.split(":", 1)[1] if ":" in v else v
        if h != h.lower() or not re.fullmatch(r"[0-9a-f]+", h):
            rep.err(loc, f"해시는 소문자 hex — {v!r}")
        elif len(h) != HEXLEN[id_format]:
            rep.err(loc, f"{id_format} 길이 {HEXLEN[id_format]} 아님({len(h)}) — {v!r}")
    elif id_format == "plain_dash":
        if not re.fullmatch(r"[0-9\-]+", v):
            rep.warn(loc, f"계좌(plain_dash)는 숫자·하이픈 권장 — {v!r}")
    # plain, sc 등은 비어있지 않으면 통과


def check_meta(rep, loc, meta, is_node):
    if not isinstance(meta, dict):
        rep.err(loc + ".meta", "meta 객체 누락"); return
    if is_node:
        if meta.get("source_domain") != "osint":
            rep.err(loc + ".meta.source_domain", f"'osint' 여야 함 — got {meta.get('source_domain')!r}")
        if not meta.get("collected_at"):
            rep.err(loc + ".meta.collected_at", "필수 누락")
        else:
            check_iso8601(rep, loc + ".meta.collected_at", meta["collected_at"])
    else:
        if not meta.get("rec_created"):
            rep.err(loc + ".meta.rec_created", "필수 누락")
        else:
            check_iso8601(rep, loc + ".meta.rec_created", meta["rec_created"])
    if not meta.get("source_id"):
        rep.err(loc + ".meta.source_id", "필수 누락(기관 vt_src id)")
    tier = meta.get("reliability_tier")
    if tier is None:
        rep.err(loc + ".meta.reliability_tier", "필수 누락")
    elif tier != 4:
        rep.warn(loc + ".meta.reliability_tier", f"OSINT는 4 권장 — got {tier!r}")
    if "confidence" in meta and not (isinstance(meta["confidence"], (int, float)) and 0 <= meta["confidence"] <= 1):
        rep.err(loc + ".meta.confidence", f"0.0~1.0 이어야 함 — got {meta['confidence']!r}")


# ── 노드/엣지 검증 ───────────────────────────────────────────
def validate_node(rep, i, node, node_index, delivery_type):
    loc = f"nodes[{i}]"
    if not isinstance(node, dict):
        rep.err(loc, "객체가 아님"); return
    label = node.get("label")
    if label not in NODE_SPECS:
        rep.err(loc + ".label", f"미지원 라벨 — {label!r} (허용: {', '.join(sorted(NODE_SPECS))})"); return
    id_field, allowed_fmts, required = NODE_SPECS[label]
    idobj = node.get("id")
    if not isinstance(idobj, dict):
        rep.err(loc + ".id", "id 객체 누락(field/value/id_format)"); return
    if idobj.get("field") != id_field:
        rep.err(loc + ".id.field", f"{label} 표준식별자는 '{id_field}' — got {idobj.get('field')!r}")
    fmt = idobj.get("id_format")
    if fmt not in allowed_fmts:
        rep.err(loc + ".id.id_format", f"{label} 허용 형식 {sorted(allowed_fmts)} — got {fmt!r}")
    else:
        check_normalized(rep, loc + ".id.value", fmt, idobj.get("value"))
    attrs = node.get("attrs", {})
    if not isinstance(attrs, dict):
        rep.err(loc + ".attrs", "attrs 객체 누락")
    else:
        for r in required:
            if r not in attrs or attrs[r] in (None, ""):
                rep.err(loc + ".attrs." + r, f"{label} 필수 속성 누락")
    check_meta(rep, loc, node.get("meta"), is_node=True)
    if delivery_type == "delta" and node.get("op") not in ("upsert", "delete"):
        rep.warn(loc + ".op", "delta 전달 시 op: upsert|delete 권장")
    # 인덱스 등록(참조무결성용)
    val = (idobj.get("value") if isinstance(idobj, dict) else None)
    if label and val:
        node_index.add((label, val))


def validate_edge(rep, i, edge, node_index, delivery_type):
    loc = f"edges[{i}]"
    if not isinstance(edge, dict):
        rep.err(loc, "객체가 아님"); return
    etype = edge.get("type")
    if etype not in EDGE_SPECS:
        rep.err(loc + ".type", f"미지원 엣지 — {etype!r} (허용: {', '.join(sorted(EDGE_SPECS))})"); return
    from_ok, to_ok = EDGE_SPECS[etype]
    for side, allowed in (("from", from_ok), ("to", to_ok)):
        obj = edge.get(side)
        if not isinstance(obj, dict) or "label" not in obj or "value" not in obj:
            rep.err(f"{loc}.{side}", "label/value 필요"); continue
        if allowed is not ANY and obj["label"] not in allowed:
            rep.err(f"{loc}.{side}.label", f"{etype} {side} 라벨은 {sorted(allowed)} — got {obj['label']!r}")
        # 참조 무결성
        if (obj["label"], obj["value"]) not in node_index:
            lvl = rep.err if delivery_type == "snapshot" else rep.warn
            lvl(f"{loc}.{side}", f"참조 노드 미선언 — ({obj['label']}, {obj['value']!r})")
    check_meta(rep, loc, edge.get("meta"), is_node=False)


def validate_manifest(rep, m, n_nodes, n_edges):
    if not isinstance(m, dict):
        rep.err("manifest", "manifest 누락"); return "snapshot"
    for f in ("agency_id", "schema_version", "delivery_type"):
        if not m.get(f):
            rep.err("manifest." + f, "필수 누락")
    if m.get("schema_version") not in (None, "ccop-v4.0"):
        rep.warn("manifest.schema_version", f"'ccop-v4.0' 예상 — got {m.get('schema_version')!r}")
    counts = m.get("counts") or {}
    if counts.get("nodes") not in (None, n_nodes):
        rep.err("manifest.counts.nodes", f"선언 {counts.get('nodes')} ≠ 실제 {n_nodes}")
    if counts.get("edges") not in (None, n_edges):
        rep.err("manifest.counts.edges", f"선언 {counts.get('edges')} ≠ 실제 {n_edges}")
    if not m.get("sha256"):
        rep.warn("manifest.sha256", "체크섬 권장(무결성)")
    dt = m.get("delivery_type", "snapshot")
    if dt not in ("snapshot", "delta"):
        rep.err("manifest.delivery_type", "snapshot | delta")
        dt = "snapshot"
    return dt


# ── 로드(JSON/NDJSON) ────────────────────────────────────────
def load(path):
    text = open(path, encoding="utf-8").read()
    try:
        return json.loads(text)  # {manifest,nodes,edges}
    except json.JSONDecodeError:
        pass
    manifest, nodes, edges = {}, [], []  # NDJSON: 라벨=노드, type=엣지, manifest 키=매니페스트
    for ln, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if "manifest" in rec: manifest = rec["manifest"]
        elif "label" in rec:  nodes.append(rec)
        elif "type" in rec:   edges.append(rec)
    return {"manifest": manifest, "nodes": nodes, "edges": edges}


def validate(data):
    rep = Report()
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    dt = validate_manifest(rep, data.get("manifest"), len(nodes), len(edges))
    node_index = set()
    for i, n in enumerate(nodes):
        validate_node(rep, i, n, node_index, dt)
    for i, e in enumerate(edges):
        validate_edge(rep, i, e, node_index, dt)
    return rep, len(nodes), len(edges)


def print_report(rep, n_nodes, n_edges, strict):
    print(f"검사 대상: 노드 {n_nodes} · 엣지 {n_edges}")
    for loc, msg in rep.errors:
        print(f"  ❌ ERROR  {loc}: {msg}")
    for loc, msg in rep.warns:
        print(f"  ⚠️  WARN   {loc}: {msg}")
    print(f"\n결과: 오류 {len(rep.errors)} · 경고 {len(rep.warns)}")
    fail = bool(rep.errors) or (strict and rep.warns)
    print("판정:", "❌ 반려(수정 필요)" if fail else "✅ 통과")
    return 1 if fail else 0


# ── 자체 테스트 ──────────────────────────────────────────────
def selftest():
    valid = {
        "manifest": {"agency_id": "osint-x", "schema_version": "ccop-v4.0", "delivery_type": "snapshot",
                     "counts": {"nodes": 2, "edges": 1}, "sha256": "abc"},
        "nodes": [
            {"label": "vt_site", "id": {"field": "url_addr", "value": "https://a.example.com/login", "id_format": "normalized_url"},
             "attrs": {"site_type": "phishing", "is_malicious": True},
             "meta": {"source_domain": "osint", "source_id": "osint-x", "reliability_tier": 4, "collected_at": "2026-07-10T09:00:00Z"}},
            {"label": "vt_ip", "id": {"field": "ip_addr", "value": "203.0.113.5", "id_format": "ipv4_dotted"},
             "attrs": {"country": "US"},
             "meta": {"source_domain": "osint", "source_id": "osint-x", "reliability_tier": 4, "collected_at": "2026-07-10T09:00:00Z"}},
        ],
        "edges": [
            {"type": "resolves_to", "from": {"label": "vt_site", "value": "https://a.example.com/login"},
             "to": {"label": "vt_ip", "value": "203.0.113.5"}, "attrs": {"resolved_dt": "2026-07-10T09:00:00Z"},
             "meta": {"source_id": "osint-x", "reliability_tier": 4, "rec_created": "2026-07-10T09:00:00Z"}},
        ],
    }
    invalid = json.loads(json.dumps(valid))
    invalid["nodes"][0]["id"]["value"] = "HTTPS://A.Example.com/login/"   # 대문자 호스트
    invalid["nodes"][1]["id"]["value"] = "203.000.113.5"                  # zero-padding
    invalid["nodes"][1]["meta"]["source_domain"] = "investigation"        # osint 아님
    invalid["nodes"][0]["attrs"].pop("site_type")                         # 필수 누락
    invalid["edges"][0]["to"]["value"] = "8.8.8.8"                        # 참조 미선언
    invalid["manifest"]["counts"]["edges"] = 5                            # 건수 불일치

    print("=== [valid] ==="); r1, a, b = validate(valid); c1 = print_report(r1, a, b, False)
    print("\n=== [invalid] ==="); r2, a, b = validate(invalid); print_report(r2, a, b, False)
    ok = (c1 == 0) and len(r2.errors) >= 5
    print("\n자체테스트:", "✅ PASS" if ok else "❌ FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="CCOP OSINT 제출물 검증 (V4.0 규격)")
    ap.add_argument("file", nargs="?", help="제출 파일(.json 또는 .ndjson)")
    ap.add_argument("--strict", action="store_true", help="경고도 실패로 처리")
    ap.add_argument("--selftest", action="store_true", help="내장 자체 테스트")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if not args.file:
        ap.error("파일 경로 또는 --selftest 필요")
    try:
        data = load(args.file)
    except Exception as e:
        print(f"❌ 파일 로드 실패: {e}"); sys.exit(2)
    rep, n, m = validate(data)
    sys.exit(print_report(rep, n, m, args.strict))


if __name__ == "__main__":
    main()
