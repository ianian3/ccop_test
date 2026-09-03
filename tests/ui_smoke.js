// CCOP UI 스모크 — 이번 사이클(2026-09) 핵심 기능 회귀 감지 (10 체크)
// 선행: 앱 기동(localhost:5002) + `npm i playwright-core` (이 폴더 또는 상위)
// 실행: node tests/ui_smoke.js   (실패 시 exit 1)
const { chromium } = require('playwright-core');
const GRAPH = process.env.TEST_GRAPH || 'ccop_ep_integrated';
const BASE = process.env.CCOP_URL || 'http://localhost:5002';

const results = [];
function check(name, ok, detail) { results.push({ name, ok, detail }); console.log(`  ${ok ? '✅' : '❌'} ${name}${detail ? ' — ' + detail : ''}`); }

(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message.slice(0, 100)));
  await p.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 30000 });
  await p.waitForTimeout(1500);

  // ① 그래프 선택 → 추천 시작점 패널
  await p.selectOption('#targetGraphInfo', GRAPH); await p.waitForTimeout(2800);
  const rec = await p.evaluate(() => document.querySelectorAll('#startRecommendList > div').length);
  check('추천 시작점 Top10', rec === 10, `${rec}항목`);

  // ② 추천 클릭 → 방사형(종횡비≈1) + 중심성 크기
  await p.click('#startRecommendList > div'); await p.waitForTimeout(4000);
  const rad = await p.evaluate(() => {
    const bb = window.cy.nodes(':visible').boundingBox();
    return { ratio: bb.h / bb.w, sizes: new Set(window.cy.nodes(':visible').map(n => n.style('width'))).size, n: window.cy.nodes().length };
  });
  check('방사형 기본 배치', rad.ratio > 0.6 && rad.ratio < 1.7, `h/w=${rad.ratio.toFixed(2)}`);
  check('중심성 크기 상시 적용', rad.sizes > 4, `${rad.sizes}단계`);

  // ③ 전체 보기 → 우선순위 샘플링(핵심 라벨 존재) + 필터칩 정확
  await p.click('#loadFullBtn'); await p.waitForTimeout(5000);
  const full = await p.evaluate(() => {
    const types = ['vt_case', 'vt_psn', 'vt_org', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_site', 'vt_crypto', 'vt_id', 'vt_atm', 'vt_transfer', 'vt_call'];
    const bad = types.filter(t => +((document.getElementById('count-' + t) || {}).textContent || -1) !== window.cy.nodes(`[label="${t}"]`).length);
    return { bad, case_n: window.cy.nodes('[label="vt_case"]').length, psn: window.cy.nodes('[label="vt_psn"]').length };
  });
  check('필터칩 카운트 12/12', full.bad.length === 0, full.bad.join(',') || `사건${full.case_n}·인물${full.psn}`);
  check('우선순위 샘플링(서사 핵심)', full.case_n > 0 && full.psn > 0);

  // ④ 군집색 토글
  await p.click('#btn-community'); await p.waitForTimeout(900);
  const comm = await p.evaluate(() => { const s = new Set(); window.cy.nodes(':visible').forEach(n => { if (parseInt(n.style('border-width')) >= 6) s.add(n.style('border-color')); }); return s.size; });
  check('군집색(인물중심 Louvain)', comm >= 4, `${comm}색`);
  await p.click('#btn-community'); await p.waitForTimeout(400);

  // ⑤ 분석 top 실행 → 리스트 → 행 클릭 → 뒤로가기
  await p.selectOption('#algoSelect', 'top:betweenness'); await p.selectOption('#algoLabel', 'vt_bacnt');
  await p.click('button[onclick="runAlgo()"]'); await p.waitForTimeout(2500);
  const rows = await p.evaluate(() => document.querySelectorAll('#node-info tr').length);
  check('분석 top 리스트', rows >= 10, `${rows}행`);
  const glow = await p.evaluate(() => window.cy.nodes().filter(n => +n.style('overlay-opacity') > 0).length);
  check('분석 overlay 강조', glow >= 10, `${glow}노드`);
  await p.click('#node-info tr'); await p.waitForTimeout(1000);
  const back = await p.evaluate(() => !!document.querySelector('#node-info button[onclick="backToAlgoList()"]'));
  check('상세 → 뒤로가기 버튼', back);
  if (back) { await p.click('#node-info button[onclick="backToAlgoList()"]'); await p.waitForTimeout(500); }
  const restored = await p.evaluate(() => document.querySelectorAll('#node-info tr').length);
  check('리스트 복원', restored >= 10, `${restored}행`);

  // ⑥ 브리핑 — 피의자 섹션
  await p.click('#tab-briefing'); await p.waitForTimeout(3000);
  const sus = await p.evaluate(() => document.querySelectorAll('div[onclick^="briefingSuspect"]').length);
  check('브리핑 피의자 카드', sus === 6, `${sus}명`);

  check('JS 페이지 에러 0', errs.length === 0, errs[0] || '');
  await b.close();
  const fail = results.filter(r => !r.ok).length;
  console.log(`\n=== UI 스모크: ${results.length - fail}/${results.length} 통과 ===`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('스모크 실행 오류:', e.message); process.exit(1); });
