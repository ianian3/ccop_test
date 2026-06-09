"""
EXAONE modeling_exaone.py 완전 초기화 + 단일 패치 적용
1. HF 모듈 캐시에서 원본 파일 복구 (download_file 활용)
2. 단 한 번의 깔끔한 패치 삽입
"""
import os
import shutil

SNAPSHOT = "0ff6b5ec7c13b049b253a16a889aa269e6b79a94"
BASE = "/home/ai-kyw-dev/.cache/huggingface/modules/transformers_modules/LGAI_hyphen_EXAONE/EXAONE_hyphen_3_dot_5_hyphen_7_dot_8B_hyphen_Instruct"
fpath = os.path.join(BASE, SNAPSHOT, "modeling_exaone.py")

# ── Step 1: 원본 파일 복구 ──────────────────────────────────────
# HF hub 원본 소스에서 직접 재다운로드
print("[1] 원본 파일 복구 중...")
model_id = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
try:
    from huggingface_hub import hf_hub_download
    original = hf_hub_download(
        repo_id=model_id,
        filename="modeling_exaone.py",
        revision=SNAPSHOT,
        force_download=True,      # 항상 새로 다운로드
        local_files_only=False,
    )
    shutil.copy2(original, fpath)
    print(f"  [OK] 원본 복구 완료: {fpath}")
except Exception as e:
    print(f"  [!] 다운로드 실패: {e}")
    # 폴백: .bak 파일들 중 가장 오래된 것 사용
    bak_candidates = [fpath + ".bak", fpath + ".bak2"]
    restored = False
    for bak in bak_candidates:
        if os.path.exists(bak):
            size = os.path.getsize(bak)
            print(f"  [→] 백업 사용: {bak} ({size} bytes)")
            shutil.copy2(bak, fpath)
            restored = True
            break
    if not restored:
        print("  [❌] 복구 불가. 수동으로 파일을 확인하세요.")
        exit(1)

# ── Step 2: 현재 파일 상태 확인 ────────────────────────────────
with open(fpath, 'r') as f:
    lines = f.readlines()
print(f"\n[2] 파일 상태: 총 {len(lines)}줄")

# 기존 패치 잔재 확인
patch_markers = ["[PATCH]", "_pq", "_pk", "PATCH v2"]
# q_len, k_len은 원본에도 있을 수 있으므로 패치 주석과 같이 있는 경우만 체크
remnants = [(i+1, l.rstrip()) for i, l in enumerate(lines)
            if any(m in l for m in patch_markers)]
if remnants:
    print(f"  [!] 잔재 패치 라인 발견 ({len(remnants)}개) → 제거합니다")
    for lineno, content in remnants[:10]:
        print(f"    L{lineno}: {content[:80]}")

# ── Step 3: 모든 패치 잔재 제거 ────────────────────────────────
print("\n[3] 패치 잔재 제거 중...")
clean_lines = []
for line in lines:
    if any(marker in line for marker in patch_markers):
        continue  # 잔재 삭제
    # 이전 패치가 만든 특정 패턴도 제거
    if "attention_mask.size(2) != q_len" in line:
        continue
    if "attention_mask.size(2) != _pq" in line:
        continue
    if "attention_mask[:, :, -q_len:" in line:
        continue
    if "attention_mask[:, :, -_pq:" in line:
        continue
    if "attention_mask is not None and attention_mask.dim() == 4" in line:
        continue
    clean_lines.append(line)
print(f"  제거 후: {len(clean_lines)}줄 (원본 대비 {len(lines)-len(clean_lines)}줄 제거됨)")

# ── Step 4: 단일 클린 패치 삽입 ────────────────────────────────
print("\n[4] 클린 패치 삽입 중...")
SDPA_MARKER = "scaled_dot_product_attention("

final_lines = []
inserted = False
for line in clean_lines:
    if SDPA_MARKER in line and not inserted:
        indent = len(line) - len(line.lstrip())
        pad = " " * indent
        # 완전히 새로운 변수명으로 충돌 방지
        patch = (
            f"{pad}# ---- ATTN MASK PATCH: KV cache shape fix ----\n"
            f"{pad}if attention_mask is not None and attention_mask.dim() == 4:\n"
            f"{pad}    _am_q = query_states.size(2)\n"
            f"{pad}    _am_k = key_states.size(2)\n"
            f"{pad}    if attention_mask.size(2) != _am_q or attention_mask.size(3) != _am_k:\n"
            f"{pad}        attention_mask = attention_mask[:, :, -_am_q:, :_am_k]\n"
            f"{pad}# ---- END PATCH ----\n"
        )
        final_lines.append(patch)
        final_lines.append(line)
        inserted = True
        print(f"  [OK] SDPA 직전에 패치 삽입 완료")
    else:
        final_lines.append(line)

if not inserted:
    print("  [❌] SDPA 마커를 찾지 못했습니다!")
    for i, l in enumerate(clean_lines[525:545], start=525):
        print(f"    L{i+1}: {l.rstrip()[:100]}")
    exit(1)

# ── Step 5: 저장 및 검증 ────────────────────────────────────────
print("\n[5] 저장 중...")
with open(fpath, 'w') as f:
    f.writelines(final_lines)

with open(fpath, 'r') as f:
    verify = f.read()

ok1 = "ATTN MASK PATCH" in verify
ok2 = "_am_q" in verify and "_am_k" in verify
# 잔재 없는지 확인
no_remnant = "[PATCH]" not in verify and "_pq" not in verify and "PATCH v2" not in verify

print(f"  패치 삽입 확인: {'✅' if ok1 else '❌'}")
print(f"  변수명 확인   : {'✅' if ok2 else '❌'}")
print(f"  잔재 없음     : {'✅' if no_remnant else '❌'}")

if ok1 and ok2 and no_remnant:
    print("\n✅ 패치 완료! test_inference.py를 다시 실행하세요.")
else:
    print("\n⚠️ 검증 일부 실패. 결과를 공유해 주세요.")
