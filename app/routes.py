# app/routes.py
from flask import Blueprint, render_template, request, jsonify, current_app, session
from collections import defaultdict
from datetime import datetime, timezone
import json
import time


# ── 비주얼 쿼리 감사(Phase 1) ─────────────────────────────────────
#   수사관의 그래프 조작(확장/경로/네트워크)을 TB_AUDIT_LOG 에 세션 단위로 기록한다.
#   목적: 재현성·증거능력. 서버에서 기록해야 위변조 불가(프론트 우회 방지).
def _audit_count(r):
    """결과 요소 수 — 조작별 반환 형태(list/dict) 흡수."""
    if isinstance(r, list):
        return len(r)
    if isinstance(r, dict):
        for k in ('elements', 'nodes', 'hubs'):
            if isinstance(r.get(k), list):
                return len(r[k])
    return None


def _audit_visual(action_cd, graph_path, session_id, input_cn='', cypher_cn='',
                  result_cnt=None, exec_ms=None, status='success'):
    """비주얼 조작 감사 로그 → TB_AUDIT_LOG. **비동기 fire-and-forget** — 조작 응답을
    절대 지연/차단하지 않는다(감사 DB가 느리거나 죽어도 수사 조작은 정상 진행).
    Phase 1: cypher_cn 은 재현용 대표 쿼리(실제 실행 Cypher 정밀 캡처는 후속 단계)."""
    import threading
    try:
        app = current_app._get_current_object()   # 스레드에서 쓸 실제 app 참조
    except Exception:
        return

    def _work():
        try:
            with app.app_context():
                from app.services.langgraph_agent import LangGraphAgent
                LangGraphAgent._write_audit_log(
                    action_cd=action_cd, graph_path=graph_path, cypher_cn=cypher_cn,
                    input_cn=input_cn, result_status=status, result_cnt=result_cnt,
                    exec_ms=exec_ms, session_id=session_id)
        except Exception:
            pass

    try:
        threading.Thread(target=_work, daemon=True).start()
    except Exception:
        pass

# 메인 API Rate Limiter: {ip: {minute_bucket: count}}
_ip_counters: dict = defaultdict(lambda: defaultdict(int))
_MAIN_API_RATE_LIMIT = 60  # 분당 60회


def _check_ip_rate_limit(ip: str) -> bool:
    """IP 기반 Rate Limit. True=허용, False=초과"""
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    _ip_counters[ip][bucket] += 1
    # 현재 버킷 카운트만 사용 (오래된 버킷 정리)
    for old_bucket in list(_ip_counters[ip]):
        if old_bucket != bucket:
            del _ip_counters[ip][old_bucket]
    return _ip_counters[ip][bucket] <= _MAIN_API_RATE_LIMIT

# [서비스 모듈들 Import]
from app.services.ai_service import AIService
from app.services.etl_service import ETLService
from app.services.graph_service import GraphService
from app.services.subgraph_service import SubGraphService
from app.services.rdb_to_graph_service import RdbToGraphService
from app.services.langgraph_agent import LangGraphAgent, InvestigationSession
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

# ── 수사 세션 저장소 (서버 메모리, 최대 200개 LRU) ──────────────────
_MAX_SESSIONS = 200
_sessions: dict = {}          # session_id → InvestigationSession
_session_order: list = []     # 삽입 순서 추적 (LRU)

def _get_or_create_session(session_id: str, graph_path: str) -> InvestigationSession:
    if session_id and session_id in _sessions:
        sess = _sessions[session_id]
        # 그래프 전환 시 옛 graph_path 고정 방지 — 요청 그래프와 다르면 세션 재생성
        if getattr(sess, 'graph_path', None) != graph_path:
            sess = InvestigationSession(graph_path=graph_path)
            _sessions[session_id] = sess
        return sess
    sess = InvestigationSession(graph_path=graph_path)
    if session_id:
        if len(_sessions) >= _MAX_SESSIONS:
            oldest = _session_order.pop(0)
            _sessions.pop(oldest, None)
        _sessions[session_id] = sess
        _session_order.append(session_id)
    return sess


