"""
그래프 맥락 추출 서비스

사건 그래프에서 법률 자문에 필요한 맥락 정보를 추출
LegalGraphRAG에서 사용

참고: GraphRAG (Microsoft, 2024) 아키텍처
"""

from flask import current_app


class GraphContextExtractor:
    """사건 그래프에서 법률 자문에 필요한 맥락 추출"""
    
    # 증거-법률 매핑 테이블
    EVIDENCE_LEGAL_MAPPING = {
        "vt_site": {
            "name": "웹사이트",
            "proves": ["범죄 현장", "디지털 증거", "유포 행위"],
            "laws": ["정보통신망법", "전자상거래법"],
            "importance": "high"
        },
        "vt_bacnt": {
            "name": "계좌",
            "proves": ["금전 피해", "범죄 수익", "자금 추적"],
            "laws": ["형법 사기죄", "범죄수익은닉규제법", "전기통신금융사기법"],
            "importance": "high"
        },
        "vt_telno": {
            "name": "전화번호",
            "proves": ["범죄자 연락처", "범행 수단", "통화 기록"],
            "laws": ["통신비밀보호법", "전기통신사업법"],
            "importance": "medium"
        },
        "vt_ip": {
            "name": "IP 주소",
            "proves": ["범죄자 위치", "신원 특정", "접속 기록"],
            "laws": ["정보통신망법", "통신비밀보호법"],
            "importance": "high"
        },
        "vt_file": {
            "name": "파일",
            "proves": ["증거물", "협박 자료", "유포 콘텐츠"],
            "laws": ["형사소송법", "정보통신망법"],
            "importance": "high"
        },
        "vt_id": {
            "name": "사용자 ID",
            "proves": ["디지털 신원", "활동 기록"],
            "laws": ["개인정보보호법"],
            "importance": "medium"
        },
        "vt_atm": {
            "name": "ATM",
            "proves": ["현금 인출 위치", "CCTV 증거"],
            "laws": ["형사소송법"],
            "importance": "medium"
        }
    }
    
    # 범죄 유형별 관련 법률
    CRIME_TYPE_LAWS = {
        "몸캠피싱": {
            "primary": ["정보통신망법 제44조의7 (영상 유포 협박)", "형법 제283조 (협박)"],
            "secondary": ["성폭력처벌법", "정보통신망법 제70조"],
            "required_evidence": ["vt_site", "vt_file", "vt_bacnt"],
            "optional_evidence": ["vt_ip", "vt_telno"]
        },
        "보이스피싱": {
            "primary": ["전기통신금융사기 피해 방지 특별법", "형법 제347조 (사기)"],
            "secondary": ["전자금융거래법"],
            "required_evidence": ["vt_telno", "vt_bacnt"],
            "optional_evidence": ["vt_ip", "vt_atm"]
        },
        "투자사기": {
            "primary": ["자본시장법", "형법 제347조 (사기)"],
            "secondary": ["유사수신행위법"],
            "required_evidence": ["vt_site", "vt_bacnt"],
            "optional_evidence": ["vt_telno", "vt_id"]
        },
        "전화금융사기": {
            "primary": ["전기통신금융사기법", "형법 제347조 (사기)"],
            "secondary": ["전자금융거래법"],
            "required_evidence": ["vt_telno", "vt_bacnt"],
            "optional_evidence": ["vt_atm"]
        },
        "스미싱": {
            "primary": ["정보통신망법", "형법 제347조 (사기)"],
            "secondary": ["전자금융거래법"],
            "required_evidence": ["vt_telno", "vt_site", "vt_bacnt"],
            "optional_evidence": ["vt_ip", "vt_file"]
        }
    }

    @classmethod
    def extract_case_context(cls, case_id: str, graph_path: str) -> dict:
        """
        사건 ID 기반 전체 맥락 추출
        
        Returns:
            {
                "case_id": "2024-001",
                "crime_type": "몸캠피싱",
                "pattern_confidence": 0.95,
                "evidence_nodes": [...],
                "missing_evidence": [...],
                "completeness_score": 0.75,
                "applicable_laws": [...],
                "graph_summary": "..."
            }
        """
        from app.services.pattern_analyzer import PatternAnalyzer
        from app.services.evidence_analyzer import EvidenceAnalyzer
        
        print(f"▶ [GraphContext] 사건 '{case_id}' 맥락 추출 시작...")
        
        # 기본 값 설정
        crime_type = "미확인"
        pattern_confidence = 0
        matched_pattern = None
        subgraph = {"nodes": {}, "edges": []}
        
        # 1. 패턴 분석
        try:
            pattern_result = PatternAnalyzer.analyze_case(case_id, graph_path)
            if pattern_result and pattern_result.get("matched_patterns"):
                matched_pattern = pattern_result["matched_patterns"][0]
                crime_type = matched_pattern.get("pattern_name", "미확인")
                pattern_confidence = matched_pattern.get("confidence", 0)
        except Exception as e:
            print(f"   ⚠️ 패턴 분석 오류: {e}")
            pattern_result = {"matched_patterns": [], "confidence": 0}
        
        # 2. 서브그래프 추출
        try:
            extracted = PatternAnalyzer._extract_case_subgraph(case_id, graph_path)
            if extracted:
                subgraph = extracted
        except Exception as e:
            print(f"   ⚠️ 서브그래프 추출 오류: {e}")
        
        # 3. 증거 완성도 평가
        evidence_result = {"completeness_score": 0, "missing_evidence": []}
        if matched_pattern and subgraph.get("nodes"):
            try:
                evidence_result = EvidenceAnalyzer.evaluate_completeness(
                    case_id, matched_pattern, subgraph
                )
            except Exception as e:
                print(f"   ⚠️ 증거 분석 오류: {e}")
        
        # 4. 증거 노드 분류
        evidence_nodes = cls._classify_evidence_nodes(subgraph)
        
        # 5. 적용 가능한 법률 식별
        applicable_laws = cls._get_applicable_laws(crime_type, evidence_nodes)
        
        # 6. 그래프 요약 생성
        graph_summary = cls._generate_summary(
            case_id, crime_type, evidence_nodes, 
            evidence_result.get("missing_evidence", [])
        )
        
        print(f"   [GraphContext] 맥락 추출 완료: {crime_type} (신뢰도 {pattern_confidence*100:.1f}%)")
        
        return {
            "case_id": case_id,
            "crime_type": crime_type,
            "pattern_confidence": pattern_confidence,
            "evidence_nodes": evidence_nodes,
            "missing_evidence": evidence_result.get("missing_evidence", []),
            "completeness_score": evidence_result.get("completeness_score", 0),
            "applicable_laws": applicable_laws,
            "graph_summary": graph_summary,
            "subgraph": subgraph
        }

    @classmethod
    def _classify_evidence_nodes(cls, subgraph: dict) -> list:
        """서브그래프에서 증거 노드 분류"""
        evidence_list = []
        
        nodes = subgraph.get("nodes", [])
        for node in nodes:
            label = node.get("label", "")
            properties = node.get("properties", {})
            
            if label in cls.EVIDENCE_LEGAL_MAPPING:
                mapping = cls.EVIDENCE_LEGAL_MAPPING[label]
                evidence_list.append({
                    "type": label,
                    "name": mapping["name"],
                    "value": cls._get_node_value(properties, label),
                    "proves": mapping["proves"],
                    "laws": mapping["laws"],
                    "importance": mapping["importance"],
                    "status": "✅ 확보"
                })
        
        return evidence_list

    @classmethod
    def _get_node_value(cls, properties: dict, label: str) -> str:
        """노드에서 대표 값 추출"""
        key_mapping = {
            "vt_flnm": ["flnm", "receipt_no"],
            "vt_telno": ["telno", "phone"],
            "vt_bacnt": ["actno", "bacnt", "account"],
            "vt_site": ["site", "url", "domain"],
            "vt_ip": ["ip", "ip_addr"],
            "vt_file": ["file", "filename"],
            "vt_id": ["id", "user_id"],
            "vt_atm": ["atm", "atm_id"]
        }
        
        keys = key_mapping.get(label, list(properties.keys()))
        for key in keys:
            if key in properties and properties[key]:
                return str(properties[key])
        
        return str(properties) if properties else ""

    @classmethod
    def _get_applicable_laws(cls, crime_type: str, evidence_nodes: list) -> dict:
        """범죄 유형과 증거에 따른 적용 법률 식별"""
        
        # 범죄 유형 기반 법률
        crime_laws = cls.CRIME_TYPE_LAWS.get(crime_type, {})
        primary_laws = crime_laws.get("primary", [])
        secondary_laws = crime_laws.get("secondary", [])
        
        # 증거 기반 추가 법률
        evidence_laws = []
        for evidence in evidence_nodes:
            evidence_laws.extend(evidence.get("laws", []))
        
        # 중복 제거
        evidence_laws = list(set(evidence_laws))
        
        return {
            "primary": primary_laws,
            "secondary": secondary_laws,
            "evidence_based": evidence_laws
        }

    @classmethod
    def _generate_summary(cls, case_id: str, crime_type: str, 
                         evidence_nodes: list, missing_evidence: list) -> str:
        """그래프 맥락 자연어 요약"""
        
        evidence_names = [e["name"] for e in evidence_nodes]
        missing_names = [m.get("description", m.get("type", "")) for m in missing_evidence]
        
        summary = f"사건번호 {case_id}는 "
        
        if crime_type != "미확인":
            summary += f"'{crime_type}' 패턴으로 분석되었습니다. "
        else:
            summary += "아직 범죄 유형이 확인되지 않았습니다. "
        
        if evidence_nodes:
            summary += f"확보된 증거: {', '.join(evidence_names)}. "
        else:
            summary += "현재 확보된 증거가 없습니다. "
        
        if missing_names:
            summary += f"추가 필요: {', '.join(missing_names[:3])}."
        
        return summary

    @classmethod
    def get_prosecution_readiness(cls, context: dict) -> dict:
        """기소 준비도 평가"""
        
        crime_type = context.get("crime_type", "미확인")
        evidence_nodes = context.get("evidence_nodes", [])
        completeness_score = context.get("completeness_score", 0)
        
        # 범죄 유형별 필수 증거 확인
        crime_laws = cls.CRIME_TYPE_LAWS.get(crime_type, {})
        required = crime_laws.get("required_evidence", [])
        optional = crime_laws.get("optional_evidence", [])
        
        evidence_types = [e["type"] for e in evidence_nodes]
        
        # 필수 증거 충족률
        required_met = sum(1 for r in required if r in evidence_types)
        required_ratio = required_met / len(required) if required else 0
        
        # 선택 증거 충족률
        optional_met = sum(1 for o in optional if o in evidence_types)
        optional_ratio = optional_met / len(optional) if optional else 0
        
        # 전체 기소 준비도 (필수 70%, 선택 30%)
        prosecution_score = required_ratio * 0.7 + optional_ratio * 0.3
        
        # 기소 가능성 판정
        if prosecution_score >= 0.85:
            status = "기소 가능"
            recommendation = "현재 증거로 기소 진행이 가능합니다."
        elif prosecution_score >= 0.60:
            status = "조건부 가능"
            recommendation = "추가 증거 확보 시 기소 가능성이 높아집니다."
        else:
            status = "증거 부족"
            recommendation = "핵심 증거 확보가 필요합니다."
        
        # 누락 증거 리스트
        missing_required = [r for r in required if r not in evidence_types]
        missing_optional = [o for o in optional if o not in evidence_types]
        
        return {
            "prosecution_score": round(prosecution_score, 2),
            "status": status,
            "recommendation": recommendation,
            "required_met": f"{required_met}/{len(required)}",
            "optional_met": f"{optional_met}/{len(optional)}",
            "missing_required": missing_required,
            "missing_optional": missing_optional
        }
