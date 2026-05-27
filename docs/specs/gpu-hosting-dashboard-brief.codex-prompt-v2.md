# Codex Review Prompt — GPU Hosting Dashboard Brief v2 (회귀 검증)

> 아래 본문을 Codex 세션에 그대로 붙여넣기.
> 첨부: `docs/specs/gpu-hosting-dashboard-brief.html` (v2, 갱신된 파일).

---

## Task

HyperCube GPU Hosting Dashboard brief 의 **v2 회귀 검증**.
v1 (당신의 직전 review) 에서 제시한 13건 권고를 brief 작성자가 ACCEPT 10 / DEFER 3 / REJECT 1 로 처리해 v2 를 만들었다.
**회귀 검증 (regression review)** 모드 — v1 권고가 의도대로 반영됐는지, 반영 과정에서 새 문제가 생겼는지, DEFER/REJECT 결정이 합리적인지 확인하라.

## v1 권고 처리 결과 요약

| # | v1 권고 | v2 처리 |
|---|---|---|
| 1 | Compute 색 = utilization quality, severity 별도 | ACCEPT (§4, §7.3) |
| 2 | Host group + GPU row + slice detail tree | ACCEPT (§4, §6, §9 HostMock) |
| 3 | Mock fixture 실패 상태 (host_offline / driver_error / mig_reconfiguring / allocation_failed / oom / xid_ecc_error) | ACCEPT (§9 EventKind) |
| 4 | KPI: Active users → Issues / Idle allocated | ACCEPT (§7.1) |
| 5 | Top Models → Mounted Models | ACCEPT (§7.9) |
| 6 | Semantic palette ↔ Identity palette 분리 | ACCEPT (§5.3) |
| 7 | SVG sparkline | ACCEPT (§7.5) |
| 8 | MIG mini grid → profile-aware segmented bar | ACCEPT (§7.4) |
| 9 | 1440x900 컬럼 priority + Live 기본 5s | ACCEPT (§4, §7.2) |
| 10 | Nice-to-have (Mounted Models rename / filter / fixture 카운트 / 빈 상태) | ACCEPT (분산) |
| 11 | Pending/Failed Allocations 별도 패널 | **DEFER** (Recent Events 내 incident sticky 로 시작) |
| 12 | Table virtualization | **DEFER** (50+ GPU 시점) |
| 13 | Aggregation API (`/api/gpu-hosting/fleet/`) | **DEFER** (mock 1차 스코프 밖) |
| 14 | 인라인 expand + 우측 detail panel 병행 (P1) | **REJECT** (mock 1차는 expand only) |

추가로 작성자가 v2 에서 자기 결정으로 확정한 항목:
- 1차 사용자 = Platform admin (admin-only)
- 1차 action = Container detail navigate (read-only)
- 최소 viewport = 1440x900
- 장애 source = Agent heartbeat + ResourceEvent (DCGM/XID 는 후속)

## 검증 초점 — 6개 관점

### A. v1 ACCEPT 권고 반영 정확성 (10건)

각 ACCEPT 항목에 대해:
- (a) brief v2 에서 실제로 반영된 위치 (섹션 번호)
- (b) **의도 왜곡 / 약화 / 부분 반영** 여부
- (c) 라벨: `[Verified] / [Partial] / [Drift] / [Missing]`

특히 다음 4개는 정밀하게 보라 (v1 에서 가장 강하게 권고한 것들):

1. **Compute 색 = utilization quality** (§7.3) — idle waste 10min &lt;20%, saturation 5min &gt;90% + compound 조건. **단순 threshold 로 회귀하지 않았는가?**
2. **Host group + GPU row + slice detail** (§4, §6, §9) — HostMock 모델 + group 행 wireframe + 코드 매핑이 일관되나? flat list 의 잔재가 남아 있나?
3. **Semantic vs Identity 색 분리** (§5.3) — 두 팔레트의 사용 영역이 명확히 분리됐나? Hero/사이드 차트가 semantic 색을 잘못 쓰지 않는가?
4. **Mock fixture 실패 상태** (§9 EventKind enum) — 6종 다 들어갔나? fixture 실제 시드(`실패 시드: host-gpu-03 host_offline · H100-03 driver_error · A100-02 idle_waste · REQ-008 allocation_failed`) 가 enum 과 일관되나?

### B. DEFER 3건의 결정 타당성

- **#11 Pending/Failed Allocations 별도 패널**: Recent Events 안 incident sticky 로 대체 — 운영자가 "실패한 신청" 을 얼마나 빠르게 찾을 수 있나? mock 1차에 빼도 되나, 빼면 안 되나?
- **#12 Table virtualization**: 30 GPU + host group 행이 추가된 wireframe 에서 1440x900 기준 실제 렌더링 row 수는? virtualization 없이도 안전한 수치인가?
- **#13 Aggregation API**: mock 만으로 1차 구현 후 실제 API 붙일 때 IA 가 깨질 가능성. 지금 결정해두지 않으면 후속 작업에서 비싸게 갚는 항목 있나?

각 항목 라벨: `[Defer OK] / [Defer Risky] / [Reverse - 지금 결정해야 함]`

### C. REJECT 1건의 거절 타당성

