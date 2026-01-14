import re
import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import HTTPException

class CypherService:
    """
    Apache AGE (PostgreSQL Graph Extension) 전용 쿼리 실행기
    - 역할: 표준 Cypher를 AGE SQL로 래핑하고 결과를 표준 JSON으로 변환
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    def _wrap_age_sql(self, query: str, graph_path: str) -> str:
        """
        [핵심 로직] Standard Cypher -> Apache AGE SQL 변환
        Example:
            Input:  MATCH (n) RETURN n
            Output: SELECT * FROM cypher('graph', $$ MATCH (n) RETURN n $$) as (n agtype)
        """
        # 1. RETURN 절 파싱 (정규식으로 반환 변수 추출)
        return_pattern = re.compile(r"RETURN\s+(.*)", re.IGNORECASE | re.DOTALL)
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

    def _format_age_result(self, row: Any) -> Dict[str, Any]:
        """
        AGE 결과(agtype 문자열/객체)를 프론트엔드용 표준 JSON으로 변환
        """
        formatted = {}
        # SQLAlchemy Row 객체 -> Dict 변환
        row_dict = row._mapping
        
        for key, value in row_dict.items():
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
                            "id": str(parsed['id']), # ID 문자열 변환
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

    async def execute(self, query: str, graph_path: str) -> List[Dict[str, Any]]:
        """
        [Public API] 외부에서 호출하는 실행 메서드
        """
        try:
            # 1. SQL 래핑
            sql = self._wrap_age_sql(query, graph_path)
            
            # 2. DB 실행
            result = await self.db.execute(text(sql))
            rows = result.fetchall()
            
            # 3. 결과 변환
            return [self._format_age_result(row) for row in rows]
            
        except Exception as e:
            print(f"[Cypher Error] {str(e)}\nQuery: {query}")
            raise HTTPException(status_code=500, detail=f"Graph Query Execution Failed: {str(e)}")