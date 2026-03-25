# AGENTS.md — audio/

AudioSystem with precise timing via `time.perf_counter()`. Critical constraints apply here.

---

## STRUCTURE

```
audio/
├── audio_system.py   # AudioSystem — BGM playback, SFX, perf_counter sync
└── __init__.py       # Empty
```

---

## CRITICAL CONSTRAINTS

```python
# FORBIDDEN — drifts ~500ms/300s with MP3/OGG
pygame.mixer.music.get_pos()
pygame.mixer.music.get_position()

# CORRECT — always use perf_counter
elapsed_ms = (time.perf_counter() - self._start_time - self._accumulated_pause) * 1000.0
```

**Never use any pygame position query for timing.** Use `AudioSystem.get_position_ms()` which is perf_counter-based.

---

## KEY METHODS

```python
audio.load_music(path: str) -> None      # OGG or WAV only
audio.play(song_duration_ms=None) -> None  # starts playback + resets perf_counter
audio.pause() / audio.resume()
audio.stop()                             # sets _is_playing = False
audio.get_position_ms() -> float         # perf_counter-based, 0 if not playing
audio.is_playing() -> bool               # checks get_busy() in real mode; duration timer in silent mode
```

---

## END-OF-SONG DETECTION

`is_playing()` logic:
1. If `_is_playing == False` or paused → `False`
2. Silent mode + `song_duration_ms` set → compare elapsed vs duration
3. Real audio → `pygame.mixer.music.get_busy()` (syncs `_is_playing` flag on False)

`GameLoop._check_song_end()` uses two conditions (either triggers FINISHED):
- `not audio.is_playing()` — primary
- 3000ms grace period after all events consumed — fallback

---

## SILENT MODE

Activated automatically when `pygame.mixer.init()` fails (no audio device). All methods are no-ops except timing. `get_position_ms()` still works via perf_counter. Pass `song_duration_ms` to `play()` for correct end-of-song detection in silent mode.

---

## SUPPORTED FORMATS

- Music (BGM): `.ogg`, `.wav`
- SFX: `.wav` only