**#14 인라인 expand + 우측 detail panel 병행 (P1)**:
- 작성자 이유: "학습 비용 + 구현 비용 + mock 1차 학습 비용 고려"
- 평가: 거절이 운영자 워크플로에 결정적 손상을 주는가? mock 1차에 expand only 로 가도 후속에서 panel 추가가 cheap 한가?
- 라벨: `[Reject OK] / [Reject Risky] / [Reverse - panel 도입해야 함]`

### D. v2 에서 새로 생긴 결정 4건의 타당성

1. **1차 사용자 = Platform admin (admin-only)** — mock 1차에 user-facing read-only 진입을 막은 결정. 후속 단계에서 user role 도입 시 IA 가 다시 흔들릴 위험?
2. **1차 action = Container detail navigate 만** — 화면에서 할당 회수·승인·host 격리 등을 할 수 없게 한 결정. 운영자가 두 화면(여기 + 다른 곳) 을 오가야 하는 비용 vs scope 통제 trade-off
3. **1440x900 컬럼 priority** (§7.2) — 1280x720 degrade 규칙이 충분히 명세됐나? "expand 안으로 이동" 의 expand 가 자동 펼침인지 사용자 클릭인지?
4. **장애 source = Agent heartbeat + ResourceEvent** — `ContainerEvent` 는 왜 제외됐나? OOM 같은 컨테이너 종료 신호가 이걸 통해 들어올 텐데 누락 가능성?

각 항목 라벨: `[OK] / [Concern] / [Change]`

### E. 반영 과정의 New Issues / 모순 / 누락

brief v2 를 통째로 읽었을 때 발견되는:
- (a) v1 권고 사이의 충돌 (서로 영향 주는 결정의 조합이 일관성 깨는가)
- (b) 새 결정(§4) 과 기존 위젯 명세(§7) 사이 불일치
- (c) §9 mock 스키마와 §6 wireframe 사이 불일치
- (d) `Mounted Models` 가 §7.9 에는 있지만 §9 `MountedModel` 인터페이스만 있고 실제 fixture 가 어떻게 채워질지 명세 누락
- (e) HostMock 의 `agentLastSeenISO` 가 host severity 결정에 어떻게 쓰이는지 명세 누락
- (f) 그 외 brief 자체 모순

### F. §11.2 남은 열린 질문 6개에 대한 입장

mock 1차 시작을 막을 만한 항목이 있나? 6개 중:
1. 임계값 정확 수치
2. GPU 별 temp threshold
3. DCGM 고급 metric 수집
4. 다음 단계 우선순위
5. Mounted Models 데이터 정확성 (`ContainerTemplate.default_models` 가 실제 mount 인지 default 인지)
6. color blindness QA

각 항목: `[Blocking mock] / [OK for mock, decide later] / [No decision needed]`

## What "good review" looks like (v1 과 동일)

- 추측보다 근거 기반 비교. Grafana / DCGM / Run:AI / Datadog 패턴과 대조.
- 약점·위험·대안 위주. 칭찬 X.
- 자기 결정 무비판적 확인 X. 충돌 대안 명시.
- 확신 수준 표시 (`[확신 없음]`).
- 시나리오 기반 (새벽 3시 알람, 100 GPU 확장).

### Do NOT

- "v1 권고가 잘 반영됐습니다" 류 일반 칭찬.
- 모든 ACCEPT 를 `[Verified]` 로 일괄 처리. 정밀하게 보라.
- "고려해 볼 수 있다" 모호한 권고. `[Reverse / Keep / Defer]` 셋 중 하나.

## Output Format

```
## TL;DR
3-5줄.
- v1 권고 반영의 가장 큰 drift 1개 (있다면)
- DEFER/REJECT 중 가장 위험한 것 1개 (또는 "모두 합리적")
- v2 에서 새로 발견한 가장 큰 위험 1개

## A. v1 ACCEPT 권고 반영 정확성 (10건)
각 권고:
- 위치
- 라벨: [Verified / Partial / Drift / Missing]
- 코멘트 (Drift/Partial/Missing 인 경우 필수)

## B. DEFER 3건 평가
각 항목: 라벨 + 근거

## C. REJECT 1건 평가
라벨 + 근거

## D. v2 새 결정 4건 평가
각 항목: 라벨 + 근거

## E. New Issues / 모순 / 누락
bullet, 발견한 것 전부

## F. 열린 질문 6건 blocking 여부
각 항목: 라벨

## Final Verdict
- [ ] mock 1차 구현 시작 OK
- [ ] 그 전에 반드시 수정해야 할 항목 (있다면 ranked)
```

## Constraints

- 한국어 또는 영어. 기술 용어 원어.
- brief 인용 시 섹션 번호 (예: "§7.3 Compute 색").
- 코드베이스 접근 가능하면 참고. 안 되면 brief 만 보고 판단하되 "코드 미확인" 명시.
- v1 review 와 모순되는 의견 변경은 명시적으로 표시 (예: "v1 에서는 X 권고했지만 v2 의 Y 결정을 보고 Z 로 입장 변경").

## Final Check Before Submitting

- [ ] 칭찬 문장이 들어가 있지 않은가?
- [ ] 각 권고에 라벨과 근거가 붙어 있는가?
- [ ] [Verified] 일괄 처리가 없는가?
- [ ] mock 1차 시작 가부 (Final Verdict) 가 명확한가?
