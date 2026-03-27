# UI — 스크린 프로토콜 및 HUD

> **목적**: exca_dance의 스크린 시스템(duck-typed 프로토콜), 전환 패턴, HUD 오버레이, 새 스크린 추가 절차를 정의한다.
>
> **대상 파일**: `src/exca_dance/ui/`, `src/exca_dance/ui/screens/`, `src/exca_dance/editor/`

---

## 스크린 프로토콜 (duck-typed, 기반 클래스 없음)

```python
class MyScreen:
    def on_enter(self, **kwargs) -> None:
        """전환 시 호출. kwargs로 데이터 수신."""
        ...

    def handle_event(self, event: pygame.event.Event) -> str | tuple[str, dict] | None:
        """이벤트별 호출. 전환 반환 또는 None."""
        ...

    def update(self, dt: float) -> str | tuple[str, dict] | None:
        """프레임별 호출. 전환 반환 또는 None."""
        ...

    def render(self, renderer, text_renderer) -> None:
        """사이드이펙트만. 반환값 없음."""
        ...
```

**전환 반환값:**
- `"screen_name"` — 데이터 없는 전환
- `("screen_name", {"key": value})` — 데이터 포함 전환
- `"quit"` — 메인 루프 종료

---

## 등록된 스크린 (8개)

| 스크린 | 클래스 | ScreenName 상수 |
|--------|--------|-----------------|
| 메인 메뉴 | `MainMenuScreen` | `"main_menu"` |
| 곡 선택 | `SongSelectScreen` | `"song_select"` |
| 게임플레이 | `GameplayScreen` | `"gameplay"` |
| 결과 | `ResultsScreen` | `"results"` |
| 리더보드 | `LeaderboardScreen` | `"leaderboard"` |
| 설정 | `SettingsScreen` | `"settings"` |
| 튜토리얼 | `TutorialScreen` | `"tutorial"` |
| 에디터 | `PoseEditorScreen` | `"editor"` |

---

## 스크린 전환 맵

```
MAIN_MENU
  ├─ "PLAY" → SONG_SELECT
  ├─ "HOW TO PLAY" → TUTORIAL
  ├─ "EDITOR" → EDITOR
  ├─ "LEADERBOARD" → LEADERBOARD
  ├─ "SETTINGS" → SETTINGS
  └─ "quit" → 게임 종료

SONG_SELECT
  ├─ Enter (유효 곡) → GAMEPLAY (beatmap=bm)
  └─ ESC → MAIN_MENU

GAMEPLAY
  ├─ ESC → 일시정지
  ├─ Q (일시정지 중) → MAIN_MENU
  ├─ RESUME → 재개
  ├─ RESTART → GAMEPLAY (같은 비트맵)
  └─ 곡 종료 → RESULTS (scoring, song_title, beatmap)

RESULTS
  ├─ "SAVE SCORE" → LEADERBOARD (mode="enter")
  ├─ "RETRY" → GAMEPLAY (같은 beatmap)
  └─ "MAIN MENU" → MAIN_MENU

LEADERBOARD / SETTINGS / TUTORIAL / EDITOR
  └─ ESC → MAIN_MENU
```

---

## 새 스크린 추가 절차

1. `ui/screens/my_screen.py` 생성 (4-메서드 프로토콜 구현)
2. `core/game_state.py:ScreenName`에 상수 추가
3. `__main__.py:main()`에서 임포트 + 등록:
   ```python
   from exca_dance.ui.screens.my_screen import MyScreen
   state_mgr.register(ScreenName.MY_SCREEN, MyScreen(renderer, text_renderer, ...))
   ```
4. 다른 스크린에서 `return ScreenName.MY_SCREEN` 또는 `return ("my_screen", {...})`

---

## HUD 시스템 (`ui/gameplay_hud.py`)

`GameplayScreen.render()`에서 매 프레임 호출:

| 요소 | 위치 | 설명 |
|------|------|------|
| 점수 | 우상단 | 네온 블루, 8자리 |
| 콤보 | 상단 중앙 | 색상 등급: ≥50=핑크, ≥25=골드, ≥10=초록 |
| 콤보 배율 | 콤보 아래 | "2× COMBO", "3× COMBO", "4× COMBO" |
| 판정 플래시 | 전체화면 | PERFECT/GREAT/GOOD/MISS 색상 |
| 판정 텍스트 | 중앙 | "PERFECT!", "GREAT!" 등 (애니메이션) |
| 진행 바 | 하단 | 경과시간/전체시간 표시 |
| 관절 상태 | 좌측 | 현재 각도 → 목표 각도, 일치율 색상 |
| FPS 카운터 | 좌상단 | F3 토글 (디버그용) |

---

## 스크린 컨벤션

- `on_enter()` always resets `self._selected = 0` for menu screens
- `render()` checks `if text_renderer is None: return` before drawing
- ESC key: pause/resume in gameplay; back-to-menu in all other screens
- Q key: quit from pause overlay only (`LoopState.PAUSED` check required)
- `GameplayScreen`은 `game_loop.tick(dt)` 호출하는 유일한 스크린
