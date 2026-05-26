# Codex Review Prompt — GPU Hosting Dashboard Design Brief

> 아래 본문을 Codex 세션에 그대로 붙여넣기.
> 첨부: `docs/specs/gpu-hosting-dashboard-brief.html` (코드베이스 접근 가능하면 read 권한 부여).

---

## Task

HyperCube(SvelteKit + Django + Docker) 의 신규 GPU Hosting Dashboard 설계 brief 를 사전 검토하라.
첨부 문서 `docs/specs/gpu-hosting-dashboard-brief.html` 의 11개 섹션이 검토 대상.
이 review 는 **mock 1차 구현 직전 단계** — "지금 결정 안 해도 되는 것" 은 다음 단계로 미루라고 명시해도 됨.

## Project Context (필요 시만 참고)

- HyperCube: 사내 컨테이너/GPU 호스팅 플랫폼. 현재는 Docker 모니터링이 중심.
- 정체성 이동: "Docker 관리" → "GPU 호스팅 플랫폼 + Docker 부가".
- GPU: H100 (MIG 슬라이스 + Whole 혼합), A100, RTX 4090. 클러스터 10-30대 가정.
- 사용 패턴: 사용자 GPU 신청 → 관리자 승인 → 슬라이스/전체 할당 → 컨테이너에서 LLM 실행.
- 백엔드 자산 이미 존재: `ContainerRequest`, `GpuAllocation`/`ContainerRequestGpuSlice`, `ModelAsset`.
- 본 작업은 본질적으로 프론트 신규. 1차는 mock 데이터.
- 관련 코드(접근 가능하면 참고): `backend/apps/containers/models.py`, `frontend/src/routes/server-2d/+page.svelte`, `frontend/src/lib/components/server2d/*`.

## What "good review" looks like

평가 기준 — 응답이 다음을 충족할 때 "좋은 review" 다.

1. **추측보다 근거 기반 비교**
   - "이 결정은 [패턴 X]와 다르다. 통상 [Y] 가 일반적이다 — 이유: [Z]" 식.
   - Grafana / DCGM exporter / Run:AI / Weights & Biases System Metrics / Datadog APM 등 통상 패턴과 비교하라.

2. **약점 / 위험 / 대안 위주**
   - "잘 정리됨" 같은 칭찬은 출력하지 말 것.
   - "사용자가 어디서 헤맬지", "6개월 뒤 어떤 결정이 뒤집힐지", "처음엔 보이지 않다가 클러스터가 3배 늘면 무너지는 가정" 위주.

3. **자기 결정을 무비판적으로 확인 X**
   - brief 가 채택한 결정(예: 행 리스트 / Compute 1차 / 임계값 40·70 / unicode sparkline) 마다 **충돌 대안을 명시적으로 검토**하고 결정이 옳다면 옳은 이유, 틀렸다면 대체안을 제시.

4. **확신 수준 표시**
   - 단정 vs 추측을 구분. 모르는 영역은 `[확신 없음]` 태그로 명시.
   - "DCGM 의 X 메트릭이 이런 의미" 같은 도메인 fact 는 틀릴 수 있으니 확신 없으면 단언하지 말 것.

5. **반례 / 시나리오 기반**
   - 추상 비평이 아니라 "운영자가 새벽 3시에 알람 받고 들어왔을 때 이 화면이 도움이 되는가" / "30대로 늘어났을 때 어떻게 깨지는가" 같은 시나리오로 평가.

### Do NOT

- "전반적으로 잘 짜인 설계입니다" 같은 요약 칭찬으로 시작/마무리.
- brief 의 모든 결정을 칭찬으로 받아넘기기.
- "고려해 볼 수 있다" 같은 모호한 권고. 결정 권고는 "이걸 바꿔라 / 그대로 둬라" 둘 중 하나로.
- 일반론 ("UX 는 사용자 중심으로 …"). HyperCube · GPU 호스팅 맥락 안에서 구체적으로.

## Review Scope — 9개 관점

각 항목마다 **(a) brief 가 채택한 결정 (b) 충돌 대안 (c) 권고 (변경 / 유지 / 추가 조사)** 형식으로 답하라.

