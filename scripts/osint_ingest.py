#!/usr/bin/env python3
"""
CCOP OSINT 대량 적재 로더 (초안 / 실구현 착수용)
흐름: 제출 JSON/NDJSON  →  검증  →  정규화 자연키(node_key)  →  COPY(staging)  →  MERGE(graph) + node_source 사이드카

사용법:
  python scripts/osint_ingest.py 제출.json --graph osint_graph
  python scripts/osint_ingest.py 제출.ndjson --dry-run          # DB 미접촉(검증+스테이징 계획만)
  python scripts/osint_ingest.py 제출.json --skip-validate       # 사전검증 생략(비권장)

사전: scripts/osint_staging.sql 로 staging/그래프/라벨 생성 완료.  .env 의 DB_* 사용.
⚠️ AgensGraph 버전별 확인 지점은 [AGVER] 주석 참조 (cypher() 반환타입 agtype, SET += map).
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
NODE_COLS = ["batch_id", "label", "id_field", "id_value", "id_format", "node_key",
             "attrs", "source_id", "reliability_tier", "collected_at", "confidence", "evidence_ref", "op"]
EDGE_COLS = ["batch_id", "edge_type", "from_label", "from_value", "from_key",
             "to_label", "to_value", "to_key", "attrs", "source_id", "reliability_tier",
             "rec_created", "confidence", "op"]


def node_key(label, id_value):
    """자연키 — dedup/idempotent 기준. 정규화된 id_value 전제."""
    return hashlib.md5(f"{label}|{id_value}".encode("utf-8")).hexdigest()


# ── Cypher 직렬화 (프로퍼티 안전 이스케이프) ────────────────────
def cy(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)   # 복합타입은 JSON 문자열로 저장
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def cy_set(var, d):
    # AgensGraph 2.16 네이티브: SET var.k = v, ...  (개별 SET — 버전 안전)
    return ", ".join(f"{var}.{k} = {cy(v)}" for k, v in d.items())


# 통합 그래프에 필요한 라벨 (없으면 생성)
LABELS_V = ["vt_src", "vt_site", "site_cluster", "vt_ip", "vt_file", "vt_id", "vt_msg",
            "vt_bacnt", "vt_telno", "vt_transfer", "vt_org", "vt_psn"]
LABELS_E = ["belongs_to_campaign", "resolves_to", "hosts", "communicated_with", "contains_file",
            "mentions_account", "operates", "registered_to", "sameAs"]


# ── DB ─────────────────────────────────────────────────────────
def connect():
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "127.0.0.1"), port=os.getenv("DB_PORT", "5432"))


def set_graph(cur, graph):
    import re
    assert re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", graph), f"invalid graph name: {graph}"
    cur.execute(f"SET graph_path = {graph}")   # AgensGraph 네이티브 — 이후 Cypher 직접 실행


def ensure_graph_labels(cur):
    for l in LABELS_V:
        cur.execute(f"CREATE VLABEL IF NOT EXISTS {l}")
    for l in LABELS_E:
        cur.execute(f"CREATE ELABEL IF NOT EXISTS {l}")


# ── 스테이징(COPY) ─────────────────────────────────────────────
def stage(cur, batch_id, nodes, edges):
    nb, eb = io.StringIO(), io.StringIO()
    nw, ew = csv.writer(nb), csv.writer(eb)
    for n in nodes:
        ido, meta = n["id"], n.get("meta", {})
        k = node_key(n["label"], ido["value"])
        nw.writerow([batch_id, n["label"], ido["field"], ido["value"], ido["id_format"], k,
                     json.dumps(n.get("attrs", {}), ensure_ascii=False),
                     meta.get("source_id"), meta.get("reliability_tier", 4),
                     meta.get("collected_at"), meta.get("confidence"), meta.get("evidence_ref"),
                     n.get("op", "upsert")])
    for e in edges:
        f, t, meta = e["from"], e["to"], e.get("meta", {})
        ew.writerow([batch_id, e["type"], f["label"], f["value"], node_key(f["label"], f["value"]),
                     t["label"], t["value"], node_key(t["label"], t["value"]),
                     json.dumps(e.get("attrs", {}), ensure_ascii=False),
                     meta.get("source_id"), meta.get("reliability_tier", 4),
                     meta.get("rec_created"), meta.get("confidence"), e.get("op", "upsert")])
    nb.seek(0); eb.seek(0)
    cur.copy_expert(f"COPY staging.osint_nodes ({','.join(NODE_COLS)}) FROM STDIN WITH (FORMAT csv)", nb)
    cur.copy_expert(f"COPY staging.osint_edges ({','.join(EDGE_COLS)}) FROM STDIN WITH (FORMAT csv)", eb)


# ── 그래프 승격(MERGE) + 사이드카 ──────────────────────────────
def promote(cur, batch_id, graph):
    # 1) staging → 메모리 (그래프 세션 전환 전에 관계형 SELECT 를 모두 fetch)
    cur.execute("""SELECT label,id_field,id_value,node_key,attrs,source_id,reliability_tier,
                          collected_at,confidence,evidence_ref,op
                   FROM staging.osint_nodes WHERE batch_id=%s""", (batch_id,))
    node_rows = cur.fetchall()
    cur.execute("""SELECT edge_type,from_label,from_key,to_label,to_key,attrs,source_id,reliability_tier,op
                   FROM staging.osint_edges WHERE batch_id=%s""", (batch_id,))
    edge_rows = cur.fetchall()
    # 2) AgensGraph 네이티브: graph_path 설정 + 라벨 보장
    set_graph(cur, graph)
    ensure_graph_labels(cur)
    # 3) 노드 MERGE (개별 SET) + node_source 사이드카
    for label, idf, idv, k, attrs, sid, tier, coll, conf, ev, op in node_rows:
        if op == "delete":
            cur.execute(f"MATCH (n:{label} {{node_key:{cy(k)}}}) DETACH DELETE n")
            continue
        props = {**(attrs or {}), "node_key": k, idf: idv,
                 "source_domain": "osint", "source_id": sid, "reliability_tier": tier}
        cur.execute(f"MERGE (n:{label} {{node_key:{cy(k)}}}) SET {cy_set('n', props)}")
        cur.execute("""INSERT INTO graph_meta.node_source
                         (node_key,label,source_id,reliability_tier,first_seen,last_seen,confidence,evidence_ref)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (node_key,source_id) DO UPDATE
                         SET last_seen=EXCLUDED.last_seen, confidence=EXCLUDED.confidence""",
                    (k, label, sid, tier, coll, coll, conf, ev))
    # 4) 엣지 MERGE
    for et, fl, fk, tl, tk, attrs, sid, tier, op in edge_rows:
        match = f"MATCH (a:{fl} {{node_key:{cy(fk)}}}),(b:{tl} {{node_key:{cy(tk)}}})"
        if op == "delete":
            cur.execute(f"{match} MATCH (a)-[e:{et}]->(b) DELETE e")
            continue
        eprops = {**(attrs or {}), "source_id": sid, "reliability_tier": tier}
        cur.execute(f"{match} MERGE (a)-[e:{et}]->(b) SET {cy_set('e', eprops)}")


def main():
    ap = argparse.ArgumentParser(description="CCOP OSINT 대량 적재 로더")
    ap.add_argument("file")
    ap.add_argument("--graph", default="osint_graph")
    ap.add_argument("--dry-run", action="store_true", help="DB 미접촉 — 검증+건수만")
    ap.add_argument("--skip-validate", action="store_true")
    args = ap.parse_args()

    from validate_osint_submission import load, validate
    data = load(args.file)
    if not args.skip_validate:
        rep, nn, ne = validate(data)
        if rep.errors:
            print(f"❌ 검증 실패 — 오류 {len(rep.errors)}건. 적재 중단 (validate_osint_submission.py 로 상세 확인)")
            for loc, msg in rep.errors[:10]:
                print(f"   {loc}: {msg}")
            sys.exit(1)
        print(f"✅ 검증 통과 (노드 {nn}·엣지 {ne})")

    m = data.get("manifest", {})
    nodes, edges = data.get("nodes", []), data.get("edges", [])
    if args.dry_run:
        print(f"[dry-run] batch agency={m.get('agency_id')} type={m.get('delivery_type')} "
              f"nodes={len(nodes)} edges={len(edges)} — DB 미접촉")
        if nodes:
            n = nodes[0]; k = node_key(n["label"], n["id"]["value"])
            print(f"[dry-run] 예시 node_key({n['label']}) = {k}")
        return

    conn = connect(); cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO staging.osint_batch
                         (agency_id,delivery_type,schema_version,window_from,window_to,
                          declared_nodes,declared_edges,sha256,status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'validated') RETURNING batch_id""",
                    (m.get("agency_id"), m.get("delivery_type", "snapshot"), m.get("schema_version"),
                     (m.get("window") or {}).get("from"), (m.get("window") or {}).get("to"),
                     (m.get("counts") or {}).get("nodes"), (m.get("counts") or {}).get("edges"), m.get("sha256")))
        batch_id = cur.fetchone()[0]
        stage(cur, batch_id, nodes, edges)
        promote(cur, batch_id, args.graph)
        cur.execute("UPDATE staging.osint_batch SET status='loaded' WHERE batch_id=%s", (batch_id,))
        conn.commit()
        print(f"✅ 적재 완료: batch_id={batch_id} · 노드 {len(nodes)} · 엣지 {len(edges)} → graph '{args.graph}'")
        print("   다음: 배치 EntityResolution 잡으로 sameAs 브릿지 (graph_meta.sameas_candidates 참조)")
    except Exception as e:
        conn.rollback()
        print(f"❌ 적재 실패(롤백): {e}")
        sys.exit(1)
    finally:
        cur.close(); conn.close()


if __name__ == "__main__":
    main()
