# 데이터 표준화 정의서 (Data Standardization Definition)

> **문서 버전**: 1.0  
> **최종 수정일**: 2026-02-02  
> **개요**: 데이터가 그래프 DB 및 RDB에 적재되기 직전 수행되는 **표준화 엔진**의 기준 정보를 정의함.

---

## 1. 표준화 데이터 플로우 (Revised Data Flow)

데이터의 품질과 일관성을 보장하기 위해, 모든 원시 데이터(Raw Data)는 **반드시 표준화 엔진을 통과한 후** DB에 적재되어야 합니다.

```mermaid
graph LR
    Raw[원시 데이터<br>(CSV/JSON)] --> StandardEngine[⚙️ 표준화 엔진<br>(Standardization Engine)]
    
    subgraph "표준화 프로세스"
        StandardEngine --> Clean[데이터 정제<br>(공백/특수문자 제거)]
        Clean --> Format[도메인 포맷팅<br>(전화번호/날짜)]
        Format --> CodeMap[코드 매핑<br>(범죄코드 통합)]
    end
    
    CodeMap --> ValidData[✅ 표준 데이터]
    CodeMap --> ErrorData[❌ 오류 데이터]
    
    ValidData --> RDB[(RDB 적재)]
    ValidData --> GDB[(Graph DB 적재)]
```

---

## 2. 상세 실행 시나리오 (Detailed Scenarios)

### Step 2: 수집 및 매핑 (Runtime - Stream ETL)

다양한 원천 시스템(Source System)에서 유입되는 이질적인 데이터를 **MDR(Meta Data Registry) 규칙**에 따라 실시간으로 변환합니다.

#### 1) 입력 데이터 (Raw Data)
*   **Source A (웹포렌식)**:
    ```json
    {"ph_num": "01012345678", "msg": "입금 부탁드립니다"}
    ```
*   **Source B (KICS)**:
    ```json
    {"HP_NO": "010-1234-5678", "SANGSE": "피의자 신문 조서"}
    ```

#### 2) 표준화 엔진 처리 (Standardization)
1.  **컬럼 매핑 (Key Mapping)**:
    *   `ph_num` (Source A) → **`telno`** (표준 용어)
    *   `HP_NO` (Source B) → **`telno`** (표준 용어)
2.  **포맷 변환 (Value Formatting)**:
    *   `01012345678` → **`010-1234-5678`** (포맷팅 규칙 적용)
    *   `010-1234-5678` → **`010-1234-5678`** (유지)

#### 3) 변환 결과 (Standardized Data)
**모든 소스는 동일한 JSON 스키마로 변환됩니다.**
```json
// Source A 변환 결과
{"telno": "010-1234-5678", "content": "입금...", "source": "web_forensic"}

// Source B 변환 결과
{"telno": "010-1234-5678", "content": "피의자...", "source": "kics"}
```

---

### Step 3: 온톨로지 적재 (Loading - Graph Merge)

표준화된 데이터를 그래프 DB(AgensGraph)에 적재할 때, **식별자(Identifier)**가 같다면 자동으로 **동일 노드로 병합(Merge)**됩니다.

#### 1) 그래프 생성 로직
*   **Ontology Class**: `vt_telno` (Phone)
*   **Identifier Key**: `telno`

#### 2) Cypher Query 예시
```cypher
// Source A 적재
MERGE (p:vt_telno {telno: '010-1234-5678'})
ON CREATE SET p.created_at = timestamp()
SET p.last_seen = 'web_forensic';

// Source B 적재
MERGE (p:vt_telno {telno: '010-1234-5678'})
SET p.kics_verified = true;
```

#### 3) 결과 (Result)
*   출처가 달라도 전화번호(`010-1234-5678`)가 같으므로 **하나의 노드(Node)**만 생성됩니다.
*   이 노드에는 두 소스의 속성이 모두 통합되어 저장됩니다. (예: `last_seen`과 `kics_verified` 속성을 모두 가짐)
*   이를 통해 **파편화된 정보의 연결(Link Analysis)**이 가능해집니다.

---

## 3. 표준 단어 정의 (Standard Words)

업무에서 사용되는 용어를 통일하고, DB 및 코드 레벨에서 사용할 영문 약어(Abbreviation)를 정의합니다.

