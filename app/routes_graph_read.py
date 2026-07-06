"""
routes_graph_read.py — 외부 LLM/시스템용 read-only 그래프 접근 API.

엔드포인트 2개:
  POST /api/v1/graph/read    — Cypher 직접 실행 (read-only 검증)
  GET  /api/v1/graph/dump    — 그래프 전체 dump (노드+엣지)

운영 규칙:
  - SELECT/MATCH/RETURN 만 허용 (CREATE/DELETE/SET/MERGE 차단)
  - 결과는 JSON 으로 반환 (외부 LLM 파싱 친화적)
  - 토큰: X-API-Key 헤더 (선택, 환경변수 LLM_API_KEY)
"""
import os, re, json, hmac
from flask import Blueprint, request, jsonify, current_app
import psycopg2

graph_read_bp = Blueprint('graph_read', __name__, url_prefix='/api/v1/graph')


# ─── 안전 검증: read-only Cypher만 허용 ─────────────────────────
_WRITE_PATTERNS = re.compile(
    r'\b(CREATE|DELETE|MERGE|SET|DETACH|DROP|UPDATE|INSERT|ALTER|TRUNCATE|REMOVE|CALL)\b',
    re.IGNORECASE
)


def _is_read_only(cypher: str) -> bool:
    """Cypher가 read-only 인지 검증."""
    if not cypher:
        return False
    # 주석 제거
    cleaned = re.sub(r'//.*$', '', cypher, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    return not _WRITE_PATTERNS.search(cleaned)


def _check_api_key(req):
    """X-API-Key 검증. LLM_API_KEY 미설정 시 외부 접근을 거부(fail-closed)."""
    expected = os.getenv('LLM_API_KEY')
    if not expected:
        current_app.logger.error(
            "LLM_API_KEY 미설정 — 외부 그래프 조회 API 접근을 거부합니다. "
            "외부 조회가 필요하면 LLM_API_KEY 환경변수를 설정하세요."
        )
        return False
    provided = req.headers.get('X-API-Key', '')
    return hmac.compare_digest(provided, expected)


@graph_read_bp.route('/read', methods=['POST'])
def graph_read():
    """
    외부 LLM/시스템이 read-only Cypher를 실행.

    Body:
      cypher:     실행할 Cypher (MATCH/RETURN만)
      graph_path: 그래프명 (예: osint_ontology, my_v40_demo)
      limit:      결과 제한 (기본 500, 최대 5000)

    Response:
      {nodes, edges, count, cypher_executed}
    """
    if not _check_api_key(request):
        return jsonify({"error": "Invalid API key"}), 401

    data = request.get_json() or {}
    cypher = data.get('cypher', '').strip()
    graph_path = data.get('graph_path', 'my_v40_demo')
    limit = min(int(data.get('limit', 500)), 5000)

    if not cypher:
        return jsonify({"error": "cypher required"}), 400

    if not _is_read_only(cypher):
        return jsonify({"error": "Only read-only Cypher allowed (MATCH/RETURN/WITH)"}), 403

    # graph_path 검증 (영문/숫자/_ 만 허용)
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"error": "Invalid graph_path"}), 400

    # LIMIT 자동 추가 (없으면)
    if not re.search(r'\bLIMIT\b', cypher, re.IGNORECASE):
        cypher = cypher.rstrip(';').rstrip() + f" LIMIT {limit}"

    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"SET graph_path = {graph_path}")
        cur.execute(cypher)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()

        return jsonify({
            "graph_path": graph_path,
            "cypher": cypher,
            "columns": cols,
            "row_count": len(rows),
            "rows": [list(map(_serialize, row)) for row in rows],
        })
    except Exception:
        current_app.logger.exception("graph_read 실행 오류")
        return jsonify({"error": "internal error"}), 500