def _save_session_db(session_id: str, sess: InvestigationSession, question: str):
    """TB_INVEST_SESSION 에 세션 스냅샷 UPSERT (실패 시 조용히 무시)"""
    if not session_id:
        return
    try:
        import json
        from app.services.rdb_to_graph_service import RdbToGraphService
        snap = sess.snapshot()
        conn = RdbToGraphService.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO TB_INVEST_SESSION
                (SESSION_ID, GRAPH_PATH, STATUS_CD, QUESTION_CN, ENTITY_CTX, UPDATED_AT)
            VALUES (%s, %s, 'IN_PROGRESS', %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (SESSION_ID) DO UPDATE SET
                STATUS_CD  = 'IN_PROGRESS',
                QUESTION_CN = EXCLUDED.QUESTION_CN,
                ENTITY_CTX  = EXCLUDED.ENTITY_CTX,
                UPDATED_AT  = CURRENT_TIMESTAMP
        """, (
            session_id,
            snap.get("graph_path"),
            question[:500],
            json.dumps(snap.get("entity_context", []), ensure_ascii=False)
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

# ------------------------------
# 1. 기본 페이지
# ------------------------------
@bp.route('/')
def index():
    # UI 세션 인증: same-origin UI 가 /api/v1 의 require_api_or_ui 엔드포인트를
    # 하드코딩 키 없이 세션 쿠키로 호출할 수 있게 함.
    session['ui_authorized'] = True
    session.permanent = True
    return render_template('index.html',
                           default_graph_path=current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))

# ------------------------------
# 2. 그래프 기본 기능 (검색, 초기화, 확장, 경로) -> GraphService 사용
# ------------------------------
@bp.route('/api/graph/clear', methods=['POST'])
def clear_graph():
    data = request.get_json()
    graph_path = data.get('graph_path', '').strip()
    
    if not graph_path: return jsonify({"status": "error", "message": "그래프 이름 없음"}), 400
    
    # 보안: 그래프 이름 유효성 검사
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400
    
    success, msg = GraphService.clear_graph(graph_path)
    if success: return jsonify({"status": "success", "message": msg})
    else: return jsonify({"status": "error", "message": msg}), 500

@bp.route('/api/graph/list', methods=['GET'])
def list_graphs():
    """그래프 목록 조회"""
    graphs = GraphService.list_graphs()
    return jsonify({"status": "success", "graphs": graphs})

@bp.route('/api/graph/create', methods=['POST'])
def create_graph():
    """새 그래프 생성"""
    data = request.get_json()
    graph_name = data.get('graph_name', '').strip()
    
    if not graph_name:
        return jsonify({"status": "error", "message": "그래프 이름이 필요합니다."}), 400
    
    # 이름 유효성 검사 (영문, 숫자, 언더스코어만)
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_name):
        return jsonify({"status": "error", "message": "그래프 이름은 영문자로 시작해야 하며, 영문, 숫자, 언더스코어만 사용 가능합니다."}), 400
    
    success, msg = GraphService.create_graph(graph_name)
    if success:
        return jsonify({"status": "success", "message": msg, "graph_name": graph_name})
    else:
        return jsonify({"status": "error", "message": msg}), 500

@bp.route('/api/graph/delete', methods=['POST'])
def delete_graph():
    """그래프 삭제"""
    data = request.get_json()
    graph_name = data.get('graph_name', '').strip()
    
    if not graph_name:
        return jsonify({"status": "error", "message": "그래프 이름이 필요합니다."}), 400
    
    # 보안: 그래프 이름 유효성 검사
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_name):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400
    
    success, msg = GraphService.delete_graph(graph_name)
    if success:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"status": "error", "message": msg}), 500

@bp.route('/api/graph/node/create', methods=['POST'])
def create_manual_node():
    """수동으로 그래프 노드 추가"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        label = data.get('label')
        properties = data.get('properties') or data.get('props', {})
        if not graph_name or not label:
            return jsonify({"status": "error", "message": "graph_name and label required"}), 400
        success, res = GraphService.create_manual_node(graph_name, label, properties)
        if success:
            return jsonify({"status": "success", "node_id": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/graph/edge/create', methods=['POST'])
def create_manual_edge():
    """수동으로 그래프 엣지 추가"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        src_id = data.get('src_id')
        tgt_id = data.get('tgt_id')
        label = data.get('label')
        properties = data.get('properties', {})
        if not all([graph_name, src_id, tgt_id, label]):
            return jsonify({"status": "error", "message": "graph_name, src_id, tgt_id, label required"}), 400
        success, res = GraphService.create_manual_edge(graph_name, src_id, tgt_id, label, properties)
        if success:
            return jsonify({"status": "success", "edge_id": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/graph/element/delete', methods=['POST'])
def delete_manual_element():
    """수동으로 노드/엣지 삭제"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        element_id = data.get('element_id')
        is_edge = data.get('is_edge', False)
        if not graph_name or not element_id:
            return jsonify({"status": "error", "message": "graph_name and element_id required"}), 400
        success, res = GraphService.delete_element(graph_name, element_id, is_edge)
        if success:
            return jsonify({"status": "success", "message": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/api/graph/load', methods=['GET'])
def load_graph_data():
    """선택된 그래프의 전체 노드/엣지 동기식 로드 (최대 N 건)"""
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    limit = request.args.get('limit', 300, type=int)
    
    # [Fix] psycopg2가 AgensGraph Vertex/Edge 객체를 직렬화 못하는 문제 해결.
    # RETURN n, r, m → 0 rows 리턴됨 (psycopg2 직렬화 실패)
    # RETURN id(n), labels(n), properties(n), type(r), id(m), labels(m), properties(m) → 정상 리턴
    # 따라서 명시적 컬럼 추출 방식으로 변경하고, 직접 Cytoscape 포맷으로 조립.
    
    import psycopg2 as _pg2
    from app.services.graph_service import GraphService
    from app.database import safe_set_graph_path

    elements = []
    node_ids = set()

    try:
        conn = _pg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        logger.error(f"[GraphLoad] DB 연결 실패: {e}")
        return jsonify([])

    try:
        safe_set_graph_path(cur, graph_path)

        # P0: 규모 가드 — 전체 엣지 수가 limit 초과면 잘림 신호(meta)를 실어
        #     프론트가 "질의/검색으로 좁혀 보세요" 안내를 띄우게 함(전체 통짜 렌더 방지)
        truncated_meta = None
        try:
            cur.execute("MATCH ()-[r]->() RETURN count(r)")
            total_edges = int(cur.fetchone()[0])
            if total_edges > limit:
                truncated_meta = {"group": "meta", "data": {
                    "kind": "graph_truncated", "shown_edges": limit, "total_edges": total_edges}}
        except Exception:
            pass

        # 딥링크 focus: 특정 IP(거점)에 접속(used_ip)한 노드만 펼침 — 대시보드 카드 클릭 진입용(결정론)
        import re
        focus_ip = request.args.get('ip', '').strip()
        if focus_ip and re.match(r'^[0-9a-fA-F.:]{3,45}$', focus_ip):
            cypher_query = f"""
                MATCH (n)-[r]->(m:vt_ip {{ip_addr:'{focus_ip}'}})
                RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)
                LIMIT {limit}
            """
            truncated_meta = None
            logger.info(f"▶ [GraphLoad] graph={graph_path} focus_ip={focus_ip}")
        else:
            cypher_query = f"""
                MATCH (n)-[r]->(m)
                RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)
                LIMIT {limit}
            """
            logger.info(f"▶ [GraphLoad] graph={graph_path} Cypher: MATCH (n)-[r]->(m) RETURN ... LIMIT {limit}")
        cur.execute(cypher_query)
        rows = cur.fetchall()

        for r in rows:
            if len(r) < 8:
                continue

            n_id, n_labels, n_props, r_id, r_type, m_id, m_labels, m_props = r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]

            # 노드 n 추가
            n_id_str = str(n_id)
            if n_id_str not in node_ids:
                node_ids.add(n_id_str)
                n_label = n_labels[0] if isinstance(n_labels, list) and n_labels else str(n_labels)
                elements.append({
                    "group": "nodes",
                    "data": {
                        "id": n_id_str,
                        "label": str(n_label).replace('"', ''),
                        "props": GraphService.safe_props(n_props if isinstance(n_props, dict) else {})
                    }
                })

            # 노드 m 추가
            m_id_str = str(m_id)
            if m_id_str not in node_ids:
                node_ids.add(m_id_str)
                m_label = m_labels[0] if isinstance(m_labels, list) and m_labels else str(m_labels)
                elements.append({
                    "group": "nodes",
                    "data": {
                        "id": m_id_str,
                        "label": str(m_label).replace('"', ''),
                        "props": GraphService.safe_props(m_props if isinstance(m_props, dict) else {})
                    }
                })

            # 엣지 추가 (n → m)
            edge_id = str(r_id)
            elements.append({
                "group": "edges",
                "data": {
                    "id": edge_id,
                    "source": n_id_str,
                    "target": m_id_str,
                    "label": str(r_type).replace('"', '') if r_type else "관계",
                    "props": {}
                }
            })

        logger.info(f"▶ [GraphLoad] 결과: 노드 {len(node_ids)}개, 엣지 {len(elements)-len(node_ids)}개"
                    + (f" (전체 {truncated_meta['data']['total_edges']}엣지 중 {limit} 표시 — 잘림)" if truncated_meta else ""))
        if truncated_meta:
            elements.insert(0, truncated_meta)
        return jsonify(elements)

    except Exception as e:
        logger.error(f"[GraphLoad Error] graph={graph_path}: {e}")
        return jsonify([])
    finally:
        conn.close()

@bp.route('/api/graph/briefing', methods=['GET'])
def graph_briefing():
    """수사 브리핑 지표 — 그래프의 6하원칙 KPI·핵심거점 IP·집금·자금흐름·sameAs (브리핑 탭용, 결정론)."""
    import re
    import psycopg2 as _pg2
    from app.database import safe_set_graph_path
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"error": "invalid graph_path"}), 400
    try:
        conn = _pg2.connect(**current_app.config['DB_CONFIG']); conn.autocommit = True; cur = conn.cursor()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    def q(c):
        # 그래프마다 없는 라벨/엣지(예: 카톡만 있는 EP는 transferred_to 없음)는 예외 → 빈 리스트로 흡수
        try:
            safe_set_graph_path(cur, graph_path); cur.execute(c); return cur.fetchall()
        except Exception:
            return []

    def q1(c):
        try:
            return int(q(c)[0][0])
        except Exception:
            return 0

    def isum(rows):
        return sum(int(x[0]) for x in rows if x[0] is not None and str(x[0]).isdigit())

    D = {"graph_path": graph_path}
    try:
        D['n_case'] = q1("MATCH (c:vt_case) RETURN count(*)")
        D['n_bacnt'] = q1("MATCH (b:vt_bacnt) RETURN count(*)")
        D['damage_total'] = isum(q("MATCH (c:vt_case) WHERE c.damage_amt IS NOT NULL RETURN c.damage_amt"))
        D['fund_total'] = isum(q("MATCH ()-[e:transferred_to]->() WHERE e.total_amount IS NOT NULL RETURN e.total_amount"))
        D['n_realname'] = q1("MATCH (p:vt_psn) WHERE p.source_id CONTAINS 'naver' RETURN count(*)")
        D['pierce'] = q1("MATCH (b:vt_bacnt)-[:belongs_to]->(o:vt_org {org_name:'피어스미디어'}) RETURN count(b)")
        D['total_nodes'] = q1("MATCH (n) RETURN count(*)")
        D['total_edges'] = q1("MATCH ()-[r]->() RETURN count(*)")
        hubs = []
        try:
            for row in q("MATCH (i:vt_ip) WHERE i.ep_count IN ['3','4','5','6'] RETURN i.ip_addr, i.ep_origin, i.ep_count"):
                ip, o, c = row[0], row[1], row[2]
                tn = q1(f"MATCH (t:vt_telno)-[:used_ip]->(:vt_ip {{ip_addr:'{ip}'}}) RETURN count(t)")
                ac = q1(f"MATCH (d:vt_id)-[:used_ip]->(:vt_ip {{ip_addr:'{ip}'}}) RETURN count(d)")
                hubs.append({'ip': ip, 'eps': o or '', 'ep_count': int(c) if c else 0, 'telno': tn, 'accounts': ac})
        except Exception:
            pass
        D['hubs'] = sorted(hubs, key=lambda x: -x['ep_count'])[:8]
        ft = []
        for row in q("MATCH (x:vt_bacnt)-[e:transferred_to]->(y:vt_bacnt) WHERE e.total_amount IS NOT NULL RETURN x.dpstr, y.dpstr, e.total_amount"):
            if row[2] is not None and str(row[2]).isdigit():
                ft.append({'from': row[0] or '?', 'to': row[1] or '?', 'amt': int(row[2])})
        D['fund_top'] = sorted(ft, key=lambda x: -x['amt'])[:6]
        try:
            D['sameas'] = [{'a': r[0], 'b': r[1], 'm': r[2]}
                           for r in q("MATCH (p1:vt_psn)-[e:sameAs]->(p2:vt_psn) RETURN p1.name, p2.name, e.method")][:10]
        except Exception:
            D['sameas'] = []

        # PageRank 영향력 Top (scripts/graph_analytics.py --set 후 pagerank 속성이 있을 때만)
        def _toppr(label, kexpr):
            rows = q(f"MATCH (n:{label}) WHERE n.pagerank IS NOT NULL RETURN {kexpr}, n.pagerank")
            top = sorted((r for r in rows if r[0] and r[1]), key=lambda x: -float(x[1]))[:5]
            return [{'k': r[0], 'pr': round(float(r[1]), 4)} for r in top]
        D['influence'] = {'bacnt': _toppr('vt_bacnt', 'coalesce(n.dpstr,n.account_no)'),
                          'psn': _toppr('vt_psn', 'n.name'),
                          'org': _toppr('vt_org', 'n.org_name')}
    except Exception as e:
        conn.close(); return jsonify({"error": str(e)}), 500
    conn.close()
    return jsonify(D)


@bp.route('/api/search', methods=['GET'])
def search_node():
    keyword = request.args.get('keyword', '').strip()
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    
    # 서비스 호출
    elements = GraphService.search_nodes(keyword, graph_path)
    return jsonify(elements)

@bp.route('/api/expand', methods=['GET'])
def expand_node():
    # 'id' 또는 'node_id' 둘 다 지원
    node_id = request.args.get('id') or request.args.get('node_id')
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    session_id = request.args.get('session_id')
    cap = request.args.get('cap', 200, type=int)   # P0: 방향별 이웃 상한 (고차수 허브 폭증 방지)

    if not node_id: return jsonify([])

    # 서비스 호출
    _t0 = time.time()
    elements = GraphService.expand_node(node_id, graph_path, cap=cap)
    _audit_visual('EXPAND', graph_path, session_id,
                  input_cn=f'node_id={node_id}',
                  cypher_cn=f"MATCH (n)-[r]-(m) WHERE id(n)='{node_id}' RETURN r, m",
                  result_cnt=_audit_count(elements), exec_ms=int((time.time() - _t0) * 1000))
    return jsonify(elements)

@bp.route('/api/path', methods=['POST'])
def find_path():
    data = request.get_json()
    src = data.get('source')
    tgt = data.get('target')
    graph_path = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    session_id = data.get('session_id')

    _t0 = time.time()
    found, elements = GraphService.find_shortest_path(src, tgt, graph_path)
    _audit_visual('PATH', graph_path, session_id,
                  input_cn=f'{src} -> {tgt}',
                  cypher_cn=f"MATCH p=shortestPath((a)-[*..6]-(b)) WHERE id(a)='{src}' AND id(b)='{tgt}' RETURN p",
                  result_cnt=(_audit_count(elements) if found else 0),
                  status=('success' if found else 'not_found'),
                  exec_ms=int((time.time() - _t0) * 1000))

    if found: return jsonify({"found": True, "elements": elements})
    else: return jsonify({"found": False, "message": "경로를 찾을 수 없습니다."})

# ------------------------------
# 2.1 N-depth 다단계 추적 API
# ------------------------------
@bp.route('/api/expand/multi', methods=['GET'])
def multi_hop_expand():
    """N-hop 다단계 확장"""
    node_id = request.args.get('id') or request.args.get('node_id')
    depth = request.args.get('depth', 2, type=int)
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    
    if not node_id:
        return jsonify({"error": "node id required"}), 400

    session_id = request.args.get('session_id')
    _t0 = time.time()
    result = GraphService.multi_hop_expand(node_id, depth, graph_path)
    _audit_visual('MULTI_HOP', graph_path, session_id,
                  input_cn=f'node_id={node_id} depth={depth}',
                  cypher_cn=f"MATCH (n)-[r*1..{depth}]-(m) WHERE id(n)='{node_id}' RETURN r, m",
                  result_cnt=_audit_count(result), exec_ms=int((time.time() - _t0) * 1000))
    return jsonify(result)

@bp.route('/api/network/accomplice', methods=['GET'])
def accomplice_network():
    """공범 네트워크 조회"""
    node_id = request.args.get('id') or request.args.get('node_id')
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))

    if not node_id:
        return jsonify({"error": "node id required"}), 400

    session_id = request.args.get('session_id')
    _t0 = time.time()
    result = GraphService.find_accomplice_network(node_id, graph_path)
    _audit_visual('ACCOMPLICE', graph_path, session_id,
                  input_cn=f'node_id={node_id}',
                  cypher_cn=f"/* accomplice network for id(n)='{node_id}' */",
                  result_cnt=_audit_count(result), exec_ms=int((time.time() - _t0) * 1000))
    return jsonify(result)