| 한글명 | 영문명 (Full) | 영문 약어 (Column/Key) | 설명 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **수사** | Investigation | `inv` | 범죄 혐의를 밝히기 위한 활동 | `vt_inv` |
| **사건** | Case | `case` | 수사의 대상이 되는 단위 | `vt_case` |
| **증거** | Evidence | `evd` | 범죄 사실을 증명하는 자료 | `vt_evd` |
| **계좌** | Account | `actno` | 금융 거래를 위한 고유 번호 | `vt_bacnt` |
| **일시** | Date & Time | `dt` | 사건이나 행위가 발생한 시점 | `reg_date`, `trx_dt` |
| **게시물** | Post | `post` | 온라인 상에 등록된 글/자료 | `vt_post` |
| **피의자** | Suspect | `susp` | 범죄 혐의를 받고 있는 자 | `vt_psn` (role='suspect') |
| **피해자** | Victim | `vctm` | 범죄로 인해 피해를 입은 자 | `vt_psn` (role='victim') |
| **전화번호** | Telephone Number | `telno` | 통신 식별 번호 | `vt_telno` |

---

## 3. 표준 도메인 정의 (Standard Domains)

데이터의 **형식(Format)**과 **유효성 규칙(Validation Rule)**을 정의합니다. 표준화 엔진은 이 규칙에 따라 데이터를 변환합니다.

### 3.1 전화번호 (Phone Number)
*   **표준 형식**: `010-XXXX-XXXX` (하이픈 필수로 포함)
*   **정제 규칙**:
    1.  숫자 외의 문자(공백, 특수문자) 제거.
    2.  `01012345678` → `010-1234-5678` (하이픈 자동 삽입).
    3.  `82-10-1234-5678` → `010-1234-5678` (국가코드 제거 및 정규화).
*   **유효성**: 9자리 이상 11자리 이하 숫자 (국내 기준).

### 3.2 일시 (DateTime)
*   **표준 형식**: `YYYY-MM-DD HH24:MI:SS` (ISO-8601 기반 확장)
*   **시간대(Timezone)**: KST (UTC+9) 기준 저장 원칙. (필요 시 UTC 병기)
*   **정제 규칙**:
    *   `2026.02.02` → `2026-02-02 00:00:00`
    *   `2026/02/02 14:00` → `2026-02-02 14:00:00`

### 3.3 금액 (Amount)
*   **표준 형식**: `Integer` (원 단위, 콤마 제거)
*   **정제 규칙**: `1,000,000원` → `1000000`

---

## 4. 표준 코드 정의 (Standard Codes)

서로 다른 출처의 코드를 **KICS 통합 코드**로 매핑합니다.

### 4.1 범죄 유형 코드 (Crime Type Code)
**112 신고 코드**와 **KICS 죄명 코드**를 매핑하여 통합 분석이 가능하게 합니다.

| 통합 코드 (Std) | 통합 코드명 | 112 신고 코드 (Source A) | KICS 죄명 (Source B) | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **C_1200** | **보이스피싱** | `112_VP`, `112_FRAUD_V` | `34700` (사기), `VP001` | 계좌 이체 유도형 |
| **C_1300** | **스미싱** | `112_SM`, `112_URL` | `34702` (컴퓨터등사용사기) | 문자 URL 클릭 유도 |
| **C_1400** | **메신저피싱** | `112_MSG` | `34700` (사기) | 가족 사칭 등 |
| **C_1500** | **몸캠피싱** | `112_BODY` | `28300` (공갈) | 동영상 유포 협박 |
| **C_1600** | **투자사기** | `112_INV`, `112_COIN` | `34700` (사기), `INV01` | 리딩방, 가상자산 |

### 4.2 은행 코드 (Bank Code) -> (참고: COMMON_CODES.md)
*   금융결제원 표준 코드를 따름.
*   예: `004`(국민), `088`(신한), `020`(우리), `090`(카카오뱅크)

---

## 5. 구현 가이드 (Implementation Guide)

### Python 표준화 함수 예시

```python
def standardize_phone(raw_phone):
    """
    입력: '010 1234 5678', '010-1234-5678', '821012345678'
    출력: '010-1234-5678'
    """
    import re
    # 1. 숫자만 추출
    digits = re.sub(r'[^0-9]', '', str(raw_phone))
    
    # 2. 국가코드(82) 제거 (선택적)
    if digits.startswith('82') and len(digits) > 10:
        digits = '0' + digits[2:]
        
    # 3. 포맷팅
    if len(digits) == 11: # 010-XXXX-XXXX
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif len(digits) == 10: # 02-XXX-XXXX or 011-XXX-XXXX
        if digits.startswith('02'):
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        
    return digits # 포맷팅 불가 시 숫자만 반환
```
