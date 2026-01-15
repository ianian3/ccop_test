"""
API 키 관리 모델
API 키 생성, 검증, 관리를 담당합니다.
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict

class APIKey:
    """API 키 모델"""
    
    @staticmethod
    def generate_key(prefix: str = "ccop") -> str:
        """
        새로운 API 키 생성
        
        Args:
            prefix: API 키 접두사 (예: "ccop")
        
        Returns:
            생성된 API 키 (예: "ccop_1a2b3c4d5e6f7g8h9i0j")
        """
        # 30바이트 랜덤 생성 -> Base64 인코딩
        random_part = secrets.token_urlsafe(30)
        return f"{prefix}_{random_part}"
    
    @staticmethod
    def hash_key(api_key: str) -> str:
        """
        API 키를 SHA-256으로 해싱
        데이터베이스에는 해시된 값을 저장
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def create_partner_key(
        partner_name: str,
        tier: str = "free",
        rate_limit: int = 1000,
        allowed_endpoints: list = None,
        expiry_days: int = 365
    ) -> Dict:
        """
        새 파트너 API 키 생성
        
        Args:
            partner_name: 파트너 이름
            tier: 티어 (free, startup, enterprise)
            rate_limit: 시간당 요청 제한
            allowed_endpoints: 허용된 엔드포인트 리스트
            expiry_days: 만료일 (일)
        
        Returns:
            {
                "api_key": "생성된 키 (평문, 한 번만 보여줌)",
                "key_hash": "해시된 키",
                "partner_data": {...}
            }
        """
        if allowed_endpoints is None:
            allowed_endpoints = ["text-to-cypher", "graph-query", "usage"]
        
        api_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(api_key)
        
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(days=expiry_days)
        
        partner_data = {
            "partner_name": partner_name,
            "tier": tier,
            "rate_limit": rate_limit,
            "allowed_endpoints": allowed_endpoints,
            "created_at": created_at.isoformat() + "Z",
            "expires_at": expires_at.isoformat() + "Z",
            "is_active": True
        }
        
        return {
            "api_key": api_key,  # 평문 (단 한 번만 표시)
            "key_hash": key_hash,  # DB에 저장할 해시
            "partner_data": partner_data
        }
    
    @staticmethod
    def validate_key_format(api_key: str) -> bool:
        """
        API 키 형식 검증
        
        올바른 형식: ccop_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        """
        if not api_key:
            return False
        
        parts = api_key.split('_', 1)
        if len(parts) != 2:
            return False
        
        prefix, key_part = parts
        
        # 접두사 확인
        if prefix not in ['ccop', 'demo']:
            return False
        
        # 키 부분 길이 확인 (최소 20자)
        if len(key_part) < 20:
            return False
        
        return True
    
    @staticmethod
    def is_expired(partner_data: Dict) -> bool:
        """API 키 만료 여부 확인"""
        expires_at = partner_data.get('expires_at')
        if not expires_at:
            return False
        
        try:
            expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            return datetime.utcnow() > expiry_date.replace(tzinfo=None)
        except:
            return False


# 파트너 티어 설정
TIERS = {
    "free": {
        "rate_limit": 1000,  # 시간당 1000 요청
        "max_results": 50,
        "allowed_endpoints": ["text-to-cypher", "usage"]
    },
    "startup": {
        "rate_limit": 10000,
        "max_results": 100,
        "allowed_endpoints": ["text-to-cypher", "graph-query", "usage", "validate-cypher"]
    },
    "enterprise": {
        "rate_limit": None,  # 무제한
        "max_results": 500,
        "allowed_endpoints": ["*"]  # 모든 엔드포인트
    }
}

def get_tier_config(tier: str) -> Dict:
    """티어 설정 가져오기"""
    return TIERS.get(tier, TIERS["free"])
