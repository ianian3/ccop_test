from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch, os

base_id = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
lora_path = os.path.expanduser("~/ccop_train/train/output/exaone-lora")
out_path = os.path.expanduser("~/ccop_train/train/output/exaone-merged")

print("[1/4] 베이스 모델 로드 중 (bfloat16, device_map=auto)...")
base = AutoModelForCausalLM.from_pretrained(
    base_id,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
    revision="0ff6b5ec7c13",
    device_map="auto"
)

print(f"[2/4] LoRA 어댑터 로드 중: {lora_path}")
model = PeftModel.from_pretrained(base, lora_path)

print("[3/4] Merge & Unload 실행 중...")
merged = model.merge_and_unload()

# Fix: EXAONE의 _tied_weights_keys 가 list인데 transformers는 dict를 기대함
# save_pretrained 전에 None으로 초기화해서 충돌 방지
if hasattr(merged, '_tied_weights_keys'):
    print(f"  [!] _tied_weights_keys 타입: {type(merged._tied_weights_keys)} → 임시 제거")
    merged._tied_weights_keys = None

os.makedirs(out_path, exist_ok=True)
print(f"[4/4] 병합된 모델 저장 중: {out_path}")
try:
    merged.save_pretrained(out_path, safe_serialization=True)
    print("  [OK] safetensors 형식으로 저장 완료")
except Exception as e:
    print(f"  [!] safetensors 저장 실패: {e}")
    print("  [→] .bin 형식으로 재시도 중...")
    merged.save_pretrained(out_path, safe_serialization=False)
    print("  [OK] .bin 형식으로 저장 완료")

tok = AutoTokenizer.from_pretrained(base_id, trust_remote_code=True)
tok.save_pretrained(out_path)
print(f"\n✅ 완료! 최종 모델 저장 경로: {out_path}")
