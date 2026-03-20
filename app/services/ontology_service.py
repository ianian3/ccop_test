"""
온톨로지 기반 그래프 분석 서비스

KICS (Korean Investigation Computer System) 기반 사이버 범죄 수사 온톨로지
"""

class KICSCrimeDomainOntology:
    """KICS 기반 한국형 사이버 범죄 온톨로지"""
    
    # 엔티티 계층 (Entity Hierarchy) - KICS 확장 모델 (4-Layer)
    ENTITIES = {
        # ═══════════════════════════════════════════════════════════════════
        # CASE LAYER - 사건 중심
        # ═══════════════════════════════════════════════════════════════════
        'Case': {
            'layer': 'Case',
            'label': 'vt_case',
            'label_ko': '사건',
            'properties': ['flnm', 'receipt_no'],
            'attributes': ['police_station', 'investigator', 'crime_type', 
                          'damage_amount', 'case_summary', 'status'],
            'role': 'anchor',
            'legal_category': '수사사건',
            'description': '수사 사건 케이스'
        },
        'Investigation': {
            'layer': 'Case',
            'label': 'vt_inv',
            'label_ko': '수사',
            'properties': ['inv_id'],
            'attributes': ['investigator', 'department', 'start_date', 'end_date'],
            'legal_category': '수사정보',
            'description': '수사 진행 정보'
        },
        
        # ═══════════════════════════════════════════════════════════════════
        # EVENT LAYER - 사건/행위 (Dynamic Ontology)
        # ═══════════════════════════════════════════════════════════════════
        'Event': {
            'layer': 'Event',
            'label': 'vt_event',
            'label_ko': '이벤트',
            'properties': ['event_id', 'event_type', 'timestamp', 'status'],
            'attributes': ['location', 'description', 'source'],
            'legal_category': '수사단서',
            'description': '시공간 정보가 포함된 동적 행위 (이체, 통화, 만남 등)'
        },
        
        # ═══════════════════════════════════════════════════════════════════
        # ACTOR LAYER - 행위자
        # ═══════════════════════════════════════════════════════════════════
        'Person': {
            'layer': 'Actor',
            'label': 'vt_psn',
            'label_ko': '인물',
            'properties': ['name', 'id_no', 'suspect_id'],
            'attributes': ['role', 'alias', 'contact'],  # role: suspect/victim/witness
            'legal_category': '피의자정보',
            'description': '인물 (용의자/피해자/참고인)'
        },
        'Persona': {
            'layer': 'Actor',
            'sublayer': 'Identity',
            'label': 'vt_persona',
            'label_ko': '페르소나',
            'properties': ['persona_id', 'persona_type', 'identifier'],
            'attributes': ['platform', 'nickname', 'profile_url'],
            'legal_category': '신원정보',
            'description': '인물의 디지털/물리적 가면 (ID, 계정 등)'
        },
        'Organization': {
            'layer': 'Actor',
            'label': 'vt_org',
            'label_ko': '조직',
            'properties': ['org_name', 'org_id'],
            'attributes': ['org_type', 'member_count', 'leader'],
            'legal_category': '피의자정보',
            'description': '조직 (범죄단체, 회사 등)'
        },
        'Device': {
            'layer': 'Actor',
            'label': 'vt_dev',
            'label_ko': '기기',
            'properties': ['device_id', 'imei', 'mac_addr'],
            'attributes': ['device_type', 'model', 'os'],
            'legal_category': '디지털증거',
            'description': '기기 (휴대폰, PC, 태블릿 등)'
        },
        
        # ═══════════════════════════════════════════════════════════════════
        # ACTION LAYER - 행위/이벤트
        # ═══════════════════════════════════════════════════════════════════
        'Transfer': {
            'layer': 'Action',
            'label': 'vt_transfer',
            'label_ko': '이체',
            'properties': ['transfer_id'],
            'attributes': ['from_account', 'to_account', 'amount', 'timestamp', 'memo'],
            'legal_category': '금융거래정보',
            'description': '자금 이체 행위'
        },
        'Call': {
            'layer': 'Action',
            'label': 'vt_call',
            'label_ko': '통화',
            'properties': ['call_id'],
            'attributes': ['caller', 'callee', 'duration', 'call_time', 'call_type'],
            'legal_category': '통신사실확인자료',
            'description': '통화 기록'
        },
        'Access': {
            'layer': 'Action',
            'label': 'vt_access',
            'label_ko': '접속',
            'properties': ['access_id'],
            'attributes': ['ip', 'url', 'access_time', 'action', 'user_agent'],
            'legal_category': '통신자료',
            'description': '웹/네트워크 접속 행위'
        },
        'Message': {
            'layer': 'Action',
            'label': 'vt_msg',
            'label_ko': '메시지',
            'properties': ['msg_id'],
            'attributes': ['sender', 'receiver', 'content_hash', 'msg_time', 'platform'],
            'legal_category': '통신사실확인자료',
            'description': '메시지 (SMS, 메신저 등)'
        },
        
        # ═══════════════════════════════════════════════════════════════════
        # EVIDENCE LAYER - 증거
        # ═══════════════════════════════════════════════════════════════════
        
        # --- Financial Evidence ---
        'BankAccount': {
            'layer': 'Evidence',
            'sublayer': 'Financial',
            'label': 'vt_bacnt',
            'label_ko': '계좌',
            'properties': ['actno', 'bacnt', 'account_no'],
            'attributes': ['bank', 'account_holder', 'account_type'],
            'legal_category': '금융거래정보'
        },
        'CryptoWallet': {
            'layer': 'Evidence',
            'sublayer': 'Financial',
            'label': 'vt_crypto',
            'label_ko': '가상자산',
            'properties': ['wallet_addr', 'crypto_addr'],
            'attributes': ['asset_type', 'exchange', 'balance'],
            'legal_category': '가상자산거래정보'
        },
        
        # --- Digital Evidence ---
        'NetworkTrace': {
            'layer': 'Evidence',
            'sublayer': 'Digital',
            'label': 'vt_ip',
            'label_ko': 'IP주소',
            'properties': ['ip', 'ip_addr'],
            'attributes': ['isp', 'country', 'city', 'vpn'],
            'legal_category': '통신자료'
        },
        'WebTrace': {
            'layer': 'Evidence',
            'sublayer': 'Digital',
            'label': 'vt_site',
            'label_ko': '사이트',
            'properties': ['url', 'site', 'domain'],
            'attributes': ['site_type', 'is_malicious'],
            'legal_category': '인터넷기록'
        },
        'FileTrace': {
            'layer': 'Evidence',
            'sublayer': 'Digital',
            'label': 'vt_file',
            'label_ko': '파일',
            'properties': ['file', 'filename', 'filepath'],
            'attributes': ['file_type', 'file_size', 'hash_md5', 'hash_sha256'],
            'legal_category': '디지털증거'
        },
        
        # --- Communication Evidence ---
        'Phone': {
            'layer': 'Evidence',
            'sublayer': 'Communication',
            'label': 'vt_telno',
            'label_ko': '전화번호',
            'properties': ['telno', 'phone'],
            'attributes': ['telecom', 'owner', 'is_burner'],
            'legal_category': '통신사실확인자료'
        },
        
        # --- Physical Evidence ---
        'ATM': {
            'layer': 'Evidence',
            'sublayer': 'Physical',
            'label': 'vt_atm',
            'label_ko': 'ATM',
            'properties': ['atm', 'atm_id'],
            'attributes': ['location', 'bank', 'address'],
            'legal_category': '물리증거'
        },
        'Location': {
            'layer': 'Evidence',
            'sublayer': 'Physical',
            'label': 'vt_loc',
            'label_ko': '위치',
            'properties': ['loc_id', 'address'],
            'attributes': ['lat', 'lng', 'place_name', 'place_type'],
            'legal_category': '위치정보'
        },
        
        # --- Vehicle Evidence (V2 추가) ---
        'Vehicle': {
            'layer': 'Evidence',
            'sublayer': 'Physical',
            'label': 'vt_vhcl',
            'label_ko': '차량',
            'properties': ['vhclno', 'vehicle_no'],
            'attributes': ['car_model', 'car_detail', 'owner_name'],
            'legal_category': '차량정보',
            'description': '차량 (번호판 기반 식별)'
        },
        'LocationEvent': {
            'layer': 'Action',
            'label': 'vt_loc_evt',
            'label_ko': '위치이벤트',
            'properties': ['loc_evt_sn'],
            'attributes': ['telno', 'lat', 'lng', 'event_type', 'timestamp'],
            'legal_category': '위치정보',
            'description': '기지국 접속 위치 기록'
        },
        'LPREvent': {
            'layer': 'Action',
            'label': 'vt_lpr_evt',
            'label_ko': 'LPR인식',
            'properties': ['rcgn_sn'],
            'attributes': ['vhclno', 'cctv_id', 'location', 'lat', 'lng', 'timestamp'],
            'legal_category': '차량정보',
            'description': '차량 번호판 인식 이벤트 (방범CCTV)'
        }
    }
    
    # Layer별 엔티티 그룹
    LAYERS = {
        'Case': ['Case', 'Investigation'],
        'Actor': ['Person', 'Organization', 'Device', 'Persona'],
        'Action': ['Transfer', 'Call', 'Access', 'Message', 'LocationEvent', 'LPREvent'],
        'Event': ['Event'], # New Dynamic Layer
        'Evidence': ['BankAccount', 'CryptoWallet', 'NetworkTrace', 'WebTrace', 
                    'FileTrace', 'Phone', 'ATM', 'Location', 'Vehicle']
    }
    
    # ═══════════════════════════════════════════════════════════════════
    # 네이밍 통합 유틸리티 (Concept Name ↔ GDB Label 양방향 매핑)
    # ═══════════════════════════════════════════════════════════════════
    
    # 개념명 → GDB 라벨 매핑 (Person → vt_psn)
    GDB_LABEL_MAP = {
        'Case': 'vt_case', 'Investigation': 'vt_inv', 'Event': 'vt_event',
        'Person': 'vt_psn', 'Persona': 'vt_persona', 'Organization': 'vt_org', 'Device': 'vt_dev',
        'Transfer': 'vt_transfer', 'Call': 'vt_call', 'Access': 'vt_access', 'Message': 'vt_msg',
        'LocationEvent': 'vt_loc_evt', 'LPREvent': 'vt_lpr_evt',
        'BankAccount': 'vt_bacnt', 'CryptoWallet': 'vt_crypto', 'NetworkTrace': 'vt_ip',
        'WebTrace': 'vt_site', 'FileTrace': 'vt_file', 'Phone': 'vt_telno',
        'ATM': 'vt_atm', 'Location': 'vt_loc', 'Vehicle': 'vt_vhcl'
    }
    
    # GDB 라벨 → 개념명 역매핑 (vt_psn → Person)
    CONCEPT_LOOKUP = {
        'vt_case': 'Case', 'vt_inv': 'Investigation', 'vt_event': 'Event',
        'vt_psn': 'Person', 'vt_persona': 'Persona', 'vt_org': 'Organization', 'vt_dev': 'Device',
        'vt_transfer': 'Transfer', 'vt_call': 'Call', 'vt_access': 'Access', 'vt_msg': 'Message',
        'vt_loc_evt': 'LocationEvent', 'vt_lpr_evt': 'LPREvent',
        'vt_bacnt': 'BankAccount', 'vt_crypto': 'CryptoWallet', 'vt_ip': 'NetworkTrace',
        'vt_site': 'WebTrace', 'vt_file': 'FileTrace', 'vt_telno': 'Phone',
        'vt_atm': 'ATM', 'vt_loc': 'Location', 'vt_vhcl': 'Vehicle'
    }
    
    # GDB 라벨 → 한국어명 매핑 (vt_psn → 인물)
    LABEL_KO_MAP = {
        'vt_case': '사건', 'vt_inv': '수사', 'vt_event': '이벤트',
        'vt_psn': '인물', 'vt_persona': '페르소나', 'vt_org': '조직', 'vt_dev': '기기',
        'vt_transfer': '이체', 'vt_call': '통화', 'vt_access': '접속', 'vt_msg': '메시지',
        'vt_loc_evt': '위치이벤트', 'vt_lpr_evt': 'LPR인식',
        'vt_bacnt': '계좌', 'vt_crypto': '가상자산', 'vt_ip': 'IP주소',
        'vt_site': '사이트', 'vt_file': '파일', 'vt_telno': '전화번호',
        'vt_atm': 'ATM', 'vt_loc': '위치', 'vt_vhcl': '차량'
    }
    
    # Layer별 GDB 라벨 그룹 (LAYERS의 GDB 라벨 버전)
    LAYERS_GDB = {
        'Case': ['vt_case', 'vt_inv'],
        'Actor': ['vt_psn', 'vt_org', 'vt_dev', 'vt_persona'],
        'Action': ['vt_transfer', 'vt_call', 'vt_access', 'vt_msg', 'vt_loc_evt', 'vt_lpr_evt'],
        'Event': ['vt_event'],
        'Evidence': ['vt_bacnt', 'vt_crypto', 'vt_ip', 'vt_site', 'vt_file', 'vt_telno', 'vt_atm', 'vt_loc', 'vt_vhcl']
    }
    
    @classmethod
    def get_gdb_label(cls, concept_name):
        """개념명을 GDB 라벨로 변환 (Person → vt_psn)"""
        return cls.GDB_LABEL_MAP.get(concept_name, concept_name)
    
    @classmethod
    def get_concept_name(cls, gdb_label):
        """GDB 라벨을 개념명으로 변환 (vt_psn → Person)"""
        return cls.CONCEPT_LOOKUP.get(gdb_label, gdb_label)
    
    @classmethod
    def get_label_ko(cls, gdb_label):
        """GDB 라벨의 한국어명 반환 (vt_psn → 인물)"""
        return cls.LABEL_KO_MAP.get(gdb_label, gdb_label)
    
    @classmethod
    def get_relationship_gdb_labels(cls, rel_name):
        """관계 정의의 domain/range를 GDB 라벨로 반환"""
        rel = cls.RELATIONSHIPS.get(rel_name)
        if not rel:
            return None, None
        domain_gdb = cls.GDB_LABEL_MAP.get(rel['domain'], rel['domain'])
        range_gdb = cls.GDB_LABEL_MAP.get(rel['range'], rel['range'])
        return domain_gdb, range_gdb
    
    # 관계 시맨틱 (Relationship Semantics) - 통합 정의
    # source_types: LLM 추론 시 컬럼 타입 조합 → 관계 타입 결정에 사용
    RELATIONSHIPS = {
        # ═══════════════════════════════════════════════════════════
        # [Layer 1 → Layer 2] Case (사건) → Actor (행위자)
        # 사건은 오직 행위자(인물/조직/기기)와만 직접 연결
        # ═══════════════════════════════════════════════════════════
        'involves': {
            'domain': 'Case',
            'range': 'Person',
            'source_types': [('case_id', 'person')],
            'semantic_relation': 'involvesPerson',
            'label_ko': '관련인물',
            'meaning': '사건에 관련된 인물',
            'legal_significance': '피의자정보'
        },
        'involves_org': {
            'domain': 'Case',
            'range': 'Organization',
            'source_types': [('case_id', 'organization'), ('case_id', 'org')],
            'semantic_relation': 'involvesOrganization',
            'label_ko': '관련조직',
            'meaning': '사건에 관련된 조직',
            'legal_significance': '피의자정보'
        },
        'involves_device': {
            'domain': 'Case',
            'range': 'Device',
            'source_types': [('case_id', 'device')],
            'semantic_relation': 'involvesDevice',
            'label_ko': '관련기기',
            'meaning': '사건에 관련된 기기',
            'legal_significance': '디지털증거'
        },
        
        # ═══════════════════════════════════════════════════════════
        # [New] Temporal Relationships (Dynamic Ontology)
        # ═══════════════════════════════════════════════════════════
        'uses_persona': {
            'domain': 'Person',
            'range': 'Persona',
            'source_types': [('person', 'persona'), ('person', 'id')],
            'semantic_relation': 'usesPersona',
            'label_ko': '사용',
            'meaning': '인물이 특정 시점에 페르소나(ID 등)를 사용',
            'legal_significance': '신원확인',
            'properties': ['start_date', 'end_date', 'is_active']
        },
        'participated_in': {
            'domain': 'Persona', # or Person
            'range': 'Event',
            'source_types': [('persona', 'event'), ('person', 'event')],
            'semantic_relation': 'participatedIn',
            'label_ko': '참여',
            'meaning': '페르소나/인물이 이벤트에 참여함',
            'legal_significance': '범죄사실',
            'properties': ['role', 'status'] # role: sender, receiver, attacker, victim
        },
        'event_involved': {
            'domain': 'Event',
            'range': 'Any', # Object or Evidence
            'source_types': [('event', 'object'), ('event', 'evidence')],
            'semantic_relation': 'involvedObject',
            'label_ko': '관련객체',
            'meaning': '이벤트에 관련된 객체나 증거',
            'legal_significance': '증거물',
            'properties': ['involvement_type']
        },
        'supported_by': {
            'domain': 'Event',
            'range': 'Evidence',
            'source_types': [('event', 'evidence')],
            'semantic_relation': 'supportedBy',
            'label_ko': '입증',
            'meaning': '이벤트 발생을 입증하는 증거',
            'legal_significance': '증거능력',
            'properties': ['confidence_score', 'verification_method']
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 4] Actor (행위자) → Evidence (증거) [소유관계]
        # 행위자가 직접 소유하거나 귀속된 증거 객체
        # ═══════════════════════════════════════════════════════════
        'owns': {
            'domain': 'Person',
            'range': 'ContactInfo',
            'source_types': [('person', 'phone')],
            'semantic_relation': 'ownsDevice',
            'label_ko': '소유',
            'meaning': '인물이 기기를 소유함',
            'legal_significance': '피의자정보',
            'properties': ['start_date', 'end_date', 'verification_source']
        },
        'owns_phone': {
            'domain': 'Person',
            'range': 'Phone',
            'source_types': [('person', 'phone'), ('user_id', 'phone')],
            'semantic_relation': 'ownsPhone',
            'label_ko': '전화소유',
            'meaning': '닉네임/인물이 전화번호를 소유함',
            'legal_significance': '통신사실확인자료'
        },
        'has_account': {
            'domain': 'Person',
            'range': 'BankAccount',
            'source_types': [('person', 'account'), ('user_id', 'account')],
            'semantic_relation': 'ownsFinancialResource',
            'label_ko': '계좌소유',
            'meaning': '닉네임/인물이 계좌를 소유함',
            'legal_significance': '금융거래정보'
        },
        'used_ip': {
            'domain': 'Person',
            'range': 'IP',
            'source_types': [('person', 'ip'), ('user_id', 'ip')],
            'semantic_relation': 'usedIPAddress',
            'label_ko': 'IP사용',
            'meaning': '닉네임/인물이 IP 주소를 사용함',
            'legal_significance': '디지털증거'
        },
        'uses_id': {
            'domain': 'Person',
            'range': 'DigitalIdentity',
            'source_types': [('person', 'user_id')],
            'semantic_relation': 'usesDigitalIdentity',
            'label_ko': 'ID사용',
            'meaning': '인물이 디지털 ID를 사용함',
            'legal_significance': '인터넷기록'
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 1 → Layer 4] Case (사건) → Evidence (증거) [사건별 증거 연결]
        # 사건에 사용된 계좌/전화/IP 증거 (핵심 수사단서)
        # ═══════════════════════════════════════════════════════════
        'eg_used_account': {
            'domain': 'Case',
            'range': 'BankAccount',
            'source_types': [('case_id', 'account')],
            'semantic_relation': 'usedAccount',
            'label_ko': '사건계좌',
            'meaning': '사건에 사용된 계좌',
            'legal_significance': '금융거래정보'
        },
        'eg_used_phone': {
            'domain': 'Case',
            'range': 'Phone',
            'source_types': [('case_id', 'phone')],
            'semantic_relation': 'usedPhone',
            'label_ko': '사건전화',
            'meaning': '사건에 사용된 전화번호',
            'legal_significance': '통신사실확인자료'
        },
        'eg_used_ip': {
            'domain': 'Case',
            'range': 'IP',
            'source_types': [('case_id', 'ip')],
            'semantic_relation': 'usedIP',
            'label_ko': '사건IP',
            'meaning': '사건에 사용된 IP 주소',
            'legal_significance': '디지털증거'
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 4 → Layer 4] Evidence (증거) Peer-to-Peer 연결
        # 증거 객체 간의 직접 연결 (핵심 분석 대상)
        # ═══════════════════════════════════════════════════════════
        'linked_to': {
            'domain': 'Any',
            'range': 'Any',
            'source_types': [('phone', 'account')],
            'semantic_relation': 'linkedResource',
            'label_ko': '연결됨',
            'meaning': '두 증거가 연결됨',
            'legal_significance': None
        },
        'accessed': {
            'domain': 'NetworkTrace',
            'range': 'WebTrace',
            'source_types': [('ip', 'site')],
            'semantic_relation': 'accessedSite',
            'label_ko': '접속',
            'meaning': 'IP에서 사이트에 접속함',
            'legal_significance': '통신자료'
        },
        'communicated_with': {
            'domain': 'NetworkTrace',
            'range': 'NetworkTrace',
            'source_types': [('ip', 'ip'), ('src_ip', 'dst_ip')],
            'semantic_relation': 'communicatedWith',
            'label_ko': '통신',
            'meaning': 'IP 간 통신',
            'legal_significance': '통신자료'
        },
        
        # ═══════════════════════════════════════════════════════════
        # 간접 관계 (Phase 1 확장)
        # ═══════════════════════════════════════════════════════════
        'transferred_to': {
            'domain': 'BankAccount',
            'range': 'BankAccount',
            'source_types': [('from_account', 'to_account'), ('sender_account', 'receiver_account')],
            'semantic_relation': 'transferredFundsTo',
            'label_ko': '이체',
            'meaning': '계좌에서 다른 계좌로 자금 이체',
            'legal_significance': '금융거래정보',
            'properties': ['amount', 'transfer_date', 'hop_level'],
            # 추론 메타 속성
            'transitive': True,  # A→B→C 이면 A→C 추론 가능
            'inference_confidence': 0.85
        },
        'registered_to': {
            'domain': 'ContactInfo',
            'range': 'Person',
            'source_types': [('phone', 'owner'), ('phone', 'registrant')],
            'semantic_relation': 'registeredOwner',
            'label_ko': '명의자',
            'meaning': '전화번호의 등록 명의자',
            'legal_significance': '통신사실확인자료'
        },
        'contacted': {
            'domain': 'ContactInfo',
            'range': 'ContactInfo',
            'source_types': [('caller', 'callee'), ('from_phone', 'to_phone')],
            'semantic_relation': 'calledNumber',
            'label_ko': '통화',
            'meaning': '전화번호 간 통화 기록',
            'legal_significance': '통신사실확인자료',
            'properties': ['call_time', 'duration', 'call_type']
        },
        'shared_resource': {
            'domain': 'Case',
            'range': 'Case',
            'source_types': [],
            'semantic_relation': 'sharesResource',
            'label_ko': '공유증거',
            'meaning': '두 사건이 동일 증거(계좌/전화 등)를 공유',
            'legal_significance': None,
            'inferred': True  # 추론으로만 생성
        },
        'same_organization': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [],
            'semantic_relation': 'belongsToSameOrg',
            'label_ko': '동일조직',
            'meaning': '동일 범죄 조직에 소속 추정',
            'legal_significance': '피의자정보',
            'inferred': True  # 추론으로만 생성
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 2] Actor 간 관계 (KICS 확장)
        # ═══════════════════════════════════════════════════════════
        'belongs_to': {
            'domain': 'Person',
            'range': 'Organization',
            'source_types': [('person', 'org'), ('member', 'organization')],
            'semantic_relation': 'belongsToOrganization',
            'label_ko': '소속',
            'meaning': '인물이 조직에 소속됨',
            'legal_significance': '피의자정보',
            'properties': ['role', 'start_date', 'end_date'] # Temporal extension
        },
        'controls': {
            'domain': 'Person',
            'range': 'BankAccount',
            'source_types': [('controller', 'account'), ('실소유자', 'account')],
            'semantic_relation': 'controlsAccount',
            'label_ko': '실지배',
            'meaning': '인물이 계좌를 실질적으로 지배함 (명의와 무관)',
            'legal_significance': '금융거래정보',
            # 추론 메타 속성
            'transitive': True,  # A가 B를 지배, B가 C를 지배 → A가 C를 지배
            'inverse': 'controlled_by',
            'inference_confidence': 0.80
        },
        'accomplice_of': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [],
            'semantic_relation': 'accompliceOf',
            'label_ko': '공범',
            'meaning': '공범 관계',
            'legal_significance': '피의자정보',
            'inferred': True
        },
        'uses_device': {
            'domain': 'Person',
            'range': 'Device',
            'source_types': [('person', 'device'), ('user', 'device')],
            'semantic_relation': 'usesDevice',
            'label_ko': '기기사용',
            'meaning': '인물이 기기를 사용함',
            'legal_significance': '디지털증거'
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 3] Actor → Action (행위 수행)
        # [Layer 3 → Layer 4] Action → Evidence (행위가 사용한 증거)
        # ═══════════════════════════════════════════════════════════
        'performed': {
            'domain': 'Person',
            'range': 'Action',
            'source_types': [('actor', 'action'), ('person', 'transfer'), ('person', 'call')],
            'semantic_relation': 'performedAction',
            'label_ko': '수행',
            'meaning': '인물이 행위를 수행함',
            'legal_significance': None
        },
        'from_account': {
            'domain': 'BankAccount',
            'range': 'Transfer',
            'source_types': [('from_account', 'transfer'), ('출금계좌', '이체')],
            'semantic_relation': 'withdrawnFrom',
            'label_ko': '출금계좌',
            'meaning': '이체의 출금 계좌',
            'legal_significance': '금융거래정보'
        },
        'to_account': {
            'domain': 'Transfer',
            'range': 'BankAccount',
            'source_types': [('transfer', 'to_account'), ('이체', '입금계좌')],
            'semantic_relation': 'depositedTo',
            'label_ko': '입금계좌',
            'meaning': '이체의 입금 계좌',
            'legal_significance': '금융거래정보'
        },
        'caller': {
            'domain': 'Phone',
            'range': 'Call',
            'source_types': [('caller', 'call'), ('발신번호', '통화')],
            'semantic_relation': 'calledFrom',
            'label_ko': '발신',
            'meaning': '통화의 발신 번호',
            'legal_significance': '통신사실확인자료'
        },
        'callee': {
            'domain': 'Call',
            'range': 'Phone',
            'source_types': [('call', 'callee'), ('통화', '수신번호')],
            'semantic_relation': 'calledTo',
            'label_ko': '수신',
            'meaning': '통화의 수신 번호',
            'legal_significance': '통신사실확인자료'
        },
        'accessed_from': {
            'domain': 'Access',
            'range': 'NetworkTrace',
            'source_types': [('access', 'ip'), ('접속', 'ip')],
            'semantic_relation': 'accessedFromIP',
            'label_ko': '접속IP',
            'meaning': '접속의 출발 IP',
            'legal_significance': '통신자료'
        },
        'accessed_to': {
            'domain': 'Access',
            'range': 'WebTrace',
            'source_types': [('access', 'url'), ('접속', 'site')],
            'semantic_relation': 'accessedToSite',
            'label_ko': '접속대상',
            'meaning': '접속의 목적지 사이트',
            'legal_significance': '인터넷기록'
        },
        'sent_msg': {
            'domain': 'Phone',
            'range': 'Message',
            'source_types': [('sender', 'message'), ('발신번호', '문자')],
            'semantic_relation': 'sentMessage',
            'label_ko': '발신',
            'meaning': '메시지 발신 번호',
            'legal_significance': '통신사실확인자료'
        },
        'received_by': {
            'domain': 'Message',
            'range': 'Person',
            'source_types': [('message', 'receiver'), ('메시지', '수신자')],
            'semantic_relation': 'receivedBy',
            'label_ko': '수신자',
            'meaning': '메시지 수신자',
            'legal_significance': '통신사실확인자료'
        },
        # Note: Case→Action 직접 연결 제거됨 (4계층 모델 준수)
        # Case는 Actor를 통해서만 Action에 연결됨:
        # Case → Actor (involves) → Action (performed)
        
        # ═══════════════════════════════════════════════════════════
        # [Enhancement] 보강 엣지 — 교차 도메인 관계
        # ═══════════════════════════════════════════════════════════
        'related_case': {
            'domain': 'Case',
            'range': 'Case',
            'semantic_relation': 'relatedCase',
            'label_ko': '관련사건',
            'meaning': '공유 증거(계좌/전화) 기반 사건 연결',
            'inference': True,
            'confidence': 0.75,
            'legal_significance': '연쇄사건 추적'
        },
        'belongs_to': {
            'domain': 'BankAccount',
            'range': 'Organization',
            'source_types': [('account', 'org'), ('계좌', '기관')],
            'semantic_relation': 'belongsToOrg',
            'label_ko': '소속기관',
            'meaning': '계좌 소속 금융기관',
            'legal_significance': '금융거래정보'
        },
        'works_at': {
            'domain': 'Person',
            'range': 'Organization',
            'source_types': [('person', 'org'), ('인물', '조직')],
            'semantic_relation': 'worksAt',
            'label_ko': '소속',
            'meaning': '인물의 소속 조직',
            'legal_significance': '내부자 식별'
        },
        'resolved_to': {
            'domain': 'NetworkTrace',
            'range': 'WebTrace',
            'semantic_relation': 'resolvedTo',
            'label_ko': 'DNS해석',
            'meaning': 'IP → 도메인 연결',
            'inference': True,
            'legal_significance': '네트워크 추적'
        },
        'mentions_account': {
            'domain': 'Message',
            'range': 'BankAccount',
            'semantic_relation': 'mentionsAccount',
            'label_ko': '계좌언급',
            'meaning': '메시지 내 계좌번호 언급',
            'inference': True,
            'confidence': 0.85,
            'legal_significance': '보이스피싱 핵심증거'
        },
    }
    
    @classmethod
    def get_relationship_rules(cls):
        """LLM 추론용 관계 규칙 반환 (source_types → relation_type)"""
        rules = {}
        for rel_type, rel_def in cls.RELATIONSHIPS.items():
            for source_types in rel_def.get('source_types', []):
                rules[source_types] = {
                    'type': rel_type,
                    'description': rel_def.get('meaning', ''),
                    'legal_significance': rel_def.get('legal_significance')
                }
        return rules

    # 컬럼 타입 추론 패턴 (Centralized Definition)
    COLUMN_PATTERNS = {
        "case": {
            "patterns": ["사건", "case", "사건번호", "접수번호"],
            "kics_label": "vt_case",
            "kics_property": "flnm",
            "description": "사건번호/관리번호"
        },
        "phone": {
            "patterns": ["전화", "phone", "telno", "tel", "mobile", "휴대폰", "연락처", "발신번호", "수신번호"],
            "kics_label": "vt_telno",
            "kics_property": "telno",
            "description": "전화번호"
        },
        "account": {
            "patterns": ["actno", "계좌", "account", "bacnt", "bank", "은행"],
            "kics_label": "vt_bacnt",
            "kics_property": "actno",
            "description": "계좌번호"
        },
        "ip": {
            "patterns": ["IP", "ip주소", "ip_addr", "ipaddr", "아이피", "ip_address"],
            "kics_label": "vt_ip",
            "kics_property": "ip",
            "description": "IP 주소"
        },
        "site": {
            "patterns": ["사이트", "site", "url", "domain", "웹", "주소", "링크"],
            "kics_label": "vt_site",
            "kics_property": "site",
            "description": "웹사이트/URL"
        },
        "file": {
            "patterns": ["파일", "file", "filename", "filepath", "첨부"],
            "kics_label": "vt_file",
            "kics_property": "file",
            "description": "파일"
        },
        "suspect": {
            "patterns": ["피의자", "suspect", "용의자", "범인", "target", "사용자", "명의자", "flnm", "rrno"],
            "kics_label": "vt_psn",
            "kics_property": "id",
            "description": "피의자 식별자 (ID/주민번호)"
        },
        "person": {
            "patterns": ["이름", "name", "성명", "피해자", "용의자", "인물"],
            "kics_label": "vt_psn",
            "kics_property": "name",
            "description": "인물"
        },
        "atm": {
            "patterns": ["atm", "atm_id", "현금인출기"],
            "kics_label": "vt_atm",
            "kics_property": "atm",
            "description": "ATM"
        },
        # === 속성 타입 (노드가 아닌 것들) ===
        "sequence": {
            "patterns": ["순번", "번호", "seq", "index", "idx", "no"],
            "kics_label": "",  # 빈 값 = 노드 아님
            "kics_property": "seq",
            "description": "순서 번호",
            "is_attribute": True
        },
        "date": {
            "patterns": ["rmt_ymdhm", "일시", "date", "시간", "time", "발생일시", "거래일시", "통화일시", "접수일자", "발생일", "이체일시", "bgng_ymdhm"],
            "kics_label": "common",
            "kics_property": "event_date",
            "description": "사건/이벤트 발생 일시"
        },
        "amount": {
            "patterns": ["dpst_amt", "금액", "amount", "이체금액", "거래금액", "피해금액"],
            "kics_label": "vt_event",
            "kics_property": "amount",
            "description": "이체/피해 금액"
        },
        "crime": {
            "patterns": ["죄명", "범죄유형", "crime", "범죄유형명", "사건개요"],
            "kics_label": "vt_case",
            "kics_property": "crime",
            "description": "범죄 유형/죄명"
        },
        "sender": {
            "patterns": ["dpstr", "송금", "송금계좌", "출금", "출금계좌", "sender", "보낸사람", "from"],
            "kics_label": "vt_transfer",
            "kics_property": "from_account",
            "description": "이체 출발 계좌"
        },
        "receiver": {
            "patterns": ["rlt_actno", "rlt_dpstr", "수취", "수금", "수취계좌", "입금", "입금계좌", "receiver", "받는사람", "to"],
            "kics_label": "vt_transfer",
            "kics_property": "to_account",
            "description": "이체 도착 계좌"
        },
        "caller": {
            "patterns": ["발신", "caller", "발신번호", "발신자", "dsptch_no"],
            "kics_label": "vt_telno",
            "kics_property": "telno",
            "description": "발신 번호",
            "is_attribute": False
        },
        "callee": {
            "patterns": ["수신", "callee", "수신번호", "수신자", "rcptn_no"],
            "kics_label": "vt_telno",
            "kics_property": "telno",
            "description": "수신 번호",
            "is_attribute": False
        },
        "duration": {
            "patterns": ["통화시간", "duration", "시간"],
            "kics_label": "",
            "kics_property": "duration",
            "description": "통화 시간 (초)",
            "is_attribute": True
        },
        "nickname": {
            "patterns": ["닉네임", "nickname", "nick", "별명"],
            "kics_label": "vt_psn",
            "kics_property": "nickname",
            "description": "닉네임/별명",
            "is_attribute": False
        },
        "message": {
            "patterns": ["메시지", "message", "내용", "content", "msg", "문자내용", "채팅내용", "메모"],
            "kics_label": "vt_msg",
            "kics_property": "content",
            "description": "메시지 내용",
            "is_attribute": False
        },
        "org": {
            "patterns": ["조직", "org", "기관", "organization", "company", "회사", "법인", "은행명"],
            "kics_label": "vt_org",
            "kics_property": "org_name",
            "description": "조직/기관명",
            "is_attribute": False
        },
        "vehicle": {
            "patterns": ["차량", "vehicle", "차량번호", "vhclno", "car", "번호판"],
            "kics_label": "vt_vhcl",
            "kics_property": "vhclno",
            "description": "차량 번호",
            "is_attribute": False
        },
        "lat": {
            "patterns": ["위도", "lat", "latitude", "bsst_lat"],
            "kics_label": "",
            "kics_property": "lat",
            "description": "위도 좌표",
            "is_attribute": True
        },
        "lng": {
            "patterns": ["경도", "lng", "longitude", "lon", "bsst_lot"],
            "kics_label": "",
            "kics_property": "lng",
            "description": "경도 좌표",
            "is_attribute": True
        },
    }

    # ─────────────────────────────────────────────
    # 온톨로지 컬럼 타입 → RDB col_map 키 매핑
    # rdb_service.py에서 이 매핑을 참조하여
    # COLUMN_PATTERNS.type → col_map[key]로 변환
    # ─────────────────────────────────────────────
    COLUMN_TYPE_TO_RDB = {
        'case_id': 'case',
        'case': 'case',          # COLUMN_PATTERNS key = 'case'
        'suspect': 'suspect',    # COLUMN_PATTERNS key = 'suspect'
        'phone': 'phone',
        'account': 'account',
        'ip': 'ip',
        'user_id': 'suspect',
        'person': 'name',
        'nickname': 'nickname',
        'date': 'date',
        'amount': 'amount',
        'crime': 'crime',
        'sender': 'sender',
        'receiver': 'receiver',
        'caller': 'caller',
        'callee': 'callee',
        'duration': 'duration',
        'site': 'site',
        'file': 'file',
        'message': 'message',
        'org': 'org',
        'vehicle': 'vehicle',
        'lat': 'lat',
        'lng': 'lng',
    }
    
    # 추론 규칙 (KICS-Specific Inference Rules)
    INFERENCE_RULES = [
        {
            'name': 'OrganizedCrime',
            'pattern': 'shared_resource_usage',
            'threshold': 3,
            'description': '동일 전화번호가 3건 이상 사건에서 사용 → 조직범죄 가능',
            'confidence': 0.80,
            'legal_basis': '범죄수익은닉규제법'
        },
        {
            'name': 'MoneyLaundering',
            'pattern': 'multi_hop_transfer',
            'threshold': 3,
            'description': '3단계 이상 계좌이체 → 자금세탁 의심',
            'confidence': 0.75,
            'legal_basis': '특정금융거래정보법'
        },
        {
            'name': 'Accomplice',
            'pattern': 'shared_contacts',
            'threshold': 5,
            'description': '2인 이상이 동일 전화번호 5건+ 공유 통화 → 공범 의심',
            'confidence': 0.70,
            'legal_basis': '형법 제30조 공동정범'
        },
        {
            'name': 'RapidTransfer',
            'pattern': 'high_frequency_transfer',
            'threshold': 10,
            'description': '1시간 내 10건+ 이체 → 대포통장 의심',
            'confidence': 0.85,
            'legal_basis': '전자금융거래법'
        },
        {
            'name': 'NightActivity',
            'pattern': 'night_time_activity',
            'threshold': 3,
            'description': '00~06시 사이 3건+ 이체/통화 → 야간 범행 패턴',
            'confidence': 0.65,
            'legal_basis': '야간 범행 가중처벌'
        },
        {
            'name': 'CrossDomainLink',
            'pattern': 'ip_account_phone_correlation',
            'threshold': 2,
            'description': '동일 IP에서 다수 계좌+전화 접속 → 총책 의심',
            'confidence': 0.80,
            'legal_basis': '정보통신망법'
        },
    ]


