import json
import logging
from app.database import get_db_connection, safe_props, safe_set_graph_path, validate_graph_path
from app.services.subgraph_service import SubGraphService
from app.services.ai_service import AIService

def _extract_keyword(question: str) -> str:
    """질문에서 가장 긴 단어를 키워드로 추출 (LLM 호출 없이 규칙 기반)"""
    words = [w.strip(".,?!\"'()") for w in question.split() if len(w) >= 2]
    return max(words, key=len) if words else question
import psycopg2
from flask import current_app

logger = logging.getLogger(__name__)

import psycopg2.extensions


class _QueryLoggingCursor(psycopg2.extensions.cursor):
    """[시각화/그래프 조회 쿼리 로깅] 실행되는 모든 SQL·Cypher 를 INFO 레벨 [QUERY] 로 남긴다."""
    def execute(self, query, vars=None):
        try:
            _q = self.mogrify(query, vars).decode("utf-8", "replace") if vars is not None else str(query)
        except Exception:
            _q = str(query)
        logger.info("[QUERY] %s", " ".join(_q.split()))
        return super().execute(query, vars)

class GraphService:

    # KICS 온톨로지 엣지 방향 — v3.7 POLE 6레이어 기준
    # (docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md §4 엣지 카탈로그)
    # 동적 DB 조회 실패 시 fallback으로 사용.
    _KICS_EDGE_DIRECTIONS = {
        # ── CASE 관련 역할 엣지 ───────────────────────────────────────
        "suspect_in":    ("vt_psn",      "vt_case"),
        "victim_in":     ("vt_psn",      "vt_case"),
        "witness_in":    ("vt_psn",      "vt_case"),
        "filed_as":      ("vt_petition", "vt_case"),
        "linked_to":     ("vt_petition", "vt_case"),
        "clusters_with": ("vt_petition", "vt_petition"),
        "related_case":  ("vt_case",     "vt_case"),   # v3.5: similar_to 대체
        # ── CASE → OBJECT 증거 연결 (v3.5 공식 등재) ─────────────────
        "eg_used_account": ("vt_case",   "vt_bacnt"),
        "eg_used_phone":   ("vt_case",   "vt_telno"),
        "eg_used_ip":      ("vt_case",   "vt_ip"),
        # ── [호환성] involves — 신규 생성 금지, 기존 DB 데이터 읽기 전용
        "involves":      ("vt_case",     "vt_psn"),
        "involves_org":  ("vt_case",     "vt_org"),
        # ── PERSON 소유/귀속 엣지 ─────────────────────────────────────
        "has_account":   ("vt_psn",      "vt_bacnt"),
        "controls":      ("vt_psn",      "vt_bacnt"),
        "owns_phone":    ("vt_psn",      "vt_telno"),
        "owns_device":   ("vt_psn",      "vt_dev"),
        "uses_id":       ("vt_psn",      "vt_id"),
        "uses_email":    ("vt_psn",      "vt_email"),
        "drives":        ("vt_psn",      "vt_vhcl"),   # 운행 (LPR·CDR 기반)
        "owns_vehicle":  ("vt_psn",      "vt_vhcl"),   # v3.5: 법적 소유 (등록원부)
        "used_ip":       ("vt_psn",      "vt_ip"),
        "member_of":     ("vt_psn",      "vt_org"),
        "works_at":      ("vt_psn",      "vt_org"),
        # ── PERSON 간 관계 ────────────────────────────────────────────
        "accomplice_of": ("vt_psn",      "vt_psn"),
        "sameAs":        ("vt_psn",      "vt_psn"),
        "contradicts":   ("vt_psn",      "vt_psn"),
        # ── PERSON v3.4 신규 ──────────────────────────────────────────
        "operates":      ("vt_psn",      "vt_site"),
        "recruits":      ("vt_psn",      "vt_psn"),
        "blackmails":    ("vt_psn",      "vt_psn"),
        # ── OBJECT → PERSON 예외 엣지 (v3.5 공식 허용) ───────────────
        "registered_to": ("vt_telno",    "vt_psn"),    # v3.5: 전화 명의자 (Phone→Person)
        # ── OBJECT 간 관계 ────────────────────────────────────────────
        "transferred_to": ("vt_bacnt",   "vt_bacnt"),
        "hosts":         ("vt_ip",       "vt_site"),   # 서버 IP → 사이트 호스팅
        "resolves_to":   ("vt_site",     "vt_ip"),     # DNS 해석
        "communicated_with": ("vt_ip",   "vt_ip"),     # IP 간 통신
        "belongs_to":    ("vt_bacnt",    "vt_org"),    # 계좌 소속 금융기관
        "contains_file": ("vt_site",     "vt_file"),   # 파일 내장·배포
        "located_at":    ("vt_atm",      "vt_loc"),    # 객체 고정 위치
        "mentions_account": ("vt_msg",   "vt_bacnt"),  # v3.5: 메시지 내 계좌 언급
        # ── [호환성] deprecated, 신규 생성 금지 ──────────────────────
        "hosted_at":     ("vt_site",     "vt_ip"),     # → hosts 대체됨
        "contacted":     ("vt_telno",    "vt_telno"),  # → caller/callee 대체됨
        # ── EVENT 관련 엣지 ───────────────────────────────────────────
        "from_account":  ("vt_bacnt",    "vt_transfer"),
        "to_account":    ("vt_transfer", "vt_bacnt"),
        "caller":        ("vt_telno",    "vt_call"),
        "callee":        ("vt_call",     "vt_telno"),
        "accessed_from": ("vt_access",   "vt_ip"),     # 접속 출발 IP
        "accessed_to":   ("vt_access",   "vt_site"),   # v3.5 복원: 접속 목적지 사이트
        "sent_msg":      ("vt_telno",    "vt_msg"),    # sent_via 대체
        "received_msg":  ("vt_msg",      "vt_telno"),  # received_by 대체
        "occurred_at":   ("vt_transfer", "vt_loc"),    # 이벤트 발생 위치 (범용)
        "recorded_in":   ("vt_vhcl",     "vt_movement"),
        # ── 사칭 범죄 엣지 (v3.3+) ────────────────────────────────────
        "used_for":      ("vt_telno",    "vt_impersonation"),
        "targets":       ("vt_impersonation", "vt_org"),
        # ── META (Provenance) ─────────────────────────────────────────
        "verified_by":   ("vt_psn",      "vt_psn"),
        # sourced_from: 모든 노드 타입 → vt_src (None = Any)
        # 버그수정 v3.7: ("vt_psn", "vt_src") 로 제한되어 있어 vt_case 등에서 방향 교정 불가
        "sourced_from":  (None,          "vt_src"),
        # ── v3.7 신규 엣지 ────────────────────────────────────────────
        "belongs_to_cluster":  ("vt_petition", "pt_cluster"),
        "used_in_device":      ("vt_telno",    "vt_dev"),
        "belongs_to_campaign": ("vt_site",     "site_cluster"),
    }

    # 스키마 캐시 (graph_path 별 저장)
    _SCHEMA_CACHE = {}
    _CACHE_TTL = 300 # 5분
    
    @staticmethod
    def get_db_connection():
        """DB 연결 헬퍼"""
        try:
            conn = psycopg2.connect(
                dbname=current_app.config['DB_CONFIG']['dbname'],
                user=current_app.config['DB_CONFIG']['user'],
                password=current_app.config['DB_CONFIG']['password'],
                host=current_app.config['DB_CONFIG']['host'],
                port=current_app.config['DB_CONFIG']['port']
            )
            conn.autocommit = True
            return conn, conn.cursor(cursor_factory=_QueryLoggingCursor)
        except Exception as e:
            logger.error(f"DB 접속 오류: {e}")
            return None, None

    @staticmethod
    def safe_props(val):
        """JSON 속성 파싱 안전장치"""
        if val is None: return {}
        if isinstance(val, dict): return val
        try:
            if isinstance(val, str) and not val.strip(): return {}
            return json.loads(val)
        except:
            return {}
    
    @staticmethod
    def _label_from_regclass(regclass_val):
        """AgensGraph tableoid::regclass ('graph.vt_xxx' / '"graph".vt_xxx') → 라벨명(vt_xxx).
        DB에 저장된 실제 라벨이므로 속성 추론보다 우선. 미분류(ag_vertex)면 None."""
        if not regclass_val:
            return None
        name = str(regclass_val).split('.')[-1].strip('"')
        if name in ('ag_vertex', 'ag_edge', ''):
            return None
        return name

    @staticmethod
    def determine_node_label(props):
        """
        노드 속성을 기반으로 적절한 label(타입) 결정
        v3.7 POLE 6레이어 온톨로지 기준 (docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md)

        반환 가능 레이블:
            SOURCE  : vt_src
            CASE    : vt_case, vt_petition
            PERSON  : vt_psn, vt_org
            OBJECT  : vt_bacnt, vt_crypto, vt_ip, vt_site, vt_file,
                      vt_id, vt_email, vt_telno, vt_vhcl, vt_dev, vt_atm
            LOCATION: vt_loc
            EVENT   : vt_transfer, vt_call, vt_access, vt_msg, vt_movement
            기본값  : vt_psn
        ※ vt_event / vt_persona 는 v3에서 폐기 (vt_movement / vt_id 로 통합)
        """
        if not props or not isinstance(props, dict):
            return 'vt_psn'

        # ── EVENT LAYER (event_type 우선) ───────────────────────────
        #   v4.0 데모/OSINT 스키마는 call_id 대신 event_type 을 사용하므로 최우선 판별.
        _evt = props.get('event_type')
        if _evt == 'call':     return 'vt_call'
        if _evt == 'transfer': return 'vt_transfer'
        if _evt == 'message':  return 'vt_msg'
        if _evt == 'access':   return 'vt_access'

        # ── SOURCE LAYER ────────────────────────────────────────────
        #   src_id/src_name 으로만 판별 (reliability_tier·source_domain 은 모든 노드 공통 출처속성이라 제외)
        if 'src_id' in props or 'src_name' in props:
            return 'vt_src'

        # ── CASE LAYER ──────────────────────────────────────────────
        if 'petition_id' in props or 'rcpt_dt' in props or 'rcpt_channel' in props:
            return 'vt_petition'
        if 'flnm' in props or 'incdnt_no' in props or 'incdnt_nm' in props:
            return 'vt_case'

        # ── OBJECT LAYER (가장 구체적 속성 우선) ──────────────────────

        # IP 주소 (v3: ip_addr 표준, is_tor/is_proxy/asn 추가 속성)
        if 'ip_addr' in props or 'ip' in props or 'ipaddr' in props \
                or 'is_tor' in props or 'is_proxy' in props or 'asn' in props:
            return 'vt_ip'

        # ATM
        if 'atm_id' in props or 'atm' in props:
            return 'vt_atm'

        # 사이트/URL (v3: url_addr 표준, site/domain 구형 컬럼 호환)
        if 'url_addr' in props or 'site' in props or 'url' in props \
                or 'dmn_addr' in props or 'domain' in props:
            return 'vt_site'

        # 가상자산
        if 'wallet_addr' in props or 'blockchain' in props:
            return 'vt_crypto'

        # 이메일
        if 'email_addr' in props or 'email' in props:
            return 'vt_email'

        # 계좌번호 (v3: account_no/bank_cd 경찰청 표준, 구형 actno/bank 호환)
        if 'account_no' in props or 'bank_cd' in props \
                or 'actno' in props or 'bank' in props or 'bacnt' in props:
            return 'vt_bacnt'

        # 전화번호 (v3: telco_nm/join_typ_cd/imsi 추가 속성)
        if 'telno' in props or 'phone' in props \
                or 'telco_nm' in props or 'imsi' in props:
            return 'vt_telno'

        # 차량
        if 'vhclno' in props or 'carmdl_nm' in props:
            return 'vt_vhcl'

        # 기기 (스마트폰/PC 등)
        if 'device_id' in props or 'imei' in props or 'mac_addr' in props:
            return 'vt_dev'

        # 파일 (v3: hash_val 표준, hash_md5/hash_sha256 구형 호환)
        if 'hash_val' in props or 'hash_sha256' in props or 'hash_md5' in props \
                or 'file_nm' in props or 'filename' in props or 'filepath' in props \
                or 'file' in props:
            return 'vt_file'

        # 디지털ID/계정 (v3: id_val+platform 복합 PK, vt_persona 흡수)
        if 'id_val' in props or 'platform' in props \
                or 'user_id' in props or 'userid' in props:
            return 'vt_id'

        # ── LOCATION LAYER ──────────────────────────────────────────
        if 'loc_id' in props or 'bsst_nm' in props or 'cctv_id' in props \
                or ('lat' in props and 'lng' in props):
            return 'vt_loc'

        # ── EVENT LAYER ─────────────────────────────────────────────
        # 이동이벤트 (v3: vt_lpr_evt + vt_loc_evt 통합, vt_movement)
        if 'mov_id' in props or 'mov_type' in props \
                or 'rcgn_sn' in props or 'loc_evt_sn' in props:
            return 'vt_movement'

        # 네트워크 접속
        if 'access_id' in props or 'action' in props or 'status_code' in props:
            return 'vt_access'

        # 메시지
        if 'msg_id' in props or 'msg_type' in props or 'app_nm' in props:
            return 'vt_msg'

        # 이체 (v3: transfer_id / dlng_sn)
        if 'transfer_id' in props or 'dlng_sn' in props or 'dlng_amt' in props:
            return 'vt_transfer'

        # 통화 (v3: call_id / call_sn)
        if 'call_id' in props or 'call_sn' in props or 'call_dur_sec' in props:
            return 'vt_call'

        # ── PERSON LAYER ────────────────────────────────────────────
        # 조직
        if 'org_id' in props or 'org_name' in props or 'brno' in props:
            return 'vt_org'

        # 인물 (이름 또는 인물 식별자)
        if 'psn_id' in props or 'name' in props or 'korn_flnm' in props \
                or 'rrno_hash' in props:
            return 'vt_psn'

        # 기본값
        return 'vt_psn'

    @staticmethod
    def get_current_schema(graph_path, force_refresh=False):
        """현재 그래프의 활성 VLABEL 및 ELABEL 정보와 각 속성 키들을 동적으로 조회 (캐시 적용)"""
        import time
        from flask import current_app
        
        # 캐시 확인
        if not force_refresh and graph_path in GraphService._SCHEMA_CACHE:
            cached_data, timestamp = GraphService._SCHEMA_CACHE[graph_path]
            if time.time() - timestamp < GraphService._CACHE_TTL:
                logger.info(f"▶ [SchemaCache] 캐시 히트: {graph_path}")
                return cached_data

        conn, cur = GraphService.get_db_connection()
        if not conn: return {"node_labels": {}, "edge_types": []}
        try:
            # Vertex 라벨 및 대표 속성 샘플링 조회
            cur.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{graph_path}' 
                  AND table_name LIKE 'vt_%'
            """)
            vertex_labels = [r[0] for r in cur.fetchall()]
            
            node_info = {}
            for label in vertex_labels:
                # 각 라벨의 컬럼(속성) 목록 조회
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = '{graph_path}' AND table_name = '{label}'
                      AND column_name NOT IN ('id', 'properties')
                """)
                cols = [r[0] for r in cur.fetchall()]
                # JSONB properties 내부의 키 샘플링
                cur.execute(f"SELECT jsonb_object_keys(properties) FROM \"{graph_path}\".\"{label}\" LIMIT 10")
                prop_keys = list(set([r[0] for r in cur.fetchall()]))
                node_info[label] = list(set(cols + prop_keys))

            # Edge 라벨 조회
            cur.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{graph_path}'
                  AND table_name NOT LIKE 'vt_%'
                  AND table_name NOT IN ('ag_vertex', 'ag_label', 'ag_edge')
            """)
            edge_labels = [r[0] for r in cur.fetchall()]

            # 엣지 방향 조회: 각 엣지 테이블에서 시작/끝 노드 레이블 샘플링
            edge_directions = {}
            for edge in edge_labels:
                # KICS 매핑에 있으면 바로 사용 (DB 쿼리 절약)
                if edge in GraphService._KICS_EDGE_DIRECTIONS:
                    edge_directions[edge] = GraphService._KICS_EDGE_DIRECTIONS[edge]
                    continue
                # 미지의 엣지는 AgensGraph 네이티브 Cypher로 실제 방향 샘플링
                try:
                    cur.execute(
                        f"MATCH (a)-[:{edge}]->(b) RETURN label(a), label(b) LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row:
                        src = str(row[0]).strip('"')
                        dst = str(row[1]).strip('"')
                        edge_directions[edge] = (src, dst)
                except Exception as e_dir:
                    logger.warning(f"엣지 방향 조회 실패 ({edge}): {e_dir}")

            schema_data = {
                "node_labels":     node_info,
                "edge_types":      edge_labels,
                "edge_directions": edge_directions,
            }
            
            # 캐시 저장
            GraphService._SCHEMA_CACHE[graph_path] = (schema_data, time.time())
            return schema_data

        except Exception as e:
            logger.error(f"Get Schema Error: {e}")
            return {"node_labels": {}, "edge_types": []}
        finally:
            conn.close()

    @staticmethod
    def clear_graph(graph_path):
        """그래프 데이터 전체 초기화"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            safe_set_graph_path(cur, graph_path)
            cur.execute("MATCH (n) DETACH DELETE n")
            return True, "삭제 완료"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def list_graphs():
        """모든 그래프 목록 조회 (성능 최적화: 카운트 제외)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []
        try:
            # AgensGraph에서 그래프 목록 조회
            cur.execute("""
                SELECT graphname
                FROM pg_catalog.ag_graph
                ORDER BY graphname;
            """)
            graphs = []
            for row in cur.fetchall():
                graph_name = row[0]
                # 외부 DB 연결 시 COUNT(*)는 매우 느리므로 0으로 반환하거나 생략
                # 필요시 별도 API로 상세 정보 조회하도록 변경 권장
                graphs.append({
                    "name": graph_name,
                    "node_count": 0  # 성능을 위해 0으로 고정
                })
            return graphs
        except Exception as e:
            logger.error(f"List Graphs Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def create_graph(graph_name):
        """새 그래프 생성"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            # AgensGraph에서 그래프 생성
            cur.execute(f"CREATE GRAPH IF NOT EXISTS {graph_name};")
            safe_set_graph_path(cur, graph_name)
            
            # 기본 vertex/edge 라벨 생성
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_psn;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_bacnt;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_telno;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_site;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_ip;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_flnm;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_id;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_atm;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_event;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_persona;")
            
            cur.execute("CREATE ELABEL IF NOT EXISTS related_to;")
            cur.execute("CREATE ELABEL IF NOT EXISTS uses_persona;")
            cur.execute("CREATE ELABEL IF NOT EXISTS participated_in;")
            cur.execute("CREATE ELABEL IF NOT EXISTS event_involved;")
            cur.execute("CREATE ELABEL IF NOT EXISTS supported_by;")
            cur.execute("CREATE ELABEL IF NOT EXISTS used_account;")
            cur.execute("CREATE ELABEL IF NOT EXISTS used_phone;")
            cur.execute("CREATE ELABEL IF NOT EXISTS digital_trace;")
            
            return True, f"그래프 '{graph_name}' 생성 완료"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def delete_graph(graph_name):
        """그래프 삭제"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            # 보호: 기본 그래프는 삭제 방지
            if graph_name in ['agens_graph', 'public']:
                return False, "시스템 그래프는 삭제할 수 없습니다."
            
            # AgensGraph에서 그래프 삭제
            cur.execute(f"DROP GRAPH IF EXISTS {graph_name} CASCADE;")
            return True, f"그래프 '{graph_name}' 삭제 완료"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def search_nodes(keyword, graph_path):
        """키워드로 노드 검색 (Cypher 전체 속성 CONTAINS) + 연결된 엣지 포함"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []

        elements = []
        seen_nodes = set()
        node_ids = []
        # Cypher 문자열 리터럴 이스케이프
        kw = (keyword or "").replace("\\", "\\\\").replace("'", "\\'")
        try:
            safe_set_graph_path(cur, graph_path)

            # 1. 전체 속성에서 키워드 검색 (모든 라벨) — 기존 SQL "properties::text LIKE '%kw%'" 등가
            cur.execute(
                f"MATCH (n) WHERE properties(n)::text CONTAINS '{kw}' "
                f"RETURN id(n), labels(n), properties(n) LIMIT 50"
            )
            for r in cur.fetchall():
                nid = str(r[0])
                if nid in seen_nodes:
                    continue
                seen_nodes.add(nid)
                node_ids.append(nid)
                labels = r[1]
                props = GraphService.safe_props(r[2])
                label = (labels[0] if labels else None) or GraphService.determine_node_label(props)
                elements.append({
                    "group": "nodes",
                    "data": {"id": nid, "label": label, "props": props}
                })

            # 2. 검색된 노드가 포함된 엣지 + 상대 노드 (서브그래프 구성)
            if node_ids:
                # ⚠️ AgensGraph 는 id() IN [list] 미지원(jsonb 오류) → id(a)='x' OR id(b)='x' 체인
                cond = " OR ".join("id(a) = '%s' OR id(b) = '%s'" % (i, i) for i in node_ids)
                cur.execute(
                    f"MATCH (a)-[r]->(b) WHERE {cond} "
                    f"RETURN id(r), type(r), properties(r), "
                    f"id(a), labels(a), properties(a), id(b), labels(b), properties(b) LIMIT 100"
                )
                for r in cur.fetchall():
                    edge_id = str(r[0])
                    etype = r[1]
                    edge_props = GraphService.safe_props(r[2])
                    aid = str(r[3]); a_labels = r[4]; a_props = GraphService.safe_props(r[5])
                    bid = str(r[6]); b_labels = r[7]; b_props = GraphService.safe_props(r[8])

                    # 엣지 양끝 노드 추가 (검색 안 된 상대 노드 포함, 중복 방지)
                    for xid, xlabels, xprops in ((aid, a_labels, a_props), (bid, b_labels, b_props)):
                        if xid not in seen_nodes:
                            seen_nodes.add(xid)
                            xlabel = (xlabels[0] if xlabels else None) or GraphService.determine_node_label(xprops)
                            elements.append({
                                "group": "nodes",
                                "data": {"id": xid, "label": xlabel, "props": xprops}
                            })

                    # 엣지 라벨 (generic ag_edge 는 속성에서 실제 관계 추출)
                    edge_label = etype
                    if etype == 'ag_edge':
                        edge_label = (
                            edge_props.get('semantic_relation') or
                            edge_props.get('domain_meaning') or
                            edge_props.get('edge_type') or
                            edge_props.get('type') or
                            'related_to'
                        )
                        if isinstance(edge_label, str):
                            edge_label = edge_label.lower()

                    elements.append({
                        "group": "edges",
                        "data": {"id": edge_id, "source": aid, "target": bid, "label": edge_label, "props": edge_props}
                    })

            return elements
        except Exception as e:
            logger.error(f"Search Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def expand_node(node_id, graph_path):
        """노드 확장 (Cypher 기반 — outgoing/incoming 양방향 MATCH 조회)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []

        elements = []
        added_edge_ids = set()
        added_node_ids = set()
        try:
            safe_set_graph_path(cur, graph_path)

            # 통일 RETURN 컬럼: id(r), type(r), properties(r), source_id, target_id, 이웃id, 이웃labels, 이웃props
            queries = [
                # outgoing: (현재노드 n)-[r]->(이웃 m)
                f"MATCH (n)-[r]->(m) WHERE id(n) = '{node_id}' "
                f"RETURN id(r), type(r), properties(r), id(n), id(m), id(m), labels(m), properties(m) LIMIT 200",
                # incoming: (이웃 m)-[r]->(현재노드 n)
                f"MATCH (n)<-[r]-(m) WHERE id(n) = '{node_id}' "
                f"RETURN id(r), type(r), properties(r), id(m), id(n), id(m), labels(m), properties(m) LIMIT 200",
            ]

            for q in queries:
                cur.execute(q)
                for r in cur.fetchall():
                    edge_id = str(r[0])
                    if edge_id in added_edge_ids:
                        continue
                    added_edge_ids.add(edge_id)

                    etype = r[1]
                    edge_props = GraphService.safe_props(r[2])
                    source_id = str(r[3])
                    target_id = str(r[4])
                    nbr_id = str(r[5])
                    nbr_labels = r[6]
                    nbr_props = GraphService.safe_props(r[7])

                    # 이웃 노드 추가 (중복 방지) — Cypher labels() 우선, 미분류 시 속성 추론
                    if nbr_id not in added_node_ids:
                        added_node_ids.add(nbr_id)
                        nbr_label = (nbr_labels[0] if nbr_labels else None) or GraphService.determine_node_label(nbr_props)
                        elements.append({
                            "group": "nodes",
                            "data": {"id": nbr_id, "label": nbr_label, "props": nbr_props}
                        })

                    # 엣지 라벨 결정 (generic ag_edge 는 속성에서 실제 관계 추출)
                    edge_label = etype
                    if etype == 'ag_edge':
                        edge_label = (
                            edge_props.get('semantic_relation') or
                            edge_props.get('domain_meaning') or
                            edge_props.get('edge_type') or
                            edge_props.get('type') or
                            'related_to'
                        )
                        if isinstance(edge_label, str):
                            edge_label = edge_label.lower()

                    elements.append({
                        "group": "edges",
                        "data": {
                            "id": edge_id,
                            "source": source_id,
                            "target": target_id,
                            "label": edge_label,
                            "props": edge_props
                        }
                    })

            return elements
        except Exception as e:
            logger.error(f"Expand Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def find_shortest_path(src, tgt, graph_path):
        """최단 경로 탐색 (BFS)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, []
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            # BFS 탐색
            queue = [[src]]
            visited = {src}
            found_path = None
            
            while queue:
                path = queue.pop(0)
                curr = path[-1]
                if curr == tgt:
                    found_path = path; break
                if len(path) > 6: continue # 깊이 제한
                
                # 이웃 노드 검색
                cur.execute(f"MATCH (u)-[]-(v) WHERE id(u) = '{curr}' RETURN id(v)")
                for row in cur.fetchall():
                    neighbor_id = str(row[0])
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append(path + [neighbor_id])
            
            if not found_path: return False, []
            
            # 경로 시각화 데이터 생성
            elements = []
            for nid in found_path:
                cur.execute(f"MATCH (n) WHERE id(n) = '{nid}' RETURN id(n), labels(n), properties(n)")
                r = cur.fetchone()
                if r:
                    node_id = str(r[0])
                    elements.append({"group": "nodes", "data": {"id": node_id, "label": r[1][0], "props": GraphService.safe_props(r[2])}})
            
            # 엣지 연결
            for i in range(len(found_path)-1):
                u, v = found_path[i], found_path[i+1]
                cur.execute(f"MATCH (u)-[r]-(v) WHERE id(u) = '{u}' AND id(v) = '{v}' RETURN id(r), type(r), properties(r)")
                edge_res = cur.fetchone()
                
                if edge_res:
                    edge_id = str(edge_res[0])
                    elements.append({"group": "edges", "data": {"id": edge_id, "source": str(u), "target": str(v), "label": edge_res[1], "props": GraphService.safe_props(edge_res[2])}})
                else:
                    # 논리적 연결일 경우 점선 처리
                    elements.append({"group": "edges", "data": {"id": f"v_{u}_{v}", "source": u, "target": v, "label": "Same Info", "props": {"type":"virtual"}}, "classes": "virtual-edge"})
                    
            return True, elements
            
        except Exception as e:
            logger.error(f"Path Error: {e}")
            return False, []
        finally:
            conn.close()

    @staticmethod
    def multi_hop_expand(node_id, depth, graph_path, max_nodes=200):
        """N-hop 다단계 확장 (Cypher 변수 길이 경로)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return {'nodes': [], 'edges': [], 'stats': {}}
        
        depth = min(int(depth), 5)  # 최대 5-hop
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            elements_nodes = []
            elements_edges = []
            node_set = set()
            edge_set = set()
            
            # 시작 노드 정보
            cur.execute(f"MATCH (n) WHERE id(n) = '{node_id}' RETURN id(n), labels(n), properties(n)")
            start = cur.fetchone()
            if start:
                sid = str(start[0])
                node_set.add(sid)
                elements_nodes.append({
                    "group": "nodes",
                    "data": {"id": sid, "label": start[1][0] if isinstance(start[1], list) else str(start[1]),
                             "props": GraphService.safe_props(start[2]), "hop": 0}
                })
            
            # 단일 hop 단계 (exact depth) 확장으로 변경
            try:
                if depth == 1:
                    query = f"""
                        MATCH (start)-[r]-(end_node)
                        WHERE id(start) = '{node_id}'
                        RETURN id(end_node), labels(end_node), properties(end_node),
                               id(r), type(r), properties(r), id(start) AS prev_id
                        LIMIT {max_nodes}
                    """
                else:
                    # 중간 경로는 무시하고 가장 마지막 단계의 노드(end_node)와 그 직전 엣지(r)만 반환
                    prev_hops = depth - 1
                    query = f"""
                        MATCH (start)-[*{prev_hops}..{prev_hops}]-(prev)-[r]-(end_node)
                        WHERE id(start) = '{node_id}'
                        RETURN id(end_node), labels(end_node), properties(end_node),
                               id(r), type(r), properties(r), id(prev) AS prev_id
                        LIMIT {max_nodes}
                    """
                
                cur.execute(query)
                exact_hop_results = cur.fetchall()
                
                for r_row in exact_hop_results:
                    nid = str(r_row[0])
                    n_label = r_row[1][0] if isinstance(r_row[1], list) else str(r_row[1])
                    n_props = GraphService.safe_props(r_row[2])
                    
                    eid = str(r_row[3])
                    e_label_raw = str(r_row[4])
                    e_props = GraphService.safe_props(r_row[5])
                    prev_id = str(r_row[6])
                    
                    # 노드 추가
                    if nid not in node_set:
                        node_set.add(nid)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {
                                "id": nid,
                                "label": n_label,
                                "props": n_props,
                                "hop": depth
                            }
                        })
                    
                    # 직전 노드(prev)도 현재 elements_nodes에 없다면 시각화를 위해 최소한의 형태로 추가
                    # (화면에 둥둥 떠다니는 걸 방지하려면 연결될 부모 노드가 필요함.
                    # 단, 중간 과정이 전부 나오는게 싫다면 이 prev 노드들은 투명하게 처리하거나
                    # 프론트엔드에서 레이아웃만 맞추는 용도로 쓸 수 있지만, 선행 노드가 화면에 없으면 Cytoscape에서 엣지가 그려지지 않음)
                    if prev_id not in node_set and prev_id != sid:
                        node_set.add(prev_id)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {
                                "id": prev_id,
                                "label": "Unknown", # 최소 정보만
                                "props": {},
                                "hop": depth - 1,
                                "hidden_intermediate": True # 프론트에서 숨김 처리 가능하도록 플래그
                            }
                        })
                        
                    # 엣지 추가
                    if eid not in edge_set:
                        edge_set.add(eid)
                        
                        # 엣지 라벨 재확인 (ag_edge일 경우 실제 타입 추출)
                        edge_label = e_label_raw
                        if edge_label == 'ag_edge' or not edge_label:
                            edge_label = (
                                e_props.get('semantic_relation') or 
                                e_props.get('domain_meaning') or
                                e_props.get('edge_type') or
                                e_props.get('type') or
                                'related_to'
                            )
                            if isinstance(edge_label, str):
                                edge_label = edge_label.lower()
                                
                        elements_edges.append({
                            "group": "edges",
                            "data": {
                                "id": eid,
                                "source": prev_id,
                                "target": nid,
                                "label": edge_label,
                                "props": e_props
                            }
                        })
                            
            except Exception as hop_err:
                logger.error(f"Exact Hop {depth} error: {hop_err}")
            
            stats = {
                'total_nodes': len(elements_nodes),
                'total_edges': len(elements_edges),
                'depth': depth,
                'start_node': node_id
            }
            
            return {
                'nodes': elements_nodes,
                'edges': elements_edges,
                'stats': stats
            }
        except Exception as e:
            logger.error(f"Multi-hop Error: {e}")
            return {'nodes': [], 'edges': [], 'stats': {'error': str(e)}}
        finally:
            conn.close()

    @staticmethod
    def find_accomplice_network(node_id, graph_path):
        """공범 네트워크 탐색 — 선택 노드에서 accomplice_of 관계 + 공유 자원 추적"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return {'nodes': [], 'edges': [], 'shared': []}
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            elements_nodes = []
            elements_edges = []
            shared_resources = []
            node_set = set()
            edge_set = set()
            
            # 1. 시작 Person 노드
            cur.execute(f"MATCH (p) WHERE id(p) = '{node_id}' RETURN id(p), labels(p), properties(p)")
            start = cur.fetchone()
            if not start:
                return {'nodes': [], 'edges': [], 'shared': [], 'error': 'Node not found'}
            
            sid = str(start[0])
            node_set.add(sid)
            elements_nodes.append({
                "group": "nodes",
                "data": {"id": sid, "label": start[1][0] if isinstance(start[1], list) else str(start[1]),
                         "props": GraphService.safe_props(start[2]), "role": "center"}
            })
            
            # 2. accomplice_of 관계로 연결된 인물들 (2-hop)
            try:
                cur.execute(f"""
                    MATCH (p1)-[r:accomplice_of]-(p2)
                    WHERE id(p1) = '{node_id}'
                    RETURN id(p2), labels(p2), properties(p2), id(r), properties(r)
                """)
                for r in cur.fetchall():
                    pid = str(r[0])
                    if pid not in node_set:
                        node_set.add(pid)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {"id": pid, "label": r[1][0] if isinstance(r[1], list) else str(r[1]),
                                     "props": GraphService.safe_props(r[2]), "role": "accomplice"}
                        })
                    eid = str(r[3])
                    if eid not in edge_set:
                        edge_set.add(eid)
                        eprops = GraphService.safe_props(r[4])
                        elements_edges.append({
                            "group": "edges",
                            "data": {"id": eid, "source": sid, "target": pid,
                                     "label": "accomplice_of", "props": eprops}
                        })
            except Exception as e:
                logger.error(f"Accomplice query error: {e}")
            
            # 3. 공유 자원 (계좌/전화) 추적
            for rel, res_label, prop_name in [
                ('has_account', 'vt_bacnt', 'actno'),
                ('owns_phone', 'vt_telno', 'telno'),
                ('used_ip', 'vt_ip', 'ip_addr')
            ]:
                try:
                    cur.execute(f"""
                        MATCH (p)-[r:{rel}]->(res:{res_label})
                        WHERE id(p) = '{node_id}'
                        RETURN id(res), labels(res), properties(res), id(r)
                    """)
                    for r in cur.fetchall():
                        rid = str(r[0])
                        if rid not in node_set:
                            node_set.add(rid)
                            rprops = GraphService.safe_props(r[2])
                            elements_nodes.append({
                                "group": "nodes",
                                "data": {"id": rid, "label": r[1][0] if isinstance(r[1], list) else str(r[1]),
                                         "props": rprops, "role": "resource"}
                            })
                            shared_resources.append({
                                'type': rel,
                                'value': rprops.get(prop_name, ''),
                                'id': rid
                            })
                        eid_r = str(r[3])
                        if eid_r not in edge_set:
                            edge_set.add(eid_r)
                            elements_edges.append({
                                "group": "edges",
                                "data": {"id": eid_r, "source": sid, "target": rid,
                                         "label": rel, "props": {}}
                            })
                except:
                    continue
            
            # 4. 관련 사건도 추가
            try:
                cur.execute(f"""
                    MATCH (c:vt_case)-[:involves]->(p)
                    WHERE id(p) = '{node_id}'
                    RETURN id(c), labels(c), properties(c)
                """)
                for r in cur.fetchall():
                    cid = str(r[0])
                    if cid not in node_set:
                        node_set.add(cid)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {"id": cid, "label": r[1][0] if isinstance(r[1], list) else str(r[1]),
                                     "props": GraphService.safe_props(r[2]), "role": "case"}
                        })
                        elements_edges.append({
                            "group": "edges",
                            "data": {"id": f"inv_{cid}_{sid}", "source": cid, "target": sid,
                                     "label": "involves", "props": {}}
                        })
            except:
                pass
            
            return {
                'nodes': elements_nodes,
                'edges': elements_edges,
                'shared': shared_resources,
                'stats': {
                    'accomplices': sum(1 for n in elements_nodes if n['data'].get('role') == 'accomplice'),
                    'cases': sum(1 for n in elements_nodes if n['data'].get('role') == 'case'),
                    'resources': len(shared_resources)
                }
            }
        except Exception as e:
            logger.error(f"Accomplice Network Error: {e}")
            return {'nodes': [], 'edges': [], 'shared': [], 'error': str(e)}
        finally:
            conn.close()

    @staticmethod
    def find_hub_nodes(graph_path, top_n=10):
        """허브 노드 탐지 (연결 수 상위 N개)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            hubs = []
            # Person 허브
            try:
                cur.execute(f"""
                    MATCH (p:vt_psn)
                    WHERE p.name <> '불상' AND p.name <> '미상'
                    RETURN id(p), p.name,
                           size((p)<-[:involves]-()) AS cases,
                           size((p)-[:has_account]->()) AS accounts,
                           size((p)-[:owns_phone]->()) AS phones,
                           size((p)-[:accomplice_of]-()) AS accomplices
                    ORDER BY cases + accounts + phones + accomplices DESC
                    LIMIT {top_n}
                """)
                for r in cur.fetchall():
                    hubs.append({
                        'id': str(r[0]), 'name': r[1], 'type': 'person',
                        'cases': r[2], 'accounts': r[3], 'phones': r[4],
                        'accomplices': r[5],
                        'total': r[2] + r[3] + r[4] + r[5]
                    })
            except Exception as e:
                logger.error(f"Person hub error: {e}")
            
            # Account 허브
            try:
                cur.execute(f"""
                    MATCH (a:vt_bacnt)
                    RETURN id(a), a.actno,
                           size((a)<-[:eg_used_account]-()) AS cases,
                           size((a)<-[:has_account]-()) AS persons
                    ORDER BY cases + persons DESC
                    LIMIT {top_n}
                """)
                for r in cur.fetchall():
                    hubs.append({
                        'id': str(r[0]), 'name': r[1], 'type': 'account',
                        'cases': r[2], 'persons': r[3],
                        'total': r[2] + r[3]
                    })
            except Exception as e:
                logger.error(f"Account hub error: {e}")
            
            # 전체 정렬
            hubs.sort(key=lambda x: x.get('total', 0), reverse=True)
            return hubs[:top_n]
            
        except Exception as e:
            logger.error(f"Hub Error: {e}")
            return []
        finally:
            conn.close()

    # ---------------------------------------------------------
    # 🤖 [Feature 4] AI Text-to-Cypher (AIService 연동)
    # ---------------------------------------------------------
    @staticmethod
    def execute_cypher(cypher_query, graph_path):
        """
        AgensGraph 네이티브 Cypher 쿼리 실행
        """
        if not cypher_query: return False, "Empty Query"

        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB Connection Failed"

        try:
            # 1. Graph Path 설정 (AgensGraph 필수)
            safe_set_graph_path(cur, graph_path)

            # 2. SQL Wrapper (SELECT * FROM cypher...) 형식인 경우 내부 Cypher만 추출
            # (Native AgensGraph에서는 직접 MATCH를 선호하므로 호환성을 위해 처리)
            real_query = cypher_query.strip()
            if real_query.upper().startswith("SELECT") and "$$" in real_query:
                import re
                match = re.search(r"\$\$(.*)\$\$", real_query, re.DOTALL)
                if match:
                    real_query = match.group(1).strip()
                    logger.info(f"▶ [GraphService] SQL Wrapper에서 내부 Cypher 추출 완료")
            
            logger.info(f"▶ [GraphService] 실행 Cypher: {real_query}")
            cur.execute(real_query)
            
            # 3. 결과 파싱 (노드와 엣지 구분 처리)
            rows = cur.fetchall()
            elements = []
            
            node_ids = set()
            edge_ids = set()
            
            import re
            import json
            
            # AgensGraph raw string regex patterns
            # Node: label[id]{props} e.g. vt_psn[4.2]{"name":"foo"}
            # Edge: label[id][src,dst]{props} e.g. involves[19.2][3.1,4.2]{"role":"bar"}
            node_pattern = re.compile(r'^([a-zA-Z0-9_]+)\[([\d\.]+)\](\{.*\})$')
            edge_pattern = re.compile(r'^([a-zA-Z0-9_]+)\[([\d\.]+)\]\[([\d\.]+),([\d\.]+)\](\{.*\})$')
            
            def parse_item(item):
                if not item: return
                item_type = type(item).__name__
                
                # 리스트나 튜플인 경우 내부 아이템들 재귀 처리 (Variable length path 대응)
                if isinstance(item, (list, tuple)):
                    for sub_item in item:
                        parse_item(sub_item)
                    return

                # 1. 노드 (Vertex) 파싱
                if item_type in ('Vertex', 'agtype_vertex') or (isinstance(item, dict) and 'id' in item and 'label' in item and 'properties' in item) or (hasattr(item, 'id') and hasattr(item, 'label') and hasattr(item, 'properties')):
                    try:
                        n_id = str(item.get('id', '')) if isinstance(item, dict) else str(getattr(item, 'id', ''))
                        if n_id and n_id not in node_ids:
                            n_label = item.get('label', 'Unknown') if isinstance(item, dict) else getattr(item, 'label', 'Unknown')
                            n_props = item.get('properties', {}) if isinstance(item, dict) else getattr(item, 'properties', {})
                            node_ids.add(n_id)
                            elements.append({
                                "group": "nodes",
                                "data": {"id": n_id, "label": str(n_label).replace('"', ''), "props": GraphService.safe_props(n_props)}
                            })
                    except Exception as e:
                        logger.error(f"[Node Parse Error] {e}")
                        
                # 2. 엣지 (Edge) 파싱
                elif item_type in ('Edge', 'agtype_edge') or (isinstance(item, dict) and 'start_id' in item and 'end_id' in item) or (hasattr(item, 'start_id') and hasattr(item, 'end_id')):
                    try:
                        e_id = str(item.get('id', '')) if isinstance(item, dict) else str(getattr(item, 'id', ''))
                        if e_id and e_id not in edge_ids:
                            e_label = item.get('label', 'Unknown') if isinstance(item, dict) else getattr(item, 'label', 'Unknown')
                            s_id = str(item.get('start_id', '')) if isinstance(item, dict) else str(getattr(item, 'start_id', ''))
                            t_id = str(item.get('end_id', '')) if isinstance(item, dict) else str(getattr(item, 'end_id', ''))
                            e_props = item.get('properties', {}) if isinstance(item, dict) else getattr(item, 'properties', {})
                            
                            edge_ids.add(e_id)
                            elements.append({
                                "group": "edges",
                                "data": {"id": e_id, "source": s_id, "target": t_id, "label": str(e_label).replace('"', ''), "props": GraphService.safe_props(e_props)}
                            })
                    except Exception as e:
                        logger.error(f"[Edge Parse Error] {e}")
                        
                # 3. Raw String 파싱 (AgensGraph 포맷)
                elif isinstance(item, str) and ('[' in item and ']' in item and '{' in item and '}' in item):
                    edge_match = edge_pattern.match(item)
                    if edge_match:
                        try:
                            e_label, e_id, s_id, t_id, props_str = edge_match.groups()
                            if e_id not in edge_ids:
                                edge_ids.add(e_id)
                                e_props = json.loads(props_str) if props_str else {}
                                elements.append({
                                    "group": "edges",
                                    "data": {"id": e_id, "source": s_id, "target": t_id, "label": e_label, "props": GraphService.safe_props(e_props)}
                                })
                        except: pass
                    else:
                        node_match = node_pattern.match(item)
                        if node_match:
                            try:
                                n_label, n_id, props_str = node_match.groups()
                                if n_id not in node_ids:
                                    node_ids.add(n_id)
                                    n_props = json.loads(props_str) if props_str else {}
                                    elements.append({
                                        "group": "nodes",
                                        "data": {"id": n_id, "label": n_label, "props": GraphService.safe_props(n_props)}
                                    })
                            except: pass

            for r in rows:
                for item in r:
                    parse_item(item)
                            
                # 3. 폴백 (Tuples/Lists) 또는 연속된 원시 타입 시퀀스 (id, label, props)
                try:
                    if len(r) >= 3:
                        # RDB 드라이버 업데이트 후 PyGreSQL이 객체를 리턴하지 않고 [id, label(List), props(Dict)] 형태로 반환할 때 방어
                        for i in range(len(r) - 2):
                            item1, item2, item3 = r[i], r[i+1], r[i+2]
                            if isinstance(item1, str) and '.' in item1 and item1.split('.')[0].isdigit() and isinstance(item2, list) and isinstance(item3, dict):
                                # 노드 식별 성공. ex: ('9.1', ['vt_transfer'], {'amount': '0'})
                                n_id = item1
                                if n_id not in node_ids:
                                    node_ids.add(n_id)
                                    raw_label = item2[0] if item2 else 'Unknown'
                                    elements.append({"group": "nodes", "data": {"id": n_id, "label": str(raw_label).replace('"', ''), "props": GraphService.safe_props(item3)}})
                                    
                    if len(r) >= 5:
                        # 엣지 방어 [Edge_ID(str), Label(str), Source_ID(str), Target_ID(str), Props(dict)]
                        for i in range(len(r) - 4):
                            item1, item2, item3, item4, item5 = r[i], r[i+1], r[i+2], r[i+3], r[i+4]
                            
                            # Type matching for destructured PyGreSQL edge object
                            if isinstance(item1, str) and isinstance(item2, str) and isinstance(item3, str) and isinstance(item4, str) and isinstance(item5, dict):
                                # Verify items 1, 3, 4 are valid AgensGraph internal IDs (ex: '9.13')
                                if '.' in item1 and '.' in item3 and '.' in item4:
                                    # Validate they are numeric IDs safely
                                    if not (item1.split('.')[0].isdigit() and item3.split('.')[0].isdigit() and item4.split('.')[0].isdigit()):
                                        continue
                                        
                                    e_id = item1
                                    if e_id not in edge_ids:
                                        edge_ids.add(e_id)
                                        raw_label = item2 if item2 else 'Unknown'
                                        elements.append({
                                            "group": "edges",
                                            "data": {"id": e_id, "source": item3, "target": item4, "label": str(raw_label).replace('"', ''), "props": GraphService.safe_props(item5)}
                                        })
                except Exception as e:
                    logger.error(f"[Fallback Sequence Parse Error] {e}")
                
            if not elements and rows:
                try:
                    col_aliases = [d[0] for d in cur.description] if cur.description else []
                except Exception:
                    col_aliases = []
                for idx, r in enumerate(rows):
                    if all(not isinstance(v, (list, tuple, dict)) or v is None for v in r):
                        cleaned = [
                            v.strip('"') if isinstance(v, str) and v.startswith('"') and v.endswith('"') else v
                            for v in r
                        ]
                        row_props = {
                            (col_aliases[i] if i < len(col_aliases) else f"col{i}"): cleaned[i]
                            for i in range(len(cleaned))
                        }
                        elements.append({
                            "group": "scalar",
                            "data": {"id": f"row_{idx}", "label": "row", "props": row_props}
                        })
            return True, elements

        except Exception as e:
            logger.error(f"Query Error: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ---------------------------------------------------------
    # 📚 [Feature 5] GraphRAG
    # ---------------------------------------------------------
    @staticmethod
    def _generate_rag_report(question, context_texts, semantic_analysis=None):
        """그래프 조회 결과 기반 수사 보고서 생성 (AIService 의존성 제거)"""
        client = AIService.get_client()

        ontology_info = ""
        if semantic_analysis:
            ontology_info = "\n\n[온톨로지 분석]\n" + semantic_analysis.get('summary', '')

        safe_context = str(context_texts[:80]) + ontology_info

        prompt = f"""
        [사이버 범죄 수사 정보분석관 분석 보고서]

        당신은 경찰청 소속 최고 수준의 사이버 범죄 수사 정보분석관입니다.
        제공된 그래프 데이터베이스의 노드와 엣지 추적 결과를 바탕으로 명확하고 팩트 기반의 수사 보고서를 작성하십시오.

        [조회 결과 데이터]
        {safe_context}

        [작성 가이드라인]
        - 어조: 단호하고 객관적인 수사관 어조 사용.
        - 원칙: 제공된 결과 데이터 외부에 있는 상상을 덧붙이지 말 것.

        ### 1. 사건 개요 및 분석 대상
        ### 2. 식별된 주요 개체
        ### 3. 자금 및 통신 흐름 분석
        ### 4. 수사 종합 평가 및 제언
        """
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"!!! RAG Report Gen Error: {e}")
            return f"보고서 생성 실패: {e}"

    @staticmethod
    def quick_query(question, graph_path):
        """빠른 그래프 조회 (온톨로지 인식 강화 - 노드 + 엣지 속성)"""
        target_kw = _extract_keyword(question)
        logger.info(f"▶ [Quick Query] 키워드 추출: '{target_kw}'")
        
        conn, cur = get_db_connection()
        if not conn: return []
        try:
            conn.autocommit = False 
            safe_set_graph_path(cur, graph_path)
            
            # 🎯 온톨로지 인식: 노드 + 엣지 속성 모두 검색
            q = f"""
            MATCH (v)-[r]-(n) 
            WHERE v.flnm CONTAINS '{target_kw}'
               OR v.telno CONTAINS '{target_kw}'
               OR v.phone CONTAINS '{target_kw}'
               OR v.bacnt CONTAINS '{target_kw}'
               OR v.actno CONTAINS '{target_kw}'
               OR v.account CONTAINS '{target_kw}'
               OR v.site CONTAINS '{target_kw}'
               OR v.url CONTAINS '{target_kw}'
               OR v.ip CONTAINS '{target_kw}'
               OR v.file CONTAINS '{target_kw}'
               OR v.crime_type CONTAINS '{target_kw}'
               OR v.ontology_type CONTAINS '{target_kw}'
               OR v.entity_subtype CONTAINS '{target_kw}'
               OR v.domain_concept CONTAINS '{target_kw}'
               OR r.crime_type CONTAINS '{target_kw}'
               OR r.crime_name CONTAINS '{target_kw}'
            RETURN id(v), labels(v), properties(v), 
                   id(r), type(r), properties(r), 
                   id(n), labels(n), properties(n) 
            LIMIT 30
            """
            logger.info(f"▶ [Quick Query] 실행 Cypher:\n{q}")
            cur.execute(q)
            rows = cur.fetchall()
            conn.commit()
            
            logger.info(f"▶ [Quick Query] 결과: {len(rows)}개 행")
            
            elements = []
            for r in rows:
                v_id = str(r[0])
                r_id = str(r[3])
                n_id = str(r[6])
                v_p = safe_props(r[2])
                n_p = safe_props(r[8])
                
                elements.append({"group": "nodes", "data": {"id": v_id, "label": r[1][0], "props": v_p}})
                elements.append({"group": "nodes", "data": {"id": n_id, "label": r[7][0], "props": n_p}})
                elements.append({"group": "edges", "data": {"id": r_id, "source": v_id, "target": n_id, "label": r[4], "props": safe_props(r[5])}})
            
            return elements
        except Exception as e:
            logger.error(f"Quick Query Error: {e}")
            return []
        finally:
            if conn: conn.close()
    
    @staticmethod
    def rag_query(question, graph_path):
        """그래프 조회 + AI 보고서 생성 (온톨로지 인식 강화 - 노드 + 엣지)"""
        target_kw = _extract_keyword(question)
        logger.info(f"▶ [RAG] 키워드 추출: '{target_kw}'")
        
        conn, cur = get_db_connection()
        if not conn: return "DB Fail", []
        try:
            conn.autocommit = False 
            safe_set_graph_path(cur, graph_path)
            
            # 🎯 온톨로지 인식: 노드 + 엣지 속성 모두 검색
            q = f"""
            MATCH p=(v)-[*1..6]-(n) 
            WHERE v.flnm CONTAINS '{target_kw}'
               OR v.name CONTAINS '{target_kw}'
               OR v.nickname CONTAINS '{target_kw}'
               OR v.org_name CONTAINS '{target_kw}'
               OR v.telno CONTAINS '{target_kw}'
               OR v.phone CONTAINS '{target_kw}'
               OR v.bacnt CONTAINS '{target_kw}'
               OR v.actno CONTAINS '{target_kw}'
               OR v.account CONTAINS '{target_kw}'
               OR v.site CONTAINS '{target_kw}'
               OR v.url CONTAINS '{target_kw}'
               OR v.ip CONTAINS '{target_kw}'
               OR v.file CONTAINS '{target_kw}'
               OR v.crime_type CONTAINS '{target_kw}'
               OR v.ontology_type CONTAINS '{target_kw}'
               OR v.entity_subtype CONTAINS '{target_kw}'
               OR v.domain_concept CONTAINS '{target_kw}'
            UNWIND edges(p) as r
            RETURN id(startNode(r)), label(startNode(r)), properties(startNode(r)), 
                   id(r), label(r), properties(r), 
                   id(endNode(r)), label(endNode(r)), properties(endNode(r)) 
            LIMIT 50
            """
            logger.info(f"▶ [RAG] 실행 Cypher:\n{q}")
            cur.execute(q)
            rows = cur.fetchall()
            conn.commit()
            
            logger.info(f"▶ [RAG] 결과: {len(rows)}개 행")
            
            if not rows: 
                return f"그래프 데이터페이스에서 '{target_kw}' 키워드와 연관된 데이터를 찾을 수 없습니다.\n검색기반(RAG) 보고서 생성을 위해서는 특정 사건번호, 피의자 이름, 또는 계좌번호 등을 프롬프트에 명시해주세요. (예: 'CASE-2025-0610 분석 보고서 작성해줘')", []

            context_texts = []
            elements = []
            for r in rows:
                v_id = str(r[0])
                r_id = str(r[3])
                n_id = str(r[6])
                v_p = safe_props(r[2])
                n_p = safe_props(r[8])
                r_p = safe_props(r[5])  # 엣지 속성
                
                # 노드 타입별 주요 속성 추출
                src_name = (v_p.get('flnm') or v_p.get('telno') or v_p.get('phone') or 
                           v_p.get('actno') or v_p.get('bacnt') or v_p.get('account') or
                           v_p.get('site') or v_p.get('url') or v_p.get('ip') or 
                           v_p.get('file') or v_p.get('name') or "Unknown")
                tgt_name = (n_p.get('flnm') or n_p.get('telno') or n_p.get('phone') or 
                           n_p.get('actno') or n_p.get('bacnt') or n_p.get('account') or
                           n_p.get('site') or n_p.get('url') or n_p.get('ip') or 
                           n_p.get('file') or n_p.get('name') or "Unknown")
                
                # 엣지 상세 정보 추출 (source, updated 제외)
                edge_details = []
                if r_p:
                    for k, v in r_p.items():
                        if k not in ['source', 'updated'] and v:
                            edge_details.append(f"{k}={v}")
                
                # 풍부한 컨텍스트 생성
                edge_type = r[4]
                if edge_details:
                    edge_info = ", ".join(edge_details)
                    context_texts.append(f"{src_name} -[{edge_type}: {edge_info}]-> {tgt_name}")
                else:
                    context_texts.append(f"{src_name} -[{edge_type}]-> {tgt_name}")
                
                elements.append({"group": "nodes", "data": {"id": v_id, "label": r[1][0], "props": v_p}})
                elements.append({"group": "nodes", "data": {"id": n_id, "label": r[7][0], "props": n_p}})
                elements.append({"group": "edges", "data": {"id": r_id, "source": v_id, "target": n_id, "label": r[4], "props": safe_props(r[5])}})


            # 온톨로지 기반 분석
            from app.services.ontology_service import SemanticAnalyzer
            semantic_analysis = SemanticAnalyzer.analyze(elements, context_texts)
            
            report = GraphService._generate_rag_report(question, context_texts, semantic_analysis)
            return report, elements
        except Exception as e:
            return str(e), []
        finally:
            conn.close()

    @staticmethod
    def create_manual_node(graph_name, label, properties):
        """수동으로 노드를 생성하는 함수 (i2 기능)
        
        Note: AgensGraph의 ccop_fraud_graph에서 Cypher CREATE는 label ID 0으로 
        노드를 생성하는 알려진 이슈가 있습니다. 이 경우 삭제 시 raw SQL을 사용합니다.
        """
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            conn.autocommit = True
            safe_set_graph_path(cur, graph_name)
            
            # Cypher CREATE로 노드 생성
            props_str = "{}"
            if properties:
                prop_list = []
                for k, v in properties.items():
                    k_str = str(k).replace('"', '').replace("'", "")
                    if isinstance(v, (int, float)):
                        prop_list.append(f"{k_str}: {v}")
                    else:
                        v_str = str(v).replace("'", "''")
                        prop_list.append(f"{k_str}: '{v_str}'")
                props_str = "{" + ", ".join(prop_list) + "}"
                
            cur.execute(f"CREATE (n:{label} {props_str}) RETURN id(n)")
            new_id = cur.fetchone()[0]
            logger.info(f"▶ [CreateNode] Cypher CREATE → {graph_name}.{label}, ID: {new_id}")
            return True, str(new_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def create_manual_edge(graph_name, src_id, tgt_id, label, properties):
        """수동으로 엣지를 생성하는 함수 (i2 기능)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            safe_set_graph_path(cur, graph_name)
            
            props_str = "{}"
            if properties:
                prop_list = []
                for k, v in properties.items():
                    k_str = str(k).replace('"', '').replace("'", "")
                    if isinstance(v, (int, float)):
                        prop_list.append(f"{k_str}: {v}")
                    else:
                        v_str = str(v).replace("'", "''") 
                        prop_list.append(f"{k_str}: '{v_str}'")
                props_str = "{" + ", ".join(prop_list) + "}"
                
            q = f"MATCH (a), (b) WHERE id(a) = '{src_id}' AND id(b) = '{tgt_id}' CREATE (a)-[r:{label} {props_str}]->(b) RETURN id(r)"
            cur.execute(q)
            new_id = cur.fetchone()[0]
            conn.commit()
            return True, str(new_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def delete_element(graph_name, element_id, is_edge=False):
        """수동으로 노드/엣지를 삭제하는 함수
        
        Cypher MATCH + DELETE를 사용합니다.
        Note: label ID가 0인 노드(AgensGraph CREATE 버그)는 삭제 불가 → 
        프론트엔드에서 '화면에서만 제거' 옵션을 제공합니다.
        """
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            conn.autocommit = True
            safe_set_graph_path(cur, graph_name)
            if is_edge:
                cur.execute(f"MATCH ()-[r]-() WHERE id(r) = '{element_id}' DELETE r")
            else:
                cur.execute(f"MATCH (n) WHERE id(n) = '{element_id}' DETACH DELETE n")
            logger.info(f"▶ [DeleteElement] Cypher DELETE, graph={graph_name}, ID: {element_id}")
            return True, "삭제 완료"
        except Exception as e:
            logger.error(f"▶ [DeleteElement] ERROR: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════════
    # 수사 분석 지원 — 자금흐름 추적 / 타임라인 (2026-07)
    # ══════════════════════════════════════════════════════════════════
    @staticmethod
    def _num(v):
        """금액/숫자 문자열 → float (콤마·'원'·None 방어)"""
        if v is None:
            return 0.0
        try:
            return float(str(v).replace(',', '').replace('원', '').strip() or 0)
        except Exception:
            return 0.0

    @staticmethod
    def _disp(props):
        """노드 표시명 추출 (계좌/전화 등 공통 폴백)"""
        if not isinstance(props, dict):
            return ''
        for k in ('name', 'flnm', 'bacnt_no', 'acct_no', 'account', 'accno', 'acnt_no',
                  'number', 'telno', 'phone', 'val', 'title', 'id_val', 'event_id'):
            v = props.get(k)
            if v not in (None, ''):
                return str(v)
        return ''

    @staticmethod
    def trace_fund_flow(start_id, graph_path, max_hops=5, direction='down', min_amount=0):
        """
        자금 흐름 다단계 추적 — 시작 계좌에서 이체 체인을 재귀 추적하고
        자금세탁 typology(순환/분산·집중/종착) 자동 탐지.
        direction: 'down'(자금 유출 방향) | 'up'(자금 유입 출처)
        반환: {nodes, edges(Cytoscape), analysis, paths}
        """
        from collections import defaultdict
        conn, cur = GraphService.get_db_connection()
        if not conn:
            return {"error": "DB 연결 실패"}
        try:
            safe_set_graph_path(cur, graph_path)
            cur.execute("""
                MATCH (a1:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(a2:vt_bacnt)
                RETURN id(a1), properties(a1), id(t), properties(t), id(a2), properties(a2)
            """)
            rows = cur.fetchall()
            if not rows:
                return {"nodes": [], "edges": [], "paths": [],
                        "analysis": {"error": "이체 데이터 없음", "num_transfers": 0}}

            acct_props = {}
            adj = defaultdict(list)      # down: from -> [(to, edge)]
            radj = defaultdict(list)     # up:   to   -> [(from, edge)]
            for a1, p1, tid, tp, a2, p2 in rows:
                a1, a2, tid = str(a1), str(a2), str(tid)
                p1, tp, p2 = GraphService.safe_props(p1), GraphService.safe_props(tp), GraphService.safe_props(p2)
                acct_props.setdefault(a1, p1); acct_props.setdefault(a2, p2)
                amt = GraphService._num(tp.get('amount', tp.get('dlng_amt', 0)))
                if amt < GraphService._num(min_amount):
                    continue
                edge = {"tid": tid, "from": a1, "to": a2, "amount": amt,
                        "ts": tp.get('timestamp', tp.get('dlng_dt', ''))}
                adj[a1].append((a2, edge))
                radj[a2].append((a1, edge))

            start_id = str(start_id)
            use_adj = adj if direction == 'down' else radj

            # BFS 트리 기준 조상 판정 헬퍼 (순환은 traversal 방향으로 판정 — 원시 엣지 방향 아님)
            parent = {}
            def is_ancestor(anc, node):
                steps, curn = 0, node
                while steps < 200:
                    if curn == anc:
                        return True
                    if curn not in parent:
                        return False
                    curn = parent[curn][0]; steps += 1
                return False

            # BFS: 각 노드 1회 방문(hop 거리) + 사용 엣지 수집 + back-edge(순환) 탐지
            hop = {start_id: 0}
            used = []
            cyclic_pairs = set()      # 순환을 이루는 raw (from,to)
            frontier = [start_id]
            cur_hop = 0
            MAX_NODES = 400
            while frontier and cur_hop < int(max_hops):
                nf = []
                for node in frontier:
                    for nxt, edge in use_adj.get(node, []):
                        used.append(edge)
                        if nxt not in hop:
                            if len(hop) < MAX_NODES:
                                hop[nxt] = hop[node] + 1
                                parent[nxt] = (node, edge)
                                nf.append(nxt)
                        elif is_ancestor(nxt, node):       # traversal 상 조상으로 회귀 = 순환
                            cyclic_pairs.add((edge['from'], edge['to']))
                frontier = nf
                cur_hop += 1
            reached = set(hop.keys())

            # 도달 노드 사이 엣지만 (from,to) 집계
            pair_agg = {}
            for e in used:
                if e['from'] in reached and e['to'] in reached:
                    key = (e['from'], e['to'])
                    a = pair_agg.setdefault(key, {"total": 0.0, "count": 0, "cyc": False})
                    a['total'] += e['amount']; a['count'] += 1
                    if key in cyclic_pairs:
                        a['cyc'] = True

            out_deg = defaultdict(int); in_deg = defaultdict(int)
            for (f, t) in pair_agg:
                out_deg[f] += 1; in_deg[t] += 1
            fan_out = [n for n in reached if out_deg[n] >= 3]
            fan_in = [n for n in reached if in_deg[n] >= 3]
            terminals = [n for n in reached if n != start_id and out_deg[n] == 0]
            circular_edges = [k for k, v in pair_agg.items() if v['cyc']]
            total_amount = sum(v['total'] for v in pair_agg.values())

            def trace_path(n):
                seq, amts, steps = [n], [], 0
                while n in parent and steps < 200:
                    p, e = parent[n]
                    amts.append(e['amount']); seq.append(p); n = p; steps += 1
                seq.reverse(); amts.reverse()
                return seq, amts
            paths = []
            for term in sorted(terminals, key=lambda n: hop[n], reverse=True)[:15]:
                seq, amts = trace_path(term)
                paths.append({
                    "accounts": [{"id": nid, "name": GraphService._disp(acct_props.get(nid, {}))} for nid in seq],
                    "amounts": amts, "hops": len(seq) - 1, "min_amount": min(amts) if amts else 0})

            def node_classes(nid):
                cls = []
                if nid == start_id: cls.append('ff-start')
                if nid in terminals: cls.append('ff-terminal')
                if nid in fan_out: cls.append('ff-fanout')
                if nid in fan_in: cls.append('ff-fanin')
                return ' '.join(cls)
            nodes = [{"group": "nodes", "classes": node_classes(nid),
                      "data": {"id": nid, "label": "vt_bacnt", "hop": hop[nid],
                               "props": acct_props.get(nid, {}),
                               "name": GraphService._disp(acct_props.get(nid, {}))}} for nid in reached]
            edges = []
            for (f, t), v in pair_agg.items():
                lbl = f"₩{int(v['total']):,}" + (f" ({v['count']}건)" if v['count'] > 1 else "")
                edges.append({"group": "edges",
                    "classes": "fund-flow-edge" + (" ff-circular" if v['cyc'] else ""),
                    "data": {"id": f"ff_{f}_{t}", "source": f, "target": t, "label": lbl,
                             "amount": v['total'], "count": v['count']}})

            start_name = GraphService._disp(acct_props.get(start_id, {})) or start_id
            analysis = {
                "start": {"id": start_id, "name": start_name},
                "direction": direction, "max_hops": int(max_hops),
                "num_accounts": len(reached),
                "num_transfers": sum(v['count'] for v in pair_agg.values()),
                "num_flow_edges": len(pair_agg), "total_amount": total_amount,
                "max_depth_reached": max(hop.values()) if hop else 0,
                "terminals": [{"id": n, "name": GraphService._disp(acct_props.get(n, {}))} for n in terminals],
                "fan_out": [{"id": n, "name": GraphService._disp(acct_props.get(n, {})), "deg": out_deg[n]} for n in fan_out],
                "fan_in": [{"id": n, "name": GraphService._disp(acct_props.get(n, {})), "deg": in_deg[n]} for n in fan_in],
                "circular_count": len(circular_edges), "has_circular": len(circular_edges) > 0,
            }
            return {"nodes": nodes, "edges": edges, "paths": paths, "analysis": analysis}
        except Exception as e:
            logger.error(f"[FundFlow] ERROR: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_timeline(graph_path, entity_id=None, event_types=None, limit=1000, corr_window_min=10):
        """
        이벤트(이체/통화/메시지) 시간순 집계 + 시간창 상관(통화→이체) 탐지.
        entity_id 지정 시 해당 노드가 참여한 이벤트만.
        반환: {events, correlations, stats}
        """
        from datetime import datetime
        from collections import Counter
        conn, cur = GraphService.get_db_connection()
        if not conn:
            return {"error": "DB 연결 실패"}
        # (label, ko, cypher, role1, role2, participant_label)
        specs = [
            ("vt_transfer", "이체",
             "MATCH (a1:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(a2:vt_bacnt) "
             "RETURN id(t), properties(t), id(a1), properties(a1), id(a2), properties(a2)",
             "출금", "입금", "vt_bacnt"),
            ("vt_call", "통화",
             "MATCH (p1)-[:caller]->(t:vt_call)-[:callee]->(p2) "
             "RETURN id(t), properties(t), id(p1), properties(p1), id(p2), properties(p2)",
             "발신", "수신", "vt_telno"),
            ("vt_msg", "메시지",
             "MATCH (p1)-[:sent_msg]->(t:vt_msg)-[:received_msg]->(p2) "
             "RETURN id(t), properties(t), id(p1), properties(p1), id(p2), properties(p2)",
             "발신", "수신", "vt_telno"),
        ]
        events = []
        try:
            safe_set_graph_path(cur, graph_path)
            for label, ko, cypher, r1, r2, plabel in specs:
                if event_types and label not in event_types:
                    continue
                try:
                    cur.execute(cypher)
                    fetched = cur.fetchall()
                except Exception as ex:      # 라벨 미존재 등 → 스킵 (autocommit이라 tx 오염 없음)
                    logger.info(f"[Timeline] {label} 스킵: {ex}")
                    continue
                for tid, tp, i1, q1, i2, q2 in fetched:
                    tp = GraphService.safe_props(tp); q1 = GraphService.safe_props(q1); q2 = GraphService.safe_props(q2)
                    ts = tp.get('timestamp', tp.get('dlng_dt', tp.get('call_strt_dt', '')))
                    parts = [
                        {"id": str(i1), "name": GraphService._disp(q1), "role": r1, "label": plabel},
                        {"id": str(i2), "name": GraphService._disp(q2), "role": r2, "label": plabel}]
                    if label == "vt_transfer":
                        detail = f"₩{int(GraphService._num(tp.get('amount', tp.get('dlng_amt', 0)))):,}"
                    elif label == "vt_call":
                        d = GraphService._num(tp.get('duration', tp.get('call_dur_sec', 0)))
                        detail = f"{int(d)}초" if d else ""
                    else:
                        detail = ""
                    events.append({"id": str(tid), "type": label, "type_ko": ko,
                                   "timestamp": ts, "participants": parts, "detail": detail})
            if entity_id:
                eid = str(entity_id)
                events = [e for e in events if any(p['id'] == eid for p in e['participants'])]

            def epoch(s):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(str(s).strip(), fmt).timestamp()
                    except Exception:
                        pass
                return None
            for e in events:
                e['ts_epoch'] = epoch(e['timestamp'])
            dated = sorted([e for e in events if e['ts_epoch'] is not None], key=lambda e: e['ts_epoch'])

            correlations = []
            win = int(corr_window_min) * 60
            calls = [e for e in dated if e['type'] == 'vt_call']
            transfers = [e for e in dated if e['type'] == 'vt_transfer']
            for tr in transfers:
                for c in calls:
                    gap = tr['ts_epoch'] - c['ts_epoch']
                    if 0 <= gap <= win:
                        correlations.append({"call_id": c['id'], "transfer_id": tr['id'],
                                             "gap_min": round(gap / 60, 1),
                                             "call_time": c['timestamp'], "transfer_time": tr['timestamp']})
            dated = dated[:int(limit)]
            stats = {"total": len(events), "dated": len(dated),
                     "by_type": dict(Counter(e['type_ko'] for e in events)),
                     "span": {"start": dated[0]['timestamp'] if dated else None,
                              "end": dated[-1]['timestamp'] if dated else None},
                     "correlations": len(correlations)}
            return {"events": dated, "correlations": correlations, "stats": stats}
        except Exception as e:
            logger.error(f"[Timeline] ERROR: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def analyze_centrality(graph_path, top_n=15):
        """
        중심성·조직구조 분석 — 전체 그래프에서 degree/betweenness(Brandes)/PageRank
        중심성 + 커뮤니티(label propagation) 계산. 순수 파이썬.
        반환: {node_meta, top_betweenness, top_pagerank, top_degree, communities, stats}
        """
        from collections import defaultdict, deque, Counter
        conn, cur = GraphService.get_db_connection()
        if not conn:
            return {"error": "DB 연결 실패"}
        try:
            safe_set_graph_path(cur, graph_path)
            cur.execute("MATCH (n) RETURN id(n), labels(n), properties(n)")
            node_rows = cur.fetchall()
            cur.execute("MATCH (a)-[r]->(b) RETURN id(a), id(b)")
            edge_rows = cur.fetchall()

            nodes = {}
            for nid, labels, props in node_rows:
                nid = str(nid)
                props = GraphService.safe_props(props)
                nodes[nid] = {"label": (labels[0] if labels else '?'),
                              "name": GraphService._disp(props)}
            adj = defaultdict(set)
            for a, b in edge_rows:
                a, b = str(a), str(b)
                if a != b and a in nodes and b in nodes:
                    adj[a].add(b); adj[b].add(a)
            ids = list(nodes.keys())
            N = len(ids)
            if N == 0:
                return {"error": "노드 없음", "stats": {"nodes": 0}}
            TOO_BIG = N > 2500          # betweenness는 O(V·E) — 대형 그래프 보호

            degree = {n: len(adj[n]) for n in ids}

            # PageRank (power iteration)
            pr = {n: 1.0 / N for n in ids}
            for _ in range(60):
                nxt = {n: (1 - 0.85) / N for n in ids}
                dangling = sum(pr[n] for n in ids if not adj[n]) / N
                for n in ids:
                    nxt[n] += 0.85 * dangling
                for n in ids:
                    if adj[n]:
                        share = 0.85 * pr[n] / len(adj[n])
                        for m in adj[n]:
                            nxt[m] += share
                pr = nxt

            # Betweenness (Brandes, unweighted)
            bet = {n: 0.0 for n in ids}
            if not TOO_BIG:
                for s in ids:
                    S = []; P = {w: [] for w in ids}
                    sigma = dict.fromkeys(ids, 0.0); sigma[s] = 1.0
                    dist = dict.fromkeys(ids, -1); dist[s] = 0
                    Q = deque([s])
                    while Q:
                        v = Q.popleft(); S.append(v)
                        for w in adj[v]:
                            if dist[w] < 0:
                                dist[w] = dist[v] + 1; Q.append(w)
                            if dist[w] == dist[v] + 1:
                                sigma[w] += sigma[v]; P[w].append(v)
                    delta = dict.fromkeys(ids, 0.0)
                    while S:
                        w = S.pop()
                        for v in P[w]:
                            if sigma[w]:
                                delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                        if w != s:
                            bet[w] += delta[w]
                for n in ids:
                    bet[n] /= 2.0       # 무방향 보정

            # 커뮤니티 (label propagation — 결정적: 고정 순서 + 타이브레이크)
            comm = {n: i for i, n in enumerate(ids)}
            for _ in range(30):
                changed = False
                for n in ids:
                    if not adj[n]:
                        continue
                    cnt = Counter(comm[m] for m in adj[n])
                    best = max(cnt.items(), key=lambda kv: (kv[1], -kv[0]))[0]
                    if comm[n] != best:
                        comm[n] = best; changed = True
                if not changed:
                    break
            # 커뮤니티 재라벨 (크기순 0..k)
            csize = Counter(comm.values())
            order = [c for c, _ in csize.most_common()]
            remap = {c: i for i, c in enumerate(order)}
            for n in ids:
                comm[n] = remap[comm[n]]

            # 정규화 + 랭킹
            bmax = max(bet.values()) or 1.0
            pmax = max(pr.values()) or 1.0
            node_meta = {n: {"c": comm[n], "b": round(bet[n] / bmax, 4),
                             "p": round(pr[n] / pmax, 4), "d": degree[n],
                             "label": nodes[n]["label"], "name": nodes[n]["name"]} for n in ids}

            def rank(metric):
                return [{"id": n, "name": nodes[n]["name"], "label": nodes[n]["label"],
                         "value": round(metric[n], 4)}
                        for n in sorted(ids, key=lambda x: metric[x], reverse=True)[:int(top_n)]
                        if metric[n] > 0]

            communities = []
            for c in range(len(order)):
                members = [n for n in ids if comm[n] == c]
                if len(members) < 2:
                    continue
                lead = max(members, key=lambda n: pr[n])
                communities.append({"id": c, "size": len(members),
                                    "lead": {"id": lead, "name": nodes[lead]["name"], "label": nodes[lead]["label"]},
                                    "label_mix": dict(Counter(nodes[n]["label"] for n in members))})
            return {
                "node_meta": node_meta,
                "top_betweenness": rank(bet), "top_pagerank": rank(pr), "top_degree": rank(degree),
                "communities": communities,
                "stats": {"nodes": N, "edges": len(edge_rows), "communities": len(communities),
                          "betweenness_computed": not TOO_BIG}}
        except Exception as e:
            logger.error(f"[Centrality] ERROR: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    @staticmethod
    def resolve_entities(graph_path, target_label='vt_psn', min_shared=1, top_n=30):
        """
        엔티티 해소(동일인 의심) — 같은 타입 노드 쌍 중 공유 '식별자원'(전화·계좌·기기·
        IP·ID)이 많거나 이름이 유사한 후보를 탐지. 사건/청원 공유는 공범이므로 제외.
        기존 sameAs 연결쌍 제외. 반환: {candidates, stats}
        """
        import re
        from difflib import SequenceMatcher
        from collections import defaultdict
        from math import log
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', str(target_label or '')):
            target_label = 'vt_psn'
        IDENTITY = {'vt_telno', 'vt_bacnt', 'vt_dev', 'vt_ip', 'vt_id', 'vt_site', 'vt_atm'}
        conn, cur = GraphService.get_db_connection()
        if not conn:
            return {"error": "DB 연결 실패"}
        try:
            safe_set_graph_path(cur, graph_path)
            cur.execute(f"MATCH (n:{target_label}) RETURN id(n), properties(n)")
            targets = {str(nid): GraphService.safe_props(p) for nid, p in cur.fetchall()}
            if len(targets) < 2:
                return {"candidates": [], "stats": {"targets": len(targets), "note": "대상 2개 미만"}}

            # 대상 → 식별자원 이웃
            res_of = defaultdict(dict)     # node -> {res_id: (label,name)}
            res_deg = defaultdict(int)     # 자원 id -> 연결 대상 수 (희소성)
            cur.execute(f"MATCH (n:{target_label})-[r]-(m) RETURN id(n), id(m), labels(m), properties(m)")
            for nid, mid, mlabels, mprops in cur.fetchall():
                nid, mid = str(nid), str(mid)
                mlabel = mlabels[0] if mlabels else '?'
                if mlabel in IDENTITY and nid in targets:
                    res_of[nid][mid] = (mlabel, GraphService._disp(GraphService.safe_props(mprops)))
            for nid in res_of:
                for rid in res_of[nid]:
                    res_deg[rid] += 1

            # 공유 상대(counterparty) — 통화·이체가 reified라 상대는 이벤트 관통 3-hop:
            #   person-[owns_phone]-전화-[caller/callee]-통화-[callee/caller]-상대전화
            #   person-[has_account]-계좌-[from/to]-이체-[to/from]-상대계좌
            # 두 사람이 같은 (희소) 상대를 접촉 = 공유 대포폰/계좌 재사용 = 동일인/공모 신호.
            contact_of = defaultdict(set); contact_meta = {}; contact_deg = defaultdict(int)
            cp_queries = [
                f"MATCH (n:{target_label})-[:owns_phone]-(p1)-[:caller]-(c:vt_call)-[:callee]-(p2) RETURN id(n), id(p2), labels(p2), properties(p2)",
                f"MATCH (n:{target_label})-[:owns_phone]-(p1)-[:callee]-(c:vt_call)-[:caller]-(p2) RETURN id(n), id(p2), labels(p2), properties(p2)",
                f"MATCH (n:{target_label})-[:has_account]-(a1)-[:from_account]-(t:vt_transfer)-[:to_account]-(a2) RETURN id(n), id(a2), labels(a2), properties(a2)",
                f"MATCH (n:{target_label})-[:has_account]-(a1)-[:to_account]-(t:vt_transfer)-[:from_account]-(a2) RETURN id(n), id(a2), labels(a2), properties(a2)",
            ]
            for q in cp_queries:
                try:
                    cur.execute(q)
                    for nid, cid, clabels, cprops in cur.fetchall():
                        nid, cid = str(nid), str(cid)
                        clabel = clabels[0] if clabels else '?'
                        if nid in targets and cid != nid and cid not in res_of.get(nid, {}):
                            if cid not in contact_of[nid]:
                                contact_of[nid].add(cid); contact_deg[cid] += 1
                            contact_meta[cid] = (clabel, GraphService._disp(GraphService.safe_props(cprops)))
                except Exception as ex:
                    logger.info(f"[EntityRes] counterparty query skip: {ex}")

            # 기존 sameAs 제외쌍
            same = set()
            try:
                cur.execute("MATCH (a)-[:sameAs]-(b) RETURN id(a), id(b)")
                for a, b in cur.fetchall():
                    same.add(frozenset((str(a), str(b))))
            except Exception:
                pass

            tids = list(targets.keys())
            candidates = []
            for i in range(len(tids)):
                for j in range(i + 1, len(tids)):
                    a, b = tids[i], tids[j]
                    if frozenset((a, b)) in same:
                        continue
                    shared = set(res_of.get(a, {})) & set(res_of.get(b, {}))
                    # 공유 상대: 2명 이상이 접촉한 상대(희소할수록 가중↑). 만인이 접촉한 허브는
                    # 짝당 1개만 공유되어 아래 '≥2개' 임계에서 자연 배제됨.
                    shared_cp = [cid for cid in (contact_of.get(a, set()) & contact_of.get(b, set()))
                                 if contact_deg[cid] >= 2]
                    name_a = GraphService._disp(targets[a]); name_b = GraphService._disp(targets[b])
                    name_sim = SequenceMatcher(None, name_a, name_b).ratio() if (name_a and name_b) else 0.0
                    # 열거형 이름(피의자1 vs 피의자2 — 끝자리 숫자만 다름)은 별개 개체 → 이름신호 무효
                    if name_sim and name_a != name_b and \
                       re.sub(r'\d+$', '', name_a) == re.sub(r'\d+$', '', name_b):
                        name_sim = 0.0
                    # 채택: 직접 공유자원 ≥min_shared, 또는 희소 공유상대 ≥2, 또는 강한 이름유사
                    if len(shared) < int(min_shared) and len(shared_cp) < 2 and name_sim < 0.85:
                        continue
                    rare_cp = [c for c in shared_cp if contact_deg[c] <= 4]     # 희소=변별력↑
                    hub_cp = [c for c in shared_cp if contact_deg[c] > 4]       # 허브=공유 인프라
                    aa = sum(1.0 / log(res_deg[r] + 1e-9) for r in shared if res_deg[r] > 1)
                    cp_score = sum(1.0 / contact_deg[c] for c in shared_cp)     # 희소할수록 가중 ↑
                    score = round(len(shared) * 3.0 + len(rare_cp) * 1.5 + aa * 0.5 + cp_score * 1.0 + name_sim * 0.8, 3)
                    # 신뢰도: 직접 공유자원=동일인 강력, 희소 공유상대=중간, 허브만 공유=공유 인프라
                    conf = 'high' if shared else ('mid' if (rare_cp or name_sim >= 0.85) else 'low')
                    reasons = []
                    if shared:
                        reasons.append(f"공유 식별자원 {len(shared)}개 (동일인 강력 의심)")
                    if rare_cp:
                        reasons.append(f"희소 공유상대 {len(rare_cp)}개")
                    if hub_cp and not rare_cp:
                        reasons.append(f"공유 인프라 {len(hub_cp)}개 (동일 사건 연루 가능)")
                    if name_sim >= 0.85:
                        reasons.append(f"이름 유사 {round(name_sim, 2)}")
                    candidates.append({
                        "a": {"id": a, "name": name_a or ('…' + a[-4:])},
                        "b": {"id": b, "name": name_b or ('…' + b[-4:])},
                        "shared_count": len(shared), "shared_cp_count": len(shared_cp),
                        "name_sim": round(name_sim, 3), "score": score, "confidence": conf,
                        "shared_resources": [{"id": r, "label": res_of[a][r][0], "name": res_of[a][r][1]}
                                             for r in shared]
                        + [{"id": c, "label": contact_meta[c][0], "name": contact_meta[c][1], "via": "2hop"}
                           for c in shared_cp],
                        "reasons": reasons})
            _cr = {'high': 2, 'mid': 1, 'low': 0}
            candidates.sort(key=lambda c: (_cr.get(c['confidence'], 0), c['score']), reverse=True)
            candidates = candidates[:int(top_n)]
            return {"candidates": candidates,
                    "stats": {"targets": len(targets), "target_label": target_label,
                              "candidate_pairs": len(candidates), "existing_sameas": len(same)}}
        except Exception as e:
            logger.error(f"[EntityResolution] ERROR: {e}")
            return {"error": str(e)}
        finally:
            conn.close()