import re
import json
from typing import List, Dict, Any, Optional
import psycopg2
import psycopg2.extras
from config import Config
from app.database import safe_set_graph_path, validate_graph_path
import logging


logger = logging.getLogger(__name__)

class CypherExecutionError(Exception):
    """Cypher 쿼리 실행 오류"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class CypherService:
    """
    Apache AGE (PostgreSQL Graph Extension) 전용 쿼리 실행기
    - 역할: 표준 Cypher를 AGE SQL로 래핑하고 결과를 표준 JSON으로 변환
    
    Usage:
        service = CypherService()
        results = service.execute("MATCH (n) RETURN n LIMIT 10", "my_graph")
    """
    def __init__(self, db_config: Optional[Dict] = None):
        """
        Args:
            db_config: DB 연결 설정 (None이면 Config에서 가져옴)
        """
        self.db_config = db_config or Config.DB_CONFIG

    def _extract_return_columns(self, query: str) -> List[str]:
        """
        RETURN 절에서 컬럼명 추출 (중복 파싱 제거용 공통 메서드)
        "RETURN p, r, b" -> ["p", "r", "b"]
        "RETURN p AS person" -> ["person"]
        """
        return_pattern = re.compile(
            r"RETURN\s+(.*?)(?:\s+(?:LIMIT|ORDER\s+BY|SKIP)\s+.*)?$",
            re.IGNORECASE | re.DOTALL
        )
        match = return_pattern.search(query)
        if not match:
            raise ValueError("CCOP 조회 쿼리에는 반드시 RETURN 절이 필요합니다.")

        columns = []
        for item in match.group(1).split(','):
            clean_item = item.strip()
            if " AS " in clean_item.upper():
                alias = clean_item.split(" AS ")[-1].strip()
                columns.append(alias.lower())
            else:
                columns.append(clean_item.lower())
        return columns

    def _parse_agensgraph_value(self, value: str) -> Dict[str, Any]:
        """
        AgensGraph 결과 문자열 파싱
        형식 1 (노드): vt_psn[4.11]{"id": "suspect_1", "name": "홍길동"}
        형식 2 (엣지): owns_phone[8.1][4.11,6.1]{"rec_created": "..."}
        형식 3 (스칼라): "문자열" 또는 숫자
        """
        if not isinstance(value, str):
            return value

        # 노드 패턴: label[graphid]{props}
        node_match = re.match(r'^(\w+)\[(\d+\.\d+)\](\{.*\})$', value, re.DOTALL)
        if node_match:
            label, gid, props_str = node_match.groups()
            try:
                props = json.loads(props_str)
            except Exception:
                props = {}
            return {"id": gid, "label": label, "properties": props}

        # 엣지 패턴: label[graphid][start_id,end_id]{props}
        edge_match = re.match(r'^(\w+)\[(\d+\.\d+)\]\[(\d+\.\d+),(\d+\.\d+)\](\{.*\})$', value, re.DOTALL)
        if edge_match:
            label, gid, start_id, end_id, props_str = edge_match.groups()
            try:
                props = json.loads(props_str)
            except Exception:
                props = {}
            return {"id": gid, "label": label, "start": start_id, "end": end_id, "properties": props}

        # 스칼라 JSON 시도
        try:
            return json.loads(value)
        except Exception:
            return value

    def _format_age_result(self, row: tuple, columns: List[str]) -> Dict[str, Any]:
        """
        AgensGraph Cypher 결과를 프론트엔드용 표준 JSON으로 변환
        """
        formatted = {}
        for idx, value in enumerate(row):
            key = columns[idx] if idx < len(columns) else f"col_{idx}"
            if value is None:
                formatted[key] = None
            elif isinstance(value, str):
                formatted[key] = self._parse_agensgraph_value(value)
            else:
                formatted[key] = value
        return formatted

    def _get_connection(self):
        """DB 연결 획득"""
        conn = psycopg2.connect(**self.db_config)
        conn.autocommit = True
        return conn

    def execute(self, query: str, graph_path: str) -> List[Dict[str, Any]]:
        """
        [Public API] 외부에서 호출하는 실행 메서드
        
        Args:
            query: Cypher 쿼리 문자열
            graph_path: 그래프 경로명
            
        Returns:
            결과 리스트 (각 행은 Dict)
            
        Raises:
            CypherExecutionError: 쿼리 실행 실패 시
        """
        conn = None
        try:
            # AgensGraph 네이티브 방식: SET graph_path 후 Cypher 직접 실행
            conn = self._get_connection()
            cur = conn.cursor()

            # 그래프 경로 설정
            safe_set_graph_path(cur, graph_path)
            logger.info("[QUERY] graph=%s | %s", graph_path, " ".join(str(query).split()))
            cur.execute(query)

            rows = cur.fetchall()

            # 결과 변환
            columns = self._extract_return_columns(query)
            return [self._format_age_result(row, columns) for row in rows]
            
        except ValueError as e:
            # RETURN 절 누락 등 검증 오류
            raise e
        except Exception as e:
            logger.error(f"[Cypher Error] {str(e)}\nQuery: {query}")
            raise CypherExecutionError(
                message=f"Graph Query Execution Failed: {str(e)}",
                status_code=500
            )
        finally:
            if conn:
                conn.close()