import os
import argparse
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def merge_models(base_model_name, lora_adapter_path, output_dir):
    """
    Base 모델과 LoRA Adapter를 하나로 병합하여 Standalone 버전을 생성합니다.
    """
    logger.info("========================================")
    logger.info("🚀 LoRA 어댑터 가중치 병합 작업 시작")
    logger.info(f"- Base Model: {base_model_name}")
    logger.info(f"- LoRA Adapter: {lora_adapter_path}")
    logger.info(f"- Output Directory: {output_dir}")
    logger.info("========================================")

    if not os.path.exists(lora_adapter_path):
        logger.error(f"LoRA Adapter 경로를 찾을 수 없습니다: {lora_adapter_path}")
        return

    # 1. Base 모델 로드 (최대한 가볍고 빠른 bfloat16 포맷 적용)
    # device_map="cpu"로 두면 메모리는 더 쓰지만, GPU OOM 걱정 없이 안전하게 병합 가능
    logger.info("1/4. Base 모델 로드 중... (시간이 다소 소요될 수 있습니다)")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        trust_remote_code=True
    )
    
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)

    # 2. LoRA(PEFT) 모델 로드 및 Base 위에 얹어 결합
    logger.info("2/4. LoRA Adapter 덧씌우기...")
    model = PeftModel.from_pretrained(base_model, lora_adapter_path)
    
    # 3. 모델 물리적 완전 병합
    logger.info("3/4. 모델 가중치 물리적 병합 진행 중... (Merge and Unload)")
    merged_model = model.merge_and_unload()
    
    # 4. 결과 저장
    logger.info(f"4/4. 병합된 최종 모델을 '{output_dir}'에 저장 중...")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    merged_model.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("✅ 병합 완료! 이제 vLLM에서 이 병합된 단일 모델 폴더만 지정하면 즉각적으로 빠른 추론이 가능합니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge LoRA weights into base model.")
    parser.add_argument("--base_model", type=str, default="deepseek-ai/deepseek-coder-7b-instruct-v1.5", help="베이스 모델 경로/이름")
    parser.add_argument("--lora_path", type=str, default="./models/ccop-v1-lora", help="학습이 완료된 LoRA 로컬 경로")
    parser.add_argument("--output_dir", type=str, default="./models/ccop-v1-merged", help="병합된 모델 저장 폴더")
    
    args = parser.parse_args()
    merge_models(args.base_model, args.lora_path, args.output_dir)
