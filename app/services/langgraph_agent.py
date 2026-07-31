import json
import logging
import os
import re
import time
from typing import TypedDict, List, Dict, Any, Optional, Union
from langgraph.graph import StateGraph, END, START
from flask import current_app
from openai import OpenAI

from app.services.ai_service import AIService
from app.services.graph_service import GraphService
from app.services.schema_tools_server import SchemaToolServer
from app.services.ontology_service import KICSCrimeDomainOntology

logger = logging.getLogger(__name__)

_T2C_V37_SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "t2c_v37_system.txt"
)
try:
    with open(_T2C_V37_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as _f:
        T2C_V37_SYSTEM_PROMPT = _f.read()
except FileNotFoundError:
    T2C_V37_SYSTEM_PROMPT = ""
    logger.warning(f"v3.7 system prompt not found at {_T2C_V37_SYSTEM_PROMPT_PATH}")

class AgentState(TypedDict):
    """LangGraph 에이전트의 상태 정의"""
    question: str
    graph_path: str
    intent: str
    keyword: Optional[str] # 추가됨
    labels: List[str] # [추가] 예상되는 노드 레이블 목록
    term1: Optional[str]
    term2: Optional[str]
    entities: List[Dict[str, Any]]
    schema_info: str
    cypher_query: str
    execution_result: Any
    error_count: int
    reflection_log: List[str]
    final_response: Any
    config: Dict[str, Any]
    metrics: Dict[str, float]

# 노드 레이블 → RDB 브리지 키 매핑 (label: (table, pk_col, props_key))
_BRIDGE_KEY_MAP: Dict[str, tuple] = {
    "vt_case":     ("TB_INCDNT_MST",        "INCDNT_NO",      "flnm"),
    "vt_petition": ("TB_PETTN_MST",         "PETTN_NO",       "flnm"),
    "vt_psn":      ("TB_PRSN",             "PRSN_ID",        "id"),
    "vt_org":      ("TB_INST",             "INST_ID",        "org_id"),
    "vt_bacnt":    ("TB_FIN_BACNT",         "BACNT_NO",       "account_no"),
    "vt_telno":    ("TB_TELNO_MST",         "TELNO",          "telno"),
    "vt_ip":       ("TB_SYS_LGN_EVT",      "CNNT_IP_ADDR",   "ip_addr"),
    "vt_site":     ("TB_WEB_DMN",           "DMN_NM",         "domain"),
    "vt_file":     ("TB_DGTL_FILE_INVNT",   "FILE_HASH",      "file_hash"),
    "vt_id":       ("TB_DGTL_ID_MST",       "ID_VAL",         "id_val"),
    "vt_email":    ("TB_EMAIL_MST",         "EMAIL_ADDR",     "email_addr"),
    "vt_crypto":   ("TB_CRYPTO_WALLET_MST", "WALLET_ADDR",    "wallet_addr"),
    "vt_vhcl":     ("TB_VHCL_MST",          "VHCLNO",         "vhclno"),
    "vt_dev":      ("TB_DEV_MST",           "DEV_ID",         "dev_id"),
    "vt_atm":      ("TB_ATM_MST",           "ATM_ID",         "atm_id"),
    "vt_loc":      ("TB_LOC_MST",           "LOC_ID",         "loc_id"),
    "vt_transfer": ("TB_FIN_BACNT_DLNG",    "DLNG_SN",        "event_id"),
    "vt_call":     ("TB_TELNO_CALL_DTL",    "CALL_SN",        "event_id"),
    "vt_msg":      ("TB_TELNO_SMS_MSG",     "SMS_SN",         "event_id"),
    "vt_access":   ("TB_SYS_LGN_EVT",      "LGN_SN",         "access_id"),
    "vt_movement": ("TB_VHCL_LPR_EVT",     "LPR_SN",         "event_id"),
}


def _enrich_elements_bridge_key(elements: List) -> List:
    """각 노드 element에 bridge_key(RDB 역추적 키) + evid_grade/src_tier 추가"""
    enriched = []
    for el in elements:
        if not isinstance(el, dict):
            enriched.append(el)
            continue
        if el.get("group") == "nodes":
            data = el.get("data", {})
            label = data.get("label", "")
            props = data.get("props", {}) or {}
            bk = None
            if label in _BRIDGE_KEY_MAP:
                tbl, pk_col, props_key = _BRIDGE_KEY_MAP[label]
                pk_val = props.get(props_key) or props.get(pk_col.lower())
                bk = {"table": tbl, "pk": pk_col, "val": pk_val}
            enriched_data = dict(data)
            enriched_data["bridge_key"] = bk
            enriched_data["evid_grade"] = props.get("evid_grade")
            enriched_data["src_tier"] = props.get("src_tier")
            enriched.append({**el, "data": enriched_data})
        else:
            enriched.append(el)
    return enriched


class LangGraphAgent:
    """
    제안된 LangGraph 기반의 AI 수사 에이전트 아키텍처 구현 클래스.
    순환형 구조(Reflection 루프)를 통해 쿼리 정확도를 스스로 개선합니다.
    """

    # V3.2 POLE 6계층 정적 fallback 스키마 (동적 조회 비활성화 또는 빈 그래프 시 사용)
    _POLE_SCHEMA: Dict[str, Any] = {
        "node_labels": {
            "vt_src":      ["src_id", "src_name", "src_type", "reliability_tier",
                            "collector", "collected_at", "update_cycle"],
            "vt_case":     ["flnm", "incdnt_no", "incdnt_nm", "incdnt_typ_cd",
                            "occrn_dt", "damage_amount", "status", "source_id"],
            "vt_petition": ["petition_id", "raw_id", "rcpt_dt", "rcpt_channel",
                            "crime_type_cd", "damage_amt", "status", "source_id"],
            "vt_psn":      ["psn_id", "name", "korn_flnm", "dob", "gender",
                            "nationality", "risk_level", "rrno_hash", "source_id"],
            "vt_org":      ["org_id", "org_name", "org_category", "brno", "source_id"],
            "vt_bacnt":    ["account_no", "bank_cd", "bank_nm", "dpstr_nm",
                            "account_type", "is_burner", "source_id"],
            "vt_telno":    ["telno", "country_code", "telco_nm", "join_typ_cd",
                            "imsi", "is_burner", "source_id"],
            "vt_ip":       ["ip_addr", "version", "isp", "asn", "country",
                            "is_vpn", "is_tor", "is_proxy", "abuse_score", "source_id"],
            "vt_site":     ["url_addr", "dmn_addr", "site_type", "is_malicious",
                            "risk_grd", "source_id"],
            "vt_file":     ["hash_val", "file_nm", "file_ext", "file_sz",
                            "is_malicious", "vt_score", "source_id"],
            "vt_id":       ["id_val", "platform", "id_type", "is_active", "source_id"],
            "vt_email":    ["email_addr", "domain", "provider", "is_disposable", "source_id"],
            "vt_crypto":   ["wallet_addr", "blockchain", "exchange", "risk_score",
                            "balance", "tx_cnt", "source_id"],
            "vt_vhcl":     ["vhclno", "vhcl_model", "owner_nm", "source_id"],
            "vt_dev":      ["device_id", "dev_type", "imei", "mac_addr",
                            "model_nm", "os_nm", "source_id"],
            "vt_atm":      ["atm_id", "bank_nm", "bank_cd", "address",
                            "lat", "lng", "source_id"],
            "vt_loc":      ["loc_id", "loc_type", "address", "lat", "lng",
                            "place_nm", "sido", "sigungu", "source_id"],
            "vt_transfer": ["event_id", "dlng_sn", "dlng_amt", "dlng_dt",
                            "dlng_se_cd", "hop_level", "is_suspicious", "source_id"],
            "vt_call":     ["event_id", "call_sn", "call_strt_dt", "call_dur_sec",
                            "call_typ_cd", "source_id"],
            "vt_msg":      ["event_id", "msg_sn", "msg_type", "content",
                            "send_dt", "source_id"],
            "vt_access":   ["event_id", "lgn_sn", "lgn_dt", "lgn_ip",
                            "device_info", "success_yn", "source_id"],
            "vt_movement": ["event_id", "mov_type", "timestamp", "lat", "lng",
                            "speed", "source_id"],
            "vt_impersonation": ["event_id", "method", "fake_name", "script_type",
                                 "start_dt", "end_dt", "source_id", "verified"],
        },
        "edge_types": [
            "suspect_in", "victim_in", "witness_in", "involves",
            "filed_as", "clusters_with", "related_case",
            "has_account", "controls", "owns_phone", "owns_vehicle",
            "used_ip", "member_of", "works_at", "uses_id",
            "from_account", "to_account", "transferred_to",
            "caller", "callee", "contacted",
            "sent_msg", "received_msg",
            "recorded_in", "occurred_at",
            "belongs_to", "resolves_to", "contains_file", "sourced_from",
            "sameAs", "contradicts", "used_for", "targets",
            "eg_used_account", "eg_used_phone", "eg_used_ip",
            "uses_email", "owns_wallet", "uses_device",
            "accessed_from", "performed_by",
        ],
        "edge_directions": {
            "suspect_in":    ("vt_psn",      "vt_case"),
            "victim_in":     ("vt_psn",      "vt_case"),
            "witness_in":    ("vt_psn",      "vt_case"),
            "involves":      ("vt_case",     "vt_psn"),
            "filed_as":      ("vt_petition", "vt_case"),
            "clusters_with": ("vt_petition", "vt_petition"),
            "related_case":  ("vt_case",     "vt_case"),
            "has_account":   ("vt_psn",      "vt_bacnt"),
            "controls":      ("vt_psn",      "vt_bacnt"),
            "owns_phone":    ("vt_psn",      "vt_telno"),
            "owns_vehicle":  ("vt_psn",      "vt_vhcl"),
            "used_ip":       ("vt_psn",      "vt_ip"),
            "member_of":     ("vt_psn",      "vt_org"),
            "works_at":      ("vt_psn",      "vt_org"),
            "uses_id":       ("vt_psn",      "vt_id"),
            "uses_email":    ("vt_psn",      "vt_email"),
            "owns_wallet":   ("vt_psn",      "vt_crypto"),
            "uses_device":   ("vt_psn",      "vt_dev"),
            "from_account":  ("vt_bacnt",    "vt_transfer"),
            "to_account":    ("vt_transfer", "vt_bacnt"),
            "transferred_to":("vt_bacnt",    "vt_bacnt"),
            "caller":        ("vt_telno",    "vt_call"),
            "callee":        ("vt_call",     "vt_telno"),
            "contacted":     ("vt_telno",    "vt_telno"),
            "sent_msg":      ("vt_telno",    "vt_msg"),
            "received_msg":  ("vt_msg",      "vt_telno"),
            "recorded_in":   ("vt_vhcl",     "vt_movement"),
            "occurred_at":   ("vt_movement", "vt_loc"),
            "accessed_from": ("vt_access",   "vt_ip"),
            "performed_by":  ("vt_access",   "vt_psn"),
            "belongs_to":    ("vt_bacnt",    "vt_org"),
            "resolves_to":   ("vt_site",     "vt_ip"),
            "contains_file": ("vt_dev",      "vt_file"),
            # sourced_from: 모든 노드 타입 → vt_src (None = Any)
            # 버그수정 v3.7: ("vt_psn","vt_src") 제한 → vt_case 등 방향 교정 무작동
            "sourced_from":  (None,          "vt_src"),
            "sameAs":        ("vt_psn",      "vt_psn"),
            "contradicts":   ("vt_psn",      "vt_psn"),
            "used_for":      ("vt_telno",    "vt_impersonation"),
            "targets":       ("vt_impersonation", "vt_org"),
            "eg_used_account":("vt_petition","vt_bacnt"),
            "eg_used_phone": ("vt_petition", "vt_telno"),
            "eg_used_ip":    ("vt_petition", "vt_ip"),
            # v3.7 신규 엣지
            "belongs_to_cluster":  ("vt_petition", "pt_cluster"),
            "used_in_device":      ("vt_telno",    "vt_dev"),
            "belongs_to_campaign": ("vt_site",     "site_cluster"),
        },
    }

    _workflow_app = None

    def __init__(self):
        if LangGraphAgent._workflow_app is None:
            workflow = self._build_workflow()
            LangGraphAgent._workflow_app = workflow.compile()
        self.app = LangGraphAgent._workflow_app

    def _get_client(self):
        return AIService.get_client()

    # --- Node Implementations ---

    def router_node(self, state: AgentState) -> Dict:
        """의도 라우터: 질문의 목적에 따라 PATH, QUERY, REPORT 등으로 분기"""
        start_time = time.time()
        logger.info(f"--- ROUTER NODE: {state['question']} ---")
        
        # 스위치: use_router
        config = state.get("config", {})
        if not config.get("use_router", True):
            logger.info("[Config] Router Node OFF. Fallbacking to QUERY.")
            words = state['question'].split()
            res = {"intent": "QUERY", "keyword": words[0] if words else ""}
        else:
            res = AIService.route_question(state['question'])
            
        metrics = {**state.get("metrics", {}), "router_node": time.time() - start_time}

        # REPORT 폐지 — 라우터가 그래도 REPORT 반환 시 QUERY 로 매핑 (안전망)
        intent = res.get("intent", "QUERY")
        if intent == "REPORT":
            logger.info("▶ Router returned REPORT — 강제로 QUERY 로 매핑 (REPORT 분기 폐지됨)")
            intent = "QUERY"

        # GUARD / GENERAL — sLLM 호출 건너뛰고 즉시 차단 신호 전파
        if intent in ("GUARD", "GENERAL"):
            block_tag = "GUARD_BLOCK" if intent == "GUARD" else "GENERAL_CHAT"
            logger.info(f"▶ Router blocked: {intent} → {block_tag}")
            return {
                "intent": intent,
                "keyword": res.get("keyword", ""),
                "labels": res.get("labels", []),
                "term1": res.get("term1"),
                "term2": res.get("term2"),
                "metrics": metrics,
                "error_message": block_tag,
            }

        return {
            "intent": intent,
            "keyword": res.get("keyword"),
            "labels": res.get("labels", []),
            "term1": res.get("term1"),
            "term2": res.get("term2"),
            "metrics": metrics
        }

    def path_finding_node(self, state: AgentState) -> Dict:
        """최단 경로 탐색 노드: 특정 알고리즘(BFS 등)을 사용하여 두 노드 간 연결 고리 탐색"""
        logger.info(f"--- PATH FINDING NODE: {state['term1']} -> {state['term2']} ---")
        
        def find_id(term):
            if not term: return None
            # 1. 원본 검색
            res = GraphService.search_nodes(term, state['graph_path'])
            if res:
                for item in res:
                    if item.get('group') == 'nodes': return item['data']['id']
            
            # 2. 정규화 검색 (수식어 제거)
            clean_term = re.sub(r'(계좌|번호|인물|사람|사이트|IP|주소|전화)', '', term).strip()
            if clean_term and clean_term != term:
                res = GraphService.search_nodes(clean_term, state['graph_path'])
                if res:
                    for item in res:
                        if item.get('group') == 'nodes': return item['data']['id']
            return None

        id1 = find_id(state['term1'])
        id2 = find_id(state['term2'])

        # 둘 중 하나라도 못 찾으면 일반 QUERY 흐름으로 Fallback 유도
        if not id1 or not id2:
            logger.warning(f"Node detection failed for PATH. Falling back to QUERY flow.")
            return {
                "intent": "QUERY", # 인텐트를 변경하여 다음 시도 시 QUERY 흐름을 타게 함 (라우터 이후 분기 로직 수정 필요)
                "error_message": f"노드 식별 실패 ({state['term1']}, {state['term2']}). 일반 질의로 전환합니다."
            }

        success, elements = GraphService.find_shortest_path(id1, id2, state['graph_path'])
        
        return {
            "final_response": {
                "status": "success" if success else "no_path",
                "results": elements,
                "type": "path"
            }
        }

    def context_retrieval_node(self, state: AgentState) -> Dict:
        """Context Retrieval: Vector DB를 사용하여 질문 내 엔티티의 실제 DB 정보를 매칭"""
        start_time = time.time()
        logger.info(f"--- CONTEXT RETRIEVAL NODE ---")
        
        config = state.get("config", {})
        metrics = state.get("metrics", {})
        
        # 이미 라우터에서 추출된 키워드 사용
        keyword = state.get('keyword')
        entities = []

        if keyword and len(keyword) >= 2:
            try:
                nodes = GraphService.search_nodes(keyword, state['graph_path'])
                entities = [
                    {"label": n["data"]["label"], "props": n["data"]["props"]}
                    for n in nodes[:3]
                    if n.get("group") == "nodes"
                ]
            except Exception as e:
                logger.error(f"Entity DB Search Error: {e}")
                
        metrics = {**state.get("metrics", {}), "context_retrieval_node": time.time() - start_time}
        return {"entities": entities, "metrics": metrics}

    @staticmethod
    def _sanitize_cypher(cypher: str) -> str:
        """sLLM 출력의 공백 누락을 자동 교정하여 AgensGraph 실행 가능하게 만드는 sanitizer."""
        # SELECT*FROM → SELECT * FROM
        cypher = re.sub(r'SELECT\s*\*\s*FROM', 'SELECT * FROM', cypher, flags=re.IGNORECASE)
        # AS( → AS (
        cypher = re.sub(r'AS\(', 'AS (', cypher, flags=re.IGNORECASE)
        # Cypher 키워드 앞에 공백이 없는 경우 추가 (닫힘 괄호 뒤)
        for kw in ['MATCH', 'WHERE', 'RETURN', 'ORDER BY', 'LIMIT', 'WITH', 'OPTIONAL']:
            cypher = re.sub(rf'\)(\s*)({kw})', rf') {kw}', cypher)
            cypher = re.sub(rf'({kw})\(', rf'{kw} (', cypher)
        # 핵심: RETURN/WHERE 뒤에 변수명이 바로 붙는 경우 공백 추가
        # RETURNp,r,b → RETURN p,r,b / WHEREc->>'name' → WHERE c->>'name'
        cypher = re.sub(r'RETURN([a-z])', r'RETURN \1', cypher)
        cypher = re.sub(r'WHERE([a-z])', r'WHERE \1', cypher)
        # MATCH( → MATCH (  (이미 처리되지만 확인)
        cypher = re.sub(r'MATCH\(', 'MATCH (', cypher)
        # 중괄호 내 속성 콜론 뒤 공백 보장: {name:'x'} → { name: 'x'}
        cypher = re.sub(r'\{(\w+):', r'{ \1: ', cypher)
        # agtype,r → agtype, r (컬럼 구분 공백)
        cypher = re.sub(r'agtype,(\w)', r'agtype, \1', cypher)
        # 변수명 뒤 쉼표 공백: p,r,b → p, r, b (RETURN 절)
        cypher = re.sub(r'(\w),(\w)', r'\1, \2', cypher)
        return cypher

    @staticmethod
    def _format_schema_b(schema: dict) -> str:
        """스키마 dict를 Format B (그래프 연결 명시형)으로 변환"""
        lines = ["[노드]"]
        for label, props in schema.get("node_labels", {}).items():
            prop_str = ", ".join(props) if props else ""
            lines.append(f"  ({label} {{{prop_str}}})")

        edge_directions = schema.get("edge_directions", {})
        lines.append("\n[관계]")
        for edge in schema.get("edge_types", []):
            if edge in edge_directions:
                src, dst = edge_directions[edge]
                lines.append(f"  ({src})-[:{edge}]->({dst})")
            else:
                lines.append(f"  (?)-[:{edge}]->(?) # 방향 미확인")

        return "\n".join(lines)

    @staticmethod
    def _filter_schema_by_labels(schema: dict, predicted_labels: List[str]) -> dict:
        """라우터 예측 레이블 기준으로 스키마를 축소 — 관련 노드·엣지만 남김"""
        if not predicted_labels:
            return schema

        node_labels = schema.get("node_labels", {})
        edge_directions = schema.get("edge_directions", {})
        edge_types = schema.get("edge_types", [])

        label_set = set(predicted_labels)

        # 예측 레이블에 연결된 엣지도 포함 (src 또는 tgt 가 예측 레이블이면 상대방도 포함)
        for edge, (src, tgt) in edge_directions.items():
            if src in label_set or tgt in label_set:
                label_set.add(src)
                label_set.add(tgt)

        filtered_nodes = {k: v for k, v in node_labels.items() if k in label_set}
        filtered_edges = {k: v for k, v in edge_directions.items()
                         if v[0] in label_set and v[1] in label_set}
        filtered_edge_types = [e for e in edge_types if e in filtered_edges]

        return {
            "node_labels": filtered_nodes,
            "edge_types": filtered_edge_types,
            "edge_directions": filtered_edges,
        }

    def schema_fetching_node(self, state: AgentState) -> Dict:
        """Schema Fetching: 현재 DB에 존재하는 라벨과 엣지 목록을 실시간으로 가져옴"""
        start_time = time.time()
        logger.info(f"--- SCHEMA FETCHING NODE ---")

        config = state.get("config", {})
        predicted_labels = state.get("labels", [])

        base_schema = LangGraphAgent._POLE_SCHEMA

        if not config.get("use_dynamic_schema", True):
            logger.info("[Config] Schema Fetching Node OFF. Using POLE static fallback.")
            active_schema = base_schema
        else:
            dynamic_schema = GraphService.get_current_schema(state['graph_path'])

            # 동적 스키마가 비어있으면 POLE 정적 스키마로 fallback
            if not dynamic_schema.get("node_labels"):
                logger.warning("[Schema] Dynamic schema is empty — falling back to POLE static schema.")
                active_schema = base_schema
            else:
                active_schema = dynamic_schema

        # exact-match 라벨 보강 (recall 안전장치): router(LLM) semantic 예측이 놓친 라벨을
        # 질문 텍스트의 스키마 용어 매칭으로 결정론적 보강 (근거: arXiv 2505.05118)
        # use_keyword_augment=False 로 끄면 기존(순수 semantic) 동작 — A/B 평가용
        if config.get("use_keyword_augment", True):
            kw_labels = KICSCrimeDomainOntology.match_labels_by_keywords(
                state.get('question', ''), set(active_schema.get('node_labels', {}).keys())
            )
            if kw_labels:
                _before = set(predicted_labels)
                predicted_labels = list(dict.fromkeys(list(predicted_labels) + kw_labels))
                _added = set(predicted_labels) - _before
                if _added:
                    logger.info(f"[Schema] keyword-augmented labels: +{sorted(_added)}")

        # 라우터 예측 레이블로 스키마 축소 (관련 노드·엣지만 남김)
        if predicted_labels:
            active_schema = LangGraphAgent._filter_schema_by_labels(active_schema, predicted_labels)
            logger.info(f"[Schema] Schema filtered to labels: {predicted_labels}")

        schema_str = LangGraphAgent._format_schema_b(active_schema)

        metrics = {**state.get("metrics", {}), "schema_fetching_node": time.time() - start_time}
        return {"schema_info": schema_str, "metrics": metrics}

    @staticmethod
    def _is_data_absence_likely(cypher: str, entities) -> bool:
        """Sprint 1 — 결과 0건이 '쿼리 오류'가 아닌 '데이터 부재' 일 가능성 휴리스틱.

        다음 조건 모두 만족 시 True (reflection 생략 가능):
        - entity 컨텍스트가 없음 (특정 노드 찾는 게 아님)
        - WHERE / MATCH-MATCH (다중 패턴) / CONTAINS / 비교 연산자 등 정밀 필터 없음
        - 즉 단순 라벨 조회 (예: MATCH (n:vt_psn) RETURN n LIMIT 5)

        False positive 위험: 잘못된 단순 라벨 사용. 그러나 단순 라벨이 V4.0 SSOT 에 있다면
        reflection 으로도 못 살림 — 정말 데이터 부재.
        """
        if entities:  # 명시적 엔티티 검색은 항상 reflection
            return False
        if not cypher:
            return True  # 빈 Cypher 는 데이터 부재로 종료
        up = cypher.upper()
        risky_tokens = (' WHERE ', ' CONTAINS ', ' STARTS WITH ', ' ENDS WITH ',
                        ' MATCH (', ' OPTIONAL MATCH ', ' UNION ', '<=', '>=', '!=')
        # MATCH 가 2회 이상이면 복잡 쿼리
        if up.count(' MATCH ') >= 2 or up.count('MATCH (') >= 2:
            return False
        for tok in risky_tokens:
            if tok in up:
                return False
        return True

    @staticmethod
    def _validate_cypher_schema(cypher: str) -> tuple:
        """Cypher의 라벨/엣지가 _POLE_SCHEMA에 정의되어 있는지 사전 검증.

        Phase 3-A: AgensGraph 실행 전 화이트리스트 검사로 빠른 실패 + 명확한 reflection 피드백 유도.
        Returns (is_valid: bool, error_message: str).
        """
        schema = LangGraphAgent._POLE_SCHEMA
        valid_labels = set(schema.get('node_labels', {}).keys()) | {'pt_cluster', 'site_cluster'}
        # edge_types는 list, edge_directions는 dict — 둘 다 합쳐서 v3.7 신규 엣지까지 포괄
        valid_edges = set(schema.get('edge_types', [])) | set(schema.get('edge_directions', {}).keys())

        used_labels = set(re.findall(r'[:(](\s*[A-Za-z_][\w]*)', cypher))
        used_labels = {l.strip() for l in used_labels}
        used_labels = {l for l in used_labels if l.startswith(('vt_', 'pt_', 'site_'))}
        invalid_labels = used_labels - valid_labels

        used_edges = set(re.findall(r'\[\w*:([a-zA-Z_][\w]*)', cypher))
        used_edges = {e for e in used_edges if e and not e.startswith('*')}
        invalid_edges = used_edges - valid_edges

        if invalid_labels or invalid_edges:
            msgs = []
            if invalid_labels:
                msgs.append(f"존재하지 않는 라벨: {sorted(invalid_labels)}. 유효 라벨에서 선택하세요.")
            if invalid_edges:
                msgs.append(f"존재하지 않는 엣지: {sorted(invalid_edges)}. 유효 엣지에서 선택하세요.")
            return False, " / ".join(msgs)
        return True, ""

    @staticmethod
    def _rewrite_order_by_dot_access(cypher: str) -> str:
        """AgensGraph는 ORDER BY에서 점 액세스 표현식을 직접 못 받음.
        ORDER BY x.prop [DESC] → RETURN에 x.prop AS _ord_N alias를 추가하고 ORDER BY _ord_N으로 치환.
        이미 RETURN에 동일 식 alias가 있으면 그걸 재사용.
        """
        m = re.search(r"(\bRETURN\b\s+)(.+?)(\s+\bORDER\s+BY\b\s+)(.+?)(?=\s*(?:\bSKIP\b|\bLIMIT\b|\bUNION\b|;|$))",
                      cypher, re.IGNORECASE | re.DOTALL)
        if not m:
            return cypher
        ret_kw, ret_clause, ob_kw, ob_clause = m.groups()
        existing_aliases = {}
        for it in re.split(r",(?![^()\[\]{}]*[)\]}])", ret_clause):
            it = it.strip()
            am = re.search(r"^(.+?)\s+AS\s+([A-Za-z_][\w]*)\s*$", it, re.IGNORECASE)
            if am:
                existing_aliases[re.sub(r"\s+", "", am.group(1))] = am.group(2)
        new_ret_items = [it.strip() for it in re.split(r",(?![^()\[\]{}]*[)\]}])", ret_clause)]
        new_ob_items = []
        added = 0
        for ob_item in re.split(r",(?![^()\[\]{}]*[)\]}])", ob_clause):
            ob_item = ob_item.strip()
            dir_m = re.search(r"\s+(ASC|DESC)\s*$", ob_item, re.IGNORECASE)
            direction = ""
            expr = ob_item
            if dir_m:
                direction = " " + dir_m.group(1).upper()
                expr = ob_item[:dir_m.start()].strip()
            if re.match(r"^[A-Za-z_][\w]*\s*$", expr):
                new_ob_items.append(expr + direction)
                continue
            key = re.sub(r"\s+", "", expr)
            if key in existing_aliases:
                new_ob_items.append(existing_aliases[key] + direction)
                continue
            alias = f"_ord_{added}"
            added += 1
            new_ret_items.append(f"{expr} AS {alias}")
            existing_aliases[key] = alias
            new_ob_items.append(alias + direction)
        new_ret_clause = ", ".join(new_ret_items)
        new_ob_clause = ", ".join(new_ob_items)
        return cypher[:m.start()] + f"{ret_kw}{new_ret_clause}{ob_kw}{new_ob_clause}" + cypher[m.end():]

    @staticmethod
    def _wrap_native_cypher(native: str, graph_path: str) -> str:
        """Native Cypher (MATCH ... RETURN ...) → AgensGraph SQL Wrapper.

        RETURN 절 변수/식을 파싱해 AS (col agtype, ...) 자동 생성.
        ORDER BY 점 액세스는 RETURN alias로 자동 끌어올림 (AgensGraph 제약 우회).
        파싱 실패 시 원본 그대로 반환 (후처리에서 다시 정리됨).
        """
        if not native or not native.strip():
            return native
        s = native.strip().rstrip(";").strip()
        if re.match(r"^\s*SELECT\s", s, re.IGNORECASE):
            return s + ";"
        s = LangGraphAgent._rewrite_order_by_dot_access(s)
        m = re.search(r"\bRETURN\b\s+(.+?)(?:\s+\b(ORDER|LIMIT|SKIP|UNION)\b|$)", s, re.IGNORECASE | re.DOTALL)
        if not m:
            return s + ";"
        return_clause = m.group(1).strip()
        items = [it.strip() for it in re.split(r",(?![^()\[\]{}]*[)\]}])", return_clause)]
        cols = []
        for idx, item in enumerate(items):
            alias_m = re.search(r"\bAS\s+([A-Za-z_][\w]*)\s*$", item, re.IGNORECASE)
            if alias_m:
                cols.append(alias_m.group(1))
                continue
            ident_m = re.match(r"^([A-Za-z_][\w]*)\s*$", item)
            if ident_m:
                cols.append(ident_m.group(1))
                continue
            cols.append(f"col{idx}")
        as_clause = ", ".join(f"{c} agtype" for c in cols)
        safe_graph = graph_path.replace("'", "''")
        return f"SELECT * FROM cypher('{safe_graph}', $$ {s} $$) AS ({as_clause});"

    def synthesis_node(self, state: AgentState) -> Dict:
        """Query Synthesis: 수집된 컨텍스트와 스키마를 바탕으로 LLM이 Cypher 쿼리 작성"""
        start_time = time.time()
        logger.info(f"--- SYNTHESIS NODE (Attempt: {state['error_count'] + 1}) ---")

        # GENERAL / GUARD 의도는 sLLM 호출 자체를 건너뛰고 즉시 차단
        # (학습 모델은 잡담/쓰기 거절 룰이 없어 Cypher를 강제로 출력함)
        if state.get('intent') == 'GUARD':
            logger.info("[Router] GUARD 의도 — synthesis 건너뜀 (쓰기/인젝션 차단)")
            return {
                "cypher_query": "",
                "error_message": "GUARD_BLOCK",
                "reflection_log": state['reflection_log'] + ["쓰기 명령 또는 프롬프트 인젝션으로 분류되어 차단"],
                "metrics": {**state.get("metrics", {}), "synthesis_node_skipped_guard": time.time() - start_time},
            }
        if state.get('intent') == 'GENERAL':
            logger.info("[Router] GENERAL 의도 — synthesis 건너뜀")
            return {
                "cypher_query": "",
                "error_message": "GENERAL_CHAT",
                "reflection_log": state['reflection_log'] + ["수사 무관 질문으로 분류되어 Cypher 생성을 건너뜀"],
                "metrics": {**state.get("metrics", {}), "synthesis_node_skipped_general": time.time() - start_time},
            }

        client = self._get_client()
        use_sllm = bool(current_app.config.get('SLLM_ENDPOINT')) and bool(T2C_V37_SYSTEM_PROMPT)

        # 성찰 로그
        reflection_context = ""
        if state['reflection_log']:
            reflection_context = "\n[이전 실패 피드백]\n" + "\n".join(state['reflection_log'][-1:])

        # 엔티티 정보
        entity_context = ""
        if state['entities']:
            entity_context = "\n[참고 엔티티]\n"
            for e in state['entities'][:3]:
                entity_context += f"- {e.get('label')}: {e.get('props')}\n"

        prompt = f"""당신은 AgensGraph Cypher 쿼리 생성 AI입니다. SQL-Wrapped Cypher만 출력하세요.

[출력 형식]
SELECT * FROM cypher('{state['graph_path']}', $$ MATCH ... RETURN ... $$) AS (컬럼 agtype, ...);

[스키마]
{state['schema_info']}

[속성 접근]
- WHERE 조건: n->>'prop' = '값'
- 금액/시간은 문자열: WHERE t->>'dlng_amt' = '500000'

[엣지 방향 규칙]
- 피의자/피해자/참고인 → suspect_in/victim_in/witness_in: (vt_psn)-[:rel]->(vt_case)
- 구형 호환: (vt_case)-[:involves]->(vt_psn)
- 계좌소유: (vt_psn)-[:has_account]->(vt_bacnt)
- 이체: (vt_bacnt)-[:from_account]->(vt_transfer)-[:to_account]->(vt_bacnt)
- 통화: (vt_telno)-[:caller]->(vt_call)-[:callee]->(vt_telno)
- 사칭: (vt_telno)-[:used_for]->(vt_impersonation)-[:targets]->(vt_org)  [V3.3]
- 진정서→사건: (vt_petition)-[:filed_as]->(vt_case)
- 계좌귀속: (vt_bacnt)-[:belongs_to]->(vt_org)
- 위치: (vt_movement)-[:occurred_at]->(vt_loc)

{entity_context}
{reflection_context}

[예제]
Q: "피해자1의 계좌"
A: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn {{name: '피해자1'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);

Q: "계좌 '110-3333-3333'에서 나간 이체"
A: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (b:vt_bacnt {{account_no: '110-3333-3333'}})-[r:from_account]->(t:vt_transfer) RETURN b, r, t $$) AS (b agtype, r agtype, t agtype);

Q: "CASE-2023-001 사건의 피의자"
A: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn)-[r:suspect_in]->(c:vt_case {{flnm: 'CASE-2023-001'}}) RETURN p, r, c $$) AS (p agtype, r agtype, c agtype);

Q: "국민은행 사칭 전화번호"
A: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (t:vt_telno)-[r1:used_for]->(imp:vt_impersonation)-[r2:targets]->(o:vt_org {{org_name: '국민은행'}}) RETURN t, r1, imp, r2, o $$) AS (t agtype, r1 agtype, imp agtype, r2 agtype, o agtype);

Q: "피의자1 소속 조직"
A: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn {{name: '피의자1'}})-[r:member_of]->(o:vt_org) RETURN p, r, o $$) AS (p agtype, r agtype, o agtype);

Q: "CASE-99 사건 연루 인물"
A: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (c:vt_case {{flnm: 'CASE-99'}})-[r:involves]->(p:vt_psn) RETURN c, r, p $$) AS (c agtype, r agtype, p agtype);

[PATH 인텐트 — 두 개체 간 연결 경로 탐색]
PATH 질문인 경우 shortestPath 패턴 사용:
MATCH p=shortestPath((a:LabelA {{key: 'val1'}})-[*..6]-(b:LabelB {{key: 'val2'}})) RETURN p
AS (p agtype);

[규칙]
1. 스키마에 있는 레이블·속성만 사용. 2. 반드시 SQL Wrapper 구조 출력.
3. 모든 컬럼은 agtype. 4. 수사 무관 질문이면 GENERAL: 답변 출력.
5. DELETE/SET/MERGE 등 쓰기 명령 절대 금지.
6. RETURN 절 변수 수와 AS(컬럼 agtype, ...) 수가 반드시 일치해야 함.

[질문]
{state['question']}"""

        try:
            sllm_failed = False
            if use_sllm:
                # Phase 2-A: 학습된 system prompt + 동적 schema chunk + 자연어
                # schema_fetching_node가 채운 state['schema_info']에는 질의 관련 라벨/엣지만 포함됨
                schema_chunk = state.get('schema_info', '').strip()
                schema_section = f"\n[관련 스키마]\n{schema_chunk}\n" if schema_chunk else ""
                user_msg = f"{schema_section}[질문]\n{state['question']}{entity_context}{reflection_context}"
                try:
                    resp = client.chat.completions.create(
                        model=current_app.config.get('SLLM_MODEL_NAME', 'qwen25_t2c_v37_v2'),
                        messages=[
                            {"role": "system", "content": T2C_V37_SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        temperature=0,
                        max_tokens=512,
                        timeout=15,
                    )
                except Exception as sllm_err:
                    logger.warning(f"[sLLM Fallback] sLLM 호출 실패 → OpenAI GPT로 폴백: {sllm_err}")
                    sllm_failed = True
                    openai_key = current_app.config.get('OPENAI_API_KEY')
                    if not openai_key:
                        raise
                    from openai import OpenAI as _OpenAI
                    fb_client = _OpenAI(api_key=openai_key)
                    resp = fb_client.chat.completions.create(
                        model='gpt-4o',
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                    )
            else:
                resp = client.chat.completions.create(
                    model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0
                )
            cypher = resp.choices[0].message.content.strip()
            # 마크다운 제거
            cypher = re.sub(r'```[a-zA-Z]*\n?', '', cypher).replace('```', '').strip()

            # sLLM은 Native Cypher만 출력하도록 학습됨 → SQL Wrapper로 변환
            # (폴백 시 GPT-4o가 prompt 기반으로 SQL Wrapped를 생성하므로 wrap 불필요)
            if use_sllm and not sllm_failed:
                cypher = LangGraphAgent._wrap_native_cypher(cypher, state['graph_path'])
            
            # --- 0. Cypher Sanitizer (sLLM 공백 누락 자동 교정) ---
            cypher = LangGraphAgent._sanitize_cypher(cypher)
            
            # --- 1. 범용 지식 방어 (General Chat Guardrail) ---
            if cypher.startswith("GENERAL:"):
                return {
                    "cypher_query": "", 
                    "error_message": "GENERAL_CHAT", 
                    "reflection_log": state['reflection_log'] + [cypher.replace("GENERAL:", "").strip()]
                }
            
            # --- 2. 쿼리 보안 방어 (Security Guardrail) ---
            upper_cypher = cypher.upper()
            forbidden_keywords = ["DELETE", "SET", "REMOVE", "MERGE", "DROP", "CREATE", "DETACH"]
            for keyword in forbidden_keywords:
                # 간단한 단어 매칭으로 치명적 쓰기 작업 탐지
                if re.search(r'\b' + keyword + r'\b', upper_cypher):
                    return {
                        "cypher_query": cypher,
                        "error_message": f"보안 정책 위반: 데이터 변경 명령어({keyword})가 감지되어 차단되었습니다."
                    }

            # --- 2b. Phase 3-A: Schema 사전 검증 (라벨/엣지 화이트리스트) ---
            #   AgensGraph 실행 전 무효 라벨/엣지를 잡아 reflection 피드백 유도.
            if state['error_count'] < 1:  # 첫 시도에서만 강제 — 무한 루프 방지
                is_valid, validation_err = LangGraphAgent._validate_cypher_schema(cypher)
                if not is_valid:
                    logger.warning(f"[Schema Validation] {validation_err}")
                    return {
                        "cypher_query": cypher,
                        "error_message": f"SCHEMA_VALIDATION_FAILED: {validation_err}",
                        "reflection_log": state['reflection_log'] + [validation_err],
                    }


            # SQL Wrapper (SELECT) 또는 Cypher (MATCH) 시작 지점 찾기
            select_idx = upper_cypher.find("SELECT")
            match_idx = upper_cypher.find("MATCH")
            
            if select_idx != -1:
                cypher = cypher[select_idx:]
            elif match_idx != -1:
                cypher = cypher[match_idx:]
                
            # 마지막 세미콜론(;) 이후의 사족 제거
            if ";" in cypher:
                cypher = cypher.split(";")[0] + ";"
                
            config = state.get("config", {})
            if config.get("use_relation_fix", True):
                original_cypher = cypher
                cypher = AIService._fix_relation_direction(cypher)
                if cypher != original_cypher:
                    logger.info("[Config] Synthesis relation auto-fix applied.")
                    
            metrics = {**state.get("metrics", {}), f"synthesis_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
                
            return {"cypher_query": cypher, "error_message": None, "metrics": metrics}
        except Exception as e:
            metrics = {**state.get("metrics", {}), f"synthesis_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
            return {"error_message": str(e), "metrics": metrics}

    def execution_node(self, state: AgentState) -> Dict:
        """Execution: 생성된 Cypher 쿼리를 실제 DB에서 실행"""
        start_time = time.time()
        logger.info(f"--- EXECUTION NODE ---")
        
        metrics = state.get("metrics", {})
        
        if not state['cypher_query']:
            metrics = {**metrics, f"execution_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
            if state.get("error_message") == "GENERAL_CHAT":
                return {"metrics": metrics} # 에러 유지
            return {"error_message": "생성된 쿼리가 없습니다.", "metrics": metrics}
            
        # 보안(Guardrail) 에러인 경우 실행하지 않고 통과
        if state.get("error_message") and "보안 정책 위반" in state.get("error_message", ""):
            logger.warning(f"Blocked Execution: {state['error_message']}")
            return {}

        # Phase 3-A: Schema 검증 실패 시 실행 건너뛰고 reflection 유도
        if state.get("error_message", "").startswith("SCHEMA_VALIDATION_FAILED"):
            logger.warning(f"Skipping execution due to schema validation failure")
            metrics = {**metrics, f"execution_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
            return {"execution_result": [], "metrics": metrics}

        # GraphService.execute_cypher 재사용 (Cytoscape 포맷 파싱 포함)
        success, result = GraphService.execute_cypher(state['cypher_query'], state['graph_path'])

        if success:
            # [개선] 결과가 0건일 때 -> 성찰 유도 (Phase 3-B: 엔티티 없어도 첫 시도면 재시도)
            # Sprint 1 — 단순 SELECT (WHERE 절 없음 + entity 컨텍스트 없음) 0건은
            # 진짜 데이터 부재로 판정해 reflection 건너뜀 (-3초)
            if not result and state['error_count'] < 1:
                if self._is_data_absence_likely(state.get('cypher_query', ''),
                                                state.get('entities')):
                    logger.info("▶ 결과 0건 + 단순 쿼리 + entity 없음 → 데이터 부재로 판정 (reflection skip)")
                    return {
                        "execution_result": [],
                        "error_message": None,  # 에러 아님 — 종료
                        "metrics": metrics,
                    }
                if state.get('entities'):
                    target_name = state['entities'][0]['props'].get('name', '엔티티')
                    err_msg = (f"QUERY_ZERO_RESULTS: 엔티티 '{target_name}'가 DB에 존재함에도 결과가 없습니다. "
                               f"관계 방향(A->B)이나 레이블(label)이 틀렸을 가능성이 높습니다.")
                else:
                    err_msg = ("QUERY_ZERO_RESULTS: 결과가 0건입니다. 관계 방향(예: suspect_in은 psn→case), "
                               "라벨 명칭, 속성 키(예: account_no vs actno)를 검토하세요.")
                logger.info(f"▶ 결과가 0건 -> 성찰 루프 진입")
                return {
                    "execution_result": [],
                    "error_message": err_msg,
                    "error_count": state["error_count"] + 0.5,
                }
            
            metrics = {**metrics, f"execution_node_attempt_{state['error_count'] + 0.5}": time.time() - start_time}
            return {
                "execution_result": result, # elements list
                "error_message": None,
                "metrics": metrics
            }
        else:
            logger.warning(f"Query Execution Failed: {result}")
            metrics = {**metrics, f"execution_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
            return {"error_message": str(result), "metrics": metrics}

    def reflection_node(self, state: AgentState) -> Dict:
        """Reflection: 실행 에러 발생 시 원인을 분석하고 다음 시도를 위한 피드백 생성.

        주의: 학습된 t2c 모델은 자연어 피드백 생성 능력이 없으므로,
        SLLM_ENDPOINT 사용 중이라도 reflection은 항상 OpenAI GPT를 사용.
        """
        start_time = time.time()
        logger.info(f"--- REFLECTION NODE ---")

        openai_api_key = current_app.config.get('OPENAI_API_KEY')
        if openai_api_key:
            from openai import OpenAI as _OpenAI
            client = _OpenAI(api_key=openai_api_key)
            reflection_model = 'gpt-4o-mini'
        else:
            client = self._get_client()
            reflection_model = current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o-mini')
        error_msg = state['error_message']
        last_query = state['cypher_query']
        
        schema_ctx = state.get("schema_info", "")
        schema_section = f"\n[현재 그래프 스키마]\n{schema_ctx}\n" if schema_ctx else ""

        prompt = f"""당신은 수사관 AI를 돕는 시니어 데이터 엔지니어입니다. 다음 쿼리 실행 중 문제가 발생했습니다.

[잘못된 쿼리]
{last_query}

[에러/문제 상황]
{error_msg}
{schema_section}
[수정 지시사항]
1. 쿼리 문법 에러라면 문법을 고치세요 (AS 절 컬럼 수 = RETURN 변수 수 확인).
2. 결과가 0건(QUERY_ZERO_RESULTS)이라면:
   - 관계 방향 (A)-[:rel]->(B) 이 반대인지 확인 (스키마의 방향 참조)
   - 잘못된 관계 레이블을 썼는지 확인
   - 속성값 표기가 틀렸는지 확인 (예: n->>'prop' = '값' 형식)
3. 다음 시도에서 반드시 고쳐야 할 짧고 명확한 지시사항 1가지만 작성하세요.

[분석 결과 및 지시사항]"""
        
        try:
            resp = client.chat.completions.create(
                model=reflection_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            feedback = resp.choices[0].message.content.strip()
            
            
            new_log = state['reflection_log'] + [feedback]
            metrics = {**state.get("metrics", {}), f"reflection_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
            return {
                "reflection_log": new_log,
                "error_count": state['error_count'] + 1,
                "error_message": None, # 루프 재진입을 위해 초기화
                "metrics": metrics
            }
        except Exception as e:
            metrics = {**state.get("metrics", {}), f"reflection_node_attempt_{state['error_count'] + 1}": time.time() - start_time}
            return {"error_count": state['error_count'] + 1, "metrics": metrics}

    def data_view_node(self, state: AgentState) -> Dict:
        """Data View: 실행 결과를 사용자에게 보여줄 최종 포맷(JSON/Summary)으로 가공"""
        start_time = time.time()
        logger.info(f"--- DATA VIEW NODE ---")

        # PATH 노드가 이미 final_response를 완성한 경우 그대로 반환
        if state.get("final_response") and state["intent"] == "PATH":
            return {}

        # 쿼리가 성공했으면 그 결과를 정규화하여 반환
        if state['intent'] == "REPORT":
            # REPORT 인텐트의 경우 설명과 요소를 반환
            report, elements = GraphService.rag_query(state['question'], state['graph_path'])
            return {"final_response": {
                "status": "success", 
                "explanation": report, 
                "elements": elements, 
                "type": "report",
                "intent": "REPORT"
            }}
        
        # GUARD: 쓰기 명령 / 프롬프트 인젝션 차단
        if state.get("error_message") == "GUARD_BLOCK":
            return {
                "final_response": {
                    "status": "blocked",
                    "cypher": "",
                    "elements": [],
                    "results_count": 0,
                    "type": "guard",
                    "intent": "GUARD",
                    "message": "죄송합니다. 쓰기/수정/삭제 명령은 실행할 수 없습니다. 이 시스템은 수사 관련 조회만 답변 가능합니다.",
                    "error": "쓰기 명령은 실행할 수 없습니다. 수사 관련 질문만 답변 가능합니다."
                }
            }

        # 일반 QUERY 결과 반환 전 가드레일 예외 처리
        if state.get("error_message") == "GENERAL_CHAT":
            return {
                "final_response": {
                    "status": "success",
                    "cypher": "일반 대화 응답",
                    "elements": [],
                    "results_count": 0,
                    "type": "general",
                    "intent": "GENERAL",
                    "message": "죄송합니다. 수사 관련 질문만 답변 가능합니다.",
                    "error": "수사 관련 질문만 답변 가능합니다. " + (state['reflection_log'][-1] if state.get('reflection_log') else "")
                }
            }

        if state.get("error_message") and "보안 정책 위반" in state["error_message"]:
             return {
                "final_response": {
                    "status": "error",
                    "cypher": state.get('cypher_query', ''),
                    "elements": [],
                    "results_count": 0,
                    "type": "guardrail",
                    "intent": "QUERY",
                    "message": "죄송합니다. 보안 정책상 실행할 수 없습니다.",
                    "error": state["error_message"]
                }
             }

        metrics = {**state.get("metrics", {}), "data_view_node": time.time() - start_time}

        raw_elements = state['execution_result'] if state['execution_result'] else []
        enriched_elements = _enrich_elements_bridge_key(raw_elements)
        result_status = "success" if not state.get("error_message") else "partial_success"

        # 0건 결과 시 유사 노드 힌트 검색
        hints = []
        if not raw_elements and state.get("keyword"):
            try:
                hint_els = GraphService.search_nodes(state["keyword"], state["graph_path"])
                # 노드만 최대 5개 힌트로 반환
                for el in hint_els:
                    if isinstance(el, dict) and el.get("group") == "nodes":
                        d = el.get("data", {})
                        p = d.get("props", {})
                        name_val = (p.get("name") or p.get("korn_flnm") or p.get("org_name")
                                    or p.get("account_no") or p.get("telno")
                                    or p.get("flnm") or d.get("id", ""))
                        hints.append({
                            "id": d.get("id"),
                            "label": d.get("label"),
                            "name": str(name_val)[:60],
                            "props": {k: v for k, v in list(p.items())[:4]}
                        })
                    if len(hints) >= 5:
                        break
            except Exception as _he:
                logger.debug(f"Hint search skip: {_he}")

        # 감사 로그 기록 (실패 시 무시)
        try:
            self._write_audit_log(
                action_cd="QUERY",
                graph_path=state.get("graph_path"),
                cypher_cn=state.get("cypher_query"),
                input_cn=state.get("question"),
                result_status=result_status,
                result_cnt=len(raw_elements),
                exec_ms=int(sum(metrics.values()) * 1000)
            )
        except Exception as _ae:
            logger.debug(f"Audit log skip: {_ae}")

        # 일반 QUERY 결과 정상 반환
        return {
            "final_response": {
                "status": result_status,
                "cypher": state['cypher_query'],
                "elements": enriched_elements,
                "results_count": len(raw_elements),
                "hints": hints,
                "type": "query",
                "intent": state['intent'],
                "error": state.get("error_message"),
                "metrics": metrics,
                "config": state.get("config", {})
            },
            "metrics": metrics
        }

    # --- Router Logics ---

    def _route_after_router(self, state: AgentState):
        """Router 노드 이후의 분기 결정"""
        intent = state["intent"]
        if intent == "REPORT":
            return "data_view"
        elif intent == "PATH":
            return "path_finding"
        else:
            return "context_retrieval"

    def _route_after_execution(self, state: AgentState):
        """Execution 노드 이후의 분기 결정 (성공 시 종료, 실패 시 성찰 루프)"""
        config = state.get("config", {})
        use_reflection = config.get("use_reflection", True)
        max_retries = config.get("max_retries", 1)
        
        if state.get("error_message"):
            if state["error_message"] == "GENERAL_CHAT" or "보안 정책 위반" in state["error_message"]:
                return "data_view" # 가드레일 위반 및 일반 대화는 즉시 종료
                
            if use_reflection and state["error_count"] < (max_retries + 1): 
                return "reflection"
            else:
                return "data_view" # 실패한 채로 종료
        return "data_view"

    def _route_after_path(self, state: AgentState):
        """Path Finding 노드 이후의 분기 결정 (실패 시 QUERY로 전환 여부)"""
        if state["intent"] == "QUERY":
            return "context_retrieval"
        return "end"

    # --- Build Workflow ---

    def _build_workflow(self):
        workflow = StateGraph(AgentState)

        # 노드 등록
        workflow.add_node("router", self.router_node)
        workflow.add_node("path_finding", self.path_finding_node)
        workflow.add_node("context_retrieval", self.context_retrieval_node)
        workflow.add_node("schema_fetching", self.schema_fetching_node)
        workflow.add_node("synthesis", self.synthesis_node)
        workflow.add_node("execution", self.execution_node)
        workflow.add_node("reflection", self.reflection_node)
        workflow.add_node("data_view", self.data_view_node)

        # 엣지 연결
        workflow.add_edge(START, "router")

        # Router 분기
        workflow.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "data_view": "data_view",
                "path_finding": "path_finding",
                "context_retrieval": "context_retrieval",
            }
        )

        # PATH flow: 성공 시 data_view, 실패 시 context_retrieval(QUERY fallback)
        workflow.add_conditional_edges(
            "path_finding",
            self._route_after_path,
            {
                "end": "data_view",
                "context_retrieval": "context_retrieval",
            }
        )

        # Query Flow
        workflow.add_edge("context_retrieval", "schema_fetching")
        workflow.add_edge("schema_fetching", "synthesis")
        workflow.add_edge("synthesis", "execution")

        # Execution 분기 (Reflection 루프)
        workflow.add_conditional_edges(
            "execution",
            self._route_after_execution,
            {
                "reflection": "reflection",
                "data_view": "data_view"
            }
        )

        workflow.add_edge("reflection", "synthesis")  # 루프: 성찰 후 재합성

        workflow.add_edge("data_view", END)

        return workflow

    @staticmethod
    def _write_audit_log(action_cd: str, graph_path: str = None, cypher_cn: str = None,
                         input_cn: str = None, result_status: str = None,
                         result_cnt: int = None, exec_ms: int = None,
                         session_id: str = None):
        """TB_AUDIT_LOG 에 감사 이력 기록 (실패 시 조용히 무시)"""
        try:
            from app.services.rdb_to_graph_service import RdbToGraphService
            conn, cur = RdbToGraphService.get_db_connection()
            if not conn:
                return
            cur.execute("""
                INSERT INTO TB_AUDIT_LOG
                    (SESSION_ID, ACTION_CD, GRAPH_PATH, CYPHER_CN,
                     INPUT_CN, RESULT_STATUS, RESULT_CNT, EXEC_MS)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (session_id, action_cd, graph_path,
                  (cypher_cn or "")[:2000],
                  (input_cn or "")[:500],
                  result_status, result_cnt, exec_ms))
            conn.commit()   # ← 누락 시 커넥션 종료로 롤백되어 감사 이력이 남지 않음
            cur.close()
            conn.close()
        except Exception:
            pass

    def run(self, question: str, graph_path: str = "tccop_graph_v6", config: Dict[str, Any] = None) -> Dict:
        """에이전트 실행"""
        # 기본 Config 설정
        if config is None:
            config = {
                "use_router": True,             # Router 노드 (의도 파악/키워드 추출)
                "use_dynamic_schema": True,     # Schema Fetching (동적 스키마 로딩)
                "use_relation_fix": True,       # Synthesis 단계 내 관계 방향 자동 교정
                "use_reflection": True,         # 실행 에러 시 Reflection 루프 사용 여부
                "max_retries": 2                # 최대 시도 횟수
            }
            
        initial_state: AgentState = {
            "question": question,
            "graph_path": graph_path,
            "intent": "QUERY",
            "keyword": None,
            "labels": [],
            "term1": None,
            "term2": None,
            "entities": [],
            "schema_info": "",
            "cypher_query": "",
            "execution_result": None,
            "error_message": None,
            "error_count": 0,
            "reflection_log": [],
            "final_response": None,
            "config": config,
            "metrics": {}
        }
        
        result = self.app.invoke(initial_state)
        return result.get("final_response", {"status": "error", "message": "에이전트 응답 생성 실패"})


class InvestigationSession:
    """수사 세션 — LangGraphAgent.run()을 래핑하여 엔티티 컨텍스트를 대화 간 유지.

    Usage:
        session = InvestigationSession(graph_path="tccop_demo")
        result = session.ask("홍길동과 연결된 계좌 보여줘")
        result2 = session.ask("그 계좌의 이체 내역 추적해줘")  # entity_context 누적
    """

    def __init__(self, graph_path: str = "tccop_graph_v6", case_no: str = None, config: Dict[str, Any] = None):
        self.graph_path = graph_path
        self.case_no = case_no
        self.config = config
        self.entity_context: List[Dict[str, Any]] = []  # 누적 엔티티 (노드 props)
        self._agent = LangGraphAgent()

    def ask(self, question: str) -> Dict:
        """질문을 실행하고 결과 엔티티를 컨텍스트에 누적한다."""
        # 이전 세션의 엔티티를 initial_state entities로 주입
        # run()은 entities를 지원하지 않으므로 여기서 초기 상태를 수동 구성
        config = self.config or {}
        if not config:
            config = {
                "use_router": True,
                "use_dynamic_schema": True,
                "use_relation_fix": True,
                "use_reflection": True,
                "max_retries": 2
            }

        initial_state: AgentState = {
            "question": question,
            "graph_path": self.graph_path,
            "intent": "QUERY",
            "keyword": None,
            "labels": [],
            "term1": None,
            "term2": None,
            "entities": list(self.entity_context),  # 이전 세션 엔티티 주입
            "schema_info": "",
            "cypher_query": "",
            "execution_result": None,
            "error_message": None,
            "error_count": 0,
            "reflection_log": [],
            "final_response": None,
            "config": config,
            "metrics": {}
        }

        result_state = self._agent.app.invoke(initial_state)
        final = result_state.get("final_response", {"status": "error", "message": "에이전트 응답 생성 실패"})

        # 새 결과 엔티티를 누적 컨텍스트에 추가 (중복 제거)
        new_elements = final.get("elements", []) if isinstance(final, dict) else []
        seen_ids = {e.get("id") for e in self.entity_context}
        for el in new_elements:
            if isinstance(el, dict) and el.get("group") == "nodes":
                data = el.get("data", {})
                node_id = data.get("id")
                if node_id and node_id not in seen_ids:
                    self.entity_context.append({
                        "id": node_id,
                        "label": data.get("label", ""),
                        "props": data.get("props", {})
                    })
                    seen_ids.add(node_id)

        # 최근 50개 엔티티만 유지 (컨텍스트 크기 제한)
        if len(self.entity_context) > 50:
            self.entity_context = self.entity_context[-50:]

        return final

    def reset(self):
        """엔티티 컨텍스트 초기화"""
        self.entity_context = []

    def snapshot(self) -> Dict:
        """현재 세션 상태 스냅샷 (TB_INVEST_SESSION.ENTITY_CTX 저장용)"""
        return {
            "graph_path": self.graph_path,
            "case_no": self.case_no,
            "entity_context": self.entity_context
        }
