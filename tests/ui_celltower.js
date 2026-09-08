// 기지국 UI 조회 검증 — 자연어 입력 → 그래프 렌더 → vt_loc 노드/라벨 확인 + 스크린샷
const { chromium } = require('playwright-core');
const SHOT = '/private/tmp/claude-501/-Users-iankwon-test-coop-v1-0/1e441d09-0c0a-45c1-9359-11e83fcaf989/scratchpad/ui_celltower.png';
(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  p.on('pageerror', e => errs.push(String(e).slice(0, 80)));
  await p.goto('http://localhost:5002/?graph_path=ccop_ep_integrated', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);

  // T2C 자연어 질의
  // 추천 모달이 떠 있으면 닫기 (입력 가림 방지)
  try { await p.click('#startRecommend .close, #startRecommend [onclick*="close"], text=×', { timeout: 1500 }); } catch (e) {}
  await p.fill('#aiInput', '기지국 위치 전부 보여줘');
  await p.click('button.btn-ai');   // Enter 미바인딩 — askAI() 버튼 클릭
  await p.waitForTimeout(9000);

  const st = await p.evaluate(() => {
    const locs = cy.$('node[label="vt_loc"]');
    const labels = locs.slice(0, 5).map(n => {
      const pr = n.data('props') || {};
      return pr.address || pr.loc_id || '(라벨없음)';
    });
    return { total: cy.nodes().length, vtloc: locs.length, labels,
             chip: (document.querySelector('[data-label="vt_loc"]') || {}).textContent || null };
  });
  console.log(`  전체 노드 ${st.total} · vt_loc ${st.vtloc}`);
  console.log('  표시 라벨:', st.labels.join(' | '));
  if (st.chip) console.log('  필터칩:', st.chip.trim());

  await p.screenshot({ path: SHOT.replace('.png', '_q1.png') });   // 1차 질의 직후 장면
  // 두 번째: 앵커 형태 질의 (번호→기지국)
  await p.fill('#aiInput', '01004385874 번호가 잡힌 기지국');
  await p.click('button.btn-ai');
  await p.waitForTimeout(9000);
  const st2 = await p.evaluate(() => ({
    vtloc: cy.$('node[label="vt_loc"]').length,
    edges: cy.$('edge[label="located_at"]').length }));
  console.log(`  2차 질의: vt_loc ${st2.vtloc} · located_at 엣지 ${st2.edges}`);

  await p.screenshot({ path: SHOT, fullPage: false });
  console.log('  스크린샷:', SHOT);
  console.log('  JS 오류:', errs.length ? errs.join(' / ') : '0');
  await b.close();
  process.exit(st.vtloc >= 30 && st2.vtloc >= 1 ? 0 : 1);
})();