class OntologyEnricher:
    """ETL 시 KICS 온톨로지 메타데이터 추가"""
    
    @staticmethod
    def enrich_node(node_label, properties):
        """KICS 기반 온톨로지 매핑"""
        ontology_type = "Unknown"
        entity_subtype = None
        domain_concept = "알 수 없음"
        legal_category = None
        
        # === 사건 (Case) ===
        if 'flnm' in properties or 'receipt_no' in properties:
            ontology_type = "Case"
            entity_subtype = "Case"
            domain_concept = "사건"
            legal_category = "수사사건"
        
        # === 이벤트 (Event) — 우선순위 높음 (Fix #3) ===
        elif 'event_type' in properties or 'event_id' in properties or 'transfer_id' in properties or 'call_id' in properties:
            ontology_type = "Event"
            entity_subtype = "Event"
            domain_concept = "이벤트"
            # event_type에 따라 법적 카테고리 세분화
            evt = properties.get('event_type', '')
            if evt == 'transfer':
                legal_category = "금융거래정보"
                domain_concept = "이체이벤트"
            elif evt == 'call':
                legal_category = "통신사실확인자료"
                domain_concept = "통화이벤트"
            elif evt == 'access':
                legal_category = "통신자료"
                domain_concept = "접속이벤트"
            else:
                legal_category = "수사단서"
        
        # === 금융증거 (Financial Evidence) ===
        elif 'actno' in properties or 'bacnt' in properties or 'account_no' in properties:
            ontology_type = "FinancialEvidence"
            entity_subtype = "BankAccount"
            domain_concept = "계좌"
            legal_category = "금융거래정보"
        
        elif 'wallet_addr' in properties or 'crypto_addr' in properties:
            ontology_type = "FinancialEvidence"
            entity_subtype = "CryptoWallet"
            domain_concept = "가상자산"
            legal_category = "가상자산거래정보"
        
        # === 디지털증거 (Digital Evidence) ===
        elif 'ip' in properties or 'ip_addr' in properties or 'ipaddr' in properties:
            ontology_type = "DigitalEvidence"
            entity_subtype = "NetworkTrace"
            domain_concept = "IP주소"
            legal_category = "통신자료"
        
        elif 'url' in properties or 'site' in properties or 'domain' in properties:
            ontology_type = "DigitalEvidence"
            entity_subtype = "WebTrace"
            domain_concept = "사이트"
            legal_category = "인터넷기록"
        
        elif 'file' in properties or 'filename' in properties or 'filepath' in properties:
            ontology_type = "DigitalEvidence"
            entity_subtype = "FileTrace"
            domain_concept = "파일"
            legal_category = "디지털증거"
        
        # === 용의자/연락처 (Suspect) ===
        elif 'telno' in properties or 'phone' in properties:
            ontology_type = "Suspect"
            entity_subtype = "ContactInfo"
            domain_concept = "전화번호"
            legal_category = "통신사실확인자료"
        
        elif 'name' in properties or 'suspect' in properties:
            ontology_type = "Suspect"
            entity_subtype = "Suspect"
            domain_concept = "용의자"
            legal_category = "피의자정보"
        
        elif 'id' in properties or 'user_id' in properties or 'nickname' in properties:
            ontology_type = "Suspect"
            entity_subtype = "DigitalIdentity"
            domain_concept = "디지털ID"
            legal_category = "인터넷기록"

        # === 물리증거 (Physical Evidence) ===
        elif 'atm' in properties or 'atm_id' in properties:
            ontology_type = "PhysicalEvidence"
            entity_subtype = "ATM"
            domain_concept = "ATM"
            legal_category = "물리증거"
        
        # 메타데이터 추가
        enriched_props = properties.copy()
        enriched_props['ontology_type'] = ontology_type
        enriched_props['entity_subtype'] = entity_subtype if entity_subtype else ontology_type
        enriched_props['domain_concept'] = domain_concept
        enriched_props['legal_category'] = legal_category
        enriched_props['kics_compliant'] = True
        
        return enriched_props
    
    @staticmethod
    def enrich_edge(edge_type, properties):
        """KICS 기반 엣지 온톨로지 매핑"""
        semantic_relation = edge_type
        domain_meaning = edge_type
        legal_significance = None
        
        # KICS 엣지 타입별 의미론적 관계 매핑
        EDGE_SEMANTICS = {
            'digital_trace': {
                'semantic_relation': 'investigatesDigitalTrace',
                'domain_meaning': '디지털 흔적 조사',
                'legal_significance': '디지털증거'
            },
            'used_account': {
                'semantic_relation': 'usedFinancialResource',
                'domain_meaning': '금융 계좌 사용',
                'legal_significance': '금융거래정보'
            },
            'used_crypto': {
                'semantic_relation': 'usedCryptoAsset',
                'domain_meaning': '가상자산 사용',
                'legal_significance': '가상자산거래정보'
            },
            'used_phone': {
                'semantic_relation': 'usedCommunicationDevice',
                'domain_meaning': '전화번호 사용',
                'legal_significance': '통신사실확인자료'
            },
            'accessed_ip': {
                'semantic_relation': 'accessedFromIP',
                'domain_meaning': 'IP 접속',
                'legal_significance': '통신자료'
            },
            'participated_in': {
                'semantic_relation': 'participatedInEvent',
                'domain_meaning': '이벤트 참여',
                'legal_significance': '범죄사실'
            },
            'event_involved': {
                'semantic_relation': 'involvedObject',
                'domain_meaning': '이벤트 관련 객체',
                'legal_significance': '증거물'
            },
            'supported_by': {
                'semantic_relation': 'supportedByEvidence',
                'domain_meaning': '증거에 의한 입증',
                'legal_significance': '증거능력'
            },
            'visited_site': {
                'semantic_relation': 'visitedWebsite',
                'domain_meaning': '사이트 방문',
                'legal_significance': '인터넷기록'
            }
        }
        
        if edge_type in EDGE_SEMANTICS:
            semantic_relation = EDGE_SEMANTICS[edge_type]['semantic_relation']
            domain_meaning = EDGE_SEMANTICS[edge_type]['domain_meaning']
            legal_significance = EDGE_SEMANTICS[edge_type]['legal_significance']
        
        # 메타데이터 추가
        enriched_props = properties.copy()
        enriched_props['semantic_relation'] = semantic_relation
        enriched_props['domain_meaning'] = domain_meaning
        if legal_significance:
            enriched_props['legal_significance'] = legal_significance
        enriched_props['kics_compliant'] = True
        
        return enriched_props


