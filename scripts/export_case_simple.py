"""
export_case_simple.py — 사건 1건을 JSON으로 export (외부 기관 전달용)

사용:
    python scripts/export_case_simple.py --case CASE-2024-001 --graph my_v40_demo --hops 2

출력:
    exports/CASE-2024-001_<timestamp>.json  (마스킹된 JSON)
    exports/CASE-2024-001_<timestamp>.txt   (자연어 요약)
"""
import argparse, json, os, datetime, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from dotenv import load_dotenv
load_dotenv()


# ─── 마스킹 규칙 (개인정보 보호) ─────────────────────────────────
def mask(value, kind):
    if not value:
        return value
    v = str(value)
    if kind == "name":
        return v[0] + "O" + (v[-1] if len(v) > 1 else "")
    if kind == "telno":
        return f"{v[:3]}-****-{v[-4:]}" if len(v) >= 7 else "[MASKED]"
    if kind == "account":
        return f"{v[:4]}-XXX-{v[-4:]}" if len(v) >= 8 else "[MASKED]"
    if kind == "ip":
        parts = v.split(".")
        return ".".join(parts[:2]) + ".XXX.XXX" if len(parts) == 4 else "[MASKED]"
    if kind == "rrno":
        return None  # 주민번호 완전 제거
    return v


PROP_MASK_MAP = {
    "korn_flnm": "name", "name": "name", "flnm": "name",
    "telno": "telno",
    "account_no": "account", "actno": "account",
    "ip_addr": "ip",
    "rrno_hash": "rrno", "rrno": "rrno",
}


def apply_mask(props):
    if not props:
        return {}
    masked = {}
    for k, v in props.items():
        kind = PROP_MASK_MAP.get(k)
        if kind == "rrno":
            continue  # 완전 제거
        if kind:
            masked[k] = mask(v, kind)
        else:
            masked[k] = v
    return masked


# ─── DB 연결 + 추출 ──────────────────────────────────────────────
def extract_case(case_no, graph_path, hops=2, limit=300):
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"), host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"SET graph_path = {graph_path}")

    cypher = f"""
        MATCH (c:vt_case {{flnm: '{case_no}'}})-[r*1..{hops}]-(n)
        RETURN id(c), labels(c), properties(c),
               id(n), labels(n), properties(n)
        LIMIT {limit}
    """
    cur.execute(cypher)
    rows = cur.fetchall()

    nodes = {}
    for c_id, c_labels, c_props, n_id, n_labels, n_props in rows:
        for nid, labels, props in [(c_id, c_labels, c_props), (n_id, n_labels, n_props)]:
            key = str(nid)
            if key not in nodes:
                nodes[key] = {
                    "id": key,
                    "label": labels[0] if labels else "node",
                    "props": apply_mask(props or {})
                }

    # 엣지 추출 (별도 쿼리)
    cypher_edges = f"""
        MATCH (c:vt_case {{flnm: '{case_no}'}})-[r*1..{hops}]-(n)
        UNWIND r AS rel
        RETURN DISTINCT id(startNode(rel)), id(endNode(rel)), type(rel), properties(rel)
        LIMIT {limit * 3}
    """
    cur.execute(cypher_edges)
    edges = []
    for s_id, t_id, etype, eprops in cur.fetchall():
        edges.append({
            "source": str(s_id),
            "target": str(t_id),
            "type": etype,
            "props": eprops or {}
        })

    conn.close()
    return nodes, edges


# ─── 자연어 요약 (외부 LLM 컨텍스트용) ────────────────────────────
EDGE_KR = {
    "suspect_in": "이(가) 피의자로 등록된 사건",
    "victim_in": "이(가) 피해자인 사건",
    "involves": "에 연루된 인물",
    "has_account": "이(가) 보유한 계좌",
    "owns_phone": "이(가) 사용하는 전화",
    "registered_to": "의 명의자",
    "from_account": "에서 출금된 이체",
    "to_account": "(으)로 입금된 이체",
    "transferred_to": "(으)로 직접 송금",
    "caller": "이(가) 발신한 통화",
    "callee": "이(가) 수신한 통화",
    "hosts": "이(가) 호스팅한 사이트",
    "contains_file": "에 포함된 파일",
    "used_for": "에 사용된 사칭",
    "targets": "이(가) 타겟한 기관",
    "belongs_to": "이(가) 소속된 기관",
    "used_ip": "이(가) 사용한 IP",
    "owns_vehicle": "이(가) 소유한 차량",
    "drives": "이(가) 운전한 차량",
}


