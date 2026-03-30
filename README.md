# Exca Dance

BGM 비트에 맞춰 굴착기 4관절(swing/boom/arm/bucket)을 조작하는 리듬 게임.
굴착기 조종을 즐겁게 배울 수 있는 교육용 소프트웨어입니다.

## Requirements

- Python 3.10+
- OpenGL 지원 그래픽 드라이버
- Windows / Linux (Ubuntu 22.04+)

## Installation

```bash
# 가상환경 생성 (권장)
python -m venv .venv

# 활성화
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 설치
pip install -e ".[dev]"
```

## Usage

```bash
# 풀스크린 (1920x1080)
python -m exca_dance

# 창 모드 (800x600)
python -m exca_dance --windowed

# 디버그 로그 활성화
python -m exca_dance --debug

# ROS2 실제 굴착기 모드 (ROS2 환경 필요, 없으면 자동 fallback)
python -m exca_dance --mode real
```

## Controls

### 기본 키 바인딩 (듀얼 스틱 레이아웃)

**Left Stick (WASD):**

| 관절 | +방향 | -방향 |
|------|-------|-------|
| Swing (선회) | A (좌) | D (우) |
| Arm (암) | W (펼침) | S (접음) |

**Right Stick (UHJK):**

| 관절 | +방향 | -방향 |
|------|-------|-------|
| Boom (붐) | J (상승) | U (하강) |
| Bucket (버킷) | K (열림) | H (말림) |

키를 누르고 있으면 해당 관절이 연속으로 움직입니다 (60°/s).
키 바인딩은 Settings 화면에서 변경 가능합니다.

### 게임 조작

| 키 | 동작 |
|----|------|
| ↑/↓ | 메뉴 항목 이동 |
| Enter | 선택/확인 |
| ESC | 일시정지 / 뒤로가기 |
| F3 | FPS 카운터 토글 |
| Q | 메인 메뉴에서 종료 |

### 자세 편집기 (Pose Editor)

| 키 | 동작 |
|----|------|
| N | 현재 위치에 새 이벤트 생성 |
| Delete | 선택된 이벤트 삭제 |
| [ / ] | 이벤트 duration 조절 |
| Space | 재생/일시정지 |
| Ctrl+S | 비트맵 저장 |
| Ctrl+O | 비트맵 불러오기 |
| Ctrl+N | 새 비트맵 |

## Game Flow

```
Main Menu → Song Select → Gameplay → Results → Leaderboard
              ↕                                    ↕
           Settings                             Save Score (이니셜 3자)
              ↕
           Pose Editor
```

## Scoring

- **Perfect** (±35ms): 300점 × 각도정확도 × 콤보배율
- **Great** (±70ms): 200점 × 각도정확도 × 콤보배율
- **Good** (±120ms): 100점 × 각도정확도 × 콤보배율
- **Miss**: 0점, 콤보 리셋

콤보 배율: 10콤보 → 2x, 25콤보 → 3x, 50콤보 → 4x

등급: S(95%+) / A(90%+) / B(80%+) / C(70%+) / D(60%+) / F

## Custom Beat Maps

`assets/beatmaps/` 폴더에 JSON 파일을 추가하면 Song Select에 자동으로 나타납니다.

```json
{
  "title": "My Song",
  "artist": "Artist Name",
  "bpm": 120.0,
  "offset_ms": 0,
  "audio_file": "assets/music/my_song.wav",
  "events": [
    {"time_ms": 1000, "target_angles": {"BOOM": 45.0, "ARM": -20.0}, "duration_ms": 500},
    {"time_ms": 2000, "target_angles": {"SWING": 30.0}, "duration_ms": 500}
  ]
}
```

인게임 Pose Editor에서도 비트맵을 직접 만들 수 있습니다.

## Project Structure

```
src/exca_dance/
├── core/           # 게임 로직 (FK, 스코어링, 비트맵, 리더보드, 키바인딩)
├── rendering/      # ModernGL 렌더러, 3D 굴착기 모델, 뷰포트, 테마
├── ui/             # HUD, 스크린 (메뉴, 곡선택, 결과, 리더보드, 설정)
├── editor/         # 자세 편집기
├── audio/          # 오디오 시스템 (perf_counter 동기화)
└── ros2_bridge/    # ROS2 인터페이스 (가상/실제 모드)
```

## Tests

```bash
pytest tests/ -v
```

## License

MIT
