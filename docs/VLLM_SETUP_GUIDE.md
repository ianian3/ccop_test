# vLLM Server Setup and Running Guide

This guide provides step-by-step instructions for setting up the virtual environment and running the vLLM server on the remote machine (`192.168.1.133`).

## 1. Environment Setup (First-time only)

If the virtual environment does not exist, follow these steps to create it.

```bash
# Create the virtual environment
python3 -m venv ~/llm_env

# Activate the environment
source ~/llm_env/bin/activate

# Install vLLM and dependencies
pip install --upgrade pip
pip install vllm
```

## 2. Running the vLLM Server (Routine)

Use the following command to start the OpenAI-compatible API server with the Text-to-Cypher LoRA adapter.

```bash
# 1. Clear existing vLLM processes to free up GPU memory
kill -9 $(pgrep -f vllm)

# 2. Activate the virtual environment
source ~/llm_env/bin/activate

# 3. Launch the server (Optimized for RTX 5090)
python3 -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-coder-7b-instruct-v1.5 \
    --enable-lora \
    --lora-modules text-to-cypher=/home/ai-kyw-dev/text2cypher_train/models/text2cypher-lora \
    --max-lora-rank 32 \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.90 \
    --dtype bfloat16
```

### Key Parameters:
- `--host 0.0.0.0`: Essential for allowing external connections (from the application server).
- `--enable-lora`: Enables LoRA adapter support.
- `--lora-modules`: Maps the LoRA adapter path to a name (`text-to-cypher`).
- `--gpu-memory-utilization 0.90`: Reserves 90% of GPU VRAM for the model.

## 3. Maintenance and Troubleshooting

### Checking Server Connectivity
From the application server, verify if the port is open:
```bash
nc -zv 192.168.1.133 8000
```

### Verifying GPU Status
On the remote server, check if the vLLM process is correctly occupying the GPU:
```bash
nvidia-smi
```

### Checking Active Ports
Check if the port is bound to `0.0.0.0` (all interfaces) rather than `127.0.0.1`:
```bash
sudo netstat -tulpn | grep 8000
```
