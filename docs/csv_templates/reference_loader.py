#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CCOP 표준 CSV → 표준 테이블 적재 참고 구현 (전처리 기관 배포용)
================================================================

목적
  본 파일은 CCOP 플랫폼이 규격 CSV(`tbl_*.csv`)를 표준 테이블로 적재할 때
  사용하는 로직의 **참고용 발췌본**입니다. 전처리 기관이 자체 환경에서
  적재 동작(컬럼 매핑·식별키·정규화·이체방향 판정 등)을 이해·검증하는 데
  활용하도록 제공합니다.

  - 입력 파일명·컬럼 규격은 동봉된 `README.md`(CSV 규격서)를 따릅니다.
  - 표준 테이블 적재 이후의 온톨로지 그래프 변환은 별도 단계이며 본 파일 범위 밖입니다.

원본 대비 차이 (참고용 각색)
  - Flask(current_app) 의존을 제거하고 DB 접속정보·대상 스키마를 함수 인자로 받습니다.
  - 로직·SQL(INSERT/ON CONFLICT/정규화/이체방향)은 운영 구현과 동일합니다.

의존성
  pip install pandas psycopg2-binary

사용 예
  python reference_loader.py \
      --dsn "host=... port=... dbname=... user=... password=..." \
      --schema test_ccop \
      --dir ./            # tbl_*.csv 가 있는 폴더

주의
  - 본 코드는 CCOP 플랫폼 참고용 발췌본입니다. 협력 범위 내 참고 용도로만 사용하세요.
  - 대상 스키마에는 표준 테이블(tb_prsn, tb_fin_bacnt, tb_telno_mst, tb_telno_call_dtl,
    tb_fin_bacnt_dlng, tb_fin_extrc_bacnt, tb_telno_join, tb_incdnt_mst)이 사전에
    존재해야 합니다. (tb_incdnt_prsn 은 본 코드가 자동 생성)
