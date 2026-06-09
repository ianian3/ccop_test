"""
Option A: 기존 SQL Wrapper 데이터 → Native Cypher 변환 + 신규 143개 합치기
출력: 최종 통합 SFT 학습 데이터 (ShareGPT JSON)

주요 처리 흐름:
1. 기존 36,946개에서 이미 있는 native_cypher 필드를 활용
2. 멀티라인 개행 처리 + 유효성 필터링
3. CCOP 전용 143개 × 20배 오버샘플링 (도메인 특화 강화)
4. ShareGPT 형식으로 통합 출력
"""
import json, re, random, os
from pathlib import Path

EXISTING = "data/neo4j_agens_sft_V2_hybrid.jsonl"
NEW_NATIVE = "data/native_cypher_sft_sharegpt.json"
OUTPUT_ALPACA = "data/ccop_v3_sft_merged_alpaca.jsonl"
OUTPUT_SHAREGPT = "data/ccop_v3_sft_merged_sharegpt.json"

SYSTEM_MSG = """You are an AgensGraph Native Cypher query expert for cybercrime investigation (CCOP system).

CONFIRMED DB SCHEMA (tccop_graph_v6):
Nodes: vt_psn(name,id,type), vt_bacnt(actno,bank_name★,bank_cd), vt_telno(telno★no-hyphen), 
       vt_ip(ip_addr), vt_transfer(amount★string,timestamp), vt_call, vt_case(flnm,crime)

Edges:
- (vt_psn)-[:has_account]->(vt_bacnt)
- (vt_psn)-[:owns_phone]->(vt_telno)
- (vt_psn)-[:used_ip]->(vt_ip)
- (vt_bacnt)-[:from_account]->(vt_transfer)-[:to_account]->(vt_bacnt)
- (vt_telno)-[:caller]->(vt_call)-[:callee]->(vt_telno)

ABSOLUTE RULES:
1. Output ONLY AgensGraph Native Cypher (MATCH...RETURN). NO SQL wrapper ever.
2. Use bank_name (NOT bank). telno without hyphens. amount as string.
3. Single line output, no newlines, no explanation."""


def clean_native_cypher(raw: str) -> str:
    """native_cypher 필드를 한 줄의 깨끗한 쿼리로 변환"""
    if not raw:
        return ""

    # ① $$ 달러 구분자 잔재 → 즉시 거부 (SQL wrapper 찌꺼기)
    if "$$" in raw:
        return ""

    # 이스케이프된 개행 → 공백
    q = raw.replace("\\n", " ").replace("\n", " ").replace("\\r", " ").replace("\r", " ")
    # 연속 공백 제거
    q = re.sub(r" {2,}", " ", q).strip()

    # MATCH로 시작하는지 확인
    if not q.upper().strip().startswith("MATCH"):
        return ""

    # 세미콜론 이후 사족 제거
    if ";" in q:
        q = q.split(";")[0].strip()

    # ② toFloat() → 내부 표현식만 남김 (AgensGraph 미지원 함수 제거)
    q = re.sub(r'toFloat\(([^)]+)\)', r'\1', q, flags=re.IGNORECASE)

    # ③ amount 비교 시 숫자 → 문자열로 (WHERE t.amount >= 5000000 → >= '5000000')
    q = re.sub(
        r'(\.amount)\s*(>=|<=|>|<|=)\s*(\d+)(?!\d*[\'"])',
        lambda m: f"{m.group(1)} {m.group(2)} '{m.group(3)}'",
        q
    )

    # ④ toString() 제거
    q = re.sub(r'toString\(([^)]+)\)', r'\1', q, flags=re.IGNORECASE)

    # 최소 길이 검증
    if len(q) < 15:
        return ""
    return q



def is_valid(q: str) -> bool:
    """유효한 Native Cypher 여부 판별"""
    if not q:
        return False
    u = q.upper()
    return u.startswith("MATCH") and "RETURN" in u


def convert_existing_to_native(path: str):
    """기존 JSONL에서 native_cypher 필드 활용하여 변환"""
    converted = []
    skipped = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except:
                continue

            # native_cypher 필드 우선 사용
            raw_native = d.get("native_cypher", "")
            if not raw_native:
                # 없으면 output에서 MATCH 추출 시도
                out = d.get("output", "")
                m = re.search(r'MATCH\s+.+', out, re.IGNORECASE | re.DOTALL)
                raw_native = m.group(0) if m else ""

            cypher = clean_native_cypher(raw_native)
            if not is_valid(cypher):
                skipped += 1
                continue

            question = d.get("input", "").strip()
            if not question:
                skipped += 1
                continue

            converted.append({
                "question": question,
                "cypher": cypher,
                "source": "existing"
            })

    print(f"  기존 데이터: {len(converted)}개 변환 성공, {skipped}개 스킵")
    return converted


