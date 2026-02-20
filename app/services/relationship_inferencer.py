"""
LLM 기반 관계 추론 서비스 (RELATE 스타일)

CSV 데이터에서 자동으로 엔티티와 관계를 추론하여
KICS 온톨로지에 매핑하는 서비스

참고: RELATE (arXiv 2025) - 3-Stage Pipeline
  Stage 1: LLM Raw Extraction
  Stage 2: Ontology Mapping
  Stage 3: Validation
"""

import json
import re
from openai import OpenAI
from flask import current_app


class RelationshipInferencer:
    """LLM 기반 관계 추론 서비스"""
    
    # KICS 온톨로지 컬럼 타입 정의
    @classmethod
    def _get_column_patterns(cls):
        """KICS 온톨로지에서 컬럼 패턴 가져오기"""
        from app.services.ontology_service import KICSCrimeDomainOntology
        return KICSCrimeDomainOntology.COLUMN_PATTERNS
    
    # 관계 추론 규칙 - ontology_service.py에서 통합 관리
    # 아래는 fallback용으로 유지 (import 실패 시 사용)
    _FALLBACK_RELATIONSHIP_RULES = {
        # ═══════════════════════════════════════════════════════════
        # [Layer 1 → Layer 2] Case (사건) → Actor (행위자)
        # 사건은 오직 행위자(인물/조직/기기)와만 직접 연결
        # ═══════════════════════════════════════════════════════════
        ("case_id", "person"): {"type": "involves", "description": "관련 인물"},
        ("case_id", "organization"): {"type": "involves", "description": "관련 조직"},
        ("case_id", "device"): {"type": "involves", "description": "관련 기기"},
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 3] Actor (행위자) → Action (행위)
        # 행위자가 수행한 행위와 연결
        # ═══════════════════════════════════════════════════════════
        ("person", "transfer"): {"type": "performed", "description": "이체 행위"},
        ("person", "call"): {"type": "performed", "description": "통화 행위"},
        ("person", "access"): {"type": "performed", "description": "접속 행위"},
        ("person", "message"): {"type": "performed", "description": "메시지 행위"},
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 4] Actor (행위자) → Evidence (증거) [소유/귀속 관계]
        # 행위자가 직접 소유하거나 사용하는 증거 객체 (핵심 수사단서)
        # ═══════════════════════════════════════════════════════════
        ("person", "phone"): {"type": "owns_phone", "description": "소유 전화"},
        ("person", "account"): {"type": "has_account", "description": "소유 계좌"},
        ("person", "ip"): {"type": "used_ip", "description": "사용 IP"},
        ("person", "user_id"): {"type": "uses_id", "description": "사용 ID"},
        ("person", "device"): {"type": "uses_device", "description": "사용 기기"},
        ("organization", "account"): {"type": "has_account", "description": "법인 계좌"},
        # 닉네임/ID → 소유 자산 (핵심 수사단서)
        ("user_id", "account"): {"type": "has_account", "description": "닉네임 소유 계좌"},
        ("user_id", "phone"): {"type": "owns_phone", "description": "닉네임 소유 전화"},
        ("user_id", "ip"): {"type": "used_ip", "description": "닉네임 사용 IP"},
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 3 → Layer 4] Action (행위) → Evidence (증거)
        # 행위가 사용하거나 생성한 증거 객체
        # ═══════════════════════════════════════════════════════════
        ("transfer", "account"): {"type": "from_account", "description": "출금/입금 계좌"},
        ("call", "phone"): {"type": "caller", "description": "발신/수신 번호"},
        ("access", "ip"): {"type": "accessed_from", "description": "접속 IP"},
        ("access", "site"): {"type": "accessed_to", "description": "접속 사이트"},
        ("message", "phone"): {"type": "sent_by", "description": "발신 번호"},
        ("message", "file"): {"type": "attached", "description": "첨부 파일"},
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 4 → Layer 4] Evidence (증거) Peer-to-Peer 연결
        # 증거 객체 간의 직접 연결 (핵심 분석 대상)
        # ═══════════════════════════════════════════════════════════
        ("account", "account"): {"type": "transferred_to", "description": "자금 이체"},
        ("phone", "phone"): {"type": "contacted", "description": "통화/연락"},
        ("ip", "ip"): {"type": "communicated_with", "description": "IP 통신"},
        ("phone", "account"): {"type": "linked_to", "description": "번호-계좌 연결"},
        ("ip", "site"): {"type": "accessed", "description": "사이트 접속"},
    }
    
    @classmethod
    def get_relationship_rules(cls):
        """통합된 관계 규칙 가져오기 (ontology_service 우선)"""
        try:
            from app.services.ontology_service import KICSCrimeDomainOntology
            return KICSCrimeDomainOntology.get_relationship_rules()
        except ImportError:
            return cls._FALLBACK_RELATIONSHIP_RULES

    @staticmethod
    def get_client():
        """OpenAI 클라이언트 생성"""
        return OpenAI(api_key=current_app.config['OPENAI_API_KEY'])

    @classmethod
    def analyze_csv(cls, df, sample_size=5):
        """
        Stage 1: CSV 분석 및 엔티티/관계 추론
        
        Args:
            df: pandas DataFrame
            sample_size: 분석에 사용할 샘플 행 수
            
        Returns:
            추론 결과 딕셔너리
        """
        print("▶ [Inference] CSV 분석 시작...")
        
        columns = list(df.columns)
        sample_rows = df.head(sample_size).to_dict('records')
        
        # Stage 1-1: 규칙 기반 컬럼 타입 추론 (빠른 처리)
        column_types = cls._infer_column_types_by_rules(columns, sample_rows)
        
        # Stage 1-2: LLM으로 추가 컬럼 분석 (규칙으로 못 찾은 경우)
        unknown_columns = [c for c in columns if c not in column_types]
        if unknown_columns:
            llm_types = cls._infer_column_types_by_llm(unknown_columns, sample_rows)
            column_types.update(llm_types)
        
        print(f"   [Inference] 컬럼 타입 추론 완료: {len(column_types)}개 컬럼")
        
        # Stage 2: 관계 추론
        relationships = cls._infer_relationships(column_types)
        print(f"   [Inference] 관계 추론 완료: {len(relationships)}개 관계")
        
        # Stage 3: ETL 매핑 생성
        suggested_mappings = cls._generate_etl_mappings(column_types, relationships)
        
        return {
            "status": "success",
            "columns": [
                {
                    "name": col,
                    "inferred_type": info.get("type", "unknown"),
                    "kics_label": info.get("kics_label", ""),
                    "kics_property": info.get("kics_property", ""),
                    "confidence": info.get("confidence", 0.5),
                    "description": info.get("description", "")
                }
                for col, info in column_types.items()
            ],
            "relationships": relationships,
            "suggested_mappings": suggested_mappings,
            "sample_data": sample_rows[:3]
        }

    @classmethod
    def _infer_column_types_by_rules(cls, columns, sample_rows):
        """규칙 기반 컬럼 타입 추론"""
        result = {}
        
        # 우선 매칭 타입 (정확한 매칭이 중요한 타입)
        priority_types = ['ip', 'phone', 'account', 'site']
        
        for col in columns:
            col_lower = col.lower().strip()
            matched = False
            
            # 1. 정확한 매칭 (컬럼명이 패턴과 정확히 일치)
            column_patterns = cls._get_column_patterns()
            for type_name, config in column_patterns.items():
                for pattern in config["patterns"]:
                    if col_lower == pattern.lower():
                        result[col] = {
                            "type": type_name,
                            "kics_label": config["kics_label"],
                            "kics_property": config["kics_property"],
                            "description": config["description"],
                            "confidence": 0.95,
                            "source": "exact_match"
                        }
                        if config.get("is_attribute"):
                            result[col]["is_attribute"] = True
                        matched = True
                        break
                if matched:
                    break
            
            # 2. 우선 타입 부분 매칭 (IP, 전화, 계좌 등)
            if not matched:
                column_patterns = cls._get_column_patterns()
                for type_name in priority_types:
                    if type_name in column_patterns:
                        config = column_patterns[type_name]
                        for pattern in config["patterns"]:
                            if pattern.lower() in col_lower:
                                result[col] = {
                                    "type": type_name,
                                    "kics_label": config["kics_label"],
                                    "kics_property": config["kics_property"],
                                    "description": config["description"],
                                    "confidence": 0.9,
                                    "source": "priority_match"
                                }
                                matched = True
                                break
                    if matched:
                        break
            
            # 3. 일반 부분 매칭
            if not matched:
                column_patterns = cls._get_column_patterns()
                for type_name, config in column_patterns.items():
                    for pattern in config["patterns"]:
                        if pattern.lower() in col_lower or col_lower in pattern.lower():
                            result[col] = {
                                "type": type_name,
                                "kics_label": config["kics_label"],
                                "kics_property": config["kics_property"],
                                "description": config["description"],
                                "confidence": 0.85,
                                "source": "partial_match"
                            }
                            if config.get("is_attribute"):
                                result[col]["is_attribute"] = True
                            matched = True
                            break
                    if matched:
                        break
            
            # 샘플 데이터로 패턴 매칭
            if not matched and sample_rows:
                sample_values = [str(row.get(col, "")) for row in sample_rows if row.get(col)]
                inferred = cls._infer_type_from_values(sample_values)
                if inferred:
                    result[col] = inferred
        
        return result

    @classmethod
    def _infer_type_from_values(cls, values):
        """값의 패턴으로 타입 추론"""
        if not values:
            return None
            
        # 전화번호 패턴 (010-xxxx-xxxx, 02-xxx-xxxx 등)
        phone_pattern = r'^0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}$'
        if all(re.match(phone_pattern, v.replace(" ", "")) for v in values if v):
            config = cls._get_column_patterns()["phone"]
            return {
                "type": "phone",
                "kics_label": config["kics_label"],
                "kics_property": config["kics_property"],
                "description": config["description"],
                "confidence": 0.85,
                "source": "value_pattern"
            }
        
        # IP 주소 패턴
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if all(re.match(ip_pattern, v) for v in values if v):
            config = cls._get_column_patterns()["ip"]
            return {
                "type": "ip",
                "kics_label": config["kics_label"],
                "kics_property": config["kics_property"],
                "description": config["description"],
                "confidence": 0.95,
                "source": "value_pattern"
            }
        
        # 계좌번호 패턴 (숫자-숫자-숫자 또는 긴 숫자)
        account_pattern = r'^\d{3,6}[-]?\d{2,6}[-]?\d{2,8}$'
        if all(re.match(account_pattern, v.replace(" ", "")) for v in values if v):
            config = cls._get_column_patterns()["account"]
            return {
                "type": "account",
                "kics_label": config["kics_label"],
                "kics_property": config["kics_property"],
                "description": config["description"],
                "confidence": 0.80,
                "source": "value_pattern"
            }
        
        # URL 패턴
        url_pattern = r'^(https?://|www\.)'
        if any(re.match(url_pattern, v, re.IGNORECASE) for v in values if v):
            config = cls._get_column_patterns()["site"]
            return {
                "type": "site",
                "kics_label": config["kics_label"],
                "kics_property": config["kics_property"],
                "description": config["description"],
                "confidence": 0.90,
                "source": "value_pattern"
            }
        
        return None

    @classmethod
    def _infer_column_types_by_llm(cls, columns, sample_rows):
        """LLM을 사용한 컬럼 타입 추론"""
        if not columns:
            return {}
            
        client = cls.get_client()
        
        # 샘플 데이터 준비
        sample_preview = []
        for col in columns:
            values = [str(row.get(col, ""))[:50] for row in sample_rows[:3] if row.get(col)]
            sample_preview.append(f"{col}: {values}")
        
        prompt = f"""
다음 CSV 컬럼을 사이버범죄 수사 관점에서 분류하세요.

[분석할 컬럼 및 샘플값]
{chr(10).join(sample_preview)}

[분류 가능한 타입]
- case_id: 사건번호, 접수번호
- phone: 전화번호
- account: 계좌번호
- ip: IP 주소
- site: 웹사이트, URL
- file: 파일명, 경로
- user_id: 사용자 ID, 닉네임, 아이디
- person: 인물명, 성명, 이름
- atm: ATM ID
- other: 기타 (날짜, 금액 등)

[출력 형식] JSON만 반환
{{
  "컬럼명1": {{"type": "phone", "confidence": 0.8}},
  "컬럼명2": {{"type": "other", "confidence": 0.5}}
}}
"""
        
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            content = content.replace("```json", "").replace("```", "").strip()
            
            llm_result = json.loads(content)
            
            result = {}
            for col, info in llm_result.items():
                type_name = info.get("type", "other")
                if type_name in cls._get_column_patterns():
                    config = cls._get_column_patterns()[type_name]
                    result[col] = {
                        "type": type_name,
                        "kics_label": config["kics_label"],
                        "kics_property": config["kics_property"],
                        "description": config["description"],
                        "confidence": info.get("confidence", 0.7),
                        "source": "llm"
                    }
                else:
                    result[col] = {
                        "type": "other",
                        "kics_label": "",
                        "kics_property": col,
                        "description": "기타 속성",
                        "confidence": info.get("confidence", 0.5),
                        "source": "llm"
                    }
            
            return result
            
        except Exception as e:
            print(f"   ⚠️ LLM 컬럼 추론 오류: {e}")
            return {}

    @classmethod
    def _infer_relationships(cls, column_types):
        """컬럼 타입 간 관계 추론"""
        relationships = []
        
        type_to_columns = {}
        for col, info in column_types.items():
            col_type = info.get("type", "other")
            if col_type not in type_to_columns:
                type_to_columns[col_type] = []
            type_to_columns[col_type].append(col)
        
        # 통합된 관계 규칙 가져오기
        relationship_rules = cls.get_relationship_rules()
        
        # 관계 규칙 적용
        for (type1, type2), rel_info in relationship_rules.items():
            cols1 = type_to_columns.get(type1, [])
            cols2 = type_to_columns.get(type2, [])
            
            for c1 in cols1:
                for c2 in cols2:
                    relationships.append({
                        "source_col": c1,
                        "target_col": c2,
                        "source_type": type1,
                        "target_type": type2,
                        "relation_type": rel_info["type"],
                        "description": rel_info["description"],
                        "confidence": 0.85
                    })
        
        return relationships

    @classmethod
    def _generate_etl_mappings(cls, column_types, relationships):
        """ETL 서비스용 매핑 설정 생성"""
        mappings = []
        
        for rel in relationships:
            src_col = rel["source_col"]
            tgt_col = rel["target_col"]
            
            src_info = column_types.get(src_col, {})
            tgt_info = column_types.get(tgt_col, {})
            
            mapping = {
                "sourceCol": src_col,
                "targetCol": tgt_col,
                "srcLabel": src_info.get("kics_label", "vt_psn"),
                "tgtLabel": tgt_info.get("kics_label", "vt_psn"),
                "srcKey": src_info.get("kics_property", src_col),
                "tgtKey": tgt_info.get("kics_property", tgt_col),
                "edgeType": rel["relation_type"],
                "confidence": rel["confidence"],
                "description": rel["description"]
            }
            mappings.append(mapping)
        
        return mappings

    @classmethod
    def validate_mapping(cls, mapping):
        """매핑 유효성 검증"""
        required_fields = ["sourceCol", "targetCol", "srcLabel", "tgtLabel", "edgeType"]
        
        errors = []
        for field in required_fields:
            if field not in mapping or not mapping[field]:
                errors.append(f"필수 필드 누락: {field}")
        
        # KICS 라벨 검증
        valid_labels = [c["kics_label"] for c in cls._get_column_patterns().values()]
        if mapping.get("srcLabel") and mapping["srcLabel"] not in valid_labels:
            errors.append(f"유효하지 않은 소스 라벨: {mapping['srcLabel']}")
        if mapping.get("tgtLabel") and mapping["tgtLabel"] not in valid_labels:
            errors.append(f"유효하지 않은 타겟 라벨: {mapping['tgtLabel']}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
