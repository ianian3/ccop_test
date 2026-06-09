"""
한글 수사 도메인 SFT 데이터셋 필터링 + 병합 스크립트

소스:
  1. ccop_v3_sft_merged_sharegpt.json  → 한글 + vt_* 도메인만 필터
  2. sft_dataset_10k_v3.jsonl          → SQL Wrapper에서 Native Cypher 추출 후 ShareGPT 변환

출력:
  korean_cybercrime_sft.json  (ShareGPT 포맷)
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent

SYSTEM_PROMPT = (
    "You are an AgensGraph Native Cypher query expert for cybercrime investigation (CCOP system).\n\n"
    "CONFIRMED DB SCHEMA (tccop_graph_v6):\n"
    "Nodes: vt_psn(name,id,type), vt_bacnt(actno,bank_name★,bank_cd), vt_telno(telno★no-hyphen),\n"
    "       vt_ip(ip_addr), vt_transfer(amount★string,timestamp), vt_call, vt_case(flnm,crime)\n\n"
    "Edges:\n"
    "- (vt_psn)-[:has_account]->(vt_bacnt)\n"
    "- (vt_psn)-[:owns_phone]->(vt_telno)\n"
    "- (vt_psn)-[:used_ip]->(vt_ip)\n"
    "- (vt_bacnt)-[:from_account]->(vt_transfer)-[:to_account]->(vt_bacnt)\n"
    "- (vt_telno)-[:caller]->(vt_call)-[:callee]->(vt_telno)\n"
    "- (vt_case)-[:involves]->(vt_psn)\n\n"
    "ABSOLUTE RULES:\n"
    "1. Output ONLY AgensGraph Native Cypher (MATCH...RETURN). NO SQL wrapper ever.\n"
    "2. Use bank_name (NOT bank). telno without hyphens. amount as string.\n"
    "3. Single line output, no newlines, no explanation."
)

VT_LABELS = ['vt_psn', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_transfer', 'vt_case', 'vt_call']


def is_korean(text: str) -> bool:
    return any('\uac00' <= c <= '\ud7a3' for c in text)


def is_vt_domain(text: str) -> bool:
    return any(label in text for label in VT_LABELS)


def extract_native_cypher(sql_wrapper: str) -> str:
    """SELECT * FROM cypher('graph', $$ ... $$) 에서 Native Cypher 추출"""
    match = re.search(r'\$\$(.*?)\$\$', sql_wrapper, re.DOTALL)
    if match:
        cypher = match.group(1).strip()
        # 개행 → 공백
        cypher = re.sub(r'\s+', ' ', cypher).strip()
        return cypher
    return ""


def to_sharegpt(system: str, human: str, gpt: str) -> dict:
    return {
        "conversations": [
            {"from": "system", "value": system},
            {"from": "human", "value": human},
            {"from": "gpt",   "value": gpt},
        ]
    }


# ── 1. ccop_v3_sft_merged_sharegpt.json 필터링 ──────────────────────────────

print("📂 소스 1: ccop_v3_sft_merged_sharegpt.json 로드...")
with open(DATA_DIR / 'ccop_v3_sft_merged_sharegpt.json', encoding='utf-8') as f:
    sharegpt_data = json.load(f)

filtered_sharegpt = []
for item in sharegpt_data:
    convs = item.get('conversations', [])
    human_msg = next((c['value'] for c in convs if c['from'] == 'human'), '')
    gpt_msg   = next((c['value'] for c in convs if c['from'] == 'gpt'),   '')

    if is_korean(human_msg) and is_vt_domain(gpt_msg):
        # system prompt를 표준 프롬프트로 교체
        new_item = {
            "conversations": [
                {"from": "system", "value": SYSTEM_PROMPT},
                {"from": "human",  "value": human_msg},
                {"from": "gpt",    "value": gpt_msg},
            ]
        }
        filtered_sharegpt.append(new_item)

print(f"  → 필터 후: {len(filtered_sharegpt)}건 (전체 {len(sharegpt_data)}건 중)")


# ── 2. sft_dataset_10k_v3.jsonl 변환 ────────────────────────────────────────

print("\n📂 소스 2: sft_dataset_10k_v3.jsonl 로드 및 변환...")
converted = []
skipped = 0

with open(DATA_DIR / 'sft_dataset_10k_v3.jsonl', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)

        question = item.get('instruction', '')
        output   = item.get('output', '')

        # SQL Wrapper → Native Cypher 추출
        if 'SELECT' in output.upper() and '$$' in output:
            native = extract_native_cypher(output)
        else:
            native = output.strip()

        # 유효성 검사
        if not native or 'MATCH' not in native.upper():
            skipped += 1
            continue
        if not is_korean(question):
            skipped += 1
            continue

        converted.append(to_sharegpt(SYSTEM_PROMPT, question, native))

print(f"  → 변환 성공: {len(converted)}건 / 스킵: {skipped}건")


# ── 3. 병합 + 중복 제거 ──────────────────────────────────────────────────────

print("\n🔀 병합 중...")
all_data = filtered_sharegpt + converted

# (질문, 쿼리) 쌍 기준 중복 제거
seen = set()
deduped = []
for item in all_data:
    convs = item['conversations']
    key = (
        next((c['value'] for c in convs if c['from'] == 'human'), ''),
        next((c['value'] for c in convs if c['from'] == 'gpt'),   ''),
    )
    if key not in seen:
        seen.add(key)
        deduped.append(item)

print(f"  병합 전: {len(all_data)}건")
print(f"  중복 제거 후: {len(deduped)}건")


# ── 4. 저장 ──────────────────────────────────────────────────────────────────

out_path = DATA_DIR / 'korean_cybercrime_sft.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(deduped, f, ensure_ascii=False, indent=2)

print(f"\n✅ 저장 완료: {out_path}")
print(f"   최종 데이터셋: {len(deduped)}건")

# ── 5. 품질 리포트 ────────────────────────────────────────────────────────────

print("\n📊 품질 리포트:")
cypher_errors = 0
empty_q = 0
empty_a = 0

for item in deduped:
    convs = item['conversations']
    q = next((c['value'] for c in convs if c['from'] == 'human'), '')
    a = next((c['value'] for c in convs if c['from'] == 'gpt'),   '')
    if not q:
        empty_q += 1
    if not a:
        empty_a += 1
    if a and 'MATCH' not in a.upper():
        cypher_errors += 1

print(f"  빈 질문: {empty_q}건")
print(f"  빈 응답: {empty_a}건")
print(f"  MATCH 없는 output: {cypher_errors}건")
print(f"  정상: {len(deduped) - empty_q - empty_a - cypher_errors}건")