def load_new_native(path: str, oversample: int = 20):
    """신규 CCOP 전용 데이터 로드 + 오버샘플링"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    pairs = []
    for item in data:
        convs = item.get("conversations", [])
        human = next((c["value"] for c in convs if c["from"] == "human"), "")
        gpt   = next((c["value"] for c in convs if c["from"] == "gpt"), "")
        if human and is_valid(gpt):
            pairs.append({"question": human, "cypher": gpt, "source": "ccop_new"})

    # 오버샘플링 (CCOP 도메인 강화)
    oversampled = pairs * oversample
    random.shuffle(oversampled)
    print(f"  신규 데이터: {len(pairs)}개 × {oversample}배 = {len(oversampled)}개")
    return oversampled


def to_sharegpt(pairs):
    return [
        {
            "conversations": [
                {"from": "system", "value": SYSTEM_MSG},
                {"from": "human", "value": p["question"]},
                {"from": "gpt",   "value": p["cypher"]}
            ]
        }
        for p in pairs
    ]


def to_alpaca(pairs):
    return [
        {
            "instruction": p["question"],
            "input": "Generate AgensGraph Native Cypher query only.",
            "output": p["cypher"]
        }
        for p in pairs
    ]


def main():
    print("=" * 65)
    print("🔧 Option A: SQL Wrapper → Native Cypher 변환 + 통합 데이터셋")
    print("=" * 65)

    # Step 1. 기존 데이터 변환
    print("\n[1/4] 기존 데이터 변환 중... (36,946개 처리)")
    existing = convert_existing_to_native(EXISTING)

    # Step 2. 신규 CCOP 데이터 로드 + 오버샘플링
    print("\n[2/4] 신규 CCOP 데이터 로드 및 오버샘플링...")
    new_data = load_new_native(NEW_NATIVE, oversample=20)

    # Step 3. 통합 + 셔플
    print("\n[3/4] 데이터 통합 및 셔플...")
    merged = existing + new_data
    random.shuffle(merged)

    # 소스 분포 확인
    existing_cnt = sum(1 for p in merged if p["source"] == "existing")
    new_cnt      = sum(1 for p in merged if p["source"] == "ccop_new")
    print(f"  전체 : {len(merged):,}개")
    print(f"  기존  : {existing_cnt:,}개 ({existing_cnt/len(merged)*100:.1f}%)")
    print(f"  신규  : {new_cnt:,}개  ({new_cnt/len(merged)*100:.1f}%)")

    # Step 4. 저장
    print("\n[4/4] 파일 저장...")
    os.makedirs("data", exist_ok=True)

    # ShareGPT (LLaMA-Factory 권장)
    sg = to_sharegpt(merged)
    with open(OUTPUT_SHAREGPT, "w", encoding="utf-8") as f:
        json.dump(sg, f, ensure_ascii=False, indent=2)
    print(f"  ✅ ShareGPT: {OUTPUT_SHAREGPT}")
    print(f"     → {len(sg):,} samples ({Path(OUTPUT_SHAREGPT).stat().st_size/1024/1024:.1f} MB)")

    # Alpaca (Axolotl 등)
    al = to_alpaca(merged)
    with open(OUTPUT_ALPACA, "w", encoding="utf-8") as f:
        for item in al:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  ✅ Alpaca:   {OUTPUT_ALPACA}")
    print(f"     → {len(al):,} samples ({Path(OUTPUT_ALPACA).stat().st_size/1024/1024:.1f} MB)")

    # 최종 요약
    print("\n" + "=" * 65)
    print("📊 최종 학습 데이터 품질 요약")
    print("=" * 65)
    print(f"  총 학습 샘플: {len(merged):,}개")
    print(f"  기존(범용):   {existing_cnt:,}개 — Cypher 문법 일반화 역할")
    print(f"  신규(CCOP):   {new_cnt:,}개   — CCOP 도메인 특화 강화")
    print(f"  비율:         기존 {existing_cnt/len(merged)*100:.0f}% : 신규 {new_cnt/len(merged)*100:.0f}%")
    print()
    print("  [다음 단계] 서버로 업로드:")
    print(f"  scp {OUTPUT_SHAREGPT} ai-kyw-dev@192.168.1.133:~/sft_data/")
    print()

    # 샘플 출력 (신규 CCOP 데이터 위주)
    print("📝 신규 CCOP 샘플 (3개):")
    ccop_samples = [p for p in merged if p["source"] == "ccop_new"][:3]
    for i, s in enumerate(ccop_samples):
        print(f"  [{i+1}] Q: {s['question']}")
        print(f"       C: {s['cypher']}")
        print()

    print("=" * 65)
    print("✅ 완료!")


if __name__ == "__main__":
    main()