@graph_read_bp.route('/dump', methods=['GET'])
def graph_dump():
    """
    그래프 전체 노드+엣지 dump (외부 LLM 컨텍스트용).

    Query params:
      graph_path: 그래프명 (필수)
      limit:      엣지 제한 (기본 500, 최대 5000)
      format:     "json" (기본) | "triple" (간결 형식)
    """
    if not _check_api_key(request):
        return jsonify({"error": "Invalid API key"}), 401

    graph_path = request.args.get('graph_path', '')
    limit = min(int(request.args.get('limit', 500)), 5000)
    fmt = request.args.get('format', 'json')

    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"error": "Invalid graph_path"}), 400

    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"SET graph_path = {graph_path}")

        # 노드+엣지 추출 (운영 코드와 동일 패턴)
        cur.execute(f"""
            MATCH (n)-[r]->(m)
            RETURN id(n), labels(n), properties(n),
                   id(r), type(r), properties(r),
                   id(m), labels(m), properties(m)
            LIMIT {limit}
        """)
        rows = cur.fetchall()
        conn.close()

        nodes_map = {}
        edges = []
        triples = []

        for row in rows:
            n_id, n_labels, n_props, r_id, r_type, r_props, m_id, m_labels, m_props = row

            # 노드 추가 (중복 제거)
            for nid, labels, props in [(n_id, n_labels, n_props), (m_id, m_labels, m_props)]:
                key = str(nid)
                if key not in nodes_map:
                    nodes_map[key] = {
                        "id": key,
                        "label": (labels[0] if labels else "node"),
                        "props": _safe_props(props or {})
                    }

            # 엣지
            edges.append({
                "source": str(n_id),
                "target": str(m_id),
                "type": str(r_type),
                "props": _safe_props(r_props or {})
            })

            # Triple 형식 (LLM 토큰 효율)
            src_key = _key_of(n_props)
            tgt_key = _key_of(m_props)
            triples.append([src_key, str(r_type), tgt_key])

        if fmt == "triple":
            return jsonify({
                "graph_path": graph_path,
                "triple_count": len(triples),
                "triples": triples
            })

        return jsonify({
            "graph_path": graph_path,
            "node_count": len(nodes_map),
            "edge_count": len(edges),
            "nodes": list(nodes_map.values()),
            "edges": edges
        })

    except Exception:
        current_app.logger.exception("graph 조회 API 오류")
        return jsonify({"error": "internal error"}), 500


@graph_read_bp.route('/schema', methods=['GET'])
def graph_schema():
    """그래프 스키마 요약 (라벨별 노드/엣지 카운트)."""
    if not _check_api_key(request):
        return jsonify({"error": "Invalid API key"}), 401

    graph_path = request.args.get('graph_path', '')
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"error": "Invalid graph_path"}), 400

    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"SET graph_path = {graph_path}")

        cur.execute("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC")
        node_stats = [{"label": str(r[0]), "count": int(r[1])} for r in cur.fetchall()]

        cur.execute("MATCH ()-[r]->() RETURN type(r) AS edge, count(r) AS cnt ORDER BY cnt DESC")
        edge_stats = [{"type": str(r[0]), "count": int(r[1])} for r in cur.fetchall()]

        conn.close()
        return jsonify({
            "graph_path": graph_path,
            "node_labels": node_stats,
            "edge_types": edge_stats,
            "total_nodes": sum(s["count"] for s in node_stats),
            "total_edges": sum(s["count"] for s in edge_stats),
        })
    except Exception:
        current_app.logger.exception("graph 조회 API 오류")
        return jsonify({"error": "internal error"}), 500


# ─── 헬퍼 ─────────────────────────────────────────────────────
def _serialize(v):
    """psycopg2 결과 직렬화."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool, list, dict)):
        return v
    return str(v)


def _safe_props(props):
    """props 직렬화 + 큰 필드 제거."""
    return {k: _serialize(v) for k, v in props.items() if v is not None}


def _key_of(props):
    """노드의 대표 키 (LLM 추론용)."""
    if not props:
        return "_"
    for k in ('name', 'korn_flnm', 'flnm', 'telno', 'account_no',
              'ip_addr', 'url_addr', 'dmn_addr'):
        if k in props and props[k]:
            return str(props[k])
    return str(list(props.values())[0])[:30]