@bp.route('/api/modeler/query-match', methods=['POST'])
def modeler_query_match():
    """비주얼 쿼리 빌더 — modeler 패턴(schema) → MATCH 조회 → 매칭 데이터 반환.
    body: {schema:{nodes,edges}, graph_path, session_id?, limit?}"""
    data = request.get_json() or {}
    schema = data.get('schema', {})
    graph_path = data.get('graph_path') or current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6')
    session_id = data.get('session_id')
    limit = data.get('limit', 100)

    _t0 = time.time()
    result = GraphService.run_visual_query(schema, graph_path, limit)
    _audit_visual('VISUAL_QUERY', graph_path, session_id,
                  input_cn=f"nodes={len(schema.get('nodes', []))} edges={len(schema.get('edges', []))}",
                  cypher_cn=result.get('cypher', ''),
                  result_cnt=result.get('match_count'),
                  status=('error' if result.get('error') else 'success'),
                  exec_ms=int((time.time() - _t0) * 1000))
    return jsonify(result)

@bp.route('/api/network/hubs', methods=['GET'])
def hub_nodes():
    """허브 노드 탐지"""
    graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    top_n = request.args.get('top_n', 10, type=int)

    session_id = request.args.get('session_id')
    _t0 = time.time()
    hubs = GraphService.find_hub_nodes(graph_path, top_n)
    _audit_visual('HUB', graph_path, session_id,
                  input_cn=f'top_n={top_n}',
                  cypher_cn=f"/* hub detection top {top_n} */",
                  result_cnt=_audit_count(hubs), exec_ms=int((time.time() - _t0) * 1000))
    return jsonify({"hubs": hubs})

# ------------------------------
# 2.5 RDB → GDB 온톨로지 기반 변환
# ------------------------------
@bp.route('/api/rdb/to-graph', methods=['POST'])
def rdb_to_graph():
    """RDB 데이터를 KICS 온톨로지 기반으로 GDB에 변환"""
    try:
        data = request.get_json() or {}
        graph_name = data.get('graph_name', 'test_ai01')

        # V4.0 격리 스키마 — 기본 test_v40 (DA팀 V3.7 운영 적용 전 안전 격리)
        source_schema = (data.get('source_schema') or 'test_v40').strip()
        current_app.config['_V40_TARGET_SCHEMA'] = source_schema
        current_app.logger.info(f"[V4.0] /api/rdb/to-graph graph={graph_name} source_schema={source_schema}")

        success, stats = RdbToGraphService.transfer_data(graph_name)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "RDB → GDB 온톨로지 기반 변환 완료",
                "stats": stats
            })
        else:
            return jsonify({
                "status": "error",
                "message": str(stats)
            }), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/transfer-case', methods=['POST'])
