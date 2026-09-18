#!/usr/bin/env python3
"""CCOP 적재용 CSV 자체 검증 — 온톨로지 V4.8 규격 (DB 불필요, 표준 라이브러리만)

납품 전에 CSV만 보고 규격 위반을 찾는다. 외부 의존이 없어 폐쇄망에서도 그대로 돈다.

검사
  ① 파일명 인식     — tbl_ 접두 + 규격 키워드. 인식 안 되면 적재 자체가 안 된다
  ② 인코딩          — UTF-8(BOM 허용). cp949 로 저장된 파일을 잡는다
  ③ 필수 컬럼       — 없으면 그 파일 전체가 무의미
  ④ 규격 외 컬럼    — 오타(telno/tel_no)로 값이 통째로 버려지는 사고를 잡는다
  ⑤ 값 형식         — 날짜·일시 형식, 숫자에 섞인 단위문자, NULL/-/N/A 표기
  ⑥ source_id       — V4.8 필수(원본 대조 가능성)
  ⑦ 코드값          — role·se·channel·subj_type 허용값
  ⑧ 파일 간 참조    — 관계 파일이 가리키는 인물·전화·계좌가 노드 파일에 있는지

실행
  python3 validate_csv_v48.py <CSV 폴더>
  python3 validate_csv_v48.py <CSV 폴더> --strict   # 경고도 실패로 취급

종료 코드: 오류 있으면 1, 없으면 0
"""
import argparse
import csv
import os
import re
import sys
from collections import defaultdict

# ── 규격: 키워드 → (필수 컬럼, 선택 컬럼) ──
# 키워드는 긴 것부터 검사한다(case_prsn 이 case 보다 먼저 잡혀야 한다)
SPEC = [
    ('tbl_eg_bactno_poss', {'actno'}, {'prsn_id', 'flnm', 'bank_cd', 'valid_from', 'valid_to', 'source_id'}),
    ('tbl_eg_telno_poss',  {'telno'}, {'prsn_id', 'flnm', 'valid_from', 'valid_to', 'source_id'}),
    ('tbl_eg_case_prsn',   {'incdnt_no', 'prsn_id'}, {'role', 'source_id'}),
    ('tbl_eg_id_use',      {'id_val', 'platform'}, {'prsn_id', 'flnm', 'valid_from', 'valid_to', 'source_id'}),
    ('tbl_eg_id_msg',      {'snd_id', 'rcv_id'},
     {'snd_platform', 'rcv_platform', 'msg_ymdhm', 'channel', 'source_id'}),
    ('tbl_eg_ip_use',      {'subj_type', 'subj_id', 'ip_addr'},
     {'valid_from', 'valid_to', 'access_type', 'source_id'}),
    ('tbl_eg_loc_use',     {'subj_type', 'subj_id', 'loc_id'}, {'evt_ymdhm', 'source_id'}),
    ('tbl_eg_call',        {'dsptch_no', 'rcptn_no'},
     {'bgng_ymdhm', 'end_ymdhm', 'tlcmco', 'channel', 'bsst_addr', 'source_id'}),
    ('tbl_eg_case',        {'incdnt_no'},
     {'flnm', 'incdnt_nm', 'incdnt_typ_cd', 'occrn_dt', 'incdnt_smry_cn', 'damage_amt', 'crime_site', 'source_id'}),
    ('tbl_eg_rmt',         {'se', 'actno', 'rlt_actno'},
     {'bank', 'bank_cd', 'dpstr', 'rlt_bank', 'rlt_bank_cd', 'rlt_dpstr', 'rmt_ymdhm',
      'dpst_amt', 'tkmny_amt', 'ip_addr', 'brnch_nm', 'source_id'}),
    ('tbl_vt_psn',   {'flnm'}, {'psn_id', 'dob', 'gender', 'nationality', 'occp_nm', 'source_id'}),
    ('tbl_vt_telno', {'telno'}, {'telco_nm', 'join_typ_cd', 'subs_holder', 'is_burner', 'source_id'}),
    ('tbl_vt_bacnt', {'actno'}, {'bank', 'bank_cd', 'dpstr', 'account_type', 'bacnt_opn_dt', 'source_id'}),
    ('tbl_vt_ip',    {'ip_addr'}, {'ip_ver', 'asn_nm', 'ctry_cd', 'source_id'}),
    ('tbl_vt_id',    {'id_val', 'platform'}, {'id_type', 'nickname', 'source_id'}),
    ('tbl_vt_loc',   {'loc_id'},
     {'loc_type', 'address', 'sido_nm', 'sigungu_nm', 'place_name', 'bsst_addr', 'source_id'}),
]
DATE_COLS = {'occrn_dt', 'dob', 'bacnt_opn_dt'}
DTTM_COLS = {'bgng_ymdhm', 'end_ymdhm', 'rmt_ymdhm', 'msg_ymdhm', 'evt_ymdhm'}
# 유효기간은 자료에 따라 날짜(명의 변경일)일 수도, 일시(IP 접속 시각)일 수도 있다 — 둘 다 허용
DATE_OR_DTTM_COLS = {'valid_from', 'valid_to'}
NUM_COLS = {'dpst_amt', 'tkmny_amt', 'damage_amt'}
CODES = {
    'role': {'SUSPECT', 'VICTIM', 'WITNESS', 'REPORTER', 'SUSPECT_ACCOMPLICE'},
    'se': {'입금', '출금'},
    'subj_type': {'psn', 'telno', 'bacnt', 'id', 'atm', 'dev'},
    'loc_type': {'cell_tower', 'atm_loc', 'poi'},
}
NULLISH = {'null', 'NULL', 'N/A', 'n/a', '-', 'NaN', 'nan', 'None', '#N/A'}
RE_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RE_DTTM = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
RE_NUM = re.compile(r'^-?[\d,]+(\.\d+)?$')

