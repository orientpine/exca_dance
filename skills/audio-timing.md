# Audio — 오디오 및 타이밍 시스템

> **목적**: exca_dance의 오디오 재생, perf_counter 기반 정밀 타이밍, 비트 동기화, 사일런트 모드를 정의한다.
>
> **대상 파일**: `src/exca_dance/audio/audio_system.py`

---

## 타이밍 원천: `time.perf_counter()`

전체 타이밍 시스템은 `time.perf_counter()`(고해상도 단조 시계) 기반.

**왜 perf_counter인가?**
- `pygame.mixer.music.get_pos()` / `get_position()`은 MP3/OGG에서 **300초당 ~500ms 드리프트**
- perf_counter는 단조, 시스템 시계 변경에 면역, 서브마이크로초 정밀도

```python
def get_position_ms(self) -> float:
    if not self._is_playing:
        return 0.0
    elapsed = time.perf_counter() - self._start_time - self._accumulated_pause
    if self._is_paused:
        elapsed -= time.perf_counter() - self._pause_start
    return max(0.0, elapsed * 1000.0)
```

---

## 타이밍 파이프라인

```
AudioSystem          GameLoop              ScoringEngine
(perf_counter) ─────→ tick(dt) ─────→     judge()
    │                    │                     │
get_position_ms()   _check_beats()         HitResult
    │                    │                     │
    └─── 절대 ms ────→  이벤트 매칭 ────→  판정 + 점수
```

1. **곡 시작**: `audio.play()` → `_start_time = perf_counter()`
2. **매 프레임**: `current_ms = audio.get_position_ms()`
3. **비트 체크**: `time_ms`가 `current_ms` 이하인 이벤트 평가
4. **판정**: 타이밍 오차 + 각도 오차 → `ScoringEngine.judge()`
5. **자동 미스**: GOOD 윈도우(120ms) 초과 시 강제 MISS

---

## 사일런트 모드

`pygame.mixer.init()` 실패 시 (오디오 장치 없음):
- 모든 오디오 재생 메서드는 no-op
- `get_position_ms()`는 perf_counter로 정상 작동
- `is_playing()`은 경과 시간 vs `song_duration_ms` 비교

---

## 오디오 컨벤션

| 항목 | 규칙 |
|------|------|
| 타이밍 원천 | `time.perf_counter()` via `AudioSystem.get_position_ms()` |
| 오디오 포맷 | BGM: `.ogg`, `.wav` / SFX: `.wav` 전용 |
| 시간 단위 | 밀리초(ms) — `time_ms`, `duration_ms`, 판정 윈도우 |
| BPM 역할 | 참고용 — 게임 엔진이 직접 사용하지 않음 (이벤트가 절대 ms로 사전 계산) |

---

## 곡 종료 감지

`is_playing()` 로직:
1. `_is_playing == False` or paused → `False`
2. Silent mode + `song_duration_ms` 설정 → 경과 vs 길이 비교
3. 실제 오디오 → `pygame.mixer.music.get_busy()` (False 시 `_is_playing` 동기)

`GameLoop._check_song_end()` 조건 (둘 중 하나 → FINISHED):
- `not audio.is_playing()` — 1차
- 마지막 이벤트 소비 후 3000ms 경과 — 폴백

---

## 오디오 안티패턴

```python
# ❌ 절대 금지 — 500ms/300s 드리프트
pygame.mixer.music.get_pos()
pygame.mixer.music.get_position()

# ✅ 올바른 방법
current_ms = audio.get_position_ms()  # perf_counter 기반
```
