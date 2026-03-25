# AGENTS.md — core/

Game logic, data models, constants, and FK engine. The only subpackage with a non-empty `__init__.py` — re-exports models + constants so `from exca_dance.core import JointName` works.

---

## STRUCTURE

```
core/
├── __init__.py      # Re-exports: JointName, Judgment, BeatEvent, BeatMap, HitResult, + constants
├── models.py        # All dataclasses + enums (JointName, Judgment, BeatEvent, BeatMap, HitResult, ...)
├── constants.py     # JOINT_LIMITS, LINK_LENGTHS, SCORE_VALUES, JUDGMENT_WINDOWS, COMBO_THRESHOLDS
├── kinematics.py    # ExcavatorFK — forward kinematics, Z-up right-hand coordinate system
├── scoring.py       # ScoringEngine — judge(), combo, grade
├── game_loop.py     # GameLoop — tick(), beat checking, song-end detection, joint updates
├── game_state.py    # GameStateManager + ScreenName constants + _Screen Protocol
├── beatmap.py       # BeatMap JSON load/save/validate
├── hit_detection.py # JudgmentDisplay — animated judgment text (PERFECT!, GREAT!, etc.)
├── leaderboard.py   # LeaderboardManager — JSON persistence, top-N
└── keybinding.py    # KeyBindingManager — key→joint mapping, load/save
```

---

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add a joint | `models.py:JointName` + `constants.py:JOINT_LIMITS` + `constants.py:LINK_LENGTHS` |
| Change timing windows | `constants.py:JUDGMENT_WINDOWS` |
| Change scoring formula | `scoring.py:ScoringEngine.judge()` |
| Add a screen name | `game_state.py:ScreenName` |
| Change song-end logic | `game_loop.py:_check_song_end()` |
| Add beatmap validation | `beatmap.py:validate_beatmap()` |

---

## KEY DATA TYPES

```python
# JointName (str enum — JSON value is lowercase)
JointName.SWING  # "swing"
JointName.BOOM   # "boom"
JointName.ARM    # "arm"
JointName.BUCKET # "bucket"

# JOINT_LIMITS: dict[JointName, tuple[float, float]]  (min_deg, max_deg)
SWING:  (-180, 180)   BOOM: (-30, 60)   ARM: (-50, 90)   BUCKET: (0, 200)

# BeatEvent (frozen dataclass)
time_ms: int                          # absolute ms
target_angles: dict[JointName, float] # subset of joints, degrees
duration_ms: int = 500

# HitResult (frozen dataclass)
judgment: Judgment
score: int
angle_error: float      # average degrees off
timing_error_ms: float
```

---

## FK COORDINATE SYSTEM

Z-up, right-hand. `base = (0,0,0)`, `swing_pivot = (0,0,0.5)`.

- **Swing** rotates in XY plane (azimuth)
- **Boom/Arm/Bucket** angles are **cumulative** (each adds to previous segment)
- `arm_angle = boom_rad + arm_rad` — NOT absolute world angles
- Radians only inside `kinematics.py`; degrees everywhere else

Link lengths: `BOOM=2.5m`, `ARM=2.0m`, `BUCKET=0.8m`

---

## SCORING FORMULA

```python
# In ScoringEngine.judge():
self.update_combo(judgment)                        # update FIRST
combo_mult = self.get_combo_multiplier()           # then read
angle_mult = max(0.1, 1.0 - (avg_err / 20.0))    # 20° → 0.1x min
score = int(SCORE_VALUES[judgment] * angle_mult * combo_mult)
```

Combo thresholds: `10→2x`, `25→3x`, `50→4x`

---

## GAME LOOP PROTOCOL

`GameLoop.tick(dt) -> list[HitResult]`

- Always: `bridge.send_command()` + `excavator_model.update()`
- Only when PLAYING: joint updates, beat checking, song-end check
- Song ends: `is_playing() == False` OR 3000ms grace period after last event consumed
- `GameLoop` is a **service**, not a screen — only `GameplayScreen` calls `tick()`

---

## CONVENTIONS

- Angles always in degrees at API boundaries; `kinematics.py` converts internally
- Beatmap JSON uses lowercase joint keys (`"boom"`, not `"BOOM"`)
- `clamp_angles()` before FK — always enforce `JOINT_LIMITS`
- `ScreenName` constants are plain strings (e.g. `"gameplay"`) — no enum
