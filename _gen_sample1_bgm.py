"""Generate a 110-second ambient electronic BGM for sample1 beatmap.

Cyberpunk-flavoured chill track at 48 BPM in C minor.
Elements: warm pad chords, sub-bass, soft kick, hi-hat, pentatonic melody.
Output: assets/music/sample1.wav (stereo, 44100 Hz, 16-bit)
"""

from __future__ import annotations

import math
import struct
import wave

import numpy as np

# ── Constants ────────────────────────────────────────────────────────
SR = 44100  # sample rate
BPM = 48.0
BEAT = 60.0 / BPM  # 1.25 s per beat
DURATION = 110.0  # seconds
N = int(SR * DURATION)

TAU = 2.0 * math.pi


# ── Frequencies (C minor) ───────────────────────────────────────────
def freq(note: str) -> float:
    """Return frequency for a note like 'C4', 'Eb3', etc."""
    names = {"C": 0, "D": 2, "Eb": 3, "E": 4, "F": 5, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
    if note[-1].isdigit():
        octave = int(note[-1])
        name = note[:-1]
    else:
        raise ValueError(note)
    midi = 12 * (octave + 1) + names[name]
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


# ── Synthesis helpers ────────────────────────────────────────────────
def sine(f: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(TAU * f * t + phase)


def saw(f: float, t: np.ndarray, harmonics: int = 12) -> np.ndarray:
    """Band-limited sawtooth via additive synthesis."""
    out = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        out += ((-1) ** (k + 1)) * np.sin(TAU * f * k * t) / k
    return out * (2.0 / math.pi)


def envelope_adsr(
    length: int,
    attack: float = 0.05,
    decay: float = 0.1,
    sustain: float = 0.7,
    release: float = 0.3,
) -> np.ndarray:
    """Simple ADSR envelope."""
    a = int(attack * SR)
    d = int(decay * SR)
    r = int(release * SR)
    s = max(length - a - d - r, 0)
    env = np.concatenate(
        [
            np.linspace(0, 1, a, endpoint=False),
            np.linspace(1, sustain, d, endpoint=False),
            np.full(s, sustain),
            np.linspace(sustain, 0, r, endpoint=True),
        ]
    )
    return env[:length]


def lowpass(signal: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    """Simple one-pole low-pass filter."""
    rc = 1.0 / (TAU * cutoff)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    out = np.zeros_like(signal)
    out[0] = signal[0]
    for i in range(1, len(signal)):
        out[i] = out[i - 1] + alpha * (signal[i] - out[i - 1])
    return out


def reverb_simple(
    signal: np.ndarray, delay_ms: float = 80, decay: float = 0.3, taps: int = 4
) -> np.ndarray:
    """Simple comb-filter reverb."""
    out = signal.copy()
    for i in range(1, taps + 1):
        d = int(delay_ms * i * SR / 1000)
        gain = decay**i
        if d < len(out):
            out[d:] += signal[:-d] * gain if d > 0 else signal * gain
    return out


# ── Time array ───────────────────────────────────────────────────────
t = np.linspace(0, DURATION, N, endpoint=False, dtype=np.float64)

# ── Master mix ───────────────────────────────────────────────────────
mix_L = np.zeros(N, dtype=np.float64)
mix_R = np.zeros(N, dtype=np.float64)


# ── 1. PAD CHORDS ───────────────────────────────────────────────────
# Chord progression (4 beats = 5s each): Cm7 → Abmaj7 → Fm7 → Gm7
chords = [
    ["C3", "Eb3", "G3", "Bb3"],  # Cm7
    ["Ab2", "C3", "Eb3", "G3"],  # Abmaj7
    ["F2", "Ab2", "C3", "Eb3"],  # Fm7
    ["G2", "Bb2", "D3", "F3"],  # Gm7
]
chord_beats = 4  # beats per chord
chord_dur = chord_beats * BEAT  # 5 seconds

pad = np.zeros(N, dtype=np.float64)
for ci, chord in enumerate(chords * 6):  # 6 cycles = 120s (covers 110s)
    start_s = ci * chord_dur
    if start_s >= DURATION:
        break
    end_s = min(start_s + chord_dur + 1.0, DURATION)  # +1s overlap for smooth transition
    i0 = int(start_s * SR)
    i1 = min(int(end_s * SR), N)
    seg_t = t[i0:i1] - start_s
    seg_len = i1 - i0

    chord_signal = np.zeros(seg_len, dtype=np.float64)
    for note in chord:
        f = freq(note)
        # Warm pad: fundamental + soft harmonics
        chord_signal += 0.5 * sine(f, seg_t)
        chord_signal += 0.2 * sine(f * 2, seg_t, phase=0.3)
        chord_signal += 0.08 * sine(f * 3, seg_t, phase=0.7)

    # Slow attack/release envelope
    env = envelope_adsr(seg_len, attack=0.8, decay=0.3, sustain=0.6, release=1.0)
    chord_signal *= env * 0.12
    pad[i0:i1] += chord_signal

# Apply gentle filter to pad
print("Generating pad chords...")
# Vectorized lowpass for pad (faster)
rc = 1.0 / (TAU * 400.0)
dt_val = 1.0 / SR
alpha = dt_val / (rc + dt_val)
for i in range(1, N):
    pad[i] = pad[i - 1] + alpha * (pad[i] - pad[i - 1])

mix_L += pad
mix_R += pad


# ── 2. SUB BASS ─────────────────────────────────────────────────────
print("Generating bass...")
bass_roots = [
    freq("C2"),
    freq("Ab1"),
    freq("F2"),
    freq("G2"),
]
bass = np.zeros(N, dtype=np.float64)
for bi in range(int(DURATION / chord_dur) + 1):
    root_f = bass_roots[bi % len(bass_roots)]
    start_s = bi * chord_dur
    if start_s >= DURATION:
        break
    for beat_i in range(chord_beats):
        bs = start_s + beat_i * BEAT
        if bs >= DURATION:
            break
        i0 = int(bs * SR)
        dur_samples = int(BEAT * 0.9 * SR)
        i1 = min(i0 + dur_samples, N)
        seg_len = i1 - i0
        seg_t = t[i0:i1] - bs
        env = envelope_adsr(seg_len, attack=0.02, decay=0.15, sustain=0.5, release=0.3)
        bass[i0:i1] += sine(root_f, seg_t) * env * 0.18

mix_L += bass
mix_R += bass


# ── 3. KICK DRUM ────────────────────────────────────────────────────
print("Generating kick...")
kick = np.zeros(N, dtype=np.float64)
kick_dur = 0.25  # seconds
kick_samples = int(kick_dur * SR)
# Pre-compute kick sample
kick_t = np.linspace(0, kick_dur, kick_samples, endpoint=False)
kick_env = np.exp(-kick_t * 18.0)
kick_pitch = 55.0 + 120.0 * np.exp(-kick_t * 30.0)  # pitch sweep down
kick_wave = np.sin(TAU * np.cumsum(kick_pitch / SR)) * kick_env * 0.22

total_beats = int(DURATION / BEAT)
for b in range(total_beats):
    bs = b * BEAT
    i0 = int(bs * SR)
    i1 = min(i0 + kick_samples, N)
    seg = i1 - i0
    kick[i0:i1] += kick_wave[:seg]

mix_L += kick
mix_R += kick


# ── 4. HI-HAT ───────────────────────────────────────────────────────
print("Generating hi-hat...")
hihat = np.zeros(N, dtype=np.float64)
hh_dur = 0.06
hh_samples = int(hh_dur * SR)
rng = np.random.default_rng(42)
hh_noise = rng.uniform(-1, 1, hh_samples)
hh_env = np.exp(-np.linspace(0, hh_dur, hh_samples) * 50.0)
hh_wave = hh_noise * hh_env * 0.05

# Hi-hat on off-beats (every half beat)
half_beat = BEAT / 2
total_half = int(DURATION / half_beat)
for hb in range(total_half):
    if hb % 2 == 0:
        continue  # skip on-beats (kick handles those)
    hs = hb * half_beat
    i0 = int(hs * SR)
    i1 = min(i0 + hh_samples, N)
    seg = i1 - i0
    hihat[i0:i1] += hh_wave[:seg]

# Slight stereo spread
mix_L += hihat * 0.8
mix_R += hihat * 1.2


# ── 5. MELODY (pentatonic arpeggio) ─────────────────────────────────
print("Generating melody...")
# C minor pentatonic: C, Eb, F, G, Bb
melody_notes = [
    freq("C4"),
    freq("Eb4"),
    freq("F4"),
    freq("G4"),
    freq("Bb4"),
    freq("C5"),
    freq("Bb4"),
    freq("G4"),
    freq("F4"),
    freq("Eb4"),
]
melody = np.zeros(N, dtype=np.float64)
note_dur = BEAT  # one note per beat
note_samples = int(note_dur * SR)

for b in range(total_beats):
    # Play melody only on certain beats for variation
    if b % 8 < 2 or (b % 8 >= 4 and b % 8 < 6):
        continue  # rest on some beats
    bs = b * BEAT
    note_f = melody_notes[b % len(melody_notes)]
    i0 = int(bs * SR)
    i1 = min(i0 + note_samples, N)
    seg_len = i1 - i0
    seg_t = t[i0:i1] - bs

    # Clean sine with slight detune for width
    env = envelope_adsr(seg_len, attack=0.03, decay=0.2, sustain=0.4, release=0.4)
    note_L = sine(note_f, seg_t) * env * 0.08
    note_R = sine(note_f * 1.003, seg_t) * env * 0.08  # slight detune for stereo
    melody[i0:i1] += note_L
    mix_L[i0:i1] += note_L
    mix_R[i0:i1] += note_R


# ── 6. AMBIENT TEXTURE ──────────────────────────────────────────────
print("Generating ambient texture...")
# Slow evolving filtered noise for atmosphere
amb_rng = np.random.default_rng(123)
ambient = amb_rng.uniform(-1, 1, N) * 0.015
# Heavy lowpass for rumble
rc2 = 1.0 / (TAU * 120.0)
alpha2 = (1.0 / SR) / (rc2 + 1.0 / SR)
for i in range(1, N):
    ambient[i] = ambient[i - 1] + alpha2 * (ambient[i] - ambient[i - 1])

mix_L += ambient
mix_R += ambient * 0.9


# ── MASTER PROCESSING ───────────────────────────────────────────────
print("Mastering...")

# Fade in (first 3 seconds)
fade_in = int(3.0 * SR)
fade_in_env = np.linspace(0, 1, fade_in)
mix_L[:fade_in] *= fade_in_env
mix_R[:fade_in] *= fade_in_env

# Fade out (last 5 seconds)
fade_out = int(5.0 * SR)
fade_out_env = np.linspace(1, 0, fade_out)
mix_L[-fade_out:] *= fade_out_env
mix_R[-fade_out:] *= fade_out_env


# Soft clip / limiter
def soft_clip(x: np.ndarray, threshold: float = 0.85) -> np.ndarray:
    """Tanh soft clipper."""
    return np.tanh(x / threshold) * threshold


mix_L = soft_clip(mix_L)
mix_R = soft_clip(mix_R)

# Normalize to 85% headroom
peak = max(np.max(np.abs(mix_L)), np.max(np.abs(mix_R)))
if peak > 0:
    gain = 0.85 / peak
    mix_L *= gain
    mix_R *= gain

# Convert to 16-bit interleaved stereo
print("Writing WAV...")
stereo = np.empty(N * 2, dtype=np.float64)
stereo[0::2] = mix_L
stereo[1::2] = mix_R
pcm = (stereo * 32767).astype(np.int16)

with wave.open("assets/music/sample1.wav", "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(pcm.tobytes())

print(f"Done! assets/music/sample1.wav — {DURATION:.0f}s, stereo, {SR}Hz, 16-bit")
