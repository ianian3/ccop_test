"""
범죄 패턴 템플릿 라이브러리

KICS 기반 사이버 범죄 패턴 정의 및 관리
"""

class CrimePattern:
    """범죄 패턴 정의 클래스"""
    
    def __init__(self, pattern_id, name, description, required_nodes, 
                 required_edges, optional_nodes=None, scoring=None, cypher_query=None):
        self.pattern_id = pattern_id
        self.name = name
        self.description = description
        self.required_nodes = required_nodes
        self.required_edges = required_edges
        self.optional_nodes = optional_nodes or {}
        self.scoring = scoring or {
            "required_match": 0.7,
            "optional_bonus": 0.3,
            "min_threshold": 0.85
        }
        self.cypher_query = cypher_query or ""
    
    def to_dict(self):
        """패턴을 딕셔너리로 변환"""
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "required_nodes": self.required_nodes,
            "required_edges": self.required_edges,
            "optional_nodes": self.optional_nodes,
            "scoring": self.scoring,
            "cypher_query": self.cypher_query
        }


class PatternLibrary:
    """범죄 패턴 라이브러리 관리"""
    
    # 패턴 정의
    PATTERNS = {
        # 1. 몸캠피싱 (Bodycamp Phishing)
        "bodycamp_phishing": CrimePattern(
            pattern_id="bodycamp_phishing_v1",
            name="몸캠피싱",
            description="성인 사이트를 통한 영상 협박 사기. 피해자를 성인 사이트로 유인하여 영상을 녹화한 후 협박하여 금전 요구",
            required_nodes={
                "case": {
                    "label": "vt_flnm",
                    "properties": {},
                    "description": "사건 정보"
                },
                "site": {
                    "label": "vt_site",
                    "properties": {},
                    "description": "성인 사이트 또는 채팅 사이트"
                },
                "file": {
                    "label": "vt_file",
                    "properties": {},
                    "description": "녹화된 영상 파일"
                },
                "account": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "범죄자 계좌"
                }
            },
            required_edges=[
                {
                    "from": "case",
                    "to": "site",
                    "type": "digital_trace",
                    "description": "사이트 접속 흔적"
                },
                {
                    "from": "case",
                    "to": "file",
                    "type": "related_to",
                    "description": "파일 관련성"
                },
                {
                    "from": "case",
                    "to": "account",
                    "type": "used_account",
                    "description": "범죄 수익 계좌"
                }
            ],
            optional_nodes={
                "ip": {
                    "label": "vt_ip",
                    "weight": 0.2,
                    "description": "접속 IP 주소"
                },
                "phone": {
                    "label": "vt_telno",
                    "weight": 0.1,
                    "description": "범죄자 연락처"
                }
            },
            scoring={
                "required_match": 0.7,
                "optional_bonus": 0.3,
                "min_threshold": 0.85
            },
            cypher_query="""
MATCH (c:vt_flnm)-[:related_to]->(f:vt_file)
MATCH (c)-[:digital_trace]->(s:vt_site)
MATCH (c)-[:used_account]->(a:vt_bacnt)
WHERE 
  f.filename =~ '.*(avi|mp4|mov|wmv).*'
  AND (s.site CONTAINS 'chat' OR s.site CONTAINS 'cam' OR s.site CONTAINS '만남')
RETURN 
  c.flnm AS case_id, 
  s.site AS site_url, 
  f.filename AS video_file, 
  a.actno AS account_no,
  '몸캠피싱 의심' AS pattern_name
"""
        ),
        
        # 2. 보이스피싱 (Voice Phishing)
        "voice_phishing": CrimePattern(
            pattern_id="voice_phishing_v1",
            name="보이스피싱",
            description="전화를 통한 금융 사기. 금융기관이나 공공기관을 사칭하여 금전 요구",
            required_nodes={
                "case": {
                    "label": "vt_flnm",
                    "properties": {},
                    "description": "사건 정보"
                },
                "phone": {
                    "label": "vt_telno",
                    "properties": {},
                    "description": "범죄자 전화번호"
                },
                "account": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "범죄자 계좌"
                }
            },
            required_edges=[
                {
                    "from": "case",
                    "to": "phone",
                    "type": "used_phone",
                    "description": "전화 사용"
                },
                {
                    "from": "case",
                    "to": "account",
                    "type": "used_account",
                    "description": "범죄 수익 계좌"
                }
            ],
            optional_nodes={
                "ip": {
                    "label": "vt_ip",
                    "weight": 0.15,
                    "description": "통화 연결 IP"
                },
                "site": {
                    "label": "vt_site",
                    "weight": 0.15,
                    "description": "피싱 사이트"
                }
            },
            scoring={
                "required_match": 0.75,
                "optional_bonus": 0.25,
                "min_threshold": 0.80
            },
            cypher_query="""
MATCH (c:vt_flnm)-[:used_phone]->(p:vt_telno)
MATCH (c)-[:used_account]->(a:vt_bacnt)
RETURN 
  c.flnm AS case_id, 
  p.telno AS phone_number,
  a.actno AS account_no,
  '보이스피싱 의심' AS pattern_name
"""
        ),
        
        # 3. 전화금융사기 (Phone Financial Fraud)
        "phone_financial_fraud": CrimePattern(
            pattern_id="phone_financial_fraud_v1",
            name="전화금융사기",
            description="전화를 이용한 금융 사기. 여러 계좌로 금전 이체",
            required_nodes={
                "case": {
                    "label": "vt_flnm",
                    "properties": {},
                    "description": "사건 정보"
                },
                "phone": {
                    "label": "vt_telno",
                    "properties": {},
                    "description": "범죄자 전화"
                },
                "account1": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "1차 계좌"
                },
                "account2": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "2차 계좌 (자금 세탁)"
                }
            },
            required_edges=[
                {
                    "from": "case",
                    "to": "phone",
                    "type": "used_phone",
                    "description": "전화 사용"
                },
                {
                    "from": "case",
                    "to": "account1",
                    "type": "used_account",
                    "description": "1차 계좌"
                },
                {
                    "from": "case",
                    "to": "account2",
                    "type": "used_account",
                    "description": "2차 계좌"
                }
            ],
            optional_nodes={
                "atm": {
                    "label": "vt_atm",
                    "weight": 0.2,
                    "description": "ATM 출금 기록"
                }
            },
            scoring={
                "required_match": 0.7,
                "optional_bonus": 0.3,
                "min_threshold": 0.80
            },
            cypher_query="""
MATCH (c:vt_flnm)-[:used_phone]->(p:vt_telno)
MATCH (c)-[:used_account]->(a1:vt_bacnt)
MATCH (c)-[:used_account]->(a2:vt_bacnt)
WHERE a1 <> a2
RETURN 
  c.flnm AS case_id, 
  p.telno AS phone_number,
  a1.actno AS account1,
  a2.actno AS account2,
  '전화금융사기 의심' AS pattern_name
"""
        ),
        
        # 4. 투자사기 (Investment Fraud)
        "investment_fraud": CrimePattern(
            pattern_id="investment_fraud_v1",
            name="투자사기",
            description="가상의 투자 상품을 제시하여 금전 편취. 사이트 또는 앱 활용",
            required_nodes={
                "case": {
                    "label": "vt_flnm",
                    "properties": {},
                    "description": "사건 정보"
                },
                "site": {
                    "label": "vt_site",
                    "properties": {},
                    "description": "투자 사이트"
                },
                "account": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "범죄자 계좌"
                }
            },
            required_edges=[
                {
                    "from": "case",
                    "to": "site",
                    "type": "digital_trace",
                    "description": "사이트 접속"
                },
                {
                    "from": "case",
                    "to": "account",
                    "type": "used_account",
                    "description": "투자금 입금 계좌"
                }
            ],
            optional_nodes={
                "phone": {
                    "label": "vt_telno",
                    "weight": 0.2,
                    "description": "상담 전화"
                },
                "id": {
                    "label": "vt_id",
                    "weight": 0.1,
                    "description": "사이트 계정"
                }
            },
            scoring={
                "required_match": 0.7,
                "optional_bonus": 0.3,
                "min_threshold": 0.85
            },
            cypher_query="""
MATCH (c:vt_flnm)-[:digital_trace]->(s:vt_site)
MATCH (c)-[:used_account]->(a:vt_bacnt)
WHERE s.site CONTAINS '투자' OR s.site CONTAINS 'invest' OR s.site CONTAINS 'coin'
RETURN 
  c.flnm AS case_id, 
  s.site AS site_url,
  a.actno AS account_no,
  '투자사기 의심' AS pattern_name
"""
        ),
        
        # 5. 스미싱 (Smishing)
        "smishing": CrimePattern(
            pattern_id="smishing_v1",
            name="스미싱",
            description="문자 메시지를 통한 피싱. 악성 링크 클릭 유도",
            required_nodes={
                "case": {
                    "label": "vt_flnm",
                    "properties": {},
                    "description": "사건 정보"
                },
                "phone": {
                    "label": "vt_telno",
                    "properties": {},
                    "description": "발신 번호"
                },
                "site": {
                    "label": "vt_site",
                    "properties": {},
                    "description": "악성 사이트"
                },
                "account": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "범죄자 계좌"
                }
            },
            required_edges=[
                {
                    "from": "case",
                    "to": "phone",
                    "type": "used_phone",
                    "description": "문자 발신"
                },
                {
                    "from": "case",
                    "to": "site",
                    "type": "digital_trace",
                    "description": "악성 링크"
                },
                {
                    "from": "case",
                    "to": "account",
                    "type": "used_account",
                    "description": "범죄 수익"
                }
            ],
            optional_nodes={
                "ip": {
                    "label": "vt_ip",
                    "weight": 0.2,
                    "description": "사이트 IP"
                },
                "file": {
                "label": "vt_file",
                    "weight": 0.1,
                    "description": "악성 앱 파일"
                }
            },
            scoring={
                "required_match": 0.7,
                "optional_bonus": 0.3,
                "min_threshold": 0.85
            },
            cypher_query="""
MATCH (c:vt_flnm)-[:used_phone]->(p:vt_telno)
MATCH (c)-[:digital_trace]->(s:vt_site)
MATCH (c)-[:used_account]->(a:vt_bacnt)
WHERE s.site CONTAINS 'http' OR s.site CONTAINS 'bit.ly' OR s.site CONTAINS 'apk'
RETURN 
  c.flnm AS case_id,
  p.telno AS phone_number,
  s.site AS malicious_url,
  a.actno AS account_no,
  '스미싱 의심' AS pattern_name
"""
        ),
        
        # ═══════════════════════════════════════════════════════════════════
        # ACTION LAYER 기반 패턴 (KICS 확장)
        # ═══════════════════════════════════════════════════════════════════
        
        # 6. 자금세탁 체인 (Money Laundering Chain)
        "money_laundering_chain": CrimePattern(
            pattern_id="money_laundering_v2",
            name="자금세탁체인",
            description="다단계 이체를 통한 자금세탁. 3단계 이상 계좌 이동 패턴을 탐지",
            required_nodes={
                "transfer1": {
                    "label": "vt_transfer",
                    "properties": {},
                    "description": "첫 번째 이체"
                },
                "transfer2": {
                    "label": "vt_transfer",
                    "properties": {},
                    "description": "두 번째 이체"
                },
                "transfer3": {
                    "label": "vt_transfer",
                    "properties": {},
                    "description": "세 번째 이체"
                },
                "account1": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "시작 계좌"
                },
                "account2": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "중간 계좌"
                },
                "account3": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "중간 계좌 2"
                },
                "account4": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "최종 계좌"
                }
            },
            required_edges=[
                {"from": "transfer1", "to": "account1", "type": "from_account"},
                {"from": "transfer1", "to": "account2", "type": "to_account"},
                {"from": "transfer2", "to": "account2", "type": "from_account"},
                {"from": "transfer2", "to": "account3", "type": "to_account"},
                {"from": "transfer3", "to": "account3", "type": "from_account"},
                {"from": "transfer3", "to": "account4", "type": "to_account"}
            ],
            optional_nodes={},
            scoring={
                "required_match": 0.8,
                "optional_bonus": 0.2,
                "min_threshold": 0.75
            },
            cypher_query="""
MATCH path = (a1:vt_bacnt)<-[:from_account]-(t1:vt_transfer)-[:to_account]->(a2:vt_bacnt)
             <-[:from_account]-(t2:vt_transfer)-[:to_account]->(a3:vt_bacnt)
             <-[:from_account]-(t3:vt_transfer)-[:to_account]->(a4:vt_bacnt)
WHERE t1.timestamp < t2.timestamp AND t2.timestamp < t3.timestamp
RETURN 
  a1.actno AS start_account,
  a4.actno AS end_account,
  t1.amount + t2.amount + t3.amount AS total_amount,
  length(path) AS hop_count,
  '자금세탁체인' AS pattern_name
ORDER BY total_amount DESC
LIMIT 20
"""
        ),
        
        # 7. 통화 네트워크 분석 (Call Network Analysis)
        "call_network_analysis": CrimePattern(
            pattern_id="call_network_v1",
            name="통화네트워크",
            description="통화 기록 기반 조직 분석. 중앙 허브 번호와 다수 번호 간 통화 패턴",
            required_nodes={
                "call": {
                    "label": "vt_call",
                    "properties": {},
                    "description": "통화 기록"
                },
                "phone_hub": {
                    "label": "vt_telno",
                    "properties": {},
                    "description": "허브 전화번호 (조직 총책)"
                },
                "phone_member": {
                    "label": "vt_telno",
                    "properties": {},
                    "description": "조직원 번호"
                }
            },
            required_edges=[
                {"from": "call", "to": "phone_hub", "type": "caller"},
                {"from": "call", "to": "phone_member", "type": "callee"}
            ],
            optional_nodes={
                "case": {
                    "label": "vt_case",
                    "weight": 0.2,
                    "description": "관련 사건"
                }
            },
            scoring={
                "required_match": 0.7,
                "optional_bonus": 0.3,
                "min_threshold": 0.80
            },
            cypher_query="""
MATCH (p_hub:vt_telno)<-[:caller]-(call:vt_call)-[:callee]->(p_member:vt_telno)
WITH p_hub, collect(DISTINCT p_member) AS members, count(call) AS call_count
WHERE call_count >= 5
RETURN 
  p_hub.telno AS hub_phone,
  size(members) AS member_count,
  call_count,
  [m IN members | m.telno][..5] AS sample_members,
  '통화네트워크' AS pattern_name
ORDER BY call_count DESC
LIMIT 10
"""
        ),
        
        # 8. 대포통장 탐지 (Mule Account Detection)
        "mule_account_detection": CrimePattern(
            pattern_id="mule_account_v1",
            name="대포통장",
            description="다수 사건에 공통으로 등장하는 계좌 탐지. 3건 이상 연루 시 대포통장 의심",
            required_nodes={
                "case1": {
                    "label": "vt_case",
                    "properties": {},
                    "description": "사건 1"
                },
                "case2": {
                    "label": "vt_case",
                    "properties": {},
                    "description": "사건 2"
                },
                "case3": {
                    "label": "vt_case",
                    "properties": {},
                    "description": "사건 3"
                },
                "account": {
                    "label": "vt_bacnt",
                    "properties": {},
                    "description": "공통 계좌"
                }
            },
            required_edges=[
                {"from": "case1", "to": "account", "type": "used_account"},
                {"from": "case2", "to": "account", "type": "used_account"},
                {"from": "case3", "to": "account", "type": "used_account"}
            ],
            optional_nodes={
                "transfer": {
                    "label": "vt_transfer",
                    "weight": 0.3,
                    "description": "관련 이체"
                }
            },
            scoring={
                "required_match": 0.8,
                "optional_bonus": 0.2,
                "min_threshold": 0.80
            },
            cypher_query="""
MATCH (c:vt_case)-[:used_account]->(a:vt_bacnt)
WITH a, collect(DISTINCT c) AS cases
WHERE size(cases) >= 3
OPTIONAL MATCH (t:vt_transfer)-[:to_account]->(a)
RETURN 
  a.actno AS mule_account,
  a.bank AS bank,
  size(cases) AS case_count,
  [c IN cases | c.flnm][..5] AS sample_cases,
  count(t) AS transfer_count,
  '대포통장' AS pattern_name
ORDER BY case_count DESC
LIMIT 10
"""
        )
    }
    
    @classmethod
    def get_pattern(cls, pattern_id):
        """패턴 ID로 패턴 가져오기"""
        return cls.PATTERNS.get(pattern_id)
    
    @classmethod
    def get_all_patterns(cls):
        """모든 패턴 가져오기"""
        return cls.PATTERNS
    
    @classmethod
    def get_pattern_names(cls):
        """패턴 이름 목록"""
        return [p.name for p in cls.PATTERNS.values()]
    
    @classmethod
    def find_by_name(cls, name):
        """이름으로 패턴 찾기"""
        for pattern in cls.PATTERNS.values():
            if pattern.name == name:
                return pattern
        return None
    
    @classmethod
    def get_action_based_patterns(cls):
        """Action Layer 기반 패턴만 가져오기"""
        action_patterns = ["money_laundering_chain", "call_network_analysis", "mule_account_detection"]
        return {k: v for k, v in cls.PATTERNS.items() if k in action_patterns}
    
    @classmethod
    def get_pattern_by_layer(cls, layer):
        """Layer별 패턴 가져오기 (Case/Action)"""
        if layer == "Action":
            return cls.get_action_based_patterns()
        else:
            # Case 기반 패턴 (기존)
            action_patterns = ["money_laundering_chain", "call_network_analysis", "mule_account_detection"]
            return {k: v for k, v in cls.PATTERNS.items() if k not in action_patterns}