def to_natural_language(case_no, nodes, edges):
    lines = [f"[사건 {case_no} 그래프 데이터 — CCOP v4.0 export]",
             f"추출 시각: {datetime.datetime.now().isoformat()}",
             f"마스킹: partial (개인정보 일부 가림)",
             ""]

    # 노드 요약
    by_label = {}
    for n in nodes.values():
        by_label.setdefault(n["label"], []).append(n)
    lines.append(f"== 관련 노드 ({len(nodes)}개) ==")
    for label, items in sorted(by_label.items()):
        lines.append(f"  [{label}] {len(items)}개")
        for n in items[:10]:
            key_prop = (n["props"].get("name") or n["props"].get("korn_flnm")
                       or n["props"].get("flnm") or n["props"].get("telno")
                       or n["props"].get("account_no") or n["props"].get("ip_addr")
                       or n["props"].get("url_addr") or n["id"])
            lines.append(f"    - {key_prop}")
        if len(items) > 10:
            lines.append(f"    ... (외 {len(items) - 10}개)")
    lines.append("")

    # 엣지 요약 (자연어)
    lines.append(f"== 관계 ({len(edges)}개) ==")
    node_label_map = {n["id"]: n["label"] for n in nodes.values()}
    node_key_map = {
        n["id"]: (n["props"].get("name") or n["props"].get("korn_flnm")
                  or n["props"].get("flnm") or n["props"].get("telno")
                  or n["props"].get("account_no") or n["props"].get("ip_addr")
                  or n["id"][:8])
        for n in nodes.values()
    }
    edge_count = 0
    for e in edges:
        src_key = node_key_map.get(e["source"], e["source"][:8])
        tgt_key = node_key_map.get(e["target"], e["target"][:8])
        verb = EDGE_KR.get(e["type"], e["type"])
        lines.append(f"  - {src_key} {verb}: {tgt_key}")
        edge_count += 1
        if edge_count >= 50:
            lines.append(f"  ... (외 {len(edges) - 50}개 관계)")
            break

    return "\n".join(lines)


# ─── 메인 ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, help="사건번호 (예: CASE-2024-001)")
    parser.add_argument("--graph", default="my_v40_demo", help="그래프명")
    parser.add_argument("--hops", type=int, default=2, help="hop 거리 (1~3)")
    parser.add_argument("--limit", type=int, default=300, help="최대 노드 수")
    parser.add_argument("--output-dir", default="exports", help="출력 디렉토리")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{args.case}_{ts}"

    print(f"▶ 추출 중: 사건={args.case} / 그래프={args.graph} / hops={args.hops}")
    nodes, edges = extract_case(args.case, args.graph, args.hops, args.limit)
    print(f"  노드 {len(nodes)}개, 엣지 {len(edges)}개")

    # 1) JSON 파일
    json_path = Path(args.output_dir) / f"{base_name}.json"
    payload = {
        "case_no": args.case,
        "graph_path": args.graph,
        "exported_at": datetime.datetime.now().isoformat(),
        "mask_level": "partial",
        "source": "CCOP v4.0",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values()),
        "edges": edges,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 저장: {json_path}")

    # 2) 자연어 텍스트 파일
    txt_path = Path(args.output_dir) / f"{base_name}.txt"
    nl = to_natural_language(args.case, nodes, edges)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(nl)
    print(f"✅ 자연어 저장: {txt_path}")
    print()
    print("=" * 60)
    print(nl[:500])
    print("=" * 60)
    print()
    print("외부 기관 전달 시:")
    print(f"  - JSON ({json_path.stat().st_size} bytes): 시스템 통합용")
    print(f"  - TXT  ({txt_path.stat().st_size} bytes): LLM 컨텍스트용")


if __name__ == "__main__":
    main()
