const { chromium } = require('playwright-core');
const F = 'file:///private/tmp/claude-501/-Users-iankwon-test-coop-v1-0/1e441d09-0c0a-45c1-9359-11e83fcaf989/scratchpad/schema_catalog.html';
const OUT = '/private/tmp/claude-501/-Users-iankwon-test-coop-v1-0/1e441d09-0c0a-45c1-9359-11e83fcaf989/scratchpad/';
(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage({ viewport: { width: 1200, height: 1000 } });
  const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 120)));
  await p.goto(F, { waitUntil: 'load' }); await p.waitForTimeout(700);

  const base = await p.evaluate(() => ({
    nodes: document.querySelectorAll('#g .node').length,
    edges: document.querySelectorAll('#g path.edge').length,
    labels: document.querySelectorAll('#g text.elabel').length,
    panel: document.querySelector('#panel h3').textContent.trim(),
  }));
  console.log('  초기:', JSON.stringify(base));
  await p.screenshot({ path: OUT + 'vt_all.png', clip: { x: 0, y: 90, width: 1200, height: 700 } });

  // 인물 노드 클릭 (aria-label 로 특정)
  await p.click('#g .node[aria-label*="인물"]'); await p.waitForTimeout(450);
  const sel = await p.evaluate(() => ({
    head: document.querySelector('#panel h3').textContent.replace(/\s+/g,' ').trim(),
    meta: document.querySelector('#panel .pmeta').textContent.trim(),
    groups: [...document.querySelectorAll('#panel .grp')].map(e => e.textContent.trim()),
    rows: document.querySelectorAll('#panel .er').length,
    firstRow: (document.querySelector('#panel .er')||{}).textContent?.replace(/\s+/g,' ').trim().slice(0,70),
    edgesOn: document.querySelectorAll('#g path.edge.on').length,
    dimmed: document.querySelectorAll('#g .node.dimmed').length,
    tableHits: document.querySelectorAll('#cat tr.rowhit').length,
  }));
  console.log('  인물 선택:', JSON.stringify(sel, null, 0).slice(0, 400));
  await p.screenshot({ path: OUT + 'vt_psn.png', clip: { x: 0, y: 90, width: 1200, height: 700 } });

  // 계좌 클릭 (자기루프 transferred_to 확인)
  await p.click('#g .node[aria-label*="계좌"]'); await p.waitForTimeout(400);
  const bac = await p.evaluate(() => ({
    meta: document.querySelector('#panel .pmeta').textContent.trim(),
    hasSelf: [...document.querySelectorAll('#panel .grp')].some(e => e.textContent.includes('자기')),
    rows: document.querySelectorAll('#panel .er').length,
  }));
  console.log('  계좌 선택:', JSON.stringify(bac));
  await p.screenshot({ path: OUT + 'vt_bac.png', clip: { x: 0, y: 90, width: 1200, height: 700 } });

  // 리셋
  await p.click('#rst'); await p.waitForTimeout(300);
  const rst = await p.evaluate(() => ({
    on: document.querySelectorAll('#g path.edge.on').length,
    dim: document.querySelectorAll('.dimmed').length,
    hits: document.querySelectorAll('#cat tr.rowhit').length }));
  console.log('  리셋 후:', JSON.stringify(rst));
  console.log('  JS 오류:', errs.length ? errs.join(' | ') : '0');
  await b.close();
  process.exit(base.nodes === 12 && base.edges === 28 && sel.rows >= 9 && errs.length === 0 ? 0 : 1);
})();
