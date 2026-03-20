# Text-to-Cypher Model Training Guide (QLoRA)

This guide explains how to fine-tune the DeepSeek-Coder model for AgensGraph Cypher query generation using QLoRA.

## 1. Prerequisites

### Hardware Requirements
- **GPU**: NVIDIA RTX 3090 / 4090 / 5090 (24GB+ VRAM recommended)
- **Driver**: CUDA 11.8+ or 12.x

### Software Environment
Activate the environment and install training dependencies:
```bash
source ~/llm_env/bin/activate
pip install torch transformers datasets peft trl bitsandbytes accelerate
```

## 2. Dataset Preparation

The training script expects a `.jsonl` file in the following format:
```json
{
  "instruction": "Convert the following question to an AgensGraph Cypher query.",
  "input": "Find all accounts that sent money to account '12345'.",
  "graph_path": "tccop_graph_v6",
  "output": "MATCH (a:Account)-[r:TRANSFER]->(b:Account {id: '12345'}) RETURN a, r, b"
}
```
Existing dataset: `data/sft_dataset_v2_augmented.jsonl`

## 3. Running the Training (QLoRA)

Execute the `train_lora.py` script. This uses 4-bit quantization to save VRAM.

```bash
python3 scripts/train_lora.py \
    --model_name deepseek-ai/deepseek-coder-7b-instruct-v1.5 \
    --dataset_path data/sft_dataset_v2_augmented.jsonl \
    --output_dir ./models/text2cypher-lora \
    --epochs 3 \
    --batch_size 4 \
    --lr 2e-4
```

### Script Options:
- `--model_name`: The base model to start from.
- `--dataset_path`: Path to your training JSONL file.
- `--output_dir`: Where the LoRA adapters will be saved.
- `--epochs`: Number of full passes over the dataset.
- `--batch_size`: Number of samples per training step.

## 4. Post-Training: Deployment

After training is complete, the `output_dir` will contain files like `adapter_model.bin` and `adapter_config.json`. 

You can then load this adapter directly into the vLLM server by pointing the `--lora-modules` path directly to this folder:

```bash
# Deployment command (Example)
python3 -m vllm.entrypoints.openai.api_server \
    --model [BASE_MODEL_PATH] \
    --enable-lora \
    --lora-modules text-to-cypher=./models/text2cypher-lora \
    ...
```

## 5. Troubleshooting

- **Out of Memory (OOM)**: Reduce `--batch_size` to 1 or 2, or decrease `max_seq_length` in the script.
- **Loss not decreasing**: Check if the dataset format is correct or try adjusting the learning rate (`--lr`).
- **CUDA Errors**: Ensure your PyTorch version is compatible with your GPU architecture.
