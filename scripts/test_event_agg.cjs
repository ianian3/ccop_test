#!/usr/bin/env node
/**
 * 이벤트 접기 + 중첩 합계(aggregation) 헤드리스 회귀 테스트
 * - index.html 의 [COLLAPSE-CORE-BEGIN]~[COLLAPSE-CORE-END] 블록을 추출해
 *   vendor cytoscape(실제 엔진, headless)로 실행한다. 브라우저 불필요.
 * - 실행: node scripts/test_event_agg.cjs
 * - 부가: 시각 확인용 하네스 HTML 생성 (--harness <출력경로>)
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const cytoscape = require(path.join(ROOT, 'app/static/vendor/cytoscape/cytoscape.min.js'));

// ── 1) index.html 에서 접기 코어 추출 ─────────────────────────
const html = fs.readFileSync(path.join(ROOT, 'app/templates/index.html'), 'utf8');
const m = html.match(/\/\/ \[COLLAPSE-CORE-BEGIN\][\s\S]*?\/\/ \[COLLAPSE-CORE-END\]/);
if (!m) { console.error('❌ [COLLAPSE-CORE] 마커 추출 실패'); process.exit(1); }
const core = m[0];

// ── 2) 합성 데이터 ────────────────────────────────────────────
//   pA→pB 통화 12건(총 2,050초=34분10초) / pB→pA 2건(100초) / pB→pC 1건(단건)
//   a1→a2 이체 3건(합계 17,000,000원)
function buildElements() {
    const els = [];
    ['pA', 'pB', 'pC'].forEach(id => els.push({ group: 'nodes', data: { id, label: 'vt_telno', props: { telno: id } } }));
    ['a1', 'a2'].forEach(id => els.push({ group: 'nodes', data: { id, label: 'vt_bacnt', props: { account_no: id } } }));
    let eid = 0;
    const call = (src, tgt, dur, i) => {
        const ev = `call_${src}_${tgt}_${i}`;
        els.push({ group: 'nodes', data: { id: ev, label: 'vt_call', props: { call_dur_sec: dur } } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: src, target: ev, label: 'caller' } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: ev, target: tgt, label: 'callee' } });
    };
    const xfer = (src, tgt, amt, i) => {
        const ev = `tx_${src}_${tgt}_${i}`;
        els.push({ group: 'nodes', data: { id: ev, label: 'vt_transfer', props: { amount: amt } } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: src, target: ev, label: 'from_account' } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: ev, target: tgt, label: 'to_account' } });
    };
    const durs = [300, 45, 120, 600, 30, 90, 200, 15, 400, 100, 50, 100];   // 합 2,050초
    durs.forEach((d, i) => call('pA', 'pB', d, i));
    call('pB', 'pA', 40, 100); call('pB', 'pA', 60, 101);                    // 역방향 2건 (100초)
    call('pB', 'pC', 77, 200);                                               // 단건 — 합계 대상 아님
    xfer('a1', 'a2', 5000000, 0); xfer('a1', 'a2', 7000000, 1); xfer('a1', 'a2', 5000000, 2);
    // 단끝(상대 미상) — 수신만 통화 6건(pB, 총 360초), 발신만 1건(pC), 출금만 이체 2건(a1, 합 300만)
    const rxOnly = (tgt, dur, i) => {
        const ev = `rxcall_${tgt}_${i}`;
        els.push({ group: 'nodes', data: { id: ev, label: 'vt_call', props: { call_dur_sec: dur } } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: ev, target: tgt, label: 'callee' } });
    };
    const txOnly = (src, dur, i) => {
        const ev = `txcall_${src}_${i}`;
        els.push({ group: 'nodes', data: { id: ev, label: 'vt_call', props: { call_dur_sec: dur } } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: src, target: ev, label: 'caller' } });
    };
    const outOnly = (src, amt, i) => {
        const ev = `txout_${src}_${i}`;
        els.push({ group: 'nodes', data: { id: ev, label: 'vt_transfer', props: { amount: amt } } });
        els.push({ group: 'edges', data: { id: `e${eid++}`, source: src, target: ev, label: 'from_account' } });
    };
    for (let i = 0; i < 6; i++) rxOnly('pB', 60, i);
    txOnly('pC', 30, 0);
    outOnly('a1', 1000000, 0); outOnly('a1', 2000000, 1);
    return els;
}

// ── 3) 코어 실행 (module 스코프의 cy 를 클로저로 참조) ────────
const cy = cytoscape({ headless: true, styleEnabled: true, elements: buildElements() });
const fns = {};
eval(core + '\n;fns.applyEventCollapse=applyEventCollapse; fns.applyEventAggregation=applyEventAggregation;'
          + 'fns.undoEventCollapse=undoEventCollapse; fns._computeEventAggregates=_computeEventAggregates; fns._fmtDur=_fmtDur;');

// ── 4) 검증 ──────────────────────────────────────────────────
let failed = 0;
const check = (name, cond, detail) => {
    console.log((cond ? '  ✅ ' : '  ❌ ') + name + (cond ? '' : `  ← ${detail}`));
    if (!cond) failed++;
};

console.log('▶ 접기 실행');
const collapsedN = fns.applyEventCollapse();
check('이벤트 18건 접힘', collapsedN === 18, `got ${collapsedN}`);

const aggAB = cy.getElementById('evtagg__pA__pB__vt_call');
check('pA→pB 통화 합계 엣지 생성', aggAB.nonempty(), 'agg edge 없음');
check('  건수 12', aggAB.data('_aggCount') === 12, `got ${aggAB.data('_aggCount')}`);
check('  라벨 "📞통화 12건 · 총 34분 10초"', aggAB.data('label') === '📞통화 12건 · 총 34분 10초', `got "${aggAB.data('label')}"`);

const aggBA = cy.getElementById('evtagg__pB__pA__vt_call');
check('pB→pA 역방향 별도 합계 (2건·총 1분 40초)', aggBA.nonempty() && aggBA.data('label') === '📞통화 2건 · 총 1분 40초', `got "${aggBA.data('label')}"`);

check('pB→pC 단건은 합계 안 됨', cy.getElementById('evtagg__pB__pC__vt_call').empty(), '단건이 합계됨');
const singleBC = cy.edges('.collapsed-event').filter(e => e.data('_collapsedFrom') === 'call_pB_pC_200');
check('  단건 개별 엣지 표시 유지', singleBC.length === 1 && singleBC[0].visible(), '개별 엣지 숨겨짐/없음');

const aggTx = cy.getElementById('evtagg__a1__a2__vt_transfer');
check('이체 합계 "💸이체 3건 · 합계 17,000,000원"', aggTx.nonempty() && aggTx.data('label') === '💸이체 3건 · 합계 17,000,000원', `got "${aggTx.data('label')}"`);

const hidden = cy.edges('.evt-agg-hidden');
check('중첩 개별 엣지 17개 숨김 (12+2+3)', hidden.length === 17 && hidden.filter(':visible').length === 0, `hidden=${hidden.length}, visible=${hidden.filter(':visible').length}`);

console.log('▶ 단끝(상대 미상) 합계 노드');
const rxAgg = cy.getElementById('evtnodeagg__pB__out__vt_call');
check('pB 수신만 6건 → 합계 노드 "📞수신 6건 · 총 6분"', rxAgg.nonempty() && rxAgg.data('_aggText') === '📞수신 6건 · 총 6분', `got "${rxAgg.nonempty() ? rxAgg.data('_aggText') : '없음'}"`);
const rxEdge = cy.getElementById('evtnodeagg__pB__out__vt_call__e');
check('  방향 보존 (합계노드)-[callee]->(pB)', rxEdge.nonempty() && rxEdge.data('label') === 'callee' && rxEdge.data('target') === 'pB', 'edge 방향/라벨 불일치');
const outAgg = cy.getElementById('evtnodeagg__a1__in__vt_transfer');
check('a1 출금만 2건 → "💸출금 2건 · 합계 3,000,000원"', outAgg.nonempty() && outAgg.data('_aggText') === '💸출금 2건 · 합계 3,000,000원', `got "${outAgg.nonempty() ? outAgg.data('_aggText') : '없음'}"`);
check('발신 단건(pC)은 병합 안 됨 · 원본 노드 유지', cy.getElementById('evtnodeagg__pC__in__vt_call').empty() && cy.getElementById('txcall_pC_0').visible(), '단건 처리 오류');
check('단끝 이벤트 8건 + 엣지 8개 숨김', cy.elements('.evt-nodeagg-hidden').length === 16, `got ${cy.elements('.evt-nodeagg-hidden').length}`);

console.log('▶ 멱등성 (재실행)');
const again = fns.applyEventCollapse();
check('재실행 시 추가 접힘 0', again === 0, `got ${again}`);
check('합계 엣지 중복 없음 (3개 유지)', cy.edges('.collapsed-event-agg').length === 3, `got ${cy.edges('.collapsed-event-agg').length}`);
check('합계 노드 중복 없음 (2개 유지)', cy.nodes('.evt-agg-node').length === 2, `got ${cy.nodes('.evt-agg-node').length}`);

console.log('▶ 펼치기 (원복)');
fns.undoEventCollapse();
check('합성 엣지 전부 제거', cy.edges('.collapsed-event').length === 0, `잔존 ${cy.edges('.collapsed-event').length}`);
check('합계 노드 전부 제거', cy.nodes('.evt-agg-node').length === 0, `잔존 ${cy.nodes('.evt-agg-node').length}`);
check('이벤트 노드 27개 전부 복원·표시', cy.nodes('[label="vt_call"], [label="vt_transfer"]').filter(':visible').length === 27, `got ${cy.nodes('[label="vt_call"], [label="vt_transfer"]').filter(':visible').length}`);
check('원본 연결 엣지 45개 전부 표시', cy.edges('[label="caller"], [label="callee"], [label="from_account"], [label="to_account"]').filter(':visible').length === 45, `got ${cy.edges('[label="caller"], [label="callee"], [label="from_account"], [label="to_account"]').filter(':visible').length}`);

// ── 5) 시각 하네스 생성 (선택) ────────────────────────────────
const hIdx = process.argv.indexOf('--harness');
if (hIdx > -1 && process.argv[hIdx + 1]) {
    const out = process.argv[hIdx + 1];
    const harness = `<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>이벤트 합계 하네스</title>
<script src="file://${path.join(ROOT, 'app/static/vendor/cytoscape/cytoscape.min.js')}"><\/script>
<style>body{margin:0;font-family:system-ui,'Apple SD Gothic Neo';background:#161e33;color:#eee}
#bar{padding:10px 14px;display:flex;gap:10px;align-items:center}
#cyc{width:100vw;height:calc(100vh - 54px)}
button{background:#f39c12;color:#1a1a1a;border:none;border-radius:6px;padding:8px 14px;font-weight:700;cursor:pointer}</style></head>
<body><div id="bar"><b>중첩 이벤트 합계 하네스</b><button id="t" onclick="tg()">이벤트 펼치기</button>
<span id="msg" style="color:#f9ca24;font-size:13px"></span></div><div id="cyc"></div>
<script>
const cy = cytoscape({ container: document.getElementById('cyc'),
  elements: ${JSON.stringify(buildElements())},
  style: [
    { selector: 'node', style: { 'background-color': '#2a78d6', label: 'data(id)', color: '#fff', 'font-size': '11px' } },
    { selector: 'node[label="vt_call"]', style: { 'background-color': '#E67E22', shape: 'diamond', width: 22, height: 22 } },
    { selector: 'node[label="vt_transfer"]', style: { 'background-color': '#F39C12', shape: 'diamond', width: 22, height: 22 } },
    { selector: 'edge', style: { width: 1.5, 'line-color': '#5a6885', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#5a6885', 'curve-style': 'bezier', label: 'data(label)', 'font-size': '8px', color: '#8e9abf' } },
    { selector: 'edge.collapsed-event', style: { width: 3, 'line-style': 'dashed', 'line-color': '#f39c12', 'target-arrow-color': '#f39c12', color: '#f9ca24', 'font-size': '10px', 'font-weight': 'bold', 'text-background-color': '#2d2410', 'text-background-opacity': 1 } },
    { selector: 'edge.collapsed-event-agg', style: { width: 'mapData(_aggCount, 2, 20, 4, 10)', 'line-style': 'solid', 'font-size': '11px' } },
  ] });
${core}
let on = false;
function tg() {
  on = !on;
  if (on) { const n = applyEventCollapse(); document.getElementById('msg').textContent = '이벤트 ' + n + '건 접힘 · 합계 엣지 ' + cy.edges('.collapsed-event-agg').length + '개'; document.getElementById('t').textContent = '이벤트 펼치기'; }
  else { undoEventCollapse(); document.getElementById('msg').textContent = '펼침 (원본 이벤트 노드)'; document.getElementById('t').textContent = '이벤트 접기'; }
  cy.elements(':visible').layout({ name: 'cose', animate: false, fit: true }).run();
}
tg();  // 초기: 접힘+합계 상태
<\/script></body></html>`;
    fs.writeFileSync(out, harness);
    console.log('🖼  하네스 생성:', out);
}

console.log(failed === 0 ? '\n✅ 전체 통과' : `\n❌ ${failed}건 실패`);
process.exit(failed === 0 ? 0 : 1);