class SemanticAnalyzer:
    """그래프 패턴의 의미론적 해석"""
    
    @staticmethod
    def analyze(elements, context_texts):
        """온톨로지 기반 분석"""
        
        # 1. 개념 분류
        concepts = SemanticAnalyzer._classify_concepts(elements)
        
        # 2. 관계 해석
        relationships = SemanticAnalyzer._interpret_relationships(elements)
        
        # 3. 패턴 탐지
        patterns = SemanticAnalyzer._detect_patterns(elements, concepts)
        
        return {
            'concepts': concepts,
            'relationships': relationships,
            'patterns': patterns,
            'summary': SemanticAnalyzer._generate_summary(concepts, relationships, patterns)
        }
    
    @staticmethod
    def _classify_concepts(elements):
        """노드를 도메인 개념으로 분류"""
        concepts = {}
        concept_counts = {}
        
        for elem in elements:
            if elem['group'] == 'nodes':
                node_id = elem['data']['id']
                props = elem['data'].get('props', {})
                
                # 온톨로지 매핑
                concept = 'Unknown'
                if 'flnm' in props:
                    concept = 'Case'
                # Fix #1: Event 노드 인식 추가
                elif 'event_type' in props or 'event_id' in props:
                    concept = 'Event'
                elif 'telno' in props or 'phone' in props:
                    concept = 'Suspect'
                elif 'file' in props or 'site' in props or 'url' in props or 'ip' in props:
                    concept = 'DigitalEvidence'
                elif 'actno' in props or 'bacnt' in props or 'account' in props:
                    concept = 'FinancialEvidence'
                
                concepts[node_id] = concept
                concept_counts[concept] = concept_counts.get(concept, 0) + 1
        
        return {
            'mapping': concepts,
            'counts': concept_counts
        }
    
    @staticmethod
    def _interpret_relationships(elements):
        """관계의 의미 해석"""
        relationships = []
        
        for elem in elements:
            if elem['group'] == 'edges':
                edge_type = elem['data'].get('label', 'unknown')
                edge_props = elem['data'].get('props', {})
                
                if edge_type in KICSCrimeDomainOntology.RELATIONSHIPS:
                    rel_info = KICSCrimeDomainOntology.RELATIONSHIPS[edge_type]
                    
                    interpretation = {
                        'type': edge_type,
                        'meaning': rel_info['meaning'],
                        'properties': {k: v for k, v in edge_props.items() 
                                      if k not in ['source', 'updated']}
                    }
                    relationships.append(interpretation)
        
        return relationships
    
    @staticmethod
    def _detect_patterns(elements, concepts):
        """의미 있는 그래프 패턴 탐지"""
        patterns = []
        
        # 패턴 1: 공유 리소스 (동일 전화번호/계좌를 여러 사건에서 사용)
        resource_usage = {}  # {resource_id: [case_ids]}
        
        for elem in elements:
            if elem['group'] == 'edges':
                source = elem['data']['source']
                target = elem['data']['target']
                
                # Case -> Resource 패턴
                if concepts['mapping'].get(source) == 'Case':
                    resource = target
                    if resource not in resource_usage:
                        resource_usage[resource] = []
                    resource_usage[resource].append(source)
        
        # 복수 사용 리소스 탐지
        for resource, cases in resource_usage.items():
            if len(cases) > 1:
                resource_concept = concepts['mapping'].get(resource, 'Unknown')
                patterns.append({
                    'type': 'SharedResource',
                    'resource': resource,
                    'resource_type': resource_concept,
                    'cases': cases,
                    'count': len(cases),
                    'implication': f'{len(cases)}개 사건에서 동일 {resource_concept} 사용 - 조직 범죄 또는 연관 사건 가능성'
                })
        
        return patterns
    
    @staticmethod
    def _generate_summary(concepts, relationships, patterns):
        """분석 요약 생성"""
        summary_lines = []
        
        # 개념 요약
        if concepts['counts']:
            summary_lines.append("[엔티티 분류]")
            for concept, count in concepts['counts'].items():
                if concept != 'Unknown':
                    label = KICSCrimeDomainOntology.ENTITIES.get(concept, {}).get('label_ko', concept)
                    summary_lines.append(f"- {label}: {count}개")
        
        # 관계 요약
        if relationships:
            summary_lines.append("\n[관계 분석]")
            rel_types = {}
            for rel in relationships:
                rel_type = rel['type']
                if rel_type not in rel_types:
                    rel_types[rel_type] = []
                rel_types[rel_type].append(rel)
            
            for rel_type, rels in rel_types.items():
                meaning = KICSCrimeDomainOntology.RELATIONSHIPS.get(rel_type, {}).get('meaning', rel_type)
                summary_lines.append(f"- {meaning}: {len(rels)}건")
        
        # 패턴 요약
        if patterns:
            summary_lines.append("\n[탐지된 패턴]")
            for pattern in patterns:
                summary_lines.append(f"- {pattern['implication']}")
        
        return "\n".join(summary_lines)
