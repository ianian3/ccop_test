"""
Schema Format Benchmark — Text2Cypher 파싱 정확도 비교
======================================================
세 가지 스키마 포맷이 Cypher 생성 정확도에 미치는 영향을 측정합니다.

사용법:
    python scripts/schema_format_benchmark.py \
        --graph ccop_graph \
        --model gpt-4o \
        --output results_schema_fmt.json

환경 필요: OPENAI_API_KEY (또는 SLLM_ENDPOINT + SLLM_MODEL_NAME)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

# ── 프로젝트 루트를 sys.path에 추가 ──────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openai import OpenAI

# =============================================================================
# 1. 테스트 입력 — 25개 벤치마크 쿼리
# =============================================================================

BENCHMARK_QUERIES = [
    # 1단계: 기초 단일 노드 검색
    ("이름이 '피의자1'인 사람(vt_psn) 노드를 모두 찾아줘.", "basic"),
    ("계좌번호가 '110-1111-1111'인 계좌(vt_bacnt)의 주인을 보여줘.", "basic"),
    ("전화번호가 '1000000001'인 통신 기기(vt_telno) 소유자 목록을 뽑아.", "basic"),
    ("사건번호가 'CASE-2023-001'인 사건(vt_case)에 연루된 사람들을 찾아줘.", "basic"),
    ("IP 주소가 '203.108.1.223'인 IP를 통해 접속한 인물 리스트.", "basic"),
    # 2단계: 방향성 추적
    ("피의자1 명의의 계좌에서 다른 사람 계좌로 출금(from_account)된 거래 이력 전체.", "direction"),
    ("특정 ATM 기기(ATM-001)에서 돈을 입금(to_account) 시킨 사람들의 이름.", "direction"),
    ("'0100000001' 번호에서 전화를 발신(caller)하여 통화한 기록 전체.", "direction"),
    ("피해자1이 돈을 송금해서 최종적으로 돈을 받은 수신 계좌(to_account) 목록.", "direction"),
    ("불법 도박 집단이 사용한 의심 IP 세트와 연관된 접속 이벤트 내역.", "direction"),
    # 3단계: 숫자/날짜 필터링
    ("이체 금액(amount)이 500만원(5000000) 이상인 거액 송금 거래 내역.", "filter"),
    ("통화 시간(duration)이 600초를 초과하는 통화 내역 중에 발신자 번호.", "filter"),
    ("이체 금액이 딱 10만원(100000)인 의심스러운 쪼개기 입금 거래들.", "filter"),
    ("등록일시가 '2023-05-01' 이후에 만들어진 모든 대포통장 리스트.", "filter"),
    ("거래 금액이 문자열 '50000'보다 작은(<=) 소액 이체내역을 찾아줘.", "filter"),
    # 4단계: 경로 탐색
    ("피해자1의 계좌에서 출발해 3단계 거쳐 피의자1에게 도달하는 자금 이동의 경로.", "path"),
    ("피해자1과 피의자1 사이에 엮여 있는 공통된 관계망을 그려줘.", "path"),
    ("서로 다른 3개의 금융 사기 사건에 동시에 공통으로 등장하는 핵심 피의자.", "path"),
    ("범죄계좌 '110-1111-1111'에서 5단계를 거쳐 세탁된 자금의 최종 종착지 계좌들.", "path"),
    ("수사 대상자 '피의자1'에서 시작해서 '피의자2'로 향하는 연결망 최단 경로를 추출해.", "path"),
    # 5단계: 자연어/비격식
    ("내 국민은행 통장('110-1111-1111')에서 무단으로 돈 빼간 사기꾼들 다 찾아줘.", "b2c"),
    ("SKT 폰 쓰는 애들 중에 금융 사기(CASE-99) 저지른 놈들만 솎아내봐.", "b2c"),
    ("저 계좌(국민 010-1111-1111)가 토스뱅크에서 우리은행으로 돈 보낸 내역 싹 다 가져와.", "b2c"),
    ("새벽에 IP 이상한데서 로그인한 놈들 누구야 찾아봐 줘.", "b2c"),
    ("농협은행(NH)에 계좌 튼 사람 명단 싹 뽑아줘.", "b2c"),
]

# =============================================================================
# 2. 스키마 데이터 (실제 DB 대신 고정 사용 — 동일 조건 보장)
# =============================================================================

# 실제 AgensGraph 스키마 기반 (get_current_schema() 반환 형태와 동일)
CANONICAL_SCHEMA = {
    "node_labels": {
        "vt_psn":      ["name", "birth", "gender", "addr", "nationality"],
        "vt_bacnt":    ["actno", "bank", "owner", "balance", "open_date"],
        "vt_telno":    ["telno", "carrier", "owner", "reg_date"],
        "vt_case":     ["case_id", "case_type", "start_date", "status"],
        "vt_ip":       ["ip_addr", "country", "isp", "last_seen"],
        "vt_transfer": ["tx_id", "amount", "tx_date", "method"],
        "vt_call":     ["call_id", "duration", "call_date", "call_type"],
        "vt_atm":      ["atm_id", "location", "bank"],
    },
    "edge_types": [
        "has_account", "owns_phone", "used_ip", "involves",
        "from_account", "to_account", "caller", "callee",
    ],
    # 엣지 방향 정보 (Format B/C 생성용)
    "_edge_directions": {
        "has_account":  ("vt_psn",      "vt_bacnt"),
        "owns_phone":   ("vt_psn",      "vt_telno"),
        "used_ip":      ("vt_psn",      "vt_ip"),
        "involves":     ("vt_case",     "vt_psn"),
        "from_account": ("vt_bacnt",    "vt_transfer"),
        "to_account":   ("vt_transfer", "vt_bacnt"),
        "caller":       ("vt_telno",    "vt_call"),
        "callee":       ("vt_call",     "vt_telno"),
    },
}

VALID_LABELS = set(CANONICAL_SCHEMA["node_labels"].keys())
VALID_EDGES = set(CANONICAL_SCHEMA["edge_types"])
VALID_PROPS = {
    label: set(props)
    for label, props in CANONICAL_SCHEMA["node_labels"].items()
}

# =============================================================================
# 3. 스키마 포맷 생성기
# =============================================================================

def fmt_a_raw_json(schema: dict) -> str:
    """Format A: 현재 방식 — raw JSON dump"""
    payload = {
        "node_labels": schema["node_labels"],
        "edge_types":  schema["edge_types"],
    }
    return json.dumps(payload, ensure_ascii=False)


def fmt_b_graph_notation(schema: dict) -> str:
    """Format B: 그래프 연결 명시형 — 방향 포함"""
    lines = ["[노드]"]
    for label, props in schema["node_labels"].items():
        lines.append(f"  ({label} {{{', '.join(props)}}})")

    lines.append("\n[관계]")
    for edge, (src, dst) in schema["_edge_directions"].items():
        lines.append(f"  ({src})-[:{edge}]->({dst})")

    return "\n".join(lines)


def fmt_c_markdown_table(schema: dict) -> str:
    """Format C: 마크다운 테이블형"""
    lines = ["**노드 레이블**\n", "| 레이블 | 속성 |", "|--------|------|"]
    for label, props in schema["node_labels"].items():
        lines.append(f"| {label} | {', '.join(props)} |")

    lines += ["\n**관계 (방향)**\n", "| 관계 | 방향 |", "|------|------|"]
    for edge, (src, dst) in schema["_edge_directions"].items():
        lines.append(f"| {edge} | {src} → {dst} |")

    return "\n".join(lines)


FORMATS = {
    "A_raw_json":       fmt_a_raw_json,
    "B_graph_notation": fmt_b_graph_notation,
    "C_markdown_table": fmt_c_markdown_table,
}

# =============================================================================
# 4. 프롬프트 빌더 (synthesis_node 프롬프트와 동일 구조)
# =============================================================================

SYSTEM_PROMPT = (
    "당신은 AgensGraph용 Cypher 쿼리를 생성하는 전문 수사관입니다. "
    "반드시 아래 SQL-Wrapped Cypher 문법만 출력하십시오:\n"
    "SELECT * FROM cypher('<graph>', $$ MATCH ... RETURN ... $$) AS (...agtype...);\n"
    "범죄 수사와 무관한 질문이면 GENERAL: 로 시작하십시오."
)

FEWSHOT = """
[Few-Shot 예제]
Q: 피해자1의 연결 계좌 정보 보여줘
A: SELECT * FROM cypher('ccop_graph', $$ MATCH (p:vt_psn {name: '피해자1'})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);

