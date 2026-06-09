import glob

# 캐시 경로 설정
cache_dir = "/home/ai-kyw-dev/.cache/huggingface/modules/transformers_modules/LGAI_hyphen_EXAONE/**"

# 1. modeling_exaone.py 패치 (Attention Mask & Imports)
model_files = glob.glob(f"{cache_dir}/modeling_exaone.py", recursive=True)
for fpath in model_files:
    print(f"[*] Patching Model: {fpath}...")
    with open(fpath, 'r') as f:
        content = f.read()

    if "from transformers.utils.generic import check_model_inputs, maybe_autocast" in content:
        content = content.replace(
            "from transformers.utils.generic import check_model_inputs, maybe_autocast",
            "from transformers.utils.generic import check_model_inputs\n"
            "try:\n"
            "    from transformers.utils.generic import maybe_autocast\n"
            "except ImportError:\n"
            "    from contextlib import nullcontext\n"
            "    def maybe_autocast(enabled=True, *args, **kwargs): return nullcontext()"
        )
        print("  [OK] maybe_autocast fallback 추가 완료")

    old_sdpa = "attn_output = torch.nn.functional.scaled_dot_product_attention("
    new_sdpa = (
        "\n        # Fix: Attention Mask 크기 불일치 해결\n"
        "        if attention_mask is not None and attention_mask.dim() == 4:\n"
        "            if attention_mask.size(2) != query_states.size(2) or attention_mask.size(3) != key_states.size(2):\n"
        "                q_len, k_len = query_states.size(2), key_states.size(2)\n"
        "                attention_mask = attention_mask[:, :, -q_len:, :k_len]\n"
        "        attn_output = torch.nn.functional.scaled_dot_product_attention("
    )
    if old_sdpa in content and "q_len, k_len" not in content:
        content = content.replace(old_sdpa, new_sdpa)
        print("  [OK] Attention Mask 크기 불일치 패치 완료")

    with open(fpath, 'w') as f:
        f.write(content)
    print(f"  → 저장 완료: {fpath}")

# 2. configuration_exaone.py 패치 (typing_error 방지)
config_files = glob.glob(f"{cache_dir}/configuration_exaone.py", recursive=True)
for fpath in config_files:
    print(f"[*] Patching Config: {fpath}...")
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
    print(f"  → 저장 완료: {fpath}")

print("\n✨ 모든 패치 완료!")
