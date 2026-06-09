#!/bin/bash
# 서버 LLaMA-Factory 환경 세팅 스크립트
# 사용법: bash server_setup.sh

set -e

echo "=========================================="
echo " LLaMA-Factory 서버 환경 설치"
echo "=========================================="

# 1. 시스템 패키지 업데이트
echo "[1/5] 시스템 패키지 업데이트..."
sudo apt-get update -y
sudo apt-get install -y git python3-pip python3-venv

# 2. Python 가상환경 생성
echo "[2/5] Python 가상환경 생성..."
python3 -m venv ~/llama_env
source ~/llama_env/bin/activate

# 3. LLaMA-Factory 설치
echo "[3/5] LLaMA-Factory 설치..."
pip install --upgrade pip
pip install "llamafactory[torch,metrics]"

# 4. bitsandbytes (QLoRA 필수)
echo "[4/5] bitsandbytes 설치..."
pip install bitsandbytes

# 5. CUDA 확인
echo "[5/5] GPU 확인..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"없음\"}')"

echo ""
echo "✅ 설치 완료!"
echo "   가상환경 활성화: source ~/llama_env/bin/activate"
