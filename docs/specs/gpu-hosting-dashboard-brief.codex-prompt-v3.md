# Codex Review Prompt — GPU Hosting Dashboard Brief v3 (P0 회귀 검증)

> 첨부: `docs/specs/gpu-hosting-dashboard-brief.html` (v3 갱신).

---

## Task

HyperCube GPU Hosting Dashboard brief 의 **v3 P0 회귀 검증**.
당신의 v2 review Final Verdict 는 "mock 1차 구현 시작 OK, 단 아래 P0 5개 수정 후 시작" 이었다.
작성자가 P0 5개 + E 의 부가 issue 7건을 모두 반영해 v3 를 만들었다.
**이번 review 의 유일한 목적**: P0/E 항목이 정확히 반영됐는지 확인 + mock 구현 시작 가부 최종 판정.

## v2 Review 의 P0 / E 항목 처리

### P0 5건

| # | P0 항목 | v3 위치 |
|---|---|---|
| P0-1 | §4 장애 source 에 `ContainerEvent` 추가 (OOM/DIE/HEALTH_STATUS) | §4 결정 로그 + §9 `EventSource` enum |
| P0-2 | 코드 필드명 정정: `ContainerTemplate.default_model_version_ids`, `Container.mounted_model_version_ids` | §2, §7.9, §9 `SliceMock.model.versionId`, §11.1, §13 |
| P0-3 | §9 compute quality derived fields 추가 | §9 `SliceMock.qualityState`/`computePctSustained5m`/`queueDepth`/`latencyP95Ms` |
| P0-4 | §9 fixture seed 에 `mig_reconfiguring` · `oom` · `xid_ecc_error` 실제 추가 (xid_ecc_error 는 mock-only synthetic) | §9 fixture 실패 시드 6종 + EventSource `synthetic` |
| P0-5 | §7/§9 빈/오류 row state + stale heartbeat 판정 규칙 | §14 신규 + §4 결정 로그 (60-180s warn, 180s+ offline) |

### E 부가 7건

| E | 항목 | v3 처리 |
|---|---|---|
| a | §2 ↔ §4 source 모순 | §4 갱신 |
| b | idle_waste 가 EventKind 가 아님 | §9 `QualityState` 별도 필드 |
| c | HostMock agentLastSeenISO stale 기준 미명세 | 60-180s warn, 180s+ offline |
| d | host offline precedence 미명세 | 하위 GPU `severity = 'offline'` override |
| e | host-gpu-03 host_offline seed 가 wireframe 에 없음 | §6 wireframe 에 host offline group 행 추가 + fixture 카운트 정정 (GPU 6→8장) |
| f | xid_ecc_error 가 §4 DCGM/XID 후속과 모순 | mock-only `synthetic` source 명시 |
| g | 1280 degrade "expand" 가 클릭/자동 불명확 | 사용자 클릭 expand 명시 + Temp 는 compact 유지 (사용자 결정) |

### 그 외 v3 에서 작성자가 자기 결정으로 추가

- Container detail navigate = 기존 `/user/containers/[id]` route 공유 (admin permission)
- 1280x720 에서 Temp 는 compact 유지 (Pwr 만 expand)
- host-gpu-03 (Busan-A) 는 GPU 2장 보유 + host_offline 시 하위 GPU offline 상속
- GpuDetailContent 를 table row 와 독립 컴포넌트로 (후속 panel 전환 cheap, v1 REJECT 보완)
- §13 신규 — Read Model Contract (mock schema ↔ 향후 API source mapping)

## 검증 초점 — 3개 관점만

### A. P0 5건 + E 7건 반영 정확성 (필수)

각 항목 라벨: `[Verified] / [Partial] / [Drift] / [Missing]`. Drift/Partial/Missing 인 경우 근거 필수.

특히 정밀하게 보라:

1. **P0-1**: §4 와 §9 EventSource enum 이 일관되나? `oom` 의 source 가 `container_event` 로 명시됐나? heartbeat 결손도 source 식별이 가능한 구조인가?
2. **P0-2**: 코드 필드명 정정이 §2 / §7.9 / §9 / §11.1 / §13 다섯 군데 모두 정확하게 들어갔나? `default_model_version_ids` 와 `mounted_model_version_ids` 의 의미 차이 (default vs 실제 mount) 가 brief 본문에 분명한가?
3. **P0-3**: `qualityState` 가 derived 인지 stored 인지 명세됐나? saturation 조건 (`>90% sustained5m + (queueDepth>0 OR latencyP95Ms>임계 OR tempTrend↑)`) 의 "임계" 값이 §11.2 #1 에 열린 질문으로 정리됐나?
4. **P0-4**: 6 EventKind 가 fixture seed 에 모두 들어갔나? `xid_ecc_error` 의 mock-only synthetic 표기가 분명한가?
5. **P0-5 / E-c / E-d**: §14 의 4 state (`no_data`/`stale`/`agent_offline`/`permission_hidden`) 가 §6 wireframe / §7 위젯 / §9 mock 의 실제 표시 규칙과 일관되나?
6. **E-e**: host-gpu-03 offline group 의 wireframe 표시와 §9 fixture (GPU 총 8장) 가 일관되나?

### B. v3 새 결정 5건의 타당성

각 항목 라벨: `[OK] / [Concern] / [Change]`.

1. Container detail navigate = `/user/containers/[id]` 공유 (admin permission). admin 이 user route 를 그대로 보는 게 정보 표시상 문제 없나? admin 만 보여야 할 metadata 가 user 화면에 안 나와서 운영 비용 생기지 않나?
2. 1280 degrade 에서 Temp compact 유지. 이전 v2 review 의 의도와 일치하나? 더 합리적인 대안 있나?
3. host-gpu-03 GPU 2장 보유 + offline 상속. host offline group row 와 하위 GPU offline row 가 시각적으로 중복되지 않나? collapse 동작 명세 필요?
4. GpuDetailContent 독립 컴포넌트화로 v1 REJECT 보완. cheap panel 전환 보장 조건이 §10 step 10 하나로 충분한가?
5. §13 Read Model Contract 신규. source mapping 표가 mock schema 와 충돌 없나? 실제 백엔드 모델 join 이 mock 의 derived 필드 (qualityState, sustained 등) 를 합리적으로 만들 수 있나?

### C. New Drift / 누락 / 모순 (있다면)

v3 통째로 읽고 v2 에 없었던 새 issue:
- (a) v3 changelog 와 본문 사이 불일치
- (b) §12 매트릭스의 처리 라벨과 실제 본문 사이 불일치
- (c) §13 contract 와 §9 mock schema 사이 불일치
- (d) 그 외 brief 자체 모순

## What "good review" looks like

- v2 review 의 입장과 v3 본문을 정밀하게 cross-check.
- 칭찬 X.
- 라벨 일괄 처리 X.
- 모든 권고는 `[Verified / Partial / Drift / Missing / OK / Concern / Change / Keep / Defer]` 중 하나로.

### Do NOT

- "P0 가 잘 반영되었습니다" 류 요약 칭찬.
- A 섹션 12개를 일괄 `[Verified]` 처리.
- 새 issue 가 없다고 단정. 의심해보고 없으면 명시.

## Output Format

```
## TL;DR
2-3줄.
- P0 반영의 최후 drift 1개 (있다면) 또는 "P0 12건 모두 Verified"
- mock 시작 가부 최종 (OK / Block / Conditional)

## A. P0/E 12건 반영 (P0 5 + E 7)
각 항목: 위치 + 라벨 + 필요 시 근거

## B. v3 새 결정 5건
각 항목: 라벨 + 근거

## C. New Issues
bullet (없으면 "No new issues found, 확인 완료" 명시)

## Final Verdict
- [ ] mock 1차 구현 시작 OK (조건 없음)
- [ ] mock 시작 OK, 단 P1 항목 수정 권장 (있다면 ranked)
- [ ] Block — 반드시 수정 후 재검증
```

## Constraints

- 한국어 또는 영어. 기술 용어 원어.
- brief 인용 시 섹션 번호.
- 코드베이스 접근 가능하면 참고. 안 되면 brief 만 보고 판단.
- v2 review 와 입장 변경 시 명시.

## Final Check Before Submitting

- [ ] 칭찬 문장 없음
- [ ] [Verified] 일괄 처리 없음
- [ ] mock 시작 가부 Final Verdict 명확
- [ ] v3 에서 새로 생긴 issue 를 능동적으로 찾았음 (없으면 없다고 명시)
