# Core — 게임 로직

> **목적**: exca_dance의 핵심 게임 로직 — 데이터 모델, 상수, 스코어링 공식, FK 좌표계, GameLoop 프로토콜, 비트맵 포맷을 정의한다.
>
> **대상 파일**: `src/exca_dance/core/` 전체

---

## 핵심 데이터 모델 (`core/models.py`)

```python
class JointName(str, Enum):    # JSON 값은 소문자
    SWING = "swing"
    BOOM = "boom"
    ARM = "arm"
    BUCKET = "bucket"

class Judgment(str, Enum):
    PERFECT = "perfect"
    GREAT = "great"
    GOOD = "good"
    MISS = "miss"

@dataclass(frozen=True)
class BeatEvent:
    time_ms: int                              # 곡 시작부터의 절대 ms
    target_angles: dict[JointName, float]     # 목표 관절 각도 (부분집합)
    duration_ms: int = 500                    # 가이드 표시 시간

@dataclass
class BeatMap:
    title: str
    artist: str
    bpm: float           # 참고용 (게임 엔진이 직접 사용하지 않음)
    offset_ms: int       # 전역 오프셋
    audio_file: str
    difficulty: str = "NORMAL"
    events: list[BeatEvent]

@dataclass(frozen=True)
class HitResult:
    judgment: Judgment
    score: int
    angle_error: float       # 평균 각도 오차 (도)
    timing_error_ms: float   # 타이밍 오차 (ms)
```

---

## 상수 (`core/constants.py`)

```python
# 관절 각도 제한 (도)
JOINT_LIMITS: dict[JointName, tuple[float, float]] = {
    JointName.SWING:  (-180.0, 180.0),
    JointName.BOOM:   (-30.0, 60.0),
    JointName.ARM:    (-50.0, 90.0),
    JointName.BUCKET: (0.0, 200.0),
}

# 타이밍 판정 윈도우 (ms, 반창 — 양쪽 대칭)
JUDGMENT_WINDOWS = {
    Judgment.PERFECT: 35.0,
    Judgment.GREAT: 70.0,
    Judgment.GOOD: 120.0,
}

# 기본 점수
SCORE_VALUES = {
    Judgment.PERFECT: 300,
    Judgment.GREAT: 200,
    Judgment.GOOD: 100,
    Judgment.MISS: 0,
}

# 콤보 배율
COMBO_THRESHOLDS = {0: 1, 10: 2, 25: 3, 50: 4}

# 디스플레이
TARGET_FPS = 60
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
JOINT_ANGULAR_VELOCITY = 60.0  # 도/초

# 링크 길이 (미터)
BOOM_LENGTH = 2.5
ARM_LENGTH = 2.0
BUCKET_LENGTH = 0.8

# 기본 키 바인딩
DEFAULT_KEY_BINDINGS = {
    JointName.SWING:  (pygame.K_a, pygame.K_d),
    JointName.BOOM:   (pygame.K_w, pygame.K_s),
    JointName.ARM:    (pygame.K_UP, pygame.K_DOWN),
    JointName.BUCKET: (pygame.K_LEFT, pygame.K_RIGHT),
}
```

---

## 스코어링 공식 (`core/scoring.py`)

```python
def judge(self, angle_errors: dict[JointName, float], timing_error_ms: float) -> HitResult:
    # 1. 타이밍 판정 결정
    timing_judgment = Judgment.MISS
    for tier in (PERFECT, GREAT, GOOD):
        if timing_error_ms <= self._windows[tier]:
            timing_judgment = tier
            break

    # 2. 각도 판정 결정 (평균 오차 기준)
    avg_err = mean(angle_errors.values())
    angle_judgment = Judgment.MISS
    for tier in (PERFECT, GREAT, GOOD):
        if avg_err <= self._angle_thresholds[tier]:
            angle_judgment = tier
            break

    # 3. 둘 중 나쁜 것 사용
    judgment = worse(timing_judgment, angle_judgment)

    # 4. 점수 계산
    self.update_combo(judgment)                        # 콤보 먼저 업데이트
    combo_mult = self.get_combo_multiplier()
    angle_mult = max(0.1, 1.0 - (avg_err / 20.0))    # 20° → 0.1x 최소
    base = SCORE_VALUES[timing_judgment]               # 기본점은 타이밍 기준
    score = int(base * angle_mult * combo_mult)

    return HitResult(judgment=judgment, score=score, ...)
```

**난이도별 각도 임계값:**
| 난이도 | PERFECT | GREAT | GOOD |
|--------|---------|-------|------|
| EASY | 8° | 18° | 35° |
| NORMAL | 5° | 12° | 25° |
| HARD | 3° | 8° | 18° |

**등급 기준:** S(95%+) / A(90%+) / B(80%+) / C(70%+) / D(60%+) / F

---

## FK 좌표계 (`core/kinematics.py`)

- **Z-up 오른손 좌표계**: base = (0,0,0), swing_pivot = (0,0,0.5)
- **Swing**: XY 평면 회전 (방위각)
- **Boom/Arm/Bucket**: 각도는 **누적** — `arm_angle = boom_rad + arm_rad`
- **내부만 라디안**: `kinematics.py` 내부에서만 라디안 사용, 외부 API는 항상 도
- **항상 clamp 먼저**: `clamp_angles()` → FK 계산 순서 필수

---

## GameLoop 프로토콜

```python
class GameLoop:
    def tick(self, dt: float) -> list[HitResult]:
        """매 프레임 호출. PLAYING 상태일 때만 비트 체크 수행."""
        # 항상: bridge.send_command() + excavator_model.update()
        # PLAYING일 때만: joint 업데이트, 비트 체크, 곡 종료 감지
        ...

    def start_song(self, beatmap: BeatMap) -> None:
        """곡 시작. 이벤트 로딩 + 오디오 재생."""
        ...
```

- `GameLoop`는 **서비스**, 스크린 아님 — `GameplayScreen`만이 `tick()` 호출
- 곡 종료 조건: `audio.is_playing() == False` 또는 마지막 이벤트 소비 후 3000ms 경과

---

## 비트맵 (`core/beatmap.py` + `assets/beatmaps/*.json`)

```json
{
  "title": "Excavator Groove",
  "artist": "Exca Dance",
  "bpm": 120.0,
  "offset_ms": 0,
  "audio_file": "assets/music/sample1.wav",
  "difficulty": "NORMAL",
  "events": [
    {"time_ms": 2000, "target_angles": {"boom": 30.0}, "duration_ms": 500},
    {"time_ms": 4000, "target_angles": {"boom": 0.0, "arm": 20.0}, "duration_ms": 500}
  ]
}
```

**핵심 규칙:**
- BPM은 참고용 — 게임 엔진이 직접 사용하지 않음
- `time_ms`는 절대값 (비트가 아님), 비트맵에서 미리 계산
- JSON 관절 키는 **소문자** (`"boom"`, `"BOOM"` 아님)
- `validate_beatmap()`: title/bpm/events 필수, events는 시간순 정렬