1. **IA / 1차 시민 결정** — "물리 GPU 카드 1차" 가 MIG/Whole 혼합 환경에 최적인가? 클러스터 100대 시나리오에서 견디나? 대안: 슬라이스 1차 / ContainerRequest 1차 / host→GPU→slice tree.

2. **"한 화면에 바로 보임" 충실도** — KPI 4개가 진짜 1차 지표인가? Above the fold 가정이 1080p / 노트북 1440x900 에서 성립하나? Hero 위치 (KPI 아래 vs Table 아래) 결정의 근거.

3. **행 리스트 표현** — 카드 그리드 대비 trade-off 가 충분한가? 슬라이스 mini grid (`■■■□□■■`) 가독성. 인라인 sparkline: unicode block vs 작은 svg. 인라인 expand vs 우측 패널 vs 모달.

4. **임계값 색 기준** — Compute 40/70, VRAM 90, Temp 80. 운영 현실에서 의미 있는가? (예: Compute 70% 는 사실 매우 좋은 활용도일 수 있어 빨강이 false alarm) 시간 평균 / 변화율 기반으로 가야 하나?

5. **누락된 지표 / 시나리오** — DCGM (Tensor Core %, Memory Copy Util, NVLink, PCIe BW, ECC). 운영 시나리오 (OOM, 슬라이스 할당 실패, MIG 재구성 중, ECC 오류, 드라이버 장애, 호스트 장애). 멀티-노드 / 호스트 차원 누락 여부.

6. **위젯 추가 / 축소** — 추가 권고 / 삭제 권고. 사이드 패널 3개(자원별 VRAM · Top Models · Recent Events) 각각의 유지 가치.

7. **디자인 일관성** — "아이콘 최소 + 폰트 큼" 원칙이 위젯 수준에서 깨질 위험 지점. 3색 한정(accent/warn/error) 이 5+ GPU 라인 차트와 양립 가능한지, GPU 별 컬러 배정 방법.

8. **접근성 / 반응형 / 성능** — 행 리스트가 1280px 에서 컬럼 다 보이나? 어떤 컬럼 우선 숨김? 색맹 대비. LIVE 갱신 (1s/5s/1m) × 30 GPU × 60s sparkline × 4 차트 환경의 성능 함정.

9. **brief §11 열린 질문 11개** 각 항목에 대한 입장. 특히 (3) 인라인 expand + 우측 패널 병행 가치, (5) sparkline 표현 방식, (10) Hero 위치.

## Output Format

```
## TL;DR
3-5줄. 다음 셋:
- 가장 큰 위험 1개
- 가장 강한 결정 1개 (그대로 유지 권고)
- 가장 강한 변경 권고 1개

## 섹션별 검토 (1-9)
각 섹션:
- (a) brief 결정
- (b) 충돌 대안 + 근거
- (c) 권고: [CHANGE | KEEP | DEFER (mock 단계엔 결정 보류)]
- 확신 수준: [높음 | 보통 | 낮음]

## Top 3 변경 권고 (ranked)
1. ...
2. ...
3. ...

## Nice-to-have 제안
bullet, 우선순위 낮은 것들

## Open Questions to Designer
brief 작성자에게 되묻고 싶은 질문 (답이 없으면 review 가 완결 안 되는 것들)

## Out of Scope / 확신 없음
모르거나 추측인 영역 명시
```

## Constraints

- 한국어 또는 영어. 기술 용어는 원어 (refactoring, middleware, MIG, SM, DCGM 등).
- brief 인용 시 섹션 번호로 reference (예: "§4 결정 사항", "§7.2 Fleet Table").
- 코드베이스 접근 가능하면 위 경로 파일 참고. 안 되면 brief 만 보고 판단하되 "코드 미확인" 명시.
- 응답 길이 제한 없음. 단 한 섹션도 3줄 미만은 불가 — 권고에는 근거가 따라와야 함.

## Final Check Before Submitting

응답을 작성한 후, 다음을 자가 점검:
- [ ] 칭찬 문장이 들어가 있지 않은가?
- [ ] 각 권고에 "왜" 가 붙어 있는가?
- [ ] 확신 수준이 표시되어 있는가?
- [ ] 대안이 적어도 한 번은 명시적으로 제시되었는가?
- [ ] HyperCube / GPU 호스팅 맥락 안에서 구체적인가, 일반론에 그치지 않는가?
