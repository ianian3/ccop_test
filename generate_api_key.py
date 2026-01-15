"""
API 키 생성 유틸리티
파트너를 위한 API 키를 생성합니다.
"""
from app.models.api_key import APIKey

def generate_demo_key():
    """데모 파트너용 API 키 생성"""
    result = APIKey.create_partner_key(
        partner_name="demo_partner",
        tier="free",
        rate_limit=1000,
        allowed_endpoints=["text-to-cypher", "graph-query", "usage", "validate-cypher"]
    )
    
    print("=" * 60)
    print("🔑 Demo API Key Generated")
    print("=" * 60)
    print(f"\nPartner: {result['partner_data']['partner_name']}")
    print(f"Tier: {result['partner_data']['tier']}")
    print(f"Rate Limit: {result['partner_data']['rate_limit']} requests/hour")
    print(f"\n⚠️  IMPORTANT: Save this API key now! It won't be shown again.")
    print(f"\nAPI Key (plaintext):")
    print(f"  {result['api_key']}")
    print(f"\nAPI Key Hash (store in database):")
    print(f"  {result['key_hash']}")
    print(f"\nExpires: {result['partner_data']['expires_at']}")
    print("\n" + "=" * 60)
    print("\n📝 Usage Example:")
    print(f"""
    curl -X POST http://localhost:5001/api/v1/text-to-cypher \\
      -H "Authorization: Bearer {result['api_key']}" \\
      -H "Content-Type: application/json" \\
      -d '{{"question": "접수번호 2019-000392 관련 계좌 찾기"}}'
    """)
    print("=" * 60)
    
    return result

if __name__ == "__main__":
    generate_demo_key()