Q: 계좌 '110-3333-3333'에서 나간 이체 내역 전체
A: SELECT * FROM cypher('ccop_graph', $$ MATCH (b:vt_bacnt {actno: '110-3333-3333'})-[r:from_account]->(t:vt_transfer) RETURN b, r, t $$) AS (b agtype, r agtype, t agtype);

Q: 전화번호 '1000000001'을 소유한 사람
A: SELECT * FROM cypher('ccop_graph', $$ MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {telno: '1000000001'}) RETURN p, r, t $$) AS (p agtype, r agtype, t agtype);
"""

def build_prompt(question: str, schema_str: str, graph_path: str) -> str:
    return (
        f"[데이터베이스 스키마]\n{schema_str}\n\n"
        f"[AgensGraph 매핑 가이드]\n"
        f"- amount/duration/balance 등 숫자형 속성은 문자열로 저장됨. 비교 시 따옴표 사용.\n"
        f"- 속성 접근: n->>'prop_name' 형식 사용.\n"
        f"- 관계 방향: (vt_case)-[:involves]->(vt_psn) 고정.\n"
        f"- graph_path = '{graph_path}'\n\n"
        f"{FEWSHOT}\n"
        f"[질문]\n{question}\n\n"
        f"[규칙] SQL Wrapper 형태로만 출력. 추가 설명 금지."
    )

# =============================================================================
# 5. 평가 지표 계산
# =============================================================================

# AgensGraph SELECT * FROM cypher(...) 패턴
RE_SQL_WRAP   = re.compile(r"SELECT\s+\*\s+FROM\s+cypher\s*\(", re.IGNORECASE)
RE_CYPHER_BODY = re.compile(r"\$\$\s*(.+?)\s*\$\$", re.DOTALL)
RE_LABEL_USE   = re.compile(r"[:(](\w+)")
RE_EDGE_USE    = re.compile(r"\[:(\w+)\]")
RE_PROP_USE    = re.compile(r"(\w+)->>?'(\w+)'")


def evaluate(cypher: str, category: str) -> dict[str, Any]:
    """생성된 Cypher에 대한 정확도 지표를 계산합니다."""
    result: dict[str, Any] = {
        "has_sql_wrapper":     False,
        "has_cypher_body":     False,
        "invalid_labels":      [],
        "invalid_edges":       [],
        "invalid_props":       [],
        "label_accuracy":      0.0,
        "edge_accuracy":       0.0,
        "prop_accuracy":       0.0,
        "overall_score":       0.0,
        "category":            category,
    }

    upper = cypher.upper()

    # 1. SQL Wrapper 존재
    result["has_sql_wrapper"] = bool(RE_SQL_WRAP.search(cypher))

    # 2. Cypher body 추출
    body_match = RE_CYPHER_BODY.search(cypher)
    if not body_match:
        return result
    body = body_match.group(1)
    result["has_cypher_body"] = True

    # 3. 레이블 검증 (vt_ 으로 시작하는 것만)
    used_labels = {m for m in RE_LABEL_USE.findall(body) if m.startswith("vt_")}
    bad_labels  = used_labels - VALID_LABELS
    result["invalid_labels"] = sorted(bad_labels)
    result["label_accuracy"] = (
        1.0 if not used_labels
        else round(1 - len(bad_labels) / len(used_labels), 3)
    )

    # 4. 엣지 검증
    used_edges = set(RE_EDGE_USE.findall(body))
    bad_edges  = used_edges - VALID_EDGES
    result["invalid_edges"] = sorted(bad_edges)
    result["edge_accuracy"] = (
        1.0 if not used_edges
        else round(1 - len(bad_edges) / len(used_edges), 3)
    )

    # 5. 속성 검증 (n->>'prop' 패턴)
    prop_hits  = RE_PROP_USE.findall(body)  # [(var, prop), ...]
    bad_props  = []
    total_props = 0
    for var, prop in prop_hits:
        # var이 어느 label인지 body에서 추론하기는 어려우므로
        # VALID_PROPS 전체 합집합과 비교
        all_props = {p for ps in VALID_PROPS.values() for p in ps}
        total_props += 1
        if prop not in all_props:
            bad_props.append(prop)
    result["invalid_props"] = sorted(set(bad_props))
    result["prop_accuracy"] = (
        1.0 if total_props == 0
        else round(1 - len(bad_props) / total_props, 3)
    )

    # 6. 종합 점수 (가중 평균)
    w = {"wrapper": 0.25, "label": 0.30, "edge": 0.25, "prop": 0.20}
    result["overall_score"] = round(
        w["wrapper"] * float(result["has_sql_wrapper"])
        + w["label"]   * result["label_accuracy"]
        + w["edge"]    * result["edge_accuracy"]
        + w["prop"]    * result["prop_accuracy"],
        3,
    )
    return result


# =============================================================================
# 6. 메인 벤치마크 루프
# =============================================================================

def run_benchmark(graph_path: str, model: str, api_base: str | None) -> dict:
    client = OpenAI(
        base_url=api_base if api_base else None,
        api_key=os.environ.get("OPENAI_API_KEY", "EMPTY"),
    )

    all_results: dict[str, list] = {fmt: [] for fmt in FORMATS}
    errors = []

    total = len(BENCHMARK_QUERIES) * len(FORMATS)
    done  = 0

    for fmt_name, fmt_fn in FORMATS.items():
        schema_str = fmt_fn(CANONICAL_SCHEMA)
        print(f"\n{'='*60}")
        print(f"Format: {fmt_name}")
        print(f"{'='*60}")

        for question, category in BENCHMARK_QUERIES:
            done += 1
            print(f"  [{done}/{total}] ({category}) {question[:55]}...", end=" ", flush=True)

            prompt = build_prompt(question, schema_str, graph_path)
            t0 = time.time()
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    temperature=0,
                )
                cypher   = resp.choices[0].message.content.strip()
                latency  = round(time.time() - t0, 3)
                metrics  = evaluate(cypher, category)

                record = {
                    "question": question,
                    "category": category,
                    "cypher":   cypher,
                    "latency":  latency,
                    **metrics,
                }
                all_results[fmt_name].append(record)
                score_str = f"score={metrics['overall_score']:.2f}"
                print(f"✓ {score_str} ({latency}s)")

            except Exception as e:
                latency = round(time.time() - t0, 3)
                record = {
                    "question": question,
                    "category": category,
                    "cypher":   "",
                    "latency":  latency,
                    "error":    str(e),
                    "overall_score": 0.0,
                }
                all_results[fmt_name].append(record)
                errors.append({"fmt": fmt_name, "q": question, "err": str(e)})
                print(f"✗ ERROR: {e}")

            # Rate limit 방지
            time.sleep(0.3)

    return {"results": all_results, "errors": errors}


# =============================================================================
# 7. 집계 및 리포트 출력
# =============================================================================

def aggregate(results_by_fmt: dict[str, list]) -> dict:
    summary = {}
    for fmt_name, records in results_by_fmt.items():
        valid = [r for r in records if r.get("overall_score", 0) > 0 or r.get("has_sql_wrapper")]

        def mean(key):
            vals = [r[key] for r in records if isinstance(r.get(key), (int, float))]
            return round(sum(vals) / len(vals), 3) if vals else 0.0

        # 카테고리별 점수
        by_cat: dict[str, list] = {}
        for r in records:
            by_cat.setdefault(r["category"], []).append(r.get("overall_score", 0.0))
        cat_scores = {cat: round(sum(v) / len(v), 3) for cat, v in by_cat.items()}

        summary[fmt_name] = {
            "avg_overall":      mean("overall_score"),
            "avg_label_acc":    mean("label_accuracy"),
            "avg_edge_acc":     mean("edge_accuracy"),
            "avg_prop_acc":     mean("prop_accuracy"),
            "sql_wrapper_rate": round(sum(1 for r in records if r.get("has_sql_wrapper")) / len(records), 3),
            "avg_latency":      mean("latency"),
            "n_total":          len(records),
            "n_error":          sum(1 for r in records if "error" in r),
            "by_category":      cat_scores,
        }
    return summary


def print_report(summary: dict):
    print("\n" + "=" * 70)
    print("  Schema Format Benchmark — 결과 요약")
    print("=" * 70)

    header = f"{'Metric':<25}" + "".join(f"{fmt:<22}" for fmt in summary)
    print(header)
    print("-" * 70)

    metrics = [
        ("avg_overall",      "종합 점수 (avg)"),
        ("avg_label_acc",    "레이블 정확도"),
        ("avg_edge_acc",     "엣지 정확도"),
        ("avg_prop_acc",     "속성 정확도"),
        ("sql_wrapper_rate", "SQL Wrapper 성공률"),
        ("avg_latency",      "평균 응답시간(s)"),
    ]
    for key, label in metrics:
        row = f"{label:<25}" + "".join(f"{summary[fmt].get(key, 0):<22}" for fmt in summary)
        print(row)

    print("\n[카테고리별 종합 점수]")
    categories = ["basic", "direction", "filter", "path", "b2c"]
    cat_header = f"{'카테고리':<15}" + "".join(f"{fmt:<22}" for fmt in summary)
    print(cat_header)
    print("-" * 70)
    for cat in categories:
        row = f"{cat:<15}" + "".join(
            f"{summary[fmt]['by_category'].get(cat, '-'):<22}" for fmt in summary
        )
        print(row)

    # 최고 포맷
    best_fmt = max(summary, key=lambda k: summary[k]["avg_overall"])
    print(f"\n▶ 최고 성능 포맷: {best_fmt} "
          f"(종합 점수: {summary[best_fmt]['avg_overall']})")


# =============================================================================
# 8. CLI 진입점
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schema Format Benchmark for Text2Cypher")
    parser.add_argument("--graph",    default="ccop_graph",       help="그래프 이름")
    parser.add_argument("--model",    default="gpt-4o",           help="모델 이름")
    parser.add_argument("--api-base", default=None,               help="온프레미스 sLLM endpoint URL")
    parser.add_argument("--output",   default="schema_bench.json", help="결과 저장 파일")
    parser.add_argument("--quick",    action="store_true",        help="처음 5개 쿼리만 실행 (빠른 검증용)")
    args = parser.parse_args()

    if args.quick:
        # 전역 리스트 슬라이싱
        import scripts.schema_format_benchmark as _self
        _self.BENCHMARK_QUERIES = BENCHMARK_QUERIES[:5]  # type: ignore
        print("[Quick Mode] 처음 5개 쿼리만 실행합니다.")

    print(f"모델: {args.model} | 그래프: {args.graph} | 총 쿼리: {len(BENCHMARK_QUERIES)} × {len(FORMATS)} 포맷")

    raw = run_benchmark(args.graph, args.model, args.api_base)
    summary = aggregate(raw["results"])
    print_report(summary)

    output = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "model":      args.model,
            "graph_path": args.graph,
            "n_queries":  len(BENCHMARK_QUERIES),
            "formats":    list(FORMATS.keys()),
        },
        "summary": summary,
        "detail":  raw["results"],
        "errors":  raw["errors"],
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {args.output}")
