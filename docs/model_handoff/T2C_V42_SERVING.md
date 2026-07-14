# SERVING — qwen25-t2c-v42 서빙 가이드 (온라인 환경)

받는 쪽이 인터넷 가능한 환경 기준. 폐쇄망은 별도(이미지/휠 사전 반입).

## 1. 요구 사항

- NVIDIA GPU (VRAM ≥ 16GB 권장; 7B bf16 + KV캐시). 예: RTX 4090/6000 Ada/A100 등
- NVIDIA 드라이버 + CUDA 런타임 (vLLM이 요구하는 CUDA와 정합)
- Python 3.10±

## 2. 설치 — 검증된 조합

과거 최신 vLLM이 torch/CUDA 불일치와 transformers 5.x 토크나이저 에러를 유발한 이력이 있어 **아래 핀 조합을 권장**한다(CUDA 12.x 드라이버 기준).

```bash
python3 -m venv ~/t2c_env && source ~/t2c_env/bin/activate
pip install --upgrade pip
pip install "vllm==0.6.3.post1"      # torch 2.4.0+cu121 동반
pip install "transformers==4.46.3"   # 5.x 는 Qwen2Tokenizer all_special_tokens_extended 에러
```

> 최신 GPU(예: Blackwell)·최신 드라이버 환경이면 최신 vLLM이 오히려 필요할 수 있다. 그 경우 최신으로 설치하되 **모델 로드 + 추론 1회를 반드시 스모크 테스트**하고, 실패 시 위 핀 조합으로 회귀.

## 3. 서빙 기동

```bash
vllm serve ./model/qwen25-t2c-v42 \
  --served-model-name qwen25-t2c-v42 \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.9 \
  --dtype bfloat16 \
  --chat-template ./model/qwen25-t2c-v42/chat_template.jinja
```
- `--chat-template` **필수** — 이 모델은 chat_template이 분리 저장돼 있음. 빼면 프롬프트 포맷이 어긋남.
- 여러 요청 처리량이 필요하면 `--max-num-seqs`, `--enable-prefix-caching` 추가 검토.

기동 확인:
```bash
curl http://localhost:8000/v1/models      # qwen25-t2c-v42 응답
```

## 4. 호출 — ⚠️ 시스템 프롬프트 필수

`prompt/t2c_v37_system.txt` 전체를 **system 메시지로** 반드시 주입한다(온톨로지 스키마·출력 규칙이 여기 있음).

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")

system_prompt = open("prompt/t2c_v37_system.txt", encoding="utf-8").read()

resp = client.chat.completions.create(
    model="qwen25-t2c-v42",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "피의자2의 계좌를 보여줘"},
    ],
    temperature=0,
    max_tokens=512,
)
print(resp.choices[0].message.content)   # AgensGraph Cypher
```

## 5. Router 적용 (운영 표준 86.6% 재현 시)

모델 단독은 잡담(GENERAL)·위험질의(GUARD)를 처리하지 않는다(그렇게 학습됨). 운영에선 **LLM 호출 전 규칙 라우터**가 이를 차단해 +5.6p를 얻는다.

- 벤치마크에서는 `benchmark_t2c_v2.py` 의 `pre_route_guard_general()` 이 이 역할.
- 실서비스 통합 시엔 리포의 `app/services/ai_service.py`(라우터) + `app/services/langgraph_agent.py`(분기) 참조.
- **테스트 해석**: Router 없이 측정하면 general/guard 0% → 전체 ~81%. Router 켜면 ~86.6%. 둘 다 정상 결과이니 어느 모드로 측정했는지 명시할 것.

## 6. 벤치마크 실행

```bash
python eval/benchmark_t2c_v2.py \
  --endpoint http://localhost:8000/v1 \
  --model qwen25-t2c-v42 \
  --mode t2c_v37 \
  --output my_bench.json
```
결과를 `eval/bench_v42_router_232.json`(86.6%) / `bench_v42_full_232.json`(81.0%)과 대조.

## 7. 트러블슈팅

| 증상 | 원인 | 대응 |
|---|---|---|
| `Qwen2Tokenizer ... all_special_tokens_extended` | transformers 5.x | `pip install transformers==4.46.3` |
| `torch.cuda.is_available()=False` | vLLM이 끌어온 torch가 드라이버 CUDA와 불일치 | vllm==0.6.3.post1(cu121) 핀, 또는 드라이버에 맞는 vLLM |
| 응답이 엉뚱/포맷 깨짐 | 시스템 프롬프트 누락 | `t2c_v37_system.txt` 를 system 으로 주입 |
| general/guard 0% | Router 미적용 | 정상 — §5 참조 |
| OOM | max-model-len/utilization 과다 | `--max-model-len` ↓, `--gpu-memory-utilization 0.85` |

## 8. (선택) 어댑터로 실험하려면

이 번들은 병합본만 포함. LoRA 어댑터(`qwen25_t2c_v42_v1`)로 continue-learning/AB 하려면 별도 요청. 어댑터 서빙은 `vllm ... --enable-lora --lora-modules t2c=<adapter_path> --max-lora-rank 64`.
