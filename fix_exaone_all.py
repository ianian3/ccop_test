"""
통합 수정 스크립트:
1. 모든 EXAONE snapshot에 Attention Mask 패치 적용
2. LoRA 가중치 키 이름 Fix (base_model.model. 접두사 제거)
"""
import glob
import os
import shutil

# ──────────────────────────────────────────────
# PART 1: 모든 EXAONE snapshot의 modeling_exaone.py 패치
# ──────────────────────────────────────────────
print("=" * 60)
print("PART 1: modeling_exaone.py 패치 (모든 snapshot)")
print("=" * 60)

cache_dir = "/home/ai-kyw-dev/.cache/huggingface/modules/transformers_modules/LGAI_hyphen_EXAONE/**"
model_files = glob.glob(f"{cache_dir}/modeling_exaone.py", recursive=True)

if not model_files:
    print("[-] modeling_exaone.py 파일을 찾을 수 없습니다.")
else:
    for fpath in model_files:
        snapshot = os.path.basename(os.path.dirname(fpath))
        print(f"\n[*] 패치 중: ...{snapshot[:12]}...")
        with open(fpath, 'r') as f:
            content = f.read()

        changed = False

        # Fix 1: maybe_autocast import 오류
        old_import = "from transformers.utils.generic import check_model_inputs, maybe_autocast"
        if old_import in content:
            content = content.replace(
                old_import,
                "from transformers.utils.generic import check_model_inputs\n"
                "try:\n"
                "    from transformers.utils.generic import maybe_autocast\n"
                "except ImportError:\n"
                "    from contextlib import nullcontext\n"
                "    def maybe_autocast(enabled=True, *args, **kwargs): return nullcontext()"
            )
            print(f"  [OK] maybe_autocast fallback 추가")
            changed = True

        # Fix 2: Attention Mask 크기 불일치 (RuntimeError 방지)
        old_sdpa = "attn_output = torch.nn.functional.scaled_dot_product_attention("
        new_sdpa = (
            "\n        # [PATCH] Attention Mask 크기 불일치 수정\n"
            "        if attention_mask is not None and attention_mask.dim() == 4:\n"
            "            if attention_mask.size(2) != query_states.size(2) or attention_mask.size(3) != key_states.size(2):\n"
            "                q_len, k_len = query_states.size(2), key_states.size(2)\n"
            "                attention_mask = attention_mask[:, :, -q_len:, :k_len]\n"
            "        attn_output = torch.nn.functional.scaled_dot_product_attention("
        )
        if old_sdpa in content and "q_len, k_len" not in content:
            content = content.replace(old_sdpa, new_sdpa)
            print(f"  [OK] Attention Mask 크기 패치 완료")
            changed = True

        if changed:
            with open(fpath, 'w') as f:
                f.write(content)
        else:
            print(f"  [→] 이미 패치됨, 건너뜀")

# ──────────────────────────────────────────────
# PART 2: configuration_exaone.py 패치 (모든 snapshot)
# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("PART 2: configuration_exaone.py 패치 (모든 snapshot)")
print("=" * 60)

config_files = glob.glob(f"{cache_dir}/configuration_exaone.py", recursive=True)
for fpath in config_files:
    snapshot = os.path.basename(os.path.dirname(fpath))
    print(f"\n[*] 패치 중: ...{snapshot[:12]}...")
    with open(fpath, 'r') as f:
        content = f.read()
    content = content.replace(
        "except ImportError:\n    RopeParameters = None",
        "except ImportError:\n    class RopeParameters: pass"
    )
    content = content.replace(
        "rope_parameters: RopeParameters | None = None",
        "rope_parameters = None"
    )
    with open(fpath, 'w') as f:
        f.write(content)
    print(f"  [OK] 완료")

# ──────────────────────────────────────────────
# PART 3: LoRA 가중치 키 이름 수정
# (base_model.model. 접두사 제거)
# ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("PART 3: LoRA 가중치 키 이름 수정")
print("=" * 60)

lora_path = os.path.expanduser("~/ccop_train/train/output/exaone-lora")

# safetensors 또는 bin 형식 처리
try:
    from safetensors.torch import load_file, save_file
    lora_file = os.path.join(lora_path, "adapter_model.safetensors")
    use_safetensors = os.path.exists(lora_file)
except ImportError:
    use_safetensors = False

import torch

if use_safetensors:
    print(f"[*] safetensors LoRA 파일 로드: {lora_file}")
    state_dict = load_file(lora_file)
else:
    lora_file = os.path.join(lora_path, "adapter_model.bin")
    print(f"[*] .bin LoRA 파일 로드: {lora_file}")
    state_dict = torch.load(lora_file, map_location="cpu")

# 키 이름 확인
sample_keys = list(state_dict.keys())[:4]
print(f"  현재 키 샘플: {sample_keys}")

PREFIX = "base_model.model."
needs_fix = any(k.startswith(PREFIX) for k in state_dict.keys())
needs_add  = any(not k.startswith(PREFIX) and ("lora_A" in k or "lora_B" in k) for k in state_dict.keys())

if needs_fix:
    print(f"  [!] '{PREFIX}' 접두사 발견 → 제거합니다")
    # 백업
    backup_file = lora_file + ".backup"
    shutil.copy2(lora_file, backup_file)
    print(f"  [→] 원본 백업: {backup_file}")

    new_state_dict = {}
    for k, v in state_dict.items():
        new_key = k[len(PREFIX):] if k.startswith(PREFIX) else k
        new_state_dict[new_key] = v

    if use_safetensors:
        save_file(new_state_dict, lora_file)
    else:
        torch.save(new_state_dict, lora_file)

    new_sample = list(new_state_dict.keys())[:4]
    print(f"  [OK] 수정된 키 샘플: {new_sample}")
    print(f"  [OK] LoRA 어댑터 키 이름 수정 완료!")
elif needs_add:
    print(f"  [!] '{PREFIX}' 접두사가 없는 키 발견 → 추가합니다")
    backup_file = lora_file + ".backup"
    shutil.copy2(lora_file, backup_file)

    new_state_dict = {}
    for k, v in state_dict.items():
        new_key = PREFIX + k if not k.startswith(PREFIX) else k
        new_state_dict[new_key] = v

    if use_safetensors:
        save_file(new_state_dict, lora_file)
    else:
        torch.save(new_state_dict, lora_file)

    new_sample = list(new_state_dict.keys())[:4]
    print(f"  [OK] 수정된 키 샘플: {new_sample}")
else:
    print(f"  [→] 키 이름이 이미 올바릅니다. 건너뜀")

print("\n" + "=" * 60)
print("✅ 모든 패치 완료! 이제 merge_lora.py 또는 test_inference.py를 다시 실행하세요.")
print("=" * 60)
