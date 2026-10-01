"""
RDB(V4.0 스테이징 test_v40) → 그래프 적재기 (2026-10-01 정합 2단계 2c).

종전 RdbToGraphService.transfer_data(1,569줄 단일 함수)는 37개 테이블을 다뤘지만, 지원하는 스테이징 스키마
(test_v40)에 실제로 있는 것은 8개뿐이라 나머지 29개 구간은 매번 '테이블 없음'으로 조용히 실패했다
(로컬 추적 2026-10-01). 이 모듈은 실제로 동작하는 8개 테이블을 테이블별 적재 함수로 나누고 공용 GraphWriter 로
쓴다. 나머지 레거시 구간(V2/V3 원천)은 RdbToGraphService 에 그대로 두고, 그 테이블이 있을 때만 거기로 보낸다.

종전 대비 바로잡힌 것 (로컬 구/신 비교로 확인):
  · 인물 키 id → psn_id (SoT 정경) — RDB 에는 실제 인물 ID(PRSN_ID)가 있어 합성하지 않는다
  · 계좌 MERGE 는 원문, MATCH 는 정규화라 하이픈 계좌의 이체·소유 엣지가 사라지던 것 → 양쪽 같은 정규화
  · 전화 노드에 가입자명(holder_nm)이 통신사명으로 들어가던 것 → subs_holder, 통신사는 telco_nm
  · 인물 role_cd 가 nickname 으로 들어가던 것 → 넣지 않는다(역할은 사건 역할 엣지가 표현)
  · 사건 flnm 열(스테이징에선 사건명)을 crime 으로 넣던 것 → incdnt_nm
  · 속성명은 SoT 사전 이름(bank_nm·telco_nm·dlng_amt·call_dur_sec·occrn_dt …) — 이벤트 event_id 는 호환 이중 기록
  · 엣지는 실제 MATCH 건수로 센다 (종전: 실패해도 +1)
"""
import logging

from app.database import validate_graph_path
from app.services.graph_writer import GraphWriter, GraphWriteError

logger = logging.getLogger(__name__)

# 이 적재기가 다루는 스테이징 테이블 — 이 중 하나라도 있으면 V4.0 스테이징으로 본다
V40_TABLES = ('tb_incdnt_mst', 'tb_prsn', 'tb_fin_bacnt', 'tb_telno_mst',
              'tb_fin_bacnt_dlng', 'tb_telno_call_dtl', 'tb_incdnt_prsn', 'tb_telno_join')

ROLE_EDGE = {'SUSPECT': 'suspect_in', 'VICTIM': 'victim_in', 'WITNESS': 'witness_in'}


def _is_atm(no):
    s = str(no or '').strip()
    return s.upper().startswith('ATM') or s == '현금인출'


def _atm_props(no, source_id):
    import re
    s = str(no).strip()
    loc = re.search(r'[가-힣]+', s)
    num = re.search(r'(\d+)$', s)
    place = loc.group() if loc else '미상'
    name = '현금인출' if s == '현금인출' else f"{place} ATM {num.group() if num else ''}".strip()
    return {'atm_id': s, 'atm_nm': name, 'place_name': place, 'source_id': source_id}


def _num(v, cast=float):
    try:
        return cast(v) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


