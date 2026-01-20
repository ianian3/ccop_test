"""
범죄 패턴 템플릿 라이브러리

KICS 기반 사이버 범죄 패턴 정의 및 관리
"""

class CrimePattern:
    """범죄 패턴 정의 클래스"""
    
    def __init__(self, pattern_id, name, description, required_nodes, 
                 required_edges, optional_nodes=None, scoring=None):
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
    
    def to_dict(self):
        """패턴을 딕셔너리로 변환"""
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "required_nodes": self.required_nodes,
            "required_edges": self.required_edges,
            "optional_nodes": self.optional_nodes,
            "scoring": self.scoring
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
            }
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
            }
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
            }
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
            }
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
            }
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
