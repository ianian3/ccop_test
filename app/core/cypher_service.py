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

    def _wrap_age_sql(self, query: str, graph_path: str) -> str:
        """
        [핵심 로직] Standard Cypher -> Apache AGE SQL 변환
        Example:
            Input:  MATCH (n) RETURN n
            Output: SELECT * FROM cypher('graph', $$ MATCH (n) RETURN n $$) as (n agtype)
        """
        # 1. RETURN 절 파싱 (정규식으로 반환 변수 추출)
        # LIMIT, ORDER BY, SKIP 등 후속 절 제외
        return_pattern = re.compile(
            r"RETURN\s+(.*?)(?:\s+(?:LIMIT|ORDER\s+BY|SKIP)\s+.*)?$", 
            re.IGNORECASE | re.DOTALL
        )
        match = return_pattern.search(query)
        
        if not match:
            # 조회용이 아닌 경우(CREATE 등) 처리 (여기선 예외 처리)
            # AI가 조회만 하도록 유도하거나, 필요 시 로직 추가
            raise ValueError("CCOP 조회 쿼리에는 반드시 RETURN 절이 필요합니다.")

        raw_items = match.group(1).split(',')
        
        # 2. agtype 캐스팅 구문 생성
        cast_items = []
        for item in raw_items:
            clean_item = item.strip()
            # AS 별칭이 있는 경우: "e AS edge" -> "edge agtype"
            if " AS " in clean_item.upper():
                alias = clean_item.upper().split(" AS ")[-1].strip()
                cast_items.append(f"{alias} agtype")
            else:
                # 단순 변수명인 경우
                cast_items.append(f"{clean_item} agtype")
        
        columns_def = ", ".join(cast_items)
        
        # 3. 최종 SQL 조립
        # 주의: f-string 사용 시 graph_path 검증 필수 (SQL Injection 방지)
        wrapped_sql = f"SELECT * FROM cypher('{graph_path}', $$ {query} $$) as ({columns_def})"
        return wrapped_sql

    def _format_age_result(self, row: tuple, columns: List[str]) -> Dict[str, Any]:
        """
        AGE 결과(agtype 문자열/객체)를 프론트엔드용 표준 JSON으로 변환
        
        Args:
            row: psycopg2 결과 튜플
            columns: 컬럼명 리스트
        """
        formatted = {}
        
        for idx, value in enumerate(row):
            key = columns[idx] if idx < len(columns) else f"col_{idx}"
            
            if value is None:
                formatted[key] = None
                continue
                
            # AGE는 결과를 문자열 형태의 JSON으로 줄 때가 많음
            if isinstance(value, str):
                try:
                    # '::vertex', '::edge' 등 접미사 제거
                    clean_val = value.split("::")[0]
                    parsed = json.loads(clean_val)
                    
                    # 노드(Vertex) 구조 표준화
                    if isinstance(parsed, dict) and 'label' in parsed and 'id' in parsed:
                        formatted[key] = {
                            "id": str(parsed['id']),  # ID 문자열 변환
                            "label": parsed['label'],
                            "properties": parsed.get('properties', {})
                        }
                    else:
                        formatted[key] = parsed
                except (json.JSONDecodeError, TypeError):
                    formatted[key] = value
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
            # 1. SQL 래핑
            sql = self._wrap_age_sql(query, graph_path)
            
            # 2. DB 연결 및 실행
            conn = self._get_connection()
            cur = conn.cursor()
            
            # 그래프 경로 설정
            safe_set_graph_path(cur, graph_path)
            cur.execute(sql)
            
            rows = cur.fetchall()
            
            # 컬럼명 추출 (RETURN 절에서)
            return_pattern = re.compile(r"RETURN\s+(.*)", re.IGNORECASE | re.DOTALL)
            match = return_pattern.search(query)
            columns = []
            if match:
                raw_items = match.group(1).split(',')
                for item in raw_items:
                    clean_item = item.strip()
                    if " AS " in clean_item.upper():
                        alias = clean_item.split(" AS ")[-1].strip()
                        columns.append(alias.lower())
                    else:
                        columns.append(clean_item.lower())
            
            # 3. 결과 변환
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