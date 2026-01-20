"""
증거 완성도 분석기

범죄 패턴 기반 증거 체크리스트 및 완성도 평가
"""

from app.services.pattern_library import PatternLibrary


class EvidenceAnalyzer:
    """증거 완성도 분석"""
    
    @staticmethod
    def evaluate_completeness(case_id, matched_pattern, subgraph):
        """
        패턴 기반 증거 완성도 평가
        
        Args:
            case_id: 사건 ID
            matched_pattern: 매칭된 패턴 정보 (from PatternAnalyzer)
            subgraph: 사건 서브그래프
            
        Returns:
            {
                "case_id": "2019-000392",
                "pattern": "몸캠피싱",
                "completeness_score": 0.75,
                "evidence_checklist": {...},
                "missing_evidence": [...],
                "next_steps": [...]
            }
        """
        if not matched_pattern:
            return {
                "case_id": case_id,
                "completeness_score": 0.0,
                "message": "No pattern matched"
            }
        
        pattern_name = matched_pattern["pattern_name"]
        pattern = PatternLibrary.find_by_name(pattern_name)
        
        if not pattern:
            return {
                "case_id": case_id,
                "completeness_score": 0.0,
                "message": "Pattern not found in library"
            }
        
        # 1. 증거 체크리스트 생성
        checklist = EvidenceAnalyzer._create_checklist(pattern, subgraph, matched_pattern)
        
        # 2. 완성도 점수 계산
        completeness_score = EvidenceAnalyzer._calculate_completeness(checklist)
        
        # 3. 누락된 증거 분석
        missing_evidence = EvidenceAnalyzer._analyze_missing(pattern, checklist)
        
        # 4. 수사 제안사항 생성
        next_steps = EvidenceAnalyzer._generate_recommendations(missing_evidence, pattern)
        
        return {
            "case_id": case_id,
            "pattern": pattern_name,
            "completeness_score": round(completeness_score, 3),
            "evidence_checklist": checklist,
            "missing_evidence": missing_evidence,
            "next_steps": next_steps,
            "summary": EvidenceAnalyzer._generate_summary(pattern_name, completeness_score, missing_evidence)
        }
    
    @staticmethod
    def _create_checklist(pattern, subgraph, matched_pattern):
        """증거 체크리스트 생성"""
        checklist = {
            "required": {},
            "optional": {}
        }
        
        nodes = subgraph["nodes"]
        matched_nodes = matched_pattern["matched_nodes"]
        
        # 필수 증거 체크
        for node_key, node_spec in pattern.required_nodes.items():
            node_label = node_spec["label"]
            description = node_spec.get("description", node_label)
            
            if node_key in matched_nodes:
                checklist["required"][description] = {
                    "status": "✅ 완료",
                    "node_id": matched_nodes[node_key]
                }
            else:
                checklist["required"][description] = {
                    "status": "❌ 누락",
                    "node_id": None
                }
        
        # 선택 증거 체크
        for opt_key, opt_spec in pattern.optional_nodes.items():
            opt_label = opt_spec["label"]
            description = opt_spec.get("description", opt_label)
            
            # 서브그래프에서 찾기
            found = False
            for node_id, node_data in nodes.items():
                if node_data["label"] == opt_label:
                    checklist["optional"][description] = {
                        "status": "✅ 완료",
                        "node_id": node_id,
                        "weight": opt_spec.get("weight", 0.1)
                    }
                    found = True
                    break
            
            if not found:
                checklist["optional"][description] = {
                    "status": "❌ 누락",
                    "node_id": None,
                    "weight": opt_spec.get("weight", 0.1)
                }
        
        return checklist
    
    @staticmethod
    def _calculate_completeness(checklist):
        """완성도 점수 계산"""
        required = checklist["required"]
        optional = checklist["optional"]
        
        # 필수 증거 완성도 (70%)
        required_complete = sum(1 for item in required.values() if item["status"] == "✅ 완료")
        required_total = len(required)
        required_score = (required_complete / required_total) * 0.7 if required_total > 0 else 0.0
        
        # 선택 증거 완성도 (30%)
        optional_complete = sum(1 for item in optional.values() if item["status"] == "✅ 완료")
        optional_total = len(optional)
        optional_score = (optional_complete / optional_total) * 0.3 if optional_total > 0 else 0.0
        
        return required_score + optional_score
    
    @staticmethod
    def _analyze_missing(pattern, checklist):
        """누락된 증거 분석"""
        missing = []
        
        # 필수 증거 누락
        for desc, item in checklist["required"].items():
            if item["status"] == "❌ 누락":
                missing.append({
                    "type": desc,
                    "importance": "high",
                    "category": "required"
                })
        
        # 선택 증거 누락
        for desc, item in checklist["optional"].items():
            if item["status"] == "❌ 누락":
                weight = item.get("weight", 0.1)
                importance = "medium" if weight >= 0.15 else "low"
                
                missing.append({
                    "type": desc,
                    "importance": importance,
                    "category": "optional",
                    "weight": weight
                })
        
        # 중요도 순 정렬
        missing.sort(key=lambda x: (0 if x["category"] == "required" else 1, -x.get("weight", 0)))
        
        return missing
    
    @staticmethod
    def _generate_recommendations(missing_evidence, pattern):
        """수사 제안사항 생성"""
        recommendations = []
        
        # 패턴별 권장 조치
        PATTERN_ACTIONS = {
            "몸캠피싱": {
                "IP주소": "ISP에 피해자 접속 IP 로그 요청",
                "범죄자 연락처": "텔레그램/카카오톡 계정 추적",
                "성인 사이트": "사이트 서버 위치 파악 및 압수수색"
            },
            "보이스피싱": {
                "접속 IP": "통신사에 통화 연결 로그 요청",
                "피싱 사이트": "사칭 사이트 URL 확보 및 차단 요청"
            },
            "전화금융사기": {
                "ATM 출금 기록": "금융기관에 ATM CCTV 영상 요청",
                "범죄자 전화": "명의자 추적 및 소환"
            }
        }
        
        pattern_name = pattern.name
        actions = PATTERN_ACTIONS.get(pattern_name, {})
        
        for evidence in missing_evidence:
            if evidence["category"] == "required":
                # 필수 증거
                evidence_type = evidence["type"]
                action = actions.get(evidence_type, f"{evidence_type} 확보 필요")
                recommendations.append(f"[필수] {action}")
            elif evidence["importance"] == "medium":
                # 중요도 높은 선택 증거
                evidence_type = evidence["type"]
                action = actions.get(evidence_type, f"{evidence_type} 확보 권장")
                recommendations.append(f"[권장] {action}")
        
        # 일반 수사 지침
        if not recommendations:
            recommendations.append("모든 필수 증거가 확보되었습니다. 증거 분석 및 피의자 특정 단계로 진행하세요.")
        
        return recommendations[:5]  # 최대 5개
    
    @staticmethod
    def _generate_summary(pattern_name, score, missing):
        """분석 요약 생성"""
        score_pct = score * 100
        
        if score >= 0.9:
            quality = "매우 우수"
        elif score >= 0.75:
            quality = "양호"
        elif score >= 0.6:
            quality = "보통"
        else:
            quality = "부족"
        
        summary = f"'{pattern_name}' 사건의 증거 완성도는 {score_pct:.1f}%로 {quality}합니다."
        
        if missing:
            required_missing = [m for m in missing if m["category"] == "required"]
            if required_missing:
                summary += f" {len(required_missing)}개의 필수 증거가 누락되어 추가 수사가 필요합니다."
            else:
                summary += " 필수 증거는 모두 확보되었으나, 선택 증거를 추가 확보하면 사건 해결에 도움이 됩니다."
        
        return summary
