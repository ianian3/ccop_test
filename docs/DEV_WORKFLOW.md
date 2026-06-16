# CCOP 개발 → 운영 배포 워크플로우

> 브랜치 전략(2026-06-16 정립)과 배포 절차. 인프라 상세는 `docs/CHECKPOINT_20260616.md` 참고.

## 1. 브랜치 전략 (trunk-based on `dev`)

- **`dev` = 단일 트렁크 겸 기본 브랜치** (GitHub origin · Gitea cslee 둘 다 기본).
- **stable 표식 = 태그** (`prod-YYYYMMDD`, `v1.x.x`). 별도 release 브랜치 없음.
- **`feature/<주제>`** = 기능/위험 작업용 단명 브랜치 → dev 머지 후 삭제.
- **`backup/*`** = 위험 작업 전 스냅샷 (보존).
- 삭제한 브랜치는 `archive-*` 태그로 보존(무손실).

원칙:
- ⛔ **VM(skai2_vm)에서 직접 커밋 금지.** 개발은 개발 머신에서만, VM은 배포 대상.
- 모든 push는 **origin + cslee(미러) 동시** (아래 dual-push 설정).
- push하면 **GitHub Actions CI(test)** 자동 검증 → **green 확인 후 배포.**

## 2. 개발 사이클

```bash
# (선택) 기능 브랜치
git switch -c feature/my-change dev
# ... 작업 + 커밋 ...
git switch dev && git merge --no-ff feature/my-change   # 또는 dev 직접 커밋
git branch -d feature/my-change

# 양쪽 리모트 push (dual-push 설정 시 origin 하나로 둘 다 전송)
git push origin dev
```

### dual-push 설정 (1회, 개발 머신)
`git push origin dev` 한 번으로 origin(GitHub)+cslee(Gitea) 동시 전송:
```bash
git remote set-url --add --push origin https://github.com/ianian3/ccop_test.git
git remote set-url --add --push origin http://<gitea-cred>@211.188.50.27:8446/cslee/skai-vm.git
# 확인: git remote get-url --push --all origin  → 2개 URL
```

## 3. 운영 배포 (skai2_vm, 수동)

> CI는 검증만, CD는 수동. app은 Dockerfile로 VM에서 빌드(`--build` 필수).

### 권장: 헬퍼 스크립트 (pull→build→헬스체크→실패시 자동롤백)
```bash
ssh -p 10022 root@175.45.205.106
cd /root/ccop_test
bash scripts/deploy.sh
```

### 수동 단계 (참고)
```bash
cd /root/ccop_test
git pull --ff-only origin dev
docker compose -f docker-compose.cslee.yml up -d --build app
curl -sk https://localhost/api/v1/health      # {"status":"healthy"}
```

### 배포 성공 → 릴리스 태그 (개발 머신)
```bash
git tag -a prod-$(date +%Y%m%d) <배포커밋> -m "운영 배포: <요약>"
git push origin prod-$(date +%Y%m%d)
```

## 4. 롤백

```bash
# VM: 직전 stable 태그로 되돌려 재빌드
cd /root/ccop_test
git checkout prod-<직전날짜>
docker compose -f docker-compose.cslee.yml up -d --build app
# 근본 수정은 dev에서 git revert → 재배포
```
(`scripts/deploy.sh`는 헬스체크 실패 시 직전 커밋으로 **자동 롤백**.)

## 5. 배포 시 체크포인트

| 항목 | 주의 |
|------|------|
| LLM(vLLM) | 엘리스 watchdog·터널 영속화 → 평소 무조치. **엘리스 온디맨드 인스턴스가 켜져 있어야** 함 (꺼졌으면 엘리스에서 `setsid bash ~/vllm_watchdog.sh`) |
| DB | `tccopdb` 원격(49.50.128.28:5333) — 배포와 무관, 변경 금지 |
| `.env` | VM 운영값(DB=tccopdb, SLLM_ENDPOINT). gitignore라 pull이 덮어쓰지 않음 |
| 미러 | cslee도 동기화 유지(dual-push) |
| 외부 시연 | Naver Cloud ACG 소스 IP 제한 — 외부 접속은 ACG 허용 필요 |

## 6. CI/CD 현황

- **CI**: `.github/workflows/deploy.yml` — dev push 시 `test`(온톨로지 import + Flask 기동) 검증.
- **CD**: 수동(위 3절). 자동 CD가 필요하면 GitHub 시크릿(`DOCKER_*`,`VPS_*`) 등록 + 타깃을 `docker-compose.cslee.yml`로 재구성.
