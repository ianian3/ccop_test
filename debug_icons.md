"""
노드 아이콘 디버깅 가이드
=======================

## 문제: 아이콘이 표시되지 않음

아이콘 파일은 존재하지만 표시되지 않는 경우, 아래 단계를 따라 디버깅하세요.

## 1단계: 브라우저 콘솔에서 노드 데이터 확인

웹페이지를 열고 F12 (개발자 도구) → Console 탭에서:

```javascript
// 모든 노드의 label 확인
cy.nodes().forEach(n => {
    const data = n.data();
    console.log(`ID: ${data.id}, Label: ${data.label}, Props:`, data.props);
});
```

**예상 결과:**
```
ID: 3.46, Label: vt_psn, Props: {flnm: "홍길동", ...}
ID: 3.47, Label: vt_telno, Props: {telno: "010-1234", ...}
ID: 3.48, Label: vt_bacnt, Props: {actno: "123-456", ...}
```

**문제 확인:**
- ❌ 모든 label이 "vt_psn"이면 → 백엔드 문제
- ✅ label이 다양하면 → 프론트엔드 CSS/경로 문제

---

## 2단계: 이미지 로드 확인

F12 → Network 탭 → Img 필터:

1. 페이지 새로고침
2. `person.png`, `phone.png`, `account.png` 검색
3. 상태 코드 확인:
   - ✅ 200: 로드 성공
   - ❌ 404: 경로 문제

**404 에러가 나면:**
index.html의 이미지 경로를 확인하세요.

현재 경로: `static/images/person.png`
→ Flask는 `/static/...` 형식 필요

---

## 3단계: 경로 수정 (필요시)

index.html Line 377-379:

**변경 전:**
```javascript
'background-image': 'static/images/person.png'
```

**변경 후:**
```javascript
'background-image': '/static/images/person.png'  // 앞에 / 추가
```

---

## 4단계: CSS Selector 확인

브라우저 콘솔에서:

```javascript
// vt_psn label을 가진 노드 확인
const psnNodes = cy.nodes('[label="vt_psn"]');
console.log(`vt_psn 노드 수: ${psnNodes.length}`);

// 각 타입별 노드 수
console.log({
    vt_psn: cy.nodes('[label="vt_psn"]').length,
    vt_telno: cy.nodes('[label="vt_telno"]').length,
    vt_bacnt: cy.nodes('[label="vt_bacnt"]').length
});
```

---

## 5단계: 스타일 강제 적용 테스트

```javascript
// 특정 노드에 강제로 이미지 적용
cy.nodes().first().style({
    'background-image': '/static/images/person.png',
    'background-fit': 'cover'
});
```

이미지가 보이면 → CSS selector 문제
안 보이면 → 이미지 경로 문제

---

## 빠른 해결: 이미지 경로 수정

현재 index.html에 `/` 누락된 것 같습니다.
모든 이미지 경로 앞에 `/` 추가 필요!
"""
