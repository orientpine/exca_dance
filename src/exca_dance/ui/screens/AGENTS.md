# AGENTS.md — ui/screens/

Duck-typed screen implementations. No base class — all screens implement the same 4-method protocol.

---

## STRUCTURE

```
screens/
├── main_menu.py        # MainMenuScreen — 5 items: PLAY, EDITOR, LEADERBOARD, SETTINGS, QUIT
├── song_select.py      # SongSelectScreen — loads beatmaps from assets/beatmaps/
├── gameplay_screen.py  # GameplayScreen — drives GameLoop, HUD, visual cues, all viewports
├── results.py          # ResultsScreen — grade, score, judgment breakdown; RETRY/SAVE/MENU
├── leaderboard_screen.py  # LeaderboardScreen — view mode + initials entry mode
└── settings_screen.py  # SettingsScreen — key rebinding, audio volume
```

---

## SCREEN PROTOCOL

```python
class MyScreen:
    def on_enter(self, **kwargs) -> None:
        # Called on transition IN. Extract kwargs here.
        # e.g. on_enter(beatmap=bm, scoring=s)
        ...

    def handle_event(self, event: pygame.event.Event) -> TransitionResult | None:
        # Return transition or None. Called per pygame event.
        ...

    def update(self, dt: float) -> TransitionResult | None:
        # Return transition or None. Called once per frame.
        ...

    def render(self, renderer, text_renderer) -> None:
        # Side-effects only. No return value.
        ...
```

---

## TRANSITION PATTERNS

```python
# Bare string — no data
return ScreenName.MAIN_MENU          # → on_enter() called with no kwargs
return "quit"                        # → main loop exits

# 2-tuple — with data
return (ScreenName.RESULTS, {
    "scoring": self._scoring,
    "song_title": title,
    "beatmap": self._beatmap,        # pass beatmap for RETRY
})

return (ScreenName.GAMEPLAY, {"beatmap": beatmap})   # RETRY direct restart
```

---

## SCREEN FLOW

```
MAIN_MENU → SONG_SELECT → GAMEPLAY → RESULTS → LEADERBOARD (enter mode)
                                   ↘ RETRY → GAMEPLAY (same beatmap, direct)
                                   ↘ MAIN MENU
MAIN_MENU → EDITOR
MAIN_MENU → SETTINGS
MAIN_MENU → LEADERBOARD (view mode)
```

---

## ADDING A NEW SCREEN

1. Create `ui/screens/my_screen.py` implementing the 4-method protocol
2. Add `ScreenName.MY_SCREEN = "my_screen"` to `core/game_state.py:ScreenName`
3. Construct + register in `__main__.py:main()`:
   ```python
   my_screen = MyScreen(renderer, text_renderer)
   state_mgr.register(ScreenName.MY_SCREEN, my_screen)
   ```
4. Return `ScreenName.MY_SCREEN` from another screen's `handle_event` or `update`

---

## GAMEPLAY SCREEN SPECIFICS

`GameplayScreen` is the most complex screen:
- Calls `game_loop.tick(dt)` every frame (only screen that does this)
- Manages ghost rendering across all 3 viewports
- `_on_song_end(scoring)` callback → sets `_result_scoring` → `update()` detects and transitions
- Passes `beatmap` to results for RETRY support

---

## CONVENTIONS

- `on_enter()` always resets `self._selected = 0` for menu screens
- `render()` checks `if text_renderer is None: return` before drawing
- ESC key: pause/resume in gameplay; back-to-menu in all other screens
- Q key: quit from pause overlay only (`LoopState.PAUSED` check required)