"""
import argparse
import logging
import os
import re
import uuid as _uuid
from datetime import datetime as dt_parse

import pandas as pd
import psycopg2

logger = logging.getLogger("ccop.reference_loader")

# 업로드 권장 순서: 노드 먼저 → 관계/이벤트 나중
LOAD_ORDER = [
    "tbl_vt_psn", "tbl_vt_telno", "tbl_vt_bacnt", "tbl_eg_case",
    "tbl_eg_bactno_poss", "tbl_eg_telno_poss", "tbl_eg_case_prsn",
    "tbl_eg_call", "tbl_eg_rmt",
]


# ── 값 표준화 (적재 단일 지점) ────────────────────────────────────────────
def norm_telno(v):
    """전화번호 표준화 — 숫자만 남김(선행 0 보존).
    주의: CSV 숫자 추론으로 선행 0이 소실되지 않도록 반드시 dtype=str 로 읽을 것.
    """
    return re.sub(r"[^0-9]", "", str(v or ""))


def norm_account(v):
    """계좌번호 표준화 — 대시/공백 제거로 파편화 방지.
    md5/sha256 해시 식별자는 소문자화만 하고 원형 유지.
    """
    s = str(v or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{32}", s) or re.fullmatch(r"[0-9a-f]{64}", s):
        return s
    return re.sub(r"[\s\-]", "", s)


def import_predefined_schema_to_rdb(file_path, filename, db_config,
                                    target_schema="test_ccop",
                                    clear_existing=False,
                                    source_domain="KICS", source_id=None):
    """규격 CSV 1개를 표준 테이블에 적재. 파일명(filename)으로 처리 핸들러를 결정한다.

    Args:
        file_path: CSV 실제 경로
        filename : 원본 파일명 (핸들러 판별 키 — 'tbl_vt_psn' 등을 부분 포함해야 함)
        db_config: psycopg2.connect(**db_config) 로 넘길 접속정보 dict
        target_schema: 적재 대상 스키마 (search_path)
        clear_existing: True 면 적재 전 대상 스키마 표준 테이블 TRUNCATE
    Returns:
        (성공여부: bool, 통계 dict 또는 오류메시지: str)
    """
    count_stats = {"cases": 0, "suspects": 0, "accounts": 0, "phones": 0,
                   "transfers": 0, "calls": 0, "relations": 0}
    conn = cur = None
    try:
        conn = psycopg2.connect(**db_config)
        # 파일 단위 all-or-nothing (부분 적재 방지) — 중간 행 실패 시 전체 롤백
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(f'SET search_path = "{target_schema}", public;')

        if clear_existing:
            tables_to_clear = [
                "TB_DGTL_FILE_INVNT", "TB_EML_TRNS_EVT", "TB_SYS_LGN_EVT",
                "TB_DRUG_SLANG", "TB_DRUG_CLUE", "TB_FRD_VCTM_RPT",
                "TB_WEB_MLGN_IDC", "TB_WEB_ATCH", "TB_WEB_PAGE", "TB_WEB_URL", "TB_WEB_DMN",
                "TB_VHCL_TOLL_EVT", "TB_VHCL_LPR_EVT", "TB_VHCL_MST",
                "TB_GEO_TRST_CARD_TRIP", "TB_GEO_MBL_LOC_EVT",
                "TB_CHAT_MSG", "TB_TELNO_SMS_MSG", "TB_TELNO_CALL_DTL",
                "TB_TELNO_JOIN", "TB_TELNO_MST",
                "TB_FIN_EXTRC_BACNT", "TB_FIN_BACNT_DLNG", "TB_FIN_BACNT",
                "TB_INST", "TB_PRSN", "TB_INCDNT_MST",
            ]
            for table in tables_to_clear:
                # savepoint 로 statement 격리 — 미존재 테이블 오류가 전체 트랜잭션을 abort 시키지 않음
                try:
                    cur.execute("SAVEPOINT sp_trunc")
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
                    cur.execute("RELEASE SAVEPOINT sp_trunc")
                except Exception as _te:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_trunc")
                    logger.debug("TRUNCATE 건너뜀(%s): %s", table, _te)

        # dtype=str: 전화/계좌 등 0-시작 식별자의 숫자 추론(선행 0 소실) 방지
        df = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str).fillna("")
        fname = filename.lower()

        def gen_id(prefix="id"):
            return f"{prefix}_{_uuid.uuid4().hex[:16]}"

        # ── 노드: 인물 ──────────────────────────────────────────────
        if "tbl_vt_psn" in fname:
            for _, row in df.iterrows():
                flnm = str(row.get("flnm", "")).strip()
                if flnm:
                    cur.execute("""
                        INSERT INTO tb_prsn (prsn_id, korn_flnm, prsn_se_cd, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, '99', %s, %s, 1)
                        ON CONFLICT (prsn_id) DO NOTHING
                    """, (flnm, flnm, source_domain, source_id))
                    if cur.rowcount > 0:
                        count_stats["suspects"] += 1

        # ── 노드: 전화번호 ──────────────────────────────────────────
        elif "tbl_vt_telno" in fname:
            for _, row in df.iterrows():
                telno = norm_telno(row.get("telno", ""))
                if telno:
                    cur.execute("""
                        INSERT INTO tb_telno_mst (telno, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, 1)
                        ON CONFLICT (telno) DO NOTHING
                    """, (telno, source_domain, source_id))
                    if cur.rowcount > 0:
                        count_stats["phones"] += 1

        # ── 노드: 계좌 ──────────────────────────────────────────────
        elif "tbl_vt_bacnt" in fname:
            for _, row in df.iterrows():
                actno = norm_account(row.get("actno", ""))
                dpstr = str(row.get("dpstr", "")).strip()
                bank = str(row.get("bank", "")).strip()
                if actno:
                    cur.execute("""
                        INSERT INTO tb_fin_bacnt (bacnt_id, bacnt_no, bnk_cd, bank_nm, dpstr, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, NULLIF(%s,''), NULLIF(%s,''), %s, %s, 1)
                        ON CONFLICT (bacnt_no, COALESCE(bnk_cd,'')) DO UPDATE SET
                            bank_nm = COALESCE(EXCLUDED.bank_nm, tb_fin_bacnt.bank_nm),
                            dpstr   = COALESCE(EXCLUDED.dpstr,   tb_fin_bacnt.dpstr)
                    """, (gen_id("bacnt"), actno, "999", bank, dpstr, source_domain, source_id))
                    if cur.rowcount > 0:
                        count_stats["accounts"] += 1

        # ── 이벤트: 통화 ────────────────────────────────────────────
        elif "tbl_eg_call" in fname:
            for _, row in df.iterrows():
                caller = norm_telno(row.get("dsptch_no", ""))
                callee = norm_telno(row.get("rcptn_no", ""))
                start_dt = str(row.get("bgng_ymdhm", "")).strip()
                end_dt = str(row.get("end_ymdhm", "")).strip()
                tlcmco = str(row.get("tlcmco", "")).strip()
                dur_sec = 0
                try:
                    t1 = dt_parse.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
                    t2 = dt_parse.strptime(end_dt, "%Y-%m-%d %H:%M:%S")
                    dur_sec = int((t2 - t1).total_seconds())
                except Exception:
                    pass
                if caller and callee:
                    cur.execute("INSERT INTO tb_telno_mst (telno, carr_cd, source_domain, source_id, reliability_tier) "
                                "VALUES (%s, NULLIF(%s,''), %s, %s, 1) ON CONFLICT (telno) DO NOTHING",
                                (caller, tlcmco, source_domain, source_id))
                    cur.execute("INSERT INTO tb_telno_mst (telno, source_domain, source_id, reliability_tier) "
                                "VALUES (%s, %s, %s, 1) ON CONFLICT (telno) DO NOTHING",
                                (callee, source_domain, source_id))
                    cur.execute("""
                        INSERT INTO tb_telno_call_dtl
                            (call_id, caller_telno, callee_telno, bgng_dt, end_dt, duration, carr_cd, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, NULLIF(%s,'')::timestamp, NULLIF(%s,'')::timestamp, %s, NULLIF(%s,''), %s, %s, 1)
                        ON CONFLICT (call_id) DO NOTHING
                    """, (gen_id("call"), caller, callee, start_dt, end_dt, dur_sec, tlcmco, source_domain, source_id))
                    if cur.rowcount > 0:
                        count_stats["calls"] += 1

        # ── 이벤트: 계좌 이체 ──────────────────────────────────────
        elif "tbl_eg_rmt" in fname:
            for _, row in df.iterrows():
                se = str(row.get("se", "")).strip()
                dpstr = str(row.get("dpstr", "")).strip()
                bank = str(row.get("bank", "")).strip()
                actno = norm_account(row.get("actno", ""))
                rlt_bank = str(row.get("rlt_bank", "")).strip()
                rlt_dpstr = str(row.get("rlt_dpstr", "")).strip()
                rlt_actno = norm_account(row.get("rlt_actno", ""))
                date_val = str(row.get("rmt_ymdhm", "")).strip()
                try:
                    dpst_amt = int(float(str(row.get("dpst_amt", "0")).replace(",", "") or "0"))
                except Exception:
                    dpst_amt = 0
                try:
                    tkmny_amt = int(float(str(row.get("tkmny_amt", "0")).replace(",", "") or "0"))
                except Exception:
                    tkmny_amt = 0
                amount = dpst_amt if dpst_amt > 0 else tkmny_amt
                if actno:
                    cur.execute("""
                        INSERT INTO tb_fin_bacnt (bacnt_id, bacnt_no, bnk_cd, bank_nm, dpstr, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, NULLIF(%s,''), NULLIF(%s,''), %s, %s, 1)
                        ON CONFLICT (bacnt_no, COALESCE(bnk_cd,'')) DO UPDATE SET
                            bank_nm = COALESCE(EXCLUDED.bank_nm, tb_fin_bacnt.bank_nm),
                            dpstr   = COALESCE(EXCLUDED.dpstr,   tb_fin_bacnt.dpstr)
                    """, (gen_id("bacnt"), actno, "999", bank, dpstr, source_domain, source_id))
                if rlt_actno:
                    cur.execute("""
                        INSERT INTO tb_fin_bacnt (bacnt_id, bacnt_no, bnk_cd, bank_nm, dpstr, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, NULLIF(%s,''), NULLIF(%s,''), %s, %s, 1)
                        ON CONFLICT (bacnt_no, COALESCE(bnk_cd,'')) DO UPDATE SET
                            bank_nm = COALESCE(EXCLUDED.bank_nm, tb_fin_bacnt.bank_nm),
                            dpstr   = COALESCE(EXCLUDED.dpstr,   tb_fin_bacnt.dpstr)
                    """, (gen_id("bacnt"), rlt_actno, "999", rlt_bank, rlt_dpstr, source_domain, source_id))
                if actno and rlt_actno:
                    # 이체 방향: 입금이면 상대→기준, 출금이면 기준→상대
                    if se == "입금":
                        src_act, tgt_act, dlng_type = rlt_actno, actno, "deposit"
                    else:
                        src_act, tgt_act, dlng_type = actno, rlt_actno, "withdraw"
                    cur.execute("""
                        INSERT INTO tb_fin_bacnt_dlng
                            (dlng_id, src_bacnt_no, tgt_bacnt_no, amount, dlng_dt, dlng_type, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, %s, NULLIF(%s,'')::timestamp, %s, %s, %s, 1)
                        ON CONFLICT (dlng_id) DO NOTHING
                    """, (gen_id("dlng"), src_act, tgt_act, amount, date_val, dlng_type, source_domain, source_id))
                    if cur.rowcount > 0:
                        count_stats["transfers"] += 1

        # ── 관계: 계좌 소유 (인물→계좌) ────────────────────────────
        elif "tbl_eg_bactno_poss" in fname:
            for _, row in df.iterrows():
                flnm = str(row.get("flnm", "")).strip()
                actno = norm_account(row.get("actno", ""))
                if flnm and actno:
                    cur.execute("""
                        INSERT INTO tb_prsn (prsn_id, korn_flnm, prsn_se_cd, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, '99', %s, %s, 1)
                        ON CONFLICT (prsn_id) DO NOTHING
                    """, (flnm, flnm, source_domain, source_id))
                    cur.execute("""
                        INSERT INTO tb_fin_bacnt (bacnt_id, bacnt_no, bnk_cd, dpstr, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, %s, %s, %s, 1)
                        ON CONFLICT (bacnt_no, COALESCE(bnk_cd,'')) DO UPDATE SET
                            dpstr = COALESCE(EXCLUDED.dpstr, tb_fin_bacnt.dpstr)
                    """, (gen_id("bacnt"), actno, "999", flnm, source_domain, source_id))
                    cur.execute("""
                        INSERT INTO tb_fin_extrc_bacnt
                            (extrc_id, bacnt_no, prsn_id, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, %s, %s, 1)
                        ON CONFLICT (extrc_id) DO NOTHING
                    """, (gen_id("extrc"), actno, flnm, source_domain, source_id))
                    count_stats["relations"] += 1
                    count_stats["accounts"] += 1

        # ── 관계: 전화 가입 (인물→전화) ────────────────────────────
        elif "tbl_eg_telno_poss" in fname:
            for _, row in df.iterrows():
                flnm = str(row.get("flnm", "")).strip()
                telno = norm_telno(row.get("telno", ""))
                if flnm and telno:
                    cur.execute("""
                        INSERT INTO tb_prsn (prsn_id, korn_flnm, prsn_se_cd, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, '99', %s, %s, 1)
                        ON CONFLICT (prsn_id) DO NOTHING
                    """, (flnm, flnm, source_domain, source_id))
                    cur.execute("""
                        INSERT INTO tb_telno_mst (telno, holder_nm, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, %s, 1)
                        ON CONFLICT (telno) DO UPDATE SET
                            holder_nm = COALESCE(EXCLUDED.holder_nm, tb_telno_mst.holder_nm)
                    """, (telno, flnm, source_domain, source_id))
                    cur.execute("""
                        INSERT INTO tb_telno_join
                            (join_id, prsn_id, telno, join_type, source_domain, source_id, reliability_tier)
                        VALUES (%s, %s, %s, '01', %s, %s, 1)
                        ON CONFLICT (prsn_id, telno) DO NOTHING
                    """, (gen_id("join"), flnm, telno, source_domain, source_id))
                    count_stats["relations"] += 1
                    count_stats["phones"] += 1

        # ── 관계: 사건 연루 (사건↔인물) ────────────────────────────
        elif "tbl_eg_case_prsn" in fname:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tb_incdnt_prsn (
                    incdnt_no VARCHAR(100),
                    prsn_id VARCHAR(100),
                    role_cd VARCHAR(50),
                    source_domain VARCHAR(50) DEFAULT 'investigation',
                    source_id VARCHAR(100),
                    reliability_tier SMALLINT DEFAULT 1,
                    rec_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (incdnt_no, prsn_id)
                )
            """)
            for _, row in df.iterrows():
                incdnt_no = str(row.get("incdnt_no", "")).strip()
                prsn_id = str(row.get("prsn_id", "")).strip()
                role = str(row.get("role", "")).strip()
                if incdnt_no and prsn_id:
                    cur.execute("""
                        INSERT INTO tb_incdnt_prsn (incdnt_no, prsn_id, role_cd, source_domain, source_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (incdnt_no, prsn_id) DO UPDATE SET role_cd = EXCLUDED.role_cd
                    """, (incdnt_no, prsn_id, role, source_domain, source_id))
                    count_stats["relations"] += 1

        # ── 노드: 사건 ──────────────────────────────────────────────
        elif "tbl_eg_case" in fname:
            for _, row in df.iterrows():
                incdnt_no = str(row.get("incdnt_no", "")).strip()
                incdnt_nm = str(row.get("incdnt_nm", "")).strip()
                typ_cd = str(row.get("incdnt_typ_cd", "")).strip()
                occrn_dt = str(row.get("occrn_dt", "")).strip()
                smry = str(row.get("incdnt_smry_cn", "")).strip()
                if incdnt_no:
                    cur.execute("""
                        INSERT INTO tb_incdnt_mst
                            (incdnt_no, flnm, crime_type, occurred_at, source_domain, source_id, reliability_tier)
                        VALUES (%s, NULLIF(%s,''), NULLIF(%s,''), NULLIF(%s,'')::date, %s, %s, 1)
                        ON CONFLICT (incdnt_no) DO UPDATE SET
                            flnm       = COALESCE(EXCLUDED.flnm, tb_incdnt_mst.flnm),
                            crime_type = COALESCE(EXCLUDED.crime_type, tb_incdnt_mst.crime_type)
                    """, (incdnt_no, incdnt_nm or smry[:200], typ_cd, occrn_dt, source_domain, source_id))
                    if cur.rowcount > 0:
                        count_stats["cases"] += 1

        else:
            conn.rollback()
            return False, f"알 수 없는 파일명(핸들러 없음): {filename}"

        conn.commit()
        return True, count_stats

    except Exception as e:
        if conn:
            conn.rollback()
        return False, str(e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _parse_dsn(dsn: str) -> dict:
    """'key=value key=value' 형식 DSN → psycopg2 kwargs dict."""
    cfg = {}
    for tok in dsn.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            cfg[k] = v
    return cfg


def main():
    ap = argparse.ArgumentParser(description="CCOP 규격 CSV 표준테이블 적재 참고 구현")
    ap.add_argument("--dsn", required=True,
                    help='DB 접속정보. 예: "host=localhost port=5432 dbname=ccop user=ccop password=..."')
    ap.add_argument("--schema", default="test_ccop", help="적재 대상 스키마 (기본 test_ccop)")
    ap.add_argument("--dir", default=".", help="tbl_*.csv 가 위치한 폴더 (기본 현재 폴더)")
    ap.add_argument("--fresh", action="store_true", help="첫 파일 적재 전 대상 스키마 초기화(TRUNCATE)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db_config = _parse_dsn(args.dsn)

    files = []
    for key in LOAD_ORDER:  # 권장 순서대로
        for fn in sorted(os.listdir(args.dir)):
            if fn.lower().endswith(".csv") and key in fn.lower():
                files.append(fn)
    files = list(dict.fromkeys(files))  # 중복 제거, 순서 유지
    if not files:
        print(f"적재할 tbl_*.csv 파일이 없습니다: {args.dir}")
        return

    for idx, fn in enumerate(files):
        clear_now = args.fresh and idx == 0  # 첫 파일에서만 초기화
        ok, stats = import_predefined_schema_to_rdb(
            os.path.join(args.dir, fn), fn, db_config,
            target_schema=args.schema, clear_existing=clear_now,
            source_domain="PARTNER", source_id="reference-loader")
        status = "OK " if ok else "ERR"
        print(f"[{status}] {fn:26s} -> {stats}")


if __name__ == "__main__":
    main()