class RdbGraphLoader:
    """test_v40 스테이징 → 그래프. 사용: RdbGraphLoader(conn, graph, 'test_v40').run()"""

    def __init__(self, conn, graph, source_schema, source_domain='investigation'):
        if not validate_graph_path(graph):
            raise GraphWriteError(f'허용되지 않는 그래프명: {graph!r}')
        if not validate_graph_path(source_schema):
            raise GraphWriteError(f'허용되지 않는 스키마명: {source_schema!r}')
        self.conn, self.graph, self.schema, self.domain = conn, graph, source_schema, source_domain
        self.cur = conn.cursor()
        self.counts = {}

    @staticmethod
    def staging_tables(cur, schema):
        cur.execute("SELECT lower(table_name) FROM information_schema.tables WHERE table_schema = %s", (schema,))
        return {r[0] for r in cur.fetchall()}

    def _rows(self, sql):
        """원천 SELECT — 스키마를 명시해 읽는다(그래프 쓰기 graph_path 와 섞이지 않게)."""
        self.cur.execute(sql.replace('{S}', f'"{self.schema}"'))
        return self.cur.fetchall()

    def _count(self, name, n):
        self.counts[name] = self.counts.get(name, 0) + n

    # ── 테이블별 적재 ───────────────────────────────────────────────
    def load_cases(self, w):
        # 스테이징 tb_incdnt_mst.flnm 에는 사건명이 들어 있다(표준 DDL 은 INCDNT_NM=사건명)
        for no, nm, dt in self._rows('SELECT incdnt_no, flnm, occurred_at::text FROM {S}.tb_incdnt_mst'):
            if no:
                w.node('vt_case', {'incdnt_no': no, 'incdnt_nm': nm, 'occrn_dt': dt})
                self._count('cases', 1)

    def load_persons(self, w):
        for pid, name, sid in self._rows('SELECT prsn_id, korn_flnm, source_id FROM {S}.tb_prsn'):
            if pid:
                w.node('vt_psn', {'psn_id': pid, 'name': name, 'korn_flnm': name, 'source_id': sid,
                                  'is_anonymous': not (name or '').strip()})
                self._count('persons', 1)

    def load_accounts(self, w):
        from app.services.etl_service import StandardCodeMapper
        for no, bcd, bnm, dpstr, sid in self._rows(
                'SELECT bacnt_no, bnk_cd, bank_nm, dpstr, source_id FROM {S}.tb_fin_bacnt WHERE bacnt_no IS NOT NULL'):
            if _is_atm(no):
                w.node('vt_atm', _atm_props(no, sid))
            else:
                code = StandardCodeMapper.map_bank_code(bnm) or StandardCodeMapper.map_bank_code(bcd) or bcd
                w.node('vt_bacnt', {'account_no': no, 'bank_cd': code, 'bank_nm': bnm, 'dpstr': dpstr,
                                    'source_id': sid})
            self._count('accounts', 1)

    def load_phones(self, w):
        for telno, holder, carr, sid in self._rows(
                'SELECT telno, holder_nm, carr_cd, source_id FROM {S}.tb_telno_mst WHERE telno IS NOT NULL'):
            w.node('vt_telno', {'telno': telno, 'subs_holder': holder, 'telco_nm': carr, 'source_id': sid})
            self._count('phones', 1)

    def load_transfers(self, w):
        for eid, src, dt, amt, tgt, typ, sid in self._rows(
                'SELECT dlng_id, src_bacnt_no, dlng_dt::text, amount, tgt_bacnt_no, dlng_type, source_id '
                'FROM {S}.tb_fin_bacnt_dlng WHERE dlng_id IS NOT NULL'):
            w.node('vt_transfer', {'transfer_id': eid, 'event_id': eid, 'dlng_amt': _num(amt), 'dlng_dt': dt,
                                   'dlng_se_cd': '01' if typ == 'deposit' else '02', 'source_id': sid})
            meta = {'evid_grade': 'A', 'src_tier': 1}
            for end, etype, out in ((src, 'from_account', True), (tgt, 'to_account', False)):
                if not end:
                    continue
                acct = ('vt_atm', _atm_props(end, sid)) if _is_atm(end) else ('vt_bacnt', {'account_no': end})
                if acct[0] == 'vt_atm':
                    w.node('vt_atm', acct[1])                # 이체에만 나오는 ATM 도 노드로
                ev = ('vt_transfer', {'transfer_id': eid})
                w.edge(etype, acct if out else ev, ev if out else acct, meta)
            self._count('transfers', 1)

    def load_calls(self, w):
        for eid, caller, callee, dt, dur, sid in self._rows(
                'SELECT call_id, caller_telno, callee_telno, bgng_dt::text, duration, source_id '
                'FROM {S}.tb_telno_call_dtl WHERE call_id IS NOT NULL'):
            w.node('vt_call', {'call_id': eid, 'event_id': eid, 'call_strt_dt': dt,
                               'call_dur_sec': _num(dur, int), 'source_id': sid})
            meta = {'evid_grade': 'A', 'src_tier': 1}
            ev = ('vt_call', {'call_id': eid})
            if caller:
                w.edge('caller', ('vt_telno', {'telno': caller}), ev, meta)
            if callee:
                w.edge('callee', ev, ('vt_telno', {'telno': callee}), meta)
            self._count('calls', 1)

    def load_case_roles(self, w):
        # 역할 미상은 witness_in role=unknown (V4.9 involves 삭제)
        for no, pid, role in self._rows(
                'SELECT ip.incdnt_no, ip.prsn_id, ip.role_cd FROM {S}.tb_incdnt_prsn ip '
                'JOIN {S}.tb_incdnt_mst m ON m.incdnt_no = ip.incdnt_no '
                'JOIN {S}.tb_prsn p ON p.prsn_id = ip.prsn_id'):
            if no and pid:
                props = {'evid_grade': 'A', 'src_tier': 1}
                edge = ROLE_EDGE.get(str(role or '').upper())
                if not edge:
                    edge, props['role'] = 'witness_in', 'unknown'
                w.edge(edge, ('vt_psn', {'psn_id': pid}), ('vt_case', {'incdnt_no': no}), props)

    def load_phone_ownership(self, w):
        for telno, pid in self._rows('SELECT telno, prsn_id FROM {S}.tb_telno_join '
                                     'WHERE prsn_id IS NOT NULL AND telno IS NOT NULL'):
            w.edge('owns_phone', ('vt_psn', {'psn_id': pid}), ('vt_telno', {'telno': telno}),
                   {'evid_grade': 'A', 'src_tier': 1})

    def load_account_ownership(self, w):
        # 예금주명 ↔ 인물 성명 조인 (B 등급 — 이름 일치 근거)
        for no, pid in self._rows("SELECT b.bacnt_no, p.prsn_id FROM {S}.tb_fin_bacnt b "
                                  "JOIN {S}.tb_prsn p ON p.korn_flnm = b.dpstr "
                                  "WHERE b.dpstr IS NOT NULL AND b.dpstr <> ''"):
            if no and pid and not _is_atm(no):
                w.edge('has_account', ('vt_psn', {'psn_id': pid}), ('vt_bacnt', {'account_no': no}),
                       {'evid_grade': 'B', 'src_tier': 1})

    LOADERS = ('load_cases', 'load_persons', 'load_accounts', 'load_phones', 'load_transfers', 'load_calls',
               'load_case_roles', 'load_phone_ownership', 'load_account_ownership')
    TABLE_OF = {'load_cases': 'tb_incdnt_mst', 'load_persons': 'tb_prsn', 'load_accounts': 'tb_fin_bacnt',
                'load_phones': 'tb_telno_mst', 'load_transfers': 'tb_fin_bacnt_dlng',
                'load_calls': 'tb_telno_call_dtl', 'load_case_roles': 'tb_incdnt_prsn',
                'load_phone_ownership': 'tb_telno_join', 'load_account_ownership': 'tb_fin_bacnt'}

    def run(self):
        cur = self.cur
        cur.execute("SELECT 1 FROM ag_graph WHERE graphname = %s", (self.graph,))
        if not cur.fetchone():
            cur.execute(f'CREATE GRAPH {self.graph}')
        present = self.staging_tables(cur, self.schema)
        w = GraphWriter(cur, self.graph, mode='strict', batch_size=500)
        # SoT 라벨·엣지를 미리 만든다 — AgensGraph MERGE 는 없는 라벨을 만들지 못해, 후처리(출처 연결 sourced_from 등)가
        #   조용히 0건이 된다(2026-10-01 실측). GraphWriter.flush 도 쓰는 라벨은 만들지만 후처리 라벨까지는 모른다.
        from app.services.ontology_service import KICSCrimeDomainOntology as _O
        for lab in sorted({v['label'] for v in _O.ENTITIES.values()}):
            cur.execute(f'CREATE VLABEL IF NOT EXISTS {lab}')
        for el in _O.RELATIONSHIPS:
            cur.execute(f'CREATE ELABEL IF NOT EXISTS {el}')
        for name in self.LOADERS:
            if self.TABLE_OF[name] in present:
                getattr(self, name)(w)
            else:
                logger.info('[RdbGraphLoader] %s.%s 없음 — %s 건너뜀', self.schema, self.TABLE_OF[name], name)
        st = w.flush()
        self.conn.commit()
        stats = {'nodes': st['nodes'], 'edges': st['edges'], 'edges_unmatched': st['edges_unmatched'], **self.counts}
        logger.info('[RdbGraphLoader] %s → %s: %s', self.schema, self.graph, stats)
        return stats