def rdb_transfer_case():
    """특정 사건번호에 속한 노드·엣지만 부분 ETL (수사 세션 시작용)"""
    try:
        data = request.get_json() or {}
        case_no = data.get('case_no', '').strip()
        graph_name = data.get('graph_name', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
        if not case_no:
            return jsonify({"status": "error", "message": "case_no 필드가 필요합니다"}), 400

        success, stats = RdbToGraphService.transfer_case(case_no, graph_name)

        if success:
            return jsonify({
                "status": "success",
                "message": f"사건 {case_no} 부분 ETL 완료",
                "stats": stats
            })
        else:
            return jsonify({"status": "error", "message": str(stats)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/api/rdb/conversion-preview', methods=['GET'])
def rdb_conversion_preview():
    """변환 전 미리보기 (각 테이블의 레코드 수 확인)"""
    try:
        preview = RdbToGraphService.get_conversion_preview()
        if preview:
            return jsonify({"status": "success", "preview": preview})
        else:
            return jsonify({"status": "error", "message": "미리보기 생성 실패"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 2.6  온톨로지 변환 마법사 (Wizard) API  — v3.5 POLE 6-Layer
# ============================================================

# 진행 중인 wizard 작업 저장소
_wizard_jobs: dict = {}

@bp.route('/api/ontology/wizard/preview', methods=['GET'])
def ontology_wizard_preview():
    """선택한 RDB 스키마의 테이블 레코드 수 + v3.5 온톨로지 매핑 반환"""
    schema = request.args.get('schema', 'test_ccop')
    try:
        import psycopg2, re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', schema):
            return jsonify({"status": "error", "message": "유효하지 않은 스키마명"}), 400

        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        cur = conn.cursor()

        # v3.5 POLE 6계층 매핑 정의
        layer_map = [
            {
                "layer": "Case",    "layer_ko": "사건 (Case)",    "color": "#e17055",
                "items": [
                    {"table": "tb_incdnt_mst", "label": "vt_case",     "desc": "수사 사건", "key": "incdnt_no",  "pk": "flnm"},
                ]
            },
            {
                "layer": "Person",  "layer_ko": "인물/조직 (Person)", "color": "#a29bfe",
                "items": [
                    {"table": "tb_prsn",  "label": "vt_psn", "desc": "인물",  "key": "prsn_id",  "pk": "psn_id"},
                    {"table": "tb_inst",  "label": "vt_org", "desc": "조직",  "key": "inst_id",  "pk": "org_id"},
                ]
            },
            {
                "layer": "Object",  "layer_ko": "객체/증거 (Object)", "color": "#00cec9",
                "items": [
                    {"table": "tb_fin_bacnt",       "label": "vt_bacnt",  "desc": "계좌",     "key": "bacnt_no",   "pk": "account_no"},
                    {"table": "tb_telno_mst",       "label": "vt_telno",  "desc": "전화번호", "key": "telno",      "pk": "telno"},
                    {"table": "tb_vhcl_mst",        "label": "vt_vhcl",   "desc": "차량",     "key": "vhclno",     "pk": "vhclno"},
                    {"table": "tb_dgtl_file_invnt", "label": "vt_file",   "desc": "파일",     "key": "file_nm",    "pk": "hash_val"},
                    {"table": "tb_web_mlgn_idc",    "label": "vt_site",   "desc": "악성사이트","key": "url",        "pk": "url_addr"},
                ]
            },
            {
                "layer": "Event",   "layer_ko": "이벤트 (Event)",    "color": "#fdcb6e",
                "items": [
                    {"table": "tb_fin_bacnt_dlng",   "label": "vt_transfer", "desc": "이체",        "key": "dlng_sn",     "pk": "event_id"},
                    {"table": "tb_telno_call_dtl",   "label": "vt_call",     "desc": "통화",        "key": "call_sn",     "pk": "event_id"},
                    {"table": "tb_telno_sms_msg",    "label": "vt_msg",      "desc": "SMS",         "key": "sms_sn",      "pk": "event_id"},
                    {"table": "tb_chat_msg",         "label": "vt_msg",      "desc": "채팅메시지",   "key": "msg_sn",      "pk": "event_id"},
                    {"table": "tb_geo_mbl_loc_evt",  "label": "vt_movement", "desc": "기지국이동",   "key": "loc_evt_sn",  "pk": "mov_id"},
                    {"table": "tb_vhcl_lpr_evt",     "label": "vt_movement", "desc": "LPR이동",     "key": "lpr_sn",      "pk": "mov_id"},
                ]
            },
        ]

        # 엣지 규칙 정의
        edge_rules = [
            {"from": "vt_psn",     "rel": "suspect_in",  "to": "vt_case",     "source": "tb_incdnt_mst.incdnt_no + tb_prsn", "desc": "피의자 역할"},
            {"from": "vt_psn",     "rel": "victim_in",   "to": "vt_case",     "source": "tb_frd_vctm_rpt",                   "desc": "피해자 역할"},
            {"from": "vt_psn",     "rel": "has_account", "to": "vt_bacnt",    "source": "tb_fin_bacnt.dpstr_nm",             "desc": "계좌 소유"},
            {"from": "vt_psn",     "rel": "owns_phone",  "to": "vt_telno",    "source": "tb_telno_join.join_psnnm",          "desc": "전화 가입"},
            {"from": "vt_psn",     "rel": "owns_vehicle","to": "vt_vhcl",     "source": "tb_vhcl_mst.ownr_nm",              "desc": "차량 소유"},
            {"from": "vt_bacnt",   "rel": "sent_from",   "to": "vt_transfer", "source": "tb_fin_bacnt_dlng.bacnt_no",        "desc": "이체 출금계좌"},
            {"from": "vt_transfer","rel": "sent_to",     "to": "vt_bacnt",    "source": "tb_fin_bacnt_dlng.trrc_bacnt_no",   "desc": "이체 입금계좌"},
            {"from": "vt_telno",   "rel": "made_call",   "to": "vt_call",     "source": "tb_telno_call_dtl.dsptch_telno",    "desc": "발신 통화"},
            {"from": "vt_call",    "rel": "received_by", "to": "vt_telno",    "source": "tb_telno_call_dtl.rcptn_telno",     "desc": "수신 통화"},
            {"from": "vt_org",     "rel": "belongs_to",  "to": "vt_psn",      "source": "tb_inst.inst_id ↔ tb_prsn",         "desc": "기관 소속"},
        ]

        # 레코드 수 조회
        for layer in layer_map:
            for item in layer["items"]:
                try:
                    cur.execute(f'SELECT count(*) FROM {schema}."{item["table"]}"')
                    item["count"] = cur.fetchone()[0]
                except:
                    conn.rollback()
                    item["count"] = 0

        conn.close()
        return jsonify({
            "status": "success",
            "schema": schema,
            "layers": layer_map,
            "edge_rules": edge_rules
        })
    except Exception as e:
        logger.error(f"[Wizard Preview] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/api/ontology/wizard/run', methods=['POST'])
def ontology_wizard_run():
    """온톨로지 변환 마법사 실행 — 백그라운드 스레드 + 폴링"""
    import threading, uuid, re
    data = request.get_json() or {}
    graph_name = data.get('graph_name', '').strip()
    schema     = data.get('schema', 'test_ccop').strip()
    layers     = data.get('layers', [])   # ['Case','Person','Object','Event']

    if not graph_name or not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_name):
        return jsonify({"status": "error", "message": "유효한 그래프 이름을 입력하세요 (영문 시작, 영문/숫자/언더스코어)"}), 400
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', schema):
        return jsonify({"status": "error", "message": "유효하지 않은 스키마명"}), 400
    if not layers:
        return jsonify({"status": "error", "message": "변환할 레이어를 하나 이상 선택하세요"}), 400

    job_id = str(uuid.uuid4())[:8]
    _wizard_jobs[job_id] = {
        "status": "running",
        "logs": [],
        "stats": {"nodes": 0, "edges": 0},
        "graph_name": graph_name,
    }

    def _run():
        try:
            # transfer_v35(미구현·정의된 적 없음)를 정식 메서드 transfer_data로 복구.
            # transfer_data는 기본 스키마 전체 변환만 지원 → schema/layers 부분선택은 미지원(정직 로그).
            _wizard_jobs[job_id]["logs"].append(
                f"[안내] 스키마/레이어 부분선택은 현재 미지원 — 기본 스키마 전체 변환 수행 "
                f"(요청 schema={schema}, layers={layers})")
            _wizard_jobs[job_id]["logs"].append(f"[시작] '{graph_name}' 그래프로 RDB 변환")
            success, stats = RdbToGraphService.transfer_data(graph_name)
            _wizard_jobs[job_id]["stats"] = stats or {"nodes": 0, "edges": 0}
            _wizard_jobs[job_id]["logs"].append(f"[완료] success={success}, {stats}")
            _wizard_jobs[job_id]["status"] = "done" if success else "error"
        except Exception as ex:
            _wizard_jobs[job_id]["logs"].append(f"[ERROR] {ex}")
            _wizard_jobs[job_id]["status"] = "error"

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "job_id": job_id})


@bp.route('/api/ontology/wizard/status/<job_id>', methods=['GET'])
def ontology_wizard_status(job_id):
    """마법사 작업 진행 상태 폴링"""
    job = _wizard_jobs.get(job_id)
    if not job:
        return jsonify({"status": "error", "message": "작업을 찾을 수 없습니다"}), 404
    return jsonify({
        "status":     job["status"],
        "logs":       job["logs"],
        "stats":      job["stats"],
        "graph_name": job["graph_name"],
    })


# DB 정보 조회
@bp.route('/api/db/info', methods=['GET'])
def db_info():
    """현재 접속 DB 정보 반환"""
    try:
        from flask import current_app
        import psycopg2
        cfg = current_app.config['DB_CONFIG']
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        cur.execute('SELECT current_database(), version()')
        db_name, version = cur.fetchone()
        
        # RDB 테이블 목록 + 건수
        tables = {}
        rdb_tables = ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 
                       'rdb_transfers', 'rdb_calls', 'rdb_relations', 'rdb_ips']
        for t in rdb_tables:
            try:
                cur.execute(f'SELECT count(*) FROM {t}')
                tables[t] = cur.fetchone()[0]
            except:
                conn.rollback()
                tables[t] = -1  # 테이블 없음
        
        # 그래프 목록
        cur.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema','public','ag_catalog','pg_toast') AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%' ORDER BY nspname")
        graphs = [r[0] for r in cur.fetchall()]
        
        conn.close()
        return jsonify({
            "status": "success",
            "db_name": db_name,
            "host": cfg.get("host", ""),
            "port": cfg.get("port", ""),
            "version": version[:60] if version else "",
            "rdb_tables": tables,
            "graphs": graphs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# DB 목록 조회
@bp.route('/api/db/list', methods=['GET'])
def db_list():
    """서버의 전체 데이터베이스 목록 반환"""
    try:
        from flask import current_app
        import psycopg2
        cfg = current_app.config['DB_CONFIG']
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres', 'agens') ORDER BY datname")
        databases = [r[0] for r in cur.fetchall()]
        current_db = cfg.get('dbname', '')
        
        conn.close()
        return jsonify({
            "status": "success",
            "databases": databases,
            "current": current_db,
            "host": cfg.get("host", ""),
            "port": cfg.get("port", "")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# DB 전환
@bp.route('/api/db/switch', methods=['POST'])
def db_switch():
    """활성 데이터베이스 전환 (런타임)"""
    try:
        from flask import current_app
        import psycopg2
        data = request.get_json()
        target_db = data.get('db_name', '')
        
        if not target_db:
            return jsonify({"status": "error", "message": "db_name 필요"}), 400
        
        cfg = current_app.config['DB_CONFIG']
        old_db = cfg.get('dbname', '')
        
        # 연결 테스트
        test_cfg = dict(cfg)
        test_cfg['dbname'] = target_db
        try:
            test_conn = psycopg2.connect(**test_cfg)
            test_cur = test_conn.cursor()
            test_cur.execute('SELECT current_database()')
            confirmed = test_cur.fetchone()[0]
            
            # RDB 테이블 존재 여부
            rdb_tables = {}
            for t in ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 'rdb_transfers', 'rdb_calls', 'rdb_relations']:
                try:
                    test_cur.execute(f'SELECT count(*) FROM {t}')
                    rdb_tables[t] = test_cur.fetchone()[0]
                except:
                    test_conn.rollback()
                    rdb_tables[t] = -1
            
            # 그래프 목록
            test_cur.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema','public','ag_catalog','pg_toast') AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%' ORDER BY nspname")
            graphs = [r[0] for r in test_cur.fetchall()]
            
            test_conn.close()
        except Exception as e:
            return jsonify({"status": "error", "message": f"DB 연결 실패: {target_db} — {str(e)}"}), 400
        
        # 전환 실행
        cfg['dbname'] = target_db
        current_app.config['DB_CONFIG'] = cfg
        
        return jsonify({
            "status": "success",
            "message": f"DB 전환 완료: {old_db} → {target_db}",
            "db_name": confirmed,
            "rdb_tables": rdb_tables,
            "graphs": graphs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================
# 2.6 Multi-RDB 소스 관리
# ============================
# 등록된 RDB 소스 저장 (in-memory, 서버 재시작 시 초기화)
rdb_sources = {}

def _init_default_rdb_source(app):
    """앱 시작 시 기본 DB를 rdb_sources에 등록"""
    import os
    cfg = app.config.get('DB_CONFIG', {})
    # DB_CONFIG에 host가 있으면 사용, 없으면 환경변수에서 직접 읽기
    host = cfg.get('host') or os.environ.get('DB_HOST', '49.50.128.28')
    port = cfg.get('port') or os.environ.get('DB_PORT', '5333')
    dbname = cfg.get('dbname') or os.environ.get('DB_NAME', 'tccopdb')
    user = cfg.get('user') or os.environ.get('DB_USER', 'ccop')
    password = cfg.get('password') or os.environ.get('DB_PASSWORD', 'Ccop@2025')
    
    rdb_sources['default'] = {
        'alias': 'default',
        'label': f"{dbname} (기본 DB)",
        'host': host,
        'port': int(port),
        'dbname': dbname,
        'user': user,
        'password': password
    }
    logger.info(f"▶ [RDB Sources] 기본 소스 초기화: {dbname}@{host}:{port}")

@bp.route('/api/rdb/sources', methods=['GET', 'POST', 'DELETE'])
def rdb_source_management():
    """RDB 소스 관리 API
    GET: 등록된 RDB 소스 목록
    POST: 새 RDB 소스 등록 (연결 테스트 포함)
    DELETE: RDB 소스 삭제
    """
    import psycopg2
    
    # 기본 DB가 없으면 초기화
    if 'default' not in rdb_sources:
        try:
            _init_default_rdb_source(current_app)
        except Exception as e:
            logger.error(f"▶ [RDB Sources] 기본 소스 초기화 실패: {e}")
            # 환경변수 직접 사용 fallback
            import os
            rdb_sources['default'] = {
                'alias': 'default',
                'label': os.environ.get('DB_NAME', 'tccopdb') + ' (기본 DB)',
                'host': os.environ.get('DB_HOST', '49.50.128.28'),
                'port': int(os.environ.get('DB_PORT', '5333')),
                'dbname': os.environ.get('DB_NAME', 'tccopdb'),
                'user': os.environ.get('DB_USER', 'ccop'),
                'password': os.environ.get('DB_PASSWORD', 'Ccop@2025')
            }
    
    if request.method == 'GET':
        # 비밀번호는 마스킹
        result = []
        for alias, src in rdb_sources.items():
            result.append({
                'alias': src['alias'],
                'label': src.get('label', src['alias']),
                'host': src['host'],
                'port': src['port'],
                'dbname': src['dbname'],
                'user': src['user'],
                'is_default': alias == 'default'
            })
        return jsonify({"status": "success", "sources": result})
    
    elif request.method == 'POST':
        data = request.get_json()
        alias = data.get('alias', '').strip()
        host = data.get('host', '').strip()
        port = int(data.get('port', 5432))
        dbname = data.get('dbname', '').strip()
        user = data.get('user', '').strip()
        password = data.get('password', '').strip()
        label = data.get('label', '') or f"{dbname}@{host}"
        
        if not alias or not host or not dbname or not user:
            return jsonify({"status": "error", "message": "alias, host, dbname, user 필수"}), 400
        
        # 연결 테스트
        try:
            test_conn = psycopg2.connect(
                host=host, port=port, dbname=dbname,
                user=user, password=password,
                connect_timeout=5
            )
            test_conn.close()
        except Exception as e:
            return jsonify({"status": "error", "message": f"연결 실패: {e}"}), 400
        
        rdb_sources[alias] = {
            'alias': alias, 'label': label,
            'host': host, 'port': port,
            'dbname': dbname, 'user': user, 'password': password
        }
        logger.info(f"▶ [RDB Sources] 등록: {alias} ({dbname}@{host}:{port})")
        return jsonify({"status": "success", "message": f"'{alias}' RDB 소스 등록 완료"})
    
    elif request.method == 'DELETE':
        data = request.get_json()
        alias = data.get('alias', '')
        if alias == 'default':
            return jsonify({"status": "error", "message": "기본 DB는 삭제할 수 없습니다"}), 400
        if alias in rdb_sources:
            del rdb_sources[alias]
            return jsonify({"status": "success", "message": f"'{alias}' 삭제됨"})
        return jsonify({"status": "error", "message": "존재하지 않는 소스"}), 404

@bp.route('/api/rdb/tables', methods=['GET'])
def rdb_list_tables():
    """특정 RDB 소스의 테이블 목록 조회"""
    import psycopg2
    
    source_alias = request.args.get('source', 'default')
    
    # 기본 DB 초기화
    if 'default' not in rdb_sources:
        try:
            _init_default_rdb_source(current_app)
        except Exception as e:
            import os
            rdb_sources['default'] = {
                'alias': 'default', 'label': os.environ.get('DB_NAME', 'tccopdb') + ' (기본 DB)',
                'host': os.environ.get('DB_HOST', '49.50.128.28'),
                'port': int(os.environ.get('DB_PORT', '5333')),
                'dbname': os.environ.get('DB_NAME', 'tccopdb'),
                'user': os.environ.get('DB_USER', 'ccop'),
                'password': os.environ.get('DB_PASSWORD', 'Ccop@2025')
            }
    
    src = rdb_sources.get(source_alias)
    cfg = current_app.config['DB_CONFIG']

    try:
        if src:
            conn = psycopg2.connect(
                host=src['host'], port=src['port'], dbname=src['dbname'],
                user=src['user'], password=src['password'],
                connect_timeout=5
            )
            dbname = src['dbname']
        else:
            conn = psycopg2.connect(**cfg)
            dbname = cfg.get('dbname', '')
        cur = conn.cursor()
        rdb_schema = current_app.config.get('RDB_SCHEMA', 'test_ccop')

        cur.execute("""
            SELECT t.table_name,
                   GREATEST(COALESCE(c.reltuples::bigint, 0), 0) AS row_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_class c
                ON c.relname = t.table_name
                AND c.relnamespace = (
                    SELECT oid FROM pg_namespace WHERE nspname = %s
                )
            WHERE t.table_schema = %s
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """, (rdb_schema, rdb_schema))
        tables = [{"table_name": row[0], "row_count": int(row[1])} for row in cur.fetchall()]

        conn.close()
        return jsonify({
            "status": "success",
            "source": source_alias,
            "dbname": dbname,
            "tables": tables
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/browse', methods=['GET'])
def rdb_browse():
    """RDB 테이블 데이터 조회 (페이징, 다중 RDB 지원)"""
    try:
        from flask import current_app
        import psycopg2
        
        table = request.args.get('table', 'rdb_cases')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        source_alias = request.args.get('source', 'default')
        
        # 보안: 기본 DB는 rdb_, TB_, tb_ 접두사만 허용, 외부 DB는 모든 테이블 허용
        if source_alias == 'default':
            if not (table.startswith('rdb_') or table.startswith('TB_') or table.startswith('tb_')):
                return jsonify({"status": "error", "message": "허용되지 않은 테이블"}), 400
        
        # 다중 RDB 소스 연결
        src = rdb_sources.get(source_alias)
        if src:
            conn = psycopg2.connect(
                host=src['host'], port=src['port'], dbname=src['dbname'],
                user=src['user'], password=src['password']
            )
        else:
            cfg = current_app.config['DB_CONFIG']
            conn = psycopg2.connect(**cfg)
        conn.autocommit = True
        cur = conn.cursor()
        rdb_schema = current_app.config.get('RDB_SCHEMA', 'test_ccop')

        table_lower = table.lower()

        # 컬럼 정보 먼저 확인 (스키마 명시 — AgensGraph 그래프 스키마 충돌 방지)
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (rdb_schema, table_lower)
        )
        columns = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
        if not columns:
            return jsonify({"status": "error", "message": f"테이블 '{table}'을 찾을 수 없습니다. (스키마: {rdb_schema})"}), 404
        col_names = [c["name"] for c in columns]

        # 총 건수
        cur.execute(f'SELECT count(*) FROM {rdb_schema}.{table_lower}')
        total = cur.fetchone()[0]

        # 데이터 조회 (명시적 컬럼 목록 사용 — SELECT * 순서 의존 방지)
        col_list = ', '.join(f'"{c}"' for c in col_names)
        cur.execute(
            f'SELECT {col_list} FROM {rdb_schema}.{table_lower} ORDER BY 1 LIMIT %s OFFSET %s',
            (limit, offset)
        )
        rows = []
        for r in cur.fetchall():
            row = {col_names[i]: (str(val) if val is not None else None) for i, val in enumerate(r)}
            rows.append(row)
        
        conn.close()
        return jsonify({
            "status": "success",
            "table": table,
            "columns": columns,
            "rows": rows,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if limit > 0 else 0
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------------------
# 3. Text2Cypher AI 질의 기능
# ------------------------------
@bp.route('/api/query/ai', methods=['POST'])
def query_ai():
    if not _check_ip_rate_limit(request.remote_addr):
        return jsonify({"error": f"요청이 너무 많습니다. 분당 {_MAIN_API_RATE_LIMIT}회 제한."}), 429
    data = request.get_json()
    question = data.get('question')
    graph_path = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
    session_id = data.get('session_id')

    try:
        sess = _get_or_create_session(session_id, graph_path)
        temporal_continuity = bool(data.get('temporal_continuity', False))  # Q3 [시간순 연속성 적용]
        agent_res = sess.ask(question, temporal_continuity=temporal_continuity)
        _save_session_db(session_id, sess, question)

        if agent_res.get("status") == "error":
            return jsonify({"error": agent_res.get("message", "에이전트 처리 오류")}), 500

        return jsonify({
            "elements": agent_res.get("elements", []),
            "cypher": agent_res.get("cypher", ""),
            "intent": agent_res.get("intent", "QUERY"),
            "hints": agent_res.get("hints", []),
            "warnings": agent_res.get("warnings", []),   # Q3 시간순 연속성 N형 구간 안내
            "session_id": session_id,
            "entity_count": len(sess.entity_context)
        })
    except Exception as e:
        logger.error(f"Agent Query Error: {e}")
        return jsonify({"error": "분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}), 500

# ------------------------------
# 3.5 법률 RAG (Legal RAG) — UI 세션용. 알고리즘/백엔드는 LegalRAGService (파트너 API /api/v1/legal/* 와 동일 서비스).
# ------------------------------
@bp.route('/api/legal/search', methods=['POST'])
def legal_search():
    if not _check_ip_rate_limit(request.remote_addr):
        return jsonify({"status": "error", "message": f"요청이 너무 많습니다. 분당 {_MAIN_API_RATE_LIMIT}회 제한."}), 429
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({"status": "error", "message": "질문을 입력하세요."}), 400
    mode = data.get('mode', 'hybrid')
    if mode not in ('hybrid', 'bm25', 'vector'):
        return jsonify({"status": "error", "message": "mode 는 hybrid/bm25/vector 중 하나여야 합니다."}), 400
    top_k = min(max(int(data.get('top_k', 5) or 5), 1), 20)
    rerank = data.get('rerank')  # None=auto
    try:
        from app.services.legal_rag_service import LegalRAGService
        result = LegalRAGService.hybrid_search(question, top_k=top_k, mode=mode, rerank=rerank)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Legal search error: {e}")
        return jsonify({"status": "error", "message": "법률 검색 중 오류가 발생했습니다."}), 500


@bp.route('/api/legal/answer', methods=['POST'])
def legal_answer():
    if not _check_ip_rate_limit(request.remote_addr):
        return jsonify({"status": "error", "message": f"요청이 너무 많습니다. 분당 {_MAIN_API_RATE_LIMIT}회 제한."}), 429
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({"status": "error", "message": "질문을 입력하세요."}), 400
    top_k = min(max(int(data.get('top_k', 4) or 4), 1), 10)
    try:
        from app.services.legal_rag_service import LegalRAGService
        result = LegalRAGService.answer(question, top_k=top_k)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Legal answer error: {e}")
        return jsonify({"status": "error", "message": "답변 생성 중 오류가 발생했습니다."}), 500


@bp.route('/api/legal/status', methods=['GET'])
def legal_status():
    try:
        from app.services.legal_rag_service import LegalRAGService
        return jsonify({"status": "success", **LegalRAGService.status()})
    except Exception as e:
        logger.error(f"Legal status error: {e}")
        return jsonify({"status": "error", "message": "상태 조회 오류"}), 500

# ------------------------------
# 4. ETL 관련 기능 -> ETLService 사용
# ------------------------------
@bp.route('/api/etl/ai-suggest', methods=['POST'])
def etl_suggest():
    try:
        file = request.files['file']
        import pandas as pd
        df = pd.read_csv(file, nrows=3)
        headers = df.columns.tolist()
        sample = df.iloc[0].astype(str).tolist()
        
        mapping = AIService.suggest_mapping(headers, sample)
        return jsonify({"status": "success", "mapping": mapping})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/analyze-csv', methods=['POST'])
def rdb_analyze_csv():
    """CSV 파일의 컬럼을 분석하여 RDB 매핑 초안을 반환 (2-Stage AI Mapping Step 1)"""
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        
        file = request.files['file']
        import pandas as pd
        
        # CSV 로드
        df = pd.read_csv(file).fillna('')
        sample_rows = df.head(3).to_dict('records')
        cols = df.columns
        
        # --- Column Mapping 추론 (rdb_service와 동일한 방식) ---
        from app.services.ontology_service import KICSCrimeDomainOntology
        from app.services.ai_service import AIService
        
        col_map = {}
        patterns = KICSCrimeDomainOntology.COLUMN_PATTERNS
        type_to_rdb = KICSCrimeDomainOntology.COLUMN_TYPE_TO_RDB
        
        priority_order = ['caller', 'callee', 'sender', 'receiver', 'nickname']
        sorted_patterns = {t: patterns[t] for t in priority_order if t in patterns}
        for t, cfg in patterns.items():
            if t not in sorted_patterns: sorted_patterns[t] = cfg
        
        # Pass 1: Exact matches
        unmatched_cols = []
        for c in cols:
            c_lower = c.lower().strip()
            matched = False
            for type_name, config in sorted_patterns.items():
                for pattern in config["patterns"]:
                    if c_lower == pattern.lower():
                        col_type = type_to_rdb.get(type_name, type_name)
                        if col_type not in col_map:
                            col_map[col_type] = c
                            matched = True
                        elif col_map[col_type] != c:
                            if "actno" in c_lower or "dpstr" in c_lower:
                                col_map[col_type] = c
                        break
                if matched: break
            if not matched: unmatched_cols.append(c)
        
        # Pass 2: Partial matches
        still_unmatched = []
        for c in unmatched_cols:
            c_lower = c.lower().strip()
            matched = False
            for type_name, config in sorted_patterns.items():
                for pattern in config["patterns"]:
                    if pattern.lower() in c_lower or c_lower in pattern.lower():
                        col_type = type_to_rdb.get(type_name, type_name)
                        if col_type not in col_map:
                            col_map[col_type] = c
                            matched = True
                        elif col_map[col_type] != c:
                            if "actno" in c_lower or "dpstr" in c_lower:
                                col_map[col_type] = c
                        break
                if matched: break
            if not matched: still_unmatched.append(c)
            
        # Pass 3: LLM Inference
        llm_inferred_types = {}
        if still_unmatched:
            llm_result = AIService.infer_column_mapping_for_rdb(still_unmatched, sample_rows)
            for c, type_name in llm_result.items():
                if type_name and type_name != 'ignore':
                    col_type = type_to_rdb.get(type_name, type_name)
                    # 기존 매핑을 덮어쓰지 않고 추가
                    if col_type not in col_map:
                        col_map[col_type] = c
                        llm_inferred_types[c] = col_type
        
        # UI 형태로 변환
        ui_mapping = []
        for c in cols:
            mapped_type = None
            method = 'unmapped'
            for k, v in col_map.items():
                if v == c:
                    mapped_type = k
                    if c in llm_inferred_types:
                        method = 'llm'
                    elif c not in unmatched_cols:
                        method = 'exact'
                    else:
                        method = 'partial'
                    break
            
            ui_mapping.append({
                "column": c,
                "mapped_type": mapped_type,
                "method": method
            })
            
        return jsonify({
            "status": "success",
            "mapping": ui_mapping,
            "sample_data": sample_rows
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/import', methods=['POST'])
def rdb_import():
    """CSV 파일을 RDB 테이블에 적재"""
    try:
        import json
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        
        file = request.files['file']
        
        # 임시 파일 저장 (RDBService가 파일 경로를 요구함)
        import os
        from app.services.rdb_service import RDBService
        
        temp_path = f"/tmp/{file.filename}"
        file.save(temp_path)
        
        clear_rdb = request.form.get('clear_rdb', 'false').lower() == 'true'

        # 프론트엔드에서 확정한 매핑 정보 (선택적)
        frontend_mapping_str = request.form.get('column_mapping')
        frontend_mapping = None
        if frontend_mapping_str:
            try:
                frontend_mapping = json.loads(frontend_mapping_str)
            except:
                pass

        # V4.0 메타 — SOURCE_DOMAIN / SOURCE_ID (Phase 2.1.E)
        ALLOWED_DOMAINS = {'KICS', 'OSINT', 'DIGITAL', 'EXT',
                           'INVESTIGATION', 'PARTNER', 'INFERENCE'}
        source_domain = (request.form.get('source_domain') or 'KICS').upper()
        if source_domain not in ALLOWED_DOMAINS:
            return jsonify({"status": "error",
                            "message": f"Invalid source_domain '{source_domain}'. "
                                       f"Allowed: {sorted(ALLOWED_DOMAINS)}"}), 400
        source_id = request.form.get('source_id') or None

        # V4.0 격리 스키마 — 표준화 RDB 적재 위치 (기본: test_v40)
        # DA팀 V3.7 운영 적용 전까지 public 충돌 방지
        target_schema = request.form.get('target_schema', 'test_v40').strip() or 'test_v40'
        current_app.logger.info(
            f"[V4.0] /api/rdb/import source_domain={source_domain} source_id={source_id} target_schema={target_schema}"
        )

        # search_path 사전 설정 — INSERT 가 target_schema 로 가도록
        import psycopg2 as _pg2
        try:
            _conn = _pg2.connect(**current_app.config['DB_CONFIG'])
            _conn.autocommit = True
            _cur = _conn.cursor()
            _cur.execute(f'SET search_path = "{target_schema}", public;')
            # search_path 는 connection 별이므로 RDBService 내부 재연결 시 무효
            # → RDBService 호출 직전 환경변수로 전달하기 위해 g.* 또는 config 활용
            _cur.close(); _conn.close()
        except Exception as _e:
            current_app.logger.warning(f"search_path 사전 설정 실패: {_e}")

        # RDBService 가 사용할 search_path 를 config 에 임시 주입
        current_app.config['_V40_TARGET_SCHEMA'] = target_schema

        try:
            # 스마트 라우팅 분기: 파일명이 tbl_ 로 시작하면 사전 정의된 RDB 스키마로 간주
            if file.filename.lower().startswith('tbl_'):
                success, result = RDBService.import_predefined_schema_to_rdb(
                    temp_path, file.filename, clear_existing=clear_rdb,
                    source_domain=source_domain, source_id=source_id,
                )
            else:
                success, result = RDBService.import_csv_to_rdb(
                    temp_path, clear_existing=clear_rdb,
                    custom_mapping=frontend_mapping,
                    source_domain=source_domain, source_id=source_id,
                )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        if success:
            return jsonify({
                "status": "success", 
                "stats": result,
                "message": f"RDB 적재 완료! (사건 {result['cases']}건, 피의자 {result['suspects']}명)"
            })
        else:
            return jsonify({"status": "error", "message": result}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------------------
# 5. 시스템 모니터링 (Hybrid DB Monitoring)
# ------------------------------
@bp.route('/api/admin/monitoring', methods=['GET'])
def admin_monitoring():
    """시스템 전체 모니터링 데이터 반환"""
    try:
        from app.services.monitoring_service import MonitoringService
        stats = MonitoringService.get_all_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -------------------------------------------------------
# 그래프 모델러
# -------------------------------------------------------
@bp.route('/api/modeler/rdb/columns', methods=['GET'])
def modeler_rdb_columns():
    """테이블 컬럼 목록 + 샘플 데이터 조회 (Modeler 역공학용)"""
    import psycopg2, re as _re
    source_alias = request.args.get('source', 'default')
    table = request.args.get('table', '').strip()
    if not table or not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
        return jsonify({"status": "error", "message": "유효하지 않은 테이블명"}), 400

    src = rdb_sources.get(source_alias)
    rdb_schema = current_app.config.get('RDB_SCHEMA', 'test_ccop')

    try:
        if src:
            conn = psycopg2.connect(host=src['host'], port=src['port'], dbname=src['dbname'],
                                    user=src['user'], password=src['password'], connect_timeout=5)
        else:
            conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()

        # 컬럼 정보 (RDB_SCHEMA 스키마 명시)
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (rdb_schema, table))
        cols = [{"name": r[0], "db_type": r[1], "nullable": r[2] == 'YES'} for r in cur.fetchall()]

        # 샘플 3행
        samples = []
        if cols:
            col_names = [c['name'] for c in cols]
            quoted_cols = ", ".join(f'"{c}"' for c in col_names)
            cur.execute(f'SELECT {quoted_cols} FROM {rdb_schema}."{table}" LIMIT 3')
            rows = cur.fetchall()
            samples = [dict(zip(col_names, [str(v) if v is not None else None for v in row])) for row in rows]
            for col in cols:
                col['sample'] = str(samples[0].get(col['name'], '')) if samples else ''

        conn.close()
        return jsonify({"status": "success", "table": table, "columns": cols, "samples": samples,
                        "schema": rdb_schema})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
@bp.route('/modeler')
def modeler():
    """그래프 스키마 모델러 페이지"""
    session['ui_authorized'] = True
    session.permanent = True
    return render_template('modeler.html')


@bp.route('/api/modeler/generate-cypher', methods=['POST'])
def modeler_generate_cypher():
    """스키마 정의 → AgensGraph Cypher CREATE 문 생성"""
    import re as _re
    data = request.get_json()
    schema = data.get('schema', {})
    graph_path = data.get('graph_path', 'new_graph').strip()

    if not _re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400

    nodes = schema.get('nodes', [])
    edges = schema.get('edges', [])

    lines = [f"-- 그래프 생성 (이미 존재하면 skip)\nSELECT create_graph('{graph_path}');\n"]

    node_map = {n['id']: n for n in nodes}

    for node in nodes:
        label = node.get('label', '')
        props = node.get('properties', [])
        if not props:
            props_str = ""
        else:
            sample = ", ".join(
                f"{p['name']}: '{p.get('sample', p['name']+'_값')}'"
                for p in props
            )
            props_str = f" {{{sample}}}"
        lines.append(
            f"-- [{node.get('display_name', label)}] 노드 생성 예시\n"
            f"SELECT * FROM cypher('{graph_path}', $$\n"
            f"  MERGE (n:{label}{props_str})\n"
            f"  RETURN n\n"
            f"$$) AS (n agtype);\n"
        )

    for edge in edges:
        src = node_map.get(edge.get('source_id', ''), {})
        tgt = node_map.get(edge.get('target_id', ''), {})
        edge_type = edge.get('type', 'RELATED_TO')
        src_label = src.get('label', 'SRC')
        tgt_label = tgt.get('label', 'TGT')
        src_key = src.get('key_property', 'name')
        tgt_key = tgt.get('key_property', 'name')

        eprops = edge.get('properties', [])
        if eprops:
            ep_str = " {" + ", ".join(
                f"{p['name']}: '{p.get('sample', p['name']+'_값')}'"
                for p in eprops
            ) + "}"
        else:
            ep_str = ""

        lines.append(
            f"-- [{src_label}]-[:{edge_type}]->[ {tgt_label}] 관계 생성 예시\n"
            f"SELECT * FROM cypher('{graph_path}', $$\n"
            f"  MATCH (a:{src_label}), (b:{tgt_label})\n"
            f"  WHERE a->>'{src_key}' = '값1' AND b->>'{tgt_key}' = '값2'\n"
            f"  MERGE (a)-[r:{edge_type}{ep_str}]->(b)\n"
            f"  RETURN r\n"
            f"$$) AS (r agtype);\n"
        )

    return jsonify({"status": "success", "cypher": "\n".join(lines)})


@bp.route('/api/modeler/execute', methods=['POST'])
def modeler_execute():
    """스키마 정의로 그래프 생성 실행 (그래프 생성만)"""
    import re as _re
    data = request.get_json()
    graph_path = data.get('graph_path', '').strip()

    if not graph_path or not _re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400

    success, msg = GraphService.create_graph(graph_path)
    return jsonify({"status": "success" if success else "error", "message": msg})


@bp.route('/api/modeler/join-preview', methods=['POST'])
def modeler_join_preview():
    """두 테이블 조인 컬럼 매칭 건수 및 샘플 반환"""
    import re as _re
    import psycopg2

    data = request.get_json()
    src_table = (data.get('src_table') or '').strip()
    src_col   = (data.get('src_col') or '').strip()
    tgt_table = (data.get('tgt_table') or '').strip()
    tgt_col   = (data.get('tgt_col') or '').strip()

    # 화이트리스트 검증
    pat = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    if not all(_re.match(pat, v) for v in [src_table, src_col, tgt_table, tgt_col]):
        return jsonify({"status": "error", "message": "유효하지 않은 테이블/컬럼명"}), 400

    rdb_schema = current_app.config.get('RDB_SCHEMA', 'test_ccop')
    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute(
            f'SELECT count(*) FROM {rdb_schema}."{src_table}" s '
            f'JOIN {rdb_schema}."{tgt_table}" t '
            f'ON s."{src_col}" = t."{tgt_col}"'
        )
        match_count = cur.fetchone()[0]

        cur.execute(
            f'SELECT DISTINCT s."{src_col}", t."{tgt_col}" '
            f'FROM {rdb_schema}."{src_table}" s '
            f'JOIN {rdb_schema}."{tgt_table}" t '
            f'ON s."{src_col}" = t."{tgt_col}" '
            f'LIMIT 5'
        )
        samples = [[str(r[0]), str(r[1])] for r in cur.fetchall()]
        conn.close()

        return jsonify({"status": "success", "match_count": match_count, "samples": samples})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/api/modeler/load-data', methods=['POST'])
def modeler_load_data():
    """모델러 스키마 → RDB 데이터 읽어 AgensGraph에 적재"""
    import re as _re
    import psycopg2
    from app.services.etl_service import StandardCodeMapper

    data = request.get_json()
    graph_path = (data.get('graph_path') or '').strip()
    schema = data.get('schema', {})

    if not graph_path or not _re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400

    nodes = schema.get('nodes', [])
    mappable = [n for n in nodes if n.get('rdb_table') and n.get('properties')]
    if not mappable:
        return jsonify({"status": "error", "message": "RDB 테이블이 매핑된 노드가 없습니다. RDB 가져오기 마법사를 사용해 테이블을 매핑하세요."}), 400

    # AgensGraph + RDB 연결 (동일 DB 사용)
    from app.database import get_db_connection
    ag_conn, ag_cur = get_db_connection()
    if not ag_conn:
        return jsonify({"status": "error", "message": "AgensGraph DB 연결 실패"}), 500

    # 그래프 생성 (없으면)
    GraphService.create_graph(graph_path)

    rdb_schema = current_app.config.get('RDB_SCHEMA', 'test_ccop')
    total_nodes = 0
    total_errors = 0
    node_stats = []

    try:
        rdb_conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        rdb_conn.autocommit = True
        rdb_cur = rdb_conn.cursor()

        # AgensGraph 네이티브 방식: graph_path 먼저 설정
        from app.database import safe_set_graph_path
        safe_set_graph_path(ag_cur, graph_path)

        for node_def in mappable:
            label = node_def.get('label', '').strip()
            table = node_def.get('rdb_table', '').strip()
            key_prop = node_def.get('key_property', '').strip()
            props_def = node_def.get('properties', [])  # [{name, type, rdb_column, ...}]

            # 유효성 검사
            if not label or not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', label):
                continue
            if not table or not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
                continue

            # rdb_column 매핑이 있는 속성만 사용
            col_map = [(p['rdb_column'], p['name'], p.get('type', 'string'))
                       for p in props_def if p.get('rdb_column')]
            if not col_map:
                continue

            # key_property 가 없으면 첫 번째 속성 사용
            if not key_prop and col_map:
                key_prop = col_map[0][1]

            quoted_cols = ", ".join(f'"{rdb_col}"' for rdb_col, _, _ in col_map)
            try:
                rdb_cur.execute(f'SELECT {quoted_cols} FROM {rdb_schema}."{table}" LIMIT 5000')
                rows = rdb_cur.fetchall()
            except Exception as e:
                node_stats.append({"label": label, "table": table, "loaded": 0, "error": str(e)})
                total_errors += 1
                rdb_conn.rollback()
                continue

            loaded = 0
            for row in rows:
                prop_kv = {}
                for idx, (rdb_col, prop_name, prop_type) in enumerate(col_map):
                    val = row[idx]
                    if val is None:
                        continue
                    val_str = str(val).replace("'", "\\'")

                    # StandardCodeMapper 정규화
                    if prop_name in ('bank_cd', 'bank_code', 'bcode'):
                        val_str = StandardCodeMapper.map_bank_code(val_str) or val_str
                    elif prop_name in ('bank_name', 'bank_nm', 'bname'):
                        normalized = StandardCodeMapper.map_bank_code(val_str)
                        if normalized:
                            prop_kv['bank_cd'] = normalized
                    elif prop_name in ('carrier_cd', 'tele_cmpn_cd'):
                        val_str = StandardCodeMapper.map_carrier_code(val_str) or val_str
                    elif prop_name in ('carrier_nm', 'tele_cmpn_nm'):
                        normalized = StandardCodeMapper.map_carrier_code(val_str)
                        if normalized:
                            prop_kv['carrier_cd'] = normalized

                    prop_kv[prop_name] = val_str

                if not prop_kv or key_prop not in prop_kv:
                    continue

                props_str = ", ".join(f"{k}: '{v}'" for k, v in prop_kv.items())
                key_val = prop_kv[key_prop]
                cypher = (
                    f"MERGE (n:{label} {{{key_prop}: '{key_val}'}})"
                    f" ON CREATE SET n = {{{props_str}}}"
                    f" RETURN n"
                )
                try:
                    ag_cur.execute(cypher)
                    loaded += 1
                except Exception:
                    pass

            total_nodes += loaded
            node_stats.append({"label": label, "table": table, "loaded": loaded, "error": None})

        # ── 엣지 적재 ──────────────────────────────────────────
        edges = schema.get('edges', [])
        total_edges = 0
        edge_stats = []

        # 노드 id → schema node 매핑
        node_by_id = {n['id']: n for n in nodes}
        rdb_schema = current_app.config.get('RDB_SCHEMA', 'test_ccop')

        for edge_def in edges:
            edge_type = edge_def.get('type', '').strip()
            src_join_col = edge_def.get('src_join_col', '').strip()
            tgt_join_col = edge_def.get('tgt_join_col', '').strip()

            if not edge_type or not src_join_col or not tgt_join_col:
                continue

            src_node = node_by_id.get(edge_def.get('source_id', ''))
            tgt_node = node_by_id.get(edge_def.get('target_id', ''))

            if not src_node or not tgt_node:
                continue

            src_label = src_node.get('label', '').strip()
            tgt_label = tgt_node.get('label', '').strip()
            src_table = src_node.get('rdb_table', '').strip()
            tgt_table = tgt_node.get('rdb_table', '').strip()
            src_key = src_node.get('key_property', '')
            tgt_key = tgt_node.get('key_property', '')

            if not src_table or not tgt_table or not src_key or not tgt_key:
                edge_stats.append({"type": edge_type, "loaded": 0, "error": "노드에 RDB 테이블 또는 키 속성 미설정"})
                continue

            # RDB JOIN → (src_key_val, tgt_key_val) 쌍 추출
            try:
                rdb_conn3 = psycopg2.connect(**current_app.config['DB_CONFIG'])
                rdb_conn3.autocommit = True
                rdb_cur3 = rdb_conn3.cursor()
                # src_key, src_join, tgt_key, tgt_join 모두 가져오기
                src_key_col = next((p.get('rdb_column') or p['name'] for p in src_node.get('properties', []) if p['name'] == src_key), src_join_col)
                tgt_key_col = next((p.get('rdb_column') or p['name'] for p in tgt_node.get('properties', []) if p['name'] == tgt_key), tgt_join_col)

                rdb_cur3.execute(
                    f'SELECT DISTINCT s."{src_key_col}", t."{tgt_key_col}" '
                    f'FROM {rdb_schema}."{src_table}" s '
                    f'JOIN {rdb_schema}."{tgt_table}" t '
                    f'ON s."{src_join_col}" = t."{tgt_join_col}" '
                    f'LIMIT 10000'
                )
                key_pairs = rdb_cur3.fetchall()
                rdb_conn3.close()
            except Exception as e:
                edge_stats.append({"type": edge_type, "loaded": 0, "error": str(e)})
                continue

            loaded_edges = 0
            for src_val, tgt_val in key_pairs:
                if src_val is None or tgt_val is None:
                    continue
                sv = str(src_val).replace("'", "\\'")
                tv = str(tgt_val).replace("'", "\\'")
                cypher = (
                    f"MATCH (s:{src_label} {{{src_key}: '{sv}'}}), (t:{tgt_label} {{{tgt_key}: '{tv}'}})"
                    f" MERGE (s)-[r:{edge_type}]->(t)"
                    f" RETURN r"
                )
                try:
                    ag_cur.execute(cypher)
                    loaded_edges += 1
                except Exception:
                    pass

            total_edges += loaded_edges
            edge_stats.append({"type": edge_type, "src": src_label, "tgt": tgt_label, "loaded": loaded_edges, "error": None})

        rdb_conn.close()
    except Exception as e:
        return jsonify({"status": "error", "message": f"RDB 연결 실패: {e}"}), 500
    finally:
        try:
            ag_cur.close()
            ag_conn.close()
        except Exception:
            pass

    return jsonify({
        "status": "success",
        "graph_path": graph_path,
        "stats": {"nodes": total_nodes, "edges": total_edges, "errors": total_errors},
        "node_stats": node_stats,
        "edge_stats": edge_stats,
    })
