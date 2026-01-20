"""
범죄 패턴 분석 엔진

그래프 데이터에서 범죄 패턴 자동 인식 및 매칭
"""

from app.services.pattern_library import PatternLibrary
from app.services.graph_service import GraphService


class PatternAnalyzer:
    """범죄 패턴 매칭 및 분석"""
    
    @staticmethod
    def analyze_case(case_id, graph_path):
        """
        사건 그래프에서 범죄 패턴 자동 인식
        
        Args:
            case_id: 사건 ID (flnm 값)
            graph_path: 그래프 경로
            
        Returns:
            {
                "case_id": "2019-000392",
                "matched_patterns": [...],
                "primary_pattern": "몸캠피싱",
                "confidence": 0.95
            }
        """
        # 1. 사건 중심 서브그래프 추출
        subgraph = PatternAnalyzer._extract_case_subgraph(case_id, graph_path)
        
        if not subgraph:
            return {
                "case_id": case_id,
                "matched_patterns": [],
                "primary_pattern": None,
                "confidence": 0.0,
                "message": "No subgraph found for case"
            }
        
        # 2. 모든 패턴과 매칭
        matched_patterns = []
        all_patterns = PatternLibrary.get_all_patterns()
        
        for pattern_id, pattern in all_patterns.items():
            match_result = PatternAnalyzer._match_pattern(subgraph, pattern)
            
            if match_result["score"] >= pattern.scoring["min_threshold"]:
                matched_patterns.append({
                    "pattern_id": pattern.pattern_id,
                    "pattern_name": pattern.name,
                    "confidence": match_result["score"],
                    "matched_nodes": match_result["matched_nodes"],
                    "matched_edges": match_result["matched_edges"],
                    "missing_elements": match_result["missing"],
                    "details": match_result
                })
        
        # 3. 점수 순 정렬
        matched_patterns.sort(key=lambda x: x["confidence"], reverse=True)
        
        # 4. 결과 반환
        return {
            "case_id": case_id,
            "matched_patterns": matched_patterns,
            "primary_pattern": matched_patterns[0]["pattern_name"] if matched_patterns else None,
            "confidence": matched_patterns[0]["confidence"] if matched_patterns else 0.0,
            "analysis_summary": PatternAnalyzer._generate_summary(matched_patterns)
        }
    
    @staticmethod
    def _extract_case_subgraph(case_id, graph_path):
        """
        사건 ID 중심으로 1-hop 서브그래프 추출
        
        Returns:
            {
                "nodes": {node_id: {label, properties}},
                "edges": [{from, to, type, properties}]
            }
        """
        conn, cur = GraphService.get_db_connection()
        if not conn:
            return None
        
        try:
            cur.execute(f"SET graph_path = {graph_path}")
            
            # 사건 노드 찾기 (case는 예약어이므로 c로 변경)
            query = f"""
            MATCH (c:vt_flnm)
            WHERE c.flnm CONTAINS '{case_id}'
            RETURN id(c), properties(c)
            LIMIT 1
            """
            cur.execute(query)
            case_row = cur.fetchone()
            
            if not case_row:
                return None
            
            case_node_id = str(case_row[0])
            case_props = case_row[1] if case_row[1] else {}
            
            # 1-hop 연결 노드 및 엣지 가져오기
            query = f"""
            MATCH (c)-[r]-(n)
            WHERE id(c) = {case_node_id}
            RETURN id(n), labels(n), properties(n), 
                   id(r), type(r), properties(r),
                   id(c) = id(startNode(r)) as is_outgoing
            LIMIT 50
            """
            cur.execute(query)
            rows = cur.fetchall()
            
            # 서브그래프 구성
            nodes = {
                case_node_id: {
                    "label": "vt_flnm",
                    "properties": case_props
                }
            }
            edges = []
            
            for row in rows:
                node_id = str(row[0])
                node_label = row[1][0] if row[1] else "unknown"
                node_props = row[2] if row[2] else {}
                edge_id = str(row[3])
                edge_type = row[4]
                edge_props = row[5] if row[5] else {}
                is_outgoing = row[6]
                
                # 노드 추가
                if node_id not in nodes:
                    nodes[node_id] = {
                        "label": node_label,
                        "properties": node_props
                    }
                
                # 엣지 추가
                edges.append({
                    "id": edge_id,
                    "from": case_node_id if is_outgoing else node_id,
                    "to": node_id if is_outgoing else case_node_id,
                    "type": edge_type,
                    "properties": edge_props
                })
            
            return {
                "case_node_id": case_node_id,
                "nodes": nodes,
                "edges": edges
            }
            
        except Exception as e:
            print(f"Subgraph extraction error: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def _match_pattern(subgraph, pattern):
        """
        서브그래프와 패턴 매칭
        
        Returns:
            {
                "score": 0.95,
                "matched_nodes": {...},
                "matched_edges": [...],
                "missing": [...]
            }
        """
        nodes = subgraph["nodes"]
        edges = subgraph["edges"]
        
        # 1. 필수 노드 매칭
        required_node_matches = {}
        for node_key, node_spec in pattern.required_nodes.items():
            required_label = node_spec["label"]
            
            # 서브그래프에서 해당 레이블 노드 찾기
            matched = False
            for node_id, node_data in nodes.items():
                if node_data["label"] == required_label:
                    required_node_matches[node_key] = node_id
                    matched = True
                    break
            
            if not matched:
                # 필수 노드 없으면 매칭 실패
                return {
                    "score": 0.0,
                    "matched_nodes": {},
                    "matched_edges": [],
                    "missing": [f"Required node: {node_key} ({required_label})"]
                }
        
        # 2. 필수 엣지 매칭
        matched_edges = []
        missing_edges = []
        
        for edge_spec in pattern.required_edges:
            from_key = edge_spec["from"]
            to_key = edge_spec["to"]
            edge_type = edge_spec["type"]
            
            from_node_id = required_node_matches.get(from_key)
            to_node_id = required_node_matches.get(to_key)
            
            if not from_node_id or not to_node_id:
                missing_edges.append(f"{from_key} -[{edge_type}]-> {to_key}")
                continue
            
            # 엣지 존재 확인
            edge_found = False
            for edge in edges:
                if (edge["from"] == from_node_id and 
                    edge["to"] == to_node_id and 
                    edge["type"] == edge_type):
                    matched_edges.append(edge)
                    edge_found = True
                    break
            
            if not edge_found:
                missing_edges.append(f"{from_key} -[{edge_type}]-> {to_key}")
        
        # 3. 선택 노드 매칭 (보너스)
        optional_matches = 0
        total_optional = len(pattern.optional_nodes)
        
        if total_optional > 0:
            for opt_key, opt_spec in pattern.optional_nodes.items():
                opt_label = opt_spec["label"]
                for node_id, node_data in nodes.items():
                    if node_data["label"] == opt_label:
                        optional_matches += 1
                        break
        
        # 4. 점수 계산
        required_score = pattern.scoring["required_match"]
        optional_score = pattern.scoring["optional_bonus"]
        
        # 필수 엣지 매칭률
        edge_match_rate = len(matched_edges) / len(pattern.required_edges) if pattern.required_edges else 1.0
        
        # 선택 노드 매칭률
        optional_match_rate = optional_matches / total_optional if total_optional > 0 else 0.0
        
        # 최종 점수
        final_score = (edge_match_rate * required_score) + (optional_match_rate * optional_score)
        
        return {
            "score": round(final_score, 3),
            "matched_nodes": required_node_matches,
            "matched_edges": [e["type"] for e in matched_edges],
            "missing": missing_edges,
            "optional_matched": optional_matches,
            "optional_total": total_optional
        }
    
    @staticmethod
    def _generate_summary(matched_patterns):
        """분석 결과 요약 생성"""
        if not matched_patterns:
            return "패턴 매칭 실패. 증거가 부족하거나 알려지지 않은 범죄 유형일 수 있습니다."
        
        primary = matched_patterns[0]
        summary = f"이 사건은 '{primary['pattern_name']}' 패턴과 {primary['confidence']*100:.1f}% 일치합니다."
        
        if primary["missing_elements"]:
            summary += f" 다만 {len(primary['missing_elements'])}개의 증거가 누락되어 있습니다."
        
        if len(matched_patterns) > 1:
            other = ", ".join([p["pattern_name"] for p in matched_patterns[1:3]])
            summary += f" 다른 가능성: {other}"
        
        return summary
