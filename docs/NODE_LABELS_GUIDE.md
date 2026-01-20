# 노드 라벨 분류 시스템

## 🎯 지원되는 노드 타입 (8가지)

AgensGraph에서 KICS 컬럼 속성을 기반으로 자동으로 노드 타입을 분류합니다.

| 타입 | Label | 속성 키 | 아이콘 | 색상 |
|------|-------|---------|--------|------|
| 접수번호 | `vt_flnm` | flnm | person.png | 🟠 주황색 (#e17055) |
| 계좌번호 | `vt_bacnt` | actno, bank, account | account.png | 🟡 노란색 (#f1c40f) |
| 사이트 | `vt_site` | site, url, domain | site.png | 🟢 초록색 (#00b894) |
| 전화번호 | `vt_telno` | telno, phone | phone.png | 🔵 파란색 (#0984e3) |
| IP 주소 | `vt_ip` | ip, ip_addr, ipaddr | ip.png | 🟣 분홍색 (#fd79a8) |
| ATM | `vt_atm` | atm, atm_id | atm.png | 🟡 밝은 노란색 (#fdcb6e) |
| 파일명 | `vt_file` | file, filename, filepath | person.png | 🟣 보라색 (#a29bfe) |
| ID | `vt_id` | id, user_id, userid | person.png | 🟥 연한 빨강 (#fab1a0) |
| 사람 | `vt_psn` | name | person.png | 🟣 진보라 (#6c5ce7) |

---

## 📋 속성 우선순위

노드에 여러 속성이 있을 경우, 다음 우선순위로 타입을 결정합니다:

```
1. IP 주소 (ip, ip_addr, ipaddr) → vt_ip
2. ATM (atm, atm_id) → vt_atm
3. 사이트 (site, url, domain) → vt_site
4. 계좌번호 (actno, bank, account) → vt_bacnt
5. 전화번호 (telno, phone) → vt_telno
6. 파일명 (file, filename, filepath) → vt_file
7. 접수번호 (flnm) → vt_flnm
8. ID (id, user_id, userid) → vt_id
9. 이름 (name) → vt_psn
10. 기본값 → vt_psn
```

---

## 🔧 CSV 업로드 시 매핑 방법

### 1. **Source/Target 속성 키 지정**

CSV 업로드 모달에서 Source와 Target의 **속성 키 이름**을 직접 지정:

**예시 1: 전화번호 → 전화번호**
```
Source 컬럼: "발신번호"
Source 속성 키: telno → 노드 타입: vt_telno (📱)

Target 컬럼: "수신번호"  
Target 속성 키: telno → 노드 타입: vt_telno (📱)
```

**예시 2: 접수번호 → 사이트**
```
Source 컬럼: "접수번호"
Source 속성 키: flnm → 노드 타입: vt_flnm (🟠)

Target 컬럼: "URL"
Target 속성 키: site → 노드 타입: vt_site (🌐)
```

**예시 3: IP → 계좌번호**
```
Source 컬럼: "접속IP"
Source 속성 키: ip → 노드 타입: vt_ip (🟣)

Target 컬럼: "계좌번호"
Target 속성 키: actno → 노드 타입: vt_bacnt (💰)
```

### 2. **추가 속성 매핑**

나머지 컬럼은 "추가 속성 매핑" 테이블에서 설정:
- **저장 위치**: Source 속성 / Target 속성 / Edge 속성
- **속성 이름**: 원하는 키 이름 (flnm, telno, site, ip 등)

---

## 💡 실전 예시

### 사기 사건 데이터 적재

| CSV 컬럼 | 속성 키 | 저장 위치 | 노드 타입 |
|----------|---------|-----------|----------|
| 접수번호 | flnm | Source | vt_flnm 🟠 |
| 사기범전화 | telno | Target | vt_telno 📱 |
| IP주소 | ip | Target 속성 | vt_ip 🟣 |
| 피싱사이트 | site | Target 속성 | vt_site 🌐 |
| 계좌번호 | actno | Target 속성 | vt_bacnt 💰 |

→ **결과:** 각 노드가 고유한 아이콘과 색상으로 구분됨!

---

## 🎨 노드 아이콘 위치

모든 아이콘은 `/static/images/` 디렉토리에 위치:
- `person.png` - 사람, 접수번호, 파일, ID (공용)
- `phone.png` - 전화번호
- `account.png` - 계좌번호
- `site.png` - 사이트
- `ip.png` - IP 주소
- `atm.png` - ATM

---

## ✅ 확인 방법

브라우저 F12 콘솔에서:
```javascript
// 노드별 타입 확인
cy.nodes().forEach(n => {
    const data = n.data();
    console.log(`Label: ${data.label}, Props:`, data.props);
});

// 타입별 노드 수
console.log({
    'vt_flnm (접수번호)': cy.nodes('[label="vt_flnm"]').length,
    'vt_bacnt (계좌)': cy.nodes('[label="vt_bacnt"]').length,
    'vt_site (사이트)': cy.nodes('[label="vt_site"]').length,
    'vt_telno (전화)': cy.nodes('[label="vt_telno"]').length,
    'vt_ip (IP)': cy.nodes('[label="vt_ip"]').length,
    'vt_atm (ATM)': cy.nodes('[label="vt_atm"]').length,
    'vt_file (파일)': cy.nodes('[label="vt_file"]').length,
    'vt_id (ID)': cy.nodes('[label="vt_id"]').length,
    'vt_psn (사람)': cy.nodes('[label="vt_psn"]').length
});
```