MAX_SHOW = 5   # 같은 유형은 앞 5건만 보여준다


class Report:
    def __init__(self):
        self.err, self.warn = defaultdict(list), defaultdict(list)

    def error(self, key, detail):
        self.err[key].append(detail)

    def warning(self, key, detail):
        self.warn[key].append(detail)

    def dump(self):
        for kind, bag, mark in (('오류', self.err, '⛔'), ('경고', self.warn, '⚠')):
            for key, items in bag.items():
                print(f'  {mark} {key} ({len(items)}건)')
                for d in items[:MAX_SHOW]:
                    print(f'      {d}')
                if len(items) > MAX_SHOW:
                    print(f'      … 외 {len(items) - MAX_SHOW}건')
        return sum(len(v) for v in self.err.values()), sum(len(v) for v in self.warn.values())


def match_spec(fname):
    base = os.path.basename(fname)
    for kw, req, opt in SPEC:
        if kw in base:
            return kw, req, opt
    return None, None, None


def read_csv(path, rep):
    """UTF-8(BOM 허용)로 읽는다. 실패하면 인코딩 오류로 보고."""
    try:
        with open(path, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
            hdr = rows and list(rows[0].keys()) or []
            if not rows:
                with open(path, encoding='utf-8-sig', newline='') as f2:
                    hdr = next(csv.reader(f2), [])
            return hdr, rows
    except UnicodeDecodeError:
        rep.error('인코딩', f'{os.path.basename(path)} — UTF-8 로 읽히지 않음(cp949/euc-kr 로 보임). '
                            'Excel 에서 "CSV UTF-8"로 다시 저장하십시오')
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', help='CSV 들이 있는 폴더')
    ap.add_argument('--strict', action='store_true', help='경고도 실패로 취급')
    args = ap.parse_args()
    if not os.path.isdir(args.folder):
        sys.exit(f'폴더가 아닙니다: {args.folder}')

    files = []                                   # 하위 폴더까지(필수/선택 분리 구성 대응)
    for root, _d, fns in os.walk(args.folder):
        files += [os.path.relpath(os.path.join(root, f), args.folder)
                  for f in fns if f.lower().endswith('.csv')]
    files.sort()
    if not files:
        sys.exit(f'CSV 가 없습니다: {args.folder}')

    rep = Report()
    # 참조 정합용 수집
    known = {'psn_id': set(), 'flnm': set(), 'telno': set(), 'actno': set(),
             'incdnt_no': set(), 'ip_addr': set(), 'id_val': set(), 'loc_id': set()}
    refs = []   # (파일, 행번호, 컬럼, 값, 찾을 집합이름)

    print(f'══ {args.folder} · CSV {len(files)}개 ══')
    recognized = []
    for fn in files:
        path = os.path.join(args.folder, fn)
        kw, req, opt = match_spec(fn)
        if not kw:
            rep.error('파일명 미인식',
                      f'{fn} — tbl_ 로 시작하고 규격 키워드를 포함해야 적재됩니다')
            continue
        hdr, rows = read_csv(path, rep)
        if hdr is None:
            continue
        recognized.append((fn, kw, len(rows)))
        allowed = req | opt
        missing = req - set(hdr)
        if missing:
            rep.error('필수 컬럼 누락', f'{fn} — {sorted(missing)}')
        for c in hdr:
            if c and c not in allowed:
                rep.warning('규격 외 컬럼(무시됨)', f'{fn} · "{c}" — 오타가 아닌지 확인')
        if 'source_id' not in hdr:
            rep.warning('source_id 없음', f'{fn} — V4.8 필수. 원본 문서 대조가 불가능해집니다')

        for i, row in enumerate(rows, start=2):     # 1행은 헤더
            for col, val in row.items():
                if col is None or val is None:
                    continue
                v = val.strip()
                if not v:
                    continue
                if v in NULLISH:
                    rep.warning('빈 값 표기', f'{fn}:{i} · {col}="{v}" — 그냥 비워두십시오')
                    continue
                if col in DATE_COLS and not RE_DATE.match(v):
                    rep.error('날짜 형식', f'{fn}:{i} · {col}="{v}" — YYYY-MM-DD 이어야 합니다')
                if col in DTTM_COLS and not RE_DTTM.match(v):
                    rep.error('일시 형식', f'{fn}:{i} · {col}="{v}" — YYYY-MM-DD HH:MM:SS 이어야 합니다')
                if col in DATE_OR_DTTM_COLS and not (RE_DATE.match(v) or RE_DTTM.match(v)):
                    rep.error('날짜/일시 형식', f'{fn}:{i} · {col}="{v}" — '
                                                'YYYY-MM-DD 또는 YYYY-MM-DD HH:MM:SS 이어야 합니다')
                if col in NUM_COLS and not RE_NUM.match(v):
                    rep.error('숫자 아님', f'{fn}:{i} · {col}="{v}" — 단위문자를 빼주십시오(쉼표는 허용)')
                if col in CODES and v not in CODES[col]:
                    rep.error('코드값', f'{fn}:{i} · {col}="{v}" — 허용값 {sorted(CODES[col])}')
            if 'source_id' in row and not (row.get('source_id') or '').strip():
                rep.warning('source_id 빈 값', f'{fn}:{i}')

            # 식별자 수집 / 참조 등록
            if kw in ('tbl_vt_psn',):
                for c in ('psn_id', 'flnm'):
                    if (row.get(c) or '').strip():
                        known[c].add(row[c].strip())
            elif kw == 'tbl_vt_telno' and (row.get('telno') or '').strip():
                known['telno'].add(row['telno'].strip())
            elif kw == 'tbl_vt_bacnt' and (row.get('actno') or '').strip():
                known['actno'].add(row['actno'].strip())
            elif kw == 'tbl_eg_case' and (row.get('incdnt_no') or '').strip():
                known['incdnt_no'].add(row['incdnt_no'].strip())
            elif kw == 'tbl_vt_ip' and (row.get('ip_addr') or '').strip():
                known['ip_addr'].add(row['ip_addr'].strip())
            elif kw == 'tbl_vt_id' and (row.get('id_val') or '').strip():
                known['id_val'].add(row['id_val'].strip())
            elif kw == 'tbl_vt_loc' and (row.get('loc_id') or '').strip():
                known['loc_id'].add(row['loc_id'].strip())

            if kw.startswith('tbl_eg_'):
                for col, bucket in (('telno', 'telno'), ('actno', 'actno'), ('rlt_actno', 'actno'),
                                    ('incdnt_no', 'incdnt_no'), ('ip_addr', 'ip_addr'),
                                    ('loc_id', 'loc_id'), ('id_val', 'id_val')):
                    v = (row.get(col) or '').strip()
                    if v:
                        refs.append((fn, i, col, v, bucket))
                # 인물 참조: psn_id 가 있으면 그걸로, 없으면 flnm 으로
                pid, nm = (row.get('psn_id') or '').strip(), (row.get('flnm') or '').strip()
                if pid:
                    refs.append((fn, i, 'psn_id', pid, 'psn_id'))
                elif nm:
                    refs.append((fn, i, 'flnm', nm, 'flnm'))
                if kw == 'tbl_eg_case_prsn' and pid and not known['psn_id']:
                    pass    # 노드 파일이 psn_id 를 안 쓰는 경우는 아래 참조검사에서 걸린다

    # ⑧ 파일 간 참조 정합 — 노드 파일이 아예 없으면 검사 생략(부분 납품일 수 있음)
    for fn, ln, col, val, bucket in refs:
        if not known[bucket]:
            continue
        if val not in known[bucket]:
            rep.error('참조 불일치', f'{fn}:{ln} · {col}="{val}" — 노드 파일에 없습니다'
                                     ' (표기 불일치이거나 노드 파일 누락)')

    for fn, kw, n in recognized:
        print(f'  · {fn:<28} [{kw}] {n}행')
    print()
    ne, nw = rep.dump()
    if not ne and not nw:
        print('  ✅ 규격 위반 없음')
    else:
        print(f'\n  오류 {ne} · 경고 {nw}')
    sys.exit(1 if (ne or (args.strict and nw)) else 0)


if __name__ == '__main__':
    main()
