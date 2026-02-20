"""
LLM 기반 KICS 확장 스키마 자동 매핑 서비스

CSV 데이터를 KICS 확장 모델 (4-Layer)에 자동 매핑
- Layer 분류: Case, Actor, Action, Evidence
- 엔티티 타입 결정
- 관계 추론
- ETL 설정 생성
"""

import json
from openai import OpenAI
from flask import current_app


class KICSSchemaMapper:
    """LLM 기반 KICS 확장 스키마 자동 매핑"""
    
    # 스키마 정의 (LLM 프롬프트에 사용)
    SCHEMA_DEFINITION = """
[KICS 확장 스키마 - 4 Layer]

═══════════════════════════════════════════════════════════
CASE LAYER (사건 중심)
═══════════════════════════════════════════════════════════
- Case (vt_case): 사건 - flnm, receipt_no, crime_type, damage_amount
- Investigation (vt_inv): 수사 - inv_id, investigator, department

═══════════════════════════════════════════════════════════
ACTOR LAYER (행위자)
═══════════════════════════════════════════════════════════
- Person (vt_psn): 인물 - name, id_no, role (suspect/victim/witness)
- Organization (vt_org): 조직 - org_name, org_type, member_count
- Device (vt_dev): 기기 - device_id, imei, mac_addr

═══════════════════════════════════════════════════════════
ACTION LAYER (행위/이벤트)
═══════════════════════════════════════════════════════════
- Transfer (vt_transfer): 자금이체 - from_account, to_account, amount, timestamp
- Call (vt_call): 통화 - caller, callee, duration, call_time
- Access (vt_access): 접속 - ip, url, access_time
- Message (vt_msg): 메시지 - sender, receiver, content_hash, msg_time

═══════════════════════════════════════════════════════════
EVIDENCE LAYER (증거)
═══════════════════════════════════════════════════════════
Financial:
- BankAccount (vt_bacnt): 계좌 - actno, bank, account_holder
- CryptoWallet (vt_crypto): 가상자산 - wallet_addr, asset_type

Digital:
- NetworkTrace (vt_ip): IP - ip_addr, isp
- WebTrace (vt_site): 사이트 - url, domain
- FileTrace (vt_file): 파일 - filename, file_type, hash

Communication:
- Phone (vt_telno): 전화 - telno, telecom, owner

Physical:
- ATM (vt_atm): ATM - atm_id, location
- Location (vt_loc): 위치 - address, lat, lng

═══════════════════════════════════════════════════════════
관계 타입
═══════════════════════════════════════════════════════════
Actor 관계: owns, belongs_to, controls, has_account, uses_device, accomplice_of
Action 관계: performed, from_account, to_account, caller, callee, sent_by, received_by
Evidence 관계: transferred_to, contacted, linked_to, accessed, registered_to
Case 관계: involves, involves_org, involves_device (Case는 Actor에만 연결)
"""
    
    @classmethod
    def get_client(cls):
        """OpenAI 클라이언트 생성"""
        return OpenAI(api_key=current_app.config['OPENAI_API_KEY'])
    
    @classmethod
    def analyze_csv(cls, columns, sample_rows):
        """
        CSV를 KICS 확장 스키마에 매핑
        
        Args:
            columns: 컬럼명 리스트
            sample_rows: 샘플 데이터 (최대 5개)
            
        Returns:
            {
                "layer_mapping": {...},
                "detected_action": {...},
                "relationships": [...],
                "etl_config": {...}
            }
        """
        client = cls.get_client()
        
        # 샘플 데이터 준비
        sample_preview = []
        for col in columns:
            values = [str(row.get(col, ""))[:50] for row in sample_rows[:3] if row.get(col)]
            sample_preview.append(f"- {col}: {values}")
        
        prompt = f"""
{cls.SCHEMA_DEFINITION}

═══════════════════════════════════════════════════════════
분석할 CSV
═══════════════════════════════════════════════════════════
[컬럼 및 샘플값]
{chr(10).join(sample_preview)}

═══════════════════════════════════════════════════════════
작업
═══════════════════════════════════════════════════════════
1. 각 컬럼을 적절한 Layer와 Entity에 매핑하세요
2. Action(이체/통화/접속/메시지)이 감지되면 표시하세요
3. 컬럼 간 관계를 추론하세요
4. ETL 매핑 설정을 생성하세요

═══════════════════════════════════════════════════════════
출력 (JSON만 반환)
═══════════════════════════════════════════════════════════
{{
  "layer_mapping": {{
    "컬럼명": {{
      "layer": "Case|Actor|Action|Evidence",
      "entity": "Person|Transfer|BankAccount|...",
      "label": "vt_xxx",
      "role": "source|target|property",
      "confidence": 0.0-1.0
    }}
  }},
  "detected_action": {{
    "type": "Transfer|Call|Access|Message|null",
    "timestamp_col": "시간컬럼명 또는 null",
    "amount_col": "금액컬럼명 또는 null",
    "description": "설명"
  }},
  "relationships": [
    {{"from_col": "컬럼1", "to_col": "컬럼2", "type": "관계타입", "confidence": 0.0-1.0}}
  ],
  "etl_config": {{
    "nodes": [
      {{"column": "컬럼", "label": "vt_xxx", "key": "속성키"}}
    ],
    "edges": [
      {{"source_col": "컬럼1", "target_col": "컬럼2", "edge_type": "관계타입"}}
    ]
  }}
}}
"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            content = content.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(content)
            
            # 후처리: 누락된 필드 기본값 설정
            result = cls._post_process(result, columns)
            
            return {
                "success": True,
                "mapping": result,
                "source": "llm"
            }
            
        except Exception as e:
            print(f"⚠️ LLM 스키마 매핑 오류: {e}")
            # Fallback: 규칙 기반 매핑
            return cls._fallback_mapping(columns, sample_rows)
    
    @classmethod
    def _post_process(cls, result, columns):
        """LLM 결과 후처리"""
        # layer_mapping 누락 컬럼 처리
        if "layer_mapping" not in result:
            result["layer_mapping"] = {}
        
        for col in columns:
            if col not in result["layer_mapping"]:
                result["layer_mapping"][col] = {
                    "layer": "Evidence",
                    "entity": "Unknown",
                    "label": "",
                    "role": "property",
                    "confidence": 0.3
                }
        
        # detected_action 기본값
        if "detected_action" not in result:
            result["detected_action"] = {
                "type": None,
                "timestamp_col": None,
                "amount_col": None,
                "description": "Action 미감지"
            }
        
        return result
    
    @classmethod
    def _fallback_mapping(cls, columns, sample_rows):
        """규칙 기반 Fallback 매핑 (Ontology 참조)"""
        from app.services.ontology_service import KICSCrimeDomainOntology
        
        layer_mapping = {}
        detected_action = {"type": None}
        relationships = []
        
        patterns = KICSCrimeDomainOntology.COLUMN_PATTERNS
        
        for col in columns:
            col_lower = col.lower()
            matched = False
            
            # Ontology 패턴 매칭
            for type_key, config in patterns.items():
                # 패턴 매칭 (부분 일치, 대소문자 무시)
                if any(p.lower() in col_lower for p in config["patterns"]):
                    info = cls._map_pattern_to_layer_info(type_key, config)
                    
                    # [Role Detection] 컬럼명 기반 역할 조정
                    if any(k in col_lower for k in ['출금', 'from', 'sender', '발신', 'source', 'src']):
                        info['role'] = 'source'
                    elif any(k in col_lower for k in ['입금', 'to', 'receiver', '수신', 'target', 'dst']):
                        info['role'] = 'target'
                    
                    layer_mapping[col] = info
                    
                    # Action 감지 보조
                    if type_key == 'amount':
                        detected_action["amount_col"] = col
                        if not detected_action["type"]: 
                            detected_action["type"] = "Transfer"
                    
                    matched = True
                    break
            
            if not matched:
                layer_mapping[col] = {
                    "layer": "Evidence",
                    "entity": "Unknown",
                    "label": "",
                    "role": "property"
                }

        # [Enhancement] 관계 자동 추론 (Fallback)
        # Source 역할과 Target 역할을 가진 컬럼을 찾아 연결
        sources = []
        targets = []
        
        for col, info in layer_mapping.items():
            role = info.get("role")
            if role == "source": sources.append(col)
            elif role == "target": targets.append(col)
        
        # 1. Source -> Target 연결 (기본 관계)
        import itertools
        for src in sources:
            for tgt in targets:
                # 같은 컬럼 무시
                if src == tgt: continue

                # 엔티티 타입 확인
                src_ent = layer_mapping.get(src, {}).get("entity")
                tgt_ent = layer_mapping.get(tgt, {}).get("entity")

                # Action 보정 (엔티티 기반)
                action_type = detected_action.get("type")
                if not action_type:
                    if src_ent == "Phone" and tgt_ent == "Phone":
                        action_type = "Call"
                    elif src_ent == "NetworkTrace" and tgt_ent == "NetworkTrace":
                        action_type = "Access" # IP-IP Communication
                
                # 관계 타입 결정 (엔티티 조합 우선)
                # 1. 엔티티 기반 오버라이드 (액션 타입보다 우선)
                if src_ent == "NetworkTrace" and tgt_ent == "WebTrace":
                    rel_type = "accessed"
                elif src_ent == "NetworkTrace" and tgt_ent == "NetworkTrace":
                    rel_type = "communicated_with"
                elif src_ent == "BankAccount" and tgt_ent == "BankAccount":
                    rel_type = "transferred_to"
                elif src_ent == "ContactInfo" and tgt_ent == "ContactInfo":
                    rel_type = "contacted"
                elif src_ent == "ContactInfo" and tgt_ent == "BankAccount":
                    rel_type = "linked_to"
                # 2. 액션 타입 기반
                elif action_type == "Transfer":
                    rel_type = "transferred_to"
                elif action_type == "Call":
                    rel_type = "contacted"
                elif action_type == "Message":
                    rel_type = "sent_message"
                elif action_type == "Access":
                    rel_type = "accessed"
                else:
                    rel_type = "related_to"
                
                relationships.append({
                    "from_col": src,
                    "to_col": tgt,
                    "type": rel_type,
                    "confidence": 0.5
                })
        
        return {
            "success": True,
            "mapping": {
                "layer_mapping": layer_mapping,
                "detected_action": detected_action,
                "relationships": relationships,
                "etl_config": {}
            },
            "source": "fallback"
        }

    @staticmethod
    def _map_pattern_to_layer_info(type_key, config):
        """패턴 타입을 4-Layer 구조로 변환"""
        # 간소화된 매핑 규칙
        mapping_rules = {
            "case_id": {"layer": "Case", "entity": "Case", "role": "anchor"},
            "phone": {"layer": "Evidence", "entity": "Phone", "role": "source"}, 
            "account": {"layer": "Evidence", "entity": "BankAccount", "role": "target"},
            "ip": {"layer": "Evidence", "entity": "NetworkTrace", "role": "source"},
            "site": {"layer": "Evidence", "entity": "WebTrace", "role": "target"},
            "file": {"layer": "Evidence", "entity": "FileTrace", "role": "target"},
            "person": {"layer": "Actor", "entity": "Person", "role": "source"},
            "user_id": {"layer": "Actor", "entity": "Person", "role": "source"}, # ID는 Actor 속성으로 처리
            "atm": {"layer": "Evidence", "entity": "ATM", "role": "source"}
        }
        
        defaults = mapping_rules.get(type_key)
        if defaults:
            return {
                "layer": defaults["layer"],
                "entity": defaults["entity"],
                "label": config["kics_label"],
                "role": defaults["role"]
            }
            
        # Role 자동 감지 (컬럼명 기반)
        col_lower = config.get("col_name", "").lower() # config에 col_name이 없으므로 호출측에서 넘겨줘야 함.
        # But wait, config is passed from COLUMN_PATTERNS, it doesn't have col_name.
        # I need to change the method signature or handle it in _fallback_mapping.
        
        # Let's handle it in _fallback_mapping instead.
        return {
            "layer": "Evidence",
            "entity": "Unknown",
            "label": config.get("kics_label", ""),
            "role": "property"
        }
        if config.get("is_attribute") or type_key in ['amount', 'date', 'status']:
            return {
                "layer": "Action", 
                "entity": "Unknown", 
                "label": "",
                "role": "property"
            }
            
        return {
            "layer": "Evidence",
            "entity": "Unknown",
            "label": config.get("kics_label", ""),
            "role": "property"
        }
        

    
    @classmethod
    def generate_etl_config(cls, mapping_result):
        """
        매핑 결과를 ETL 설정으로 변환
        
        Returns:
            [
                {
                    "sourceCol": "출금계좌",
                    "targetCol": "입금계좌",
                    "srcLabel": "vt_bacnt",
                    "tgtLabel": "vt_bacnt",
                    "edgeType": "transferred_to"
                },
                ...
            ]
        """
        etl_configs = []
        
        if not mapping_result.get("success"):
            return etl_configs
        
        mapping = mapping_result.get("mapping", {})
        layer_mapping = mapping.get("layer_mapping", {})
        relationships = mapping.get("relationships", [])
        
        for rel in relationships:
            from_col = rel.get("from_col")
            to_col = rel.get("to_col")
            edge_type = rel.get("type")
            
            if not all([from_col, to_col, edge_type]):
                continue
            
            from_info = layer_mapping.get(from_col, {})
            to_info = layer_mapping.get(to_col, {})
            
            etl_configs.append({
                "sourceCol": from_col,
                "targetCol": to_col,
                "srcLabel": from_info.get("label", ""),
                "tgtLabel": to_info.get("label", ""),
                "srcKey": cls._get_property_key(from_info.get("entity", "")),
                "tgtKey": cls._get_property_key(to_info.get("entity", "")),
                "edgeType": edge_type,
                "confidence": rel.get("confidence", 0.7)
            })
        
        return etl_configs
    
    @classmethod
    def _get_property_key(cls, entity_name):
        """엔티티 이름에서 기본 속성 키 결정"""
        key_map = {
            "Case": "flnm",
            "Person": "name",
            "Organization": "org_name",
            "Device": "device_id",
            "Transfer": "transfer_id",
            "Call": "call_id",
            "Access": "access_id",
            "Message": "msg_id",
            "BankAccount": "actno",
            "CryptoWallet": "wallet_addr",
            "NetworkTrace": "ip",
            "WebTrace": "url",
            "FileTrace": "filename",
            "Phone": "telno",
            "ATM": "atm_id",
            "Location": "address"
        }
        return key_map.get(entity_name, "id")
    
    @classmethod
    def detect_action_type(cls, columns, sample_rows):
        """
        CSV에서 Action 타입 자동 감지
        
        Returns:
            {
                "type": "Transfer|Call|Access|Message|None",
                "confidence": 0.0-1.0,
                "evidence": ["근거1", "근거2"]
            }
        """
        evidence = []
        
        cols_str = " ".join(columns).lower()
        
        # Transfer 감지
        if any(k in cols_str for k in ['송금', '이체', 'transfer', '출금', '입금', 'from_account', 'to_account']):
            evidence.append("계좌 이체 관련 컬럼 발견")
            return {"type": "Transfer", "confidence": 0.9, "evidence": evidence}
        
        # Call 감지
        if any(k in cols_str for k in ['통화', 'call', '발신', '수신', 'caller', 'callee', 'duration']):
            evidence.append("통화 관련 컬럼 발견")
            return {"type": "Call", "confidence": 0.9, "evidence": evidence}
        
        # Access 감지
        if any(k in cols_str for k in ['접속', 'access', 'login', 'url', 'user_agent']):
            evidence.append("접속 관련 컬럼 발견")
            return {"type": "Access", "confidence": 0.85, "evidence": evidence}
        
        # Message 감지
        if any(k in cols_str for k in ['메시지', 'message', 'sms', 'content', 'sender', 'receiver']):
            evidence.append("메시지 관련 컬럼 발견")
            return {"type": "Message", "confidence": 0.85, "evidence": evidence}
        
        return {"type": None, "confidence": 0.0, "evidence": ["Action 미감지"]}
