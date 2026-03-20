import os
import argparse
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    set_seed
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

def format_instruction(example):
    """
    Format the instruction, input, and output into a single string for the model to learn.
    """
    prompt = f"### Instruction:\n{example['instruction']}\n\n"
    prompt += f"### Input:\n{example['input']} (Graph: {example['graph_path']})\n\n"
    prompt += f"### Response:\n{example['output']}"
    return prompt

def train():
    parser = argparse.ArgumentParser(description="QLoRA Fine-Tuning for Text-to-Cypher Model")
    parser.add_argument("--model_name", type=str, default="deepseek-ai/deepseek-coder-7b-instruct-v1.5", help="Base model path or name")
    parser.add_argument("--dataset_path", type=str, default="data/sft_dataset_v2_augmented.jsonl", help="Path to the JSONL dataset")
    parser.add_argument("--output_dir", type=str, default="./models/text2cypher-lora", help="Output directory for LoRA adapters")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size per device")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    args = parser.parse_args()

    set_seed(42)

    print(f"Loading dataset from {args.dataset_path}...")
    dataset = load_dataset("json", data_files=args.dataset_path, split="train")
    
    # BitsAndBytes Configuration for 4-bit Quantization (QLoRA)
    # Reduces VRAM usage significantly, allowing 7B models to train on 24GB GPUs (like RTX 3090/4090)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    print(f"Loading base model {args.model_name}...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="cuda:0", # [Crucial Fix] Explicitly pin to GPU 0 to prevent CPU/CUDA mismatch
        trust_remote_code=True,
        torch_dtype=torch.bfloat16
    )
    model.config.use_cache = False  # Required for gradient checkpointing

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    # [Safe Pad Token Setting] Mapping to EOS directly avoids CPU-tensor creation during resize_token_embeddings
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 모델 사양에도 명시적으로 패딩 토큰을 알려주어 추가 임베딩 생성을 방지합니다.
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False # 학습 시에는 False
    
    # ※ 중요: model.resize_token_embeddings()를 호출하면 안 됩니다!

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    # LoRA Configuration
    peft_config = LoraConfig(
        r=16,          # Rank
        lora_alpha=32, # Alpha scaling
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"], # Target all linear layers for better learning
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )

    # Training Arguments
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4, # Increase effectively batch size
        optim="paged_adamw_32bit",
        save_steps=50,
        logging_steps=10,
        learning_rate=args.lr,
        weight_decay=0.001,
        fp16=False,
        bf16=True, # Use bfloat16 for newer GPUs (Ampere architecture or newer)
        max_grad_norm=0.3,
        max_steps=-1,
        warmup_steps=100,
        lr_scheduler_type="cosine",
        report_to="none" # Set to "wandb" if you use Weights & Biases
    )

    print("Setting up SFTTrainer...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        args=training_args,
        formatting_func=format_instruction,
        max_seq_length=1024,
        tokenizer=tokenizer,
    )

    print("Starting fine-tuning...")

    print("Starting fine-tuning...")
    trainer.train()

    print(f"Saving final LoRA adapter to {args.output_dir}...")
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print("Training complete! You can now load this adapter into vLLM.")

if __name__ == "__main__":
    train()
