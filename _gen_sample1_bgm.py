"""Generate a 110-second epic space-adventure BGM for sample1 beatmap.

Hopeful, bright, exciting — a hero's journey to save Earth.
D major, 48 BPM. Builds from quiet starfield to triumphant climax.

Structure:
  0-20s   "Departure"  — gentle arpeggio + shimmer, floating in space
  20-45s  "Ascent"     — pads enter, bass joins, momentum builds
  45-75s  "Journey"    — full arrangement, driving rhythm, soaring melody
  75-95s  "Triumph"    — maximum energy, octave-up melody, epic
  95-110s "Beyond"     — resolution, gentle fade to stars

Output: assets/music/sample1.wav (stereo, 44100 Hz, 16-bit)
"""

from __future__ import annotations

import math
import wave

import numpy as np

# ── Constants ────────────────────────────────────────────────────────
SR = 44100
BPM = 48.0
BEAT = 60.0 / BPM  # 1.25s
DURATION = 110.0
N = int(SR * DURATION)
TAU = 2.0 * math.pi

# ── Note frequencies ─────────────────────────────────────────────────
_NOTE_NAMES = {
    "C": 0,
    "C#": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}


def freq(note: str) -> float:
    octave = int(note[-1])
    name = note[:-1]
    midi = 12 * (octave + 1) + _NOTE_NAMES[name]
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


# ── Synthesis primitives ─────────────────────────────────────────────
def sine(f: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(TAU * f * t + phase)


def tri(f: float, t: np.ndarray) -> np.ndarray:
    """Band-limited triangle wave."""
    out = np.zeros_like(t)
    for k in range(8):
        n = 2 * k + 1
        out += ((-1) ** k) * np.sin(TAU * f * n * t) / (n * n)
    return out * (8.0 / (math.pi * math.pi))


def adsr(length: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    ai = int(a * SR)
    di = int(d * SR)
    ri = int(r * SR)
    si = max(length - ai - di - ri, 0)
    env = np.concatenate(
        [
            np.linspace(0, 1, max(ai, 1), endpoint=False),
            np.linspace(1, s, max(di, 1), endpoint=False),
            np.full(si, s),
            np.linspace(s, 0, max(ri, 1)),
        ]
    )
    return env[:length]


def intensity(time_s: float) -> float:
    """Dynamic intensity curve: 0→1 over the song structure."""
    if time_s < 20:
        return 0.15 + 0.15 * (time_s / 20.0)
    elif time_s < 45:
        return 0.3 + 0.35 * ((time_s - 20) / 25.0)
    elif time_s < 75:
        return 0.65 + 0.25 * ((time_s - 45) / 30.0)
    elif time_s < 95:
        return 0.9 + 0.1 * math.sin((time_s - 75) * 0.3)
    else:
        return max(0.9 * (1.0 - (time_s - 95) / 15.0), 0.0)


# ── Time & mix ───────────────────────────────────────────────────────
t = np.linspace(0, DURATION, N, endpoint=False, dtype=np.float64)
mix_L = np.zeros(N, dtype=np.float64)
mix_R = np.zeros(N, dtype=np.float64)

# ── Chord progression (D major: I → V → vi → IV) ────────────────────
# Wide cinematic voicings with 7ths
chords = [
    # Dmaj9: bright, open, hopeful
    ["D2", "A2", "D3", "F#3", "A3", "E4"],
    # A/C# (first inversion): soaring lift
    ["A1", "C#3", "E3", "A3", "C#4"],
    # Bm7: gentle emotion, longing
    ["B1", "F#2", "B2", "D3", "A3", "F#4"],
    # Gmaj7: warmth, resolution
    ["G1", "D2", "G2", "B2", "D3", "F#3"],
]
CHORD_BEATS = 4
CHORD_DUR = CHORD_BEATS * BEAT  # 5 seconds each

# ═══════════════════════════════════════════════════════════════════════
# 1. SHIMMERING STAR FIELD (full duration — high sine clusters)
# ═══════════════════════════════════════════════════════════════════════
print("[1/8] Star shimmer...")
shimmer = np.zeros(N, dtype=np.float64)
shimmer_freqs = [freq("D6"), freq("F#6"), freq("A6"), freq("E6"), freq("B5")]
for i, sf in enumerate(shimmer_freqs):
    phase = i * 1.3
    amp_mod = 0.008 * (0.4 + 0.6 * np.abs(np.sin(t * (0.15 + i * 0.07) + phase)))
    shimmer += sine(sf, t, phase) * amp_mod

# Stereo spread via phase offset
shimmer_R = np.zeros(N, dtype=np.float64)
for i, sf in enumerate(shimmer_freqs):
    phase = i * 1.3 + 0.5
    amp_mod = 0.008 * (0.4 + 0.6 * np.abs(np.sin(t * (0.15 + i * 0.07) + phase + 0.8)))
    shimmer_R += sine(sf, t, phase) * amp_mod

mix_L += shimmer
mix_R += shimmer_R

# ═══════════════════════════════════════════════════════════════════════
# 2. ARPEGGIATOR (sense of motion, journey forward)
# ═══════════════════════════════════════════════════════════════════════
print("[2/8] Arpeggiator...")
arp_patterns = {
    0: [freq("D4"), freq("F#4"), freq("A4"), freq("D5"), freq("A4"), freq("F#4")],
    1: [freq("C#4"), freq("E4"), freq("A4"), freq("C#5"), freq("A4"), freq("E4")],
    2: [freq("B3"), freq("D4"), freq("F#4"), freq("B4"), freq("F#4"), freq("D4")],
    3: [freq("G3"), freq("B3"), freq("D4"), freq("G4"), freq("D4"), freq("B3")],
}
# Each beat subdivided into 6 arp notes (sextuplets)
arp_note_dur = BEAT / 6
arp_samples = int(arp_note_dur * SR)

for ci in range(int(DURATION / CHORD_DUR) + 1):
    chord_idx = ci % 4
    pattern = arp_patterns[chord_idx]
    chord_start = ci * CHORD_DUR
    if chord_start >= DURATION:
        break

    for beat in range(CHORD_BEATS):
        beat_start = chord_start + beat * BEAT
        for ni, nf in enumerate(pattern):
            ns = beat_start + ni * arp_note_dur
            if ns >= DURATION:
                break
            i0 = int(ns * SR)
            i1 = min(i0 + arp_samples, N)
            sl = i1 - i0
            if sl <= 0:
                continue
            seg_t = t[i0:i1] - ns
            env = adsr(sl, a=0.01, d=0.05, s=0.3, r=0.08)
            # Dynamic volume based on song intensity
            vol = intensity(ns) * 0.12
            note_sig = sine(nf, seg_t) * env * vol
            # Slight stereo alternation
            if ni % 2 == 0:
                mix_L[i0:i1] += note_sig * 1.1
                mix_R[i0:i1] += note_sig * 0.7
            else:
                mix_L[i0:i1] += note_sig * 0.7
                mix_R[i0:i1] += note_sig * 1.1

# ═══════════════════════════════════════════════════════════════════════
# 3. BRIGHT PAD CHORDS (enter at ~15s, build warmth)
# ═══════════════════════════════════════════════════════════════════════
print("[3/8] Pad chords...")
for ci in range(int(DURATION / CHORD_DUR) + 1):
    chord_notes = chords[ci % 4]
    start_s = ci * CHORD_DUR
    if start_s >= DURATION:
        break
    end_s = min(start_s + CHORD_DUR + 0.8, DURATION)
    i0 = int(start_s * SR)
    i1 = min(int(end_s * SR), N)
    sl = i1 - i0
    seg_t = t[i0:i1] - start_s

    pad_sig = np.zeros(sl, dtype=np.float64)
    for note in chord_notes:
        f = freq(note)
        # Rich warm pad: fundamental + octave + soft 5th harmonic
        pad_sig += 0.35 * sine(f, seg_t)
        pad_sig += 0.18 * sine(f * 2, seg_t, phase=0.2)
        pad_sig += 0.06 * sine(f * 3, seg_t, phase=0.5)
        pad_sig += 0.03 * tri(f, seg_t)  # adds warmth

    env = adsr(sl, a=1.2, d=0.5, s=0.55, r=0.8)
    # Pad enters gradually from ~15s
    vol_mult = max(0.0, min(1.0, (start_s - 12.0) / 8.0)) if start_s < 20 else 1.0
    pad_sig *= env * 0.07 * intensity(start_s) * vol_mult

    mix_L[i0:i1] += pad_sig
    mix_R[i0:i1] += pad_sig

# ═══════════════════════════════════════════════════════════════════════
# 4. EPIC BASS (octave pulses, enters at ~18s)
# ═══════════════════════════════════════════════════════════════════════
print("[4/8] Bass...")
bass_roots = [freq("D2"), freq("A1"), freq("B1"), freq("G1")]
for ci in range(int(DURATION / CHORD_DUR) + 1):
    root_f = bass_roots[ci % 4]
    start_s = ci * CHORD_DUR
    if start_s < 18 or start_s >= DURATION:
        if start_s >= DURATION:
            break
        continue

    for beat_i in range(CHORD_BEATS):
        bs = start_s + beat_i * BEAT
        if bs >= DURATION:
            break
        i0 = int(bs * SR)
        dur_s = BEAT * 0.85
        i1 = min(i0 + int(dur_s * SR), N)
        sl = i1 - i0
        if sl <= 0:
            continue
        seg_t = t[i0:i1] - bs

        env = adsr(sl, a=0.02, d=0.1, s=0.6, r=0.25)
        # Warm bass with sub + body
        bass_sig = 0.5 * sine(root_f, seg_t)
        bass_sig += 0.3 * sine(root_f * 2, seg_t)  # octave up for presence
        bass_sig += 0.1 * tri(root_f, seg_t)  # adds grit
        bass_sig *= env * 0.16 * intensity(bs)

        # Bass on beat 0 and 2 gets extra punch (octave jump)
        if beat_i in (0, 2):
            bass_sig *= 1.3

        mix_L[i0:i1] += bass_sig
        mix_R[i0:i1] += bass_sig

# ═══════════════════════════════════════════════════════════════════════
# 5. CINEMATIC KICK (enters at ~20s, builds drive)
# ═══════════════════════════════════════════════════════════════════════
print("[5/8] Kick drum...")
kick_dur_s = 0.3
kick_samples = int(kick_dur_s * SR)
kick_t_arr = np.linspace(0, kick_dur_s, kick_samples, endpoint=False)
kick_env = np.exp(-kick_t_arr * 14.0)
# Cinematic boom: deeper pitch sweep
kick_pitch = 50.0 + 150.0 * np.exp(-kick_t_arr * 25.0)
kick_wave = np.sin(TAU * np.cumsum(kick_pitch / SR)) * kick_env * 0.25
# Add transient click for definition
click = np.exp(-kick_t_arr * 80.0) * 0.08
kick_wave[: len(click)] += click

total_beats = int(DURATION / BEAT)
for b in range(total_beats):
    bs = b * BEAT
    if bs < 20:
        continue
    i0 = int(bs * SR)
    i1 = min(i0 + kick_samples, N)
    seg = i1 - i0
    vol = intensity(bs)
    mix_L[i0:i1] += kick_wave[:seg] * vol
    mix_R[i0:i1] += kick_wave[:seg] * vol

# ═══════════════════════════════════════════════════════════════════════
# 6. SNARE / CLAP (off-beats, enters at ~35s for drive)
# ═══════════════════════════════════════════════════════════════════════
print("[6/8] Snare hits...")
snare_dur_s = 0.15
snare_samples = int(snare_dur_s * SR)
rng = np.random.default_rng(77)
snare_noise = rng.uniform(-1, 1, snare_samples)
snare_env = np.exp(-np.linspace(0, snare_dur_s, snare_samples) * 30.0)
# Tuned snare body + noise
snare_t_arr = np.linspace(0, snare_dur_s, snare_samples, endpoint=False)
snare_body = np.sin(TAU * 180 * snare_t_arr) * np.exp(-snare_t_arr * 40.0)
snare_wave = snare_noise * snare_env * 0.06 + snare_body * 0.04

for b in range(total_beats):
    bs = b * BEAT
    if bs < 35:
        continue
    # Snare on beats 1 and 3 (off-beats in a 4-beat group)
    beat_in_bar = b % 4
    if beat_in_bar not in (1, 3):
        continue
    i0 = int(bs * SR)
    i1 = min(i0 + snare_samples, N)
    seg = i1 - i0
    vol = intensity(bs)
    mix_L[i0:i1] += snare_wave[:seg] * vol * 0.9
    mix_R[i0:i1] += snare_wave[:seg] * vol * 1.1

# ═══════════════════════════════════════════════════════════════════════
# 7. SOARING MELODY (enters at ~40s, D major pentatonic)
# ═══════════════════════════════════════════════════════════════════════
print("[7/8] Melody...")
# D major pentatonic: D E F# A B — heroic, uplifting
melody_sequence = [
    # Phase 1: simple ascending motif (40-60s)
    "D4",
    "E4",
    "F#4",
    "A4",
    "B4",
    "A4",
    "F#4",
    "E4",
    "D4",
    "F#4",
    "A4",
    "B4",
    "D5",
    "B4",
    "A4",
    "F#4",
    # Phase 2: soaring higher (60-80s)
    "A4",
    "B4",
    "D5",
    "E5",
    "F#5",
    "E5",
    "D5",
    "B4",
    "F#4",
    "A4",
    "D5",
    "F#5",
    "A5",
    "F#5",
    "D5",
    "A4",
    # Phase 3: triumphant peak (80-95s)
    "D5",
    "F#5",
    "A5",
    "B5",
    "A5",
    "F#5",
    "D5",
    "B4",
    "A4",
    "D5",
    "F#5",
    "A5",
    "D6",
    "A5",
    "F#5",
    "D5",
]

mel_note_dur = BEAT * 0.9
mel_samples = int(mel_note_dur * SR)

melody_start_beat = int(40 / BEAT)  # beat ~32
for mi in range(len(melody_sequence)):
    b = melody_start_beat + mi
    bs = b * BEAT
    if bs >= 100:  # stop melody before fade
        break

    note_name = melody_sequence[mi % len(melody_sequence)]
    nf = freq(note_name)
    i0 = int(bs * SR)
    i1 = min(i0 + mel_samples, N)
    sl = i1 - i0
    if sl <= 0:
        continue
    seg_t = t[i0:i1] - bs

    env = adsr(sl, a=0.04, d=0.15, s=0.5, r=0.35)
    vol = intensity(bs) * 0.10

    # Bright bell-like tone: sine + octave + slight 5th
    mel_sig = 0.6 * sine(nf, seg_t)
    mel_sig += 0.25 * sine(nf * 2, seg_t, phase=0.1)
    mel_sig += 0.08 * sine(nf * 3, seg_t, phase=0.3)
    mel_sig += 0.04 * sine(nf * 1.498, seg_t)  # perfect 5th color

    mel_sig *= env * vol

    # Stereo: slight detune for width
    mel_R = mel_sig * 0.95
    mel_L = mel_sig * 1.05
    # Add very subtle delay to right channel (10ms) for space
    delay_samples = int(0.010 * SR)
    mix_L[i0:i1] += mel_L
    r_start = min(i0 + delay_samples, N)
    r_end = min(i1 + delay_samples, N)
    r_len = r_end - r_start
    mix_R[r_start:r_end] += mel_R[:r_len]

# ═══════════════════════════════════════════════════════════════════════
# 8. RISING TENSION SWEEPS (at section transitions)
# ═══════════════════════════════════════════════════════════════════════
print("[8/8] Tension risers...")
riser_times = [17.0, 42.0, 72.0]  # just before each new section
for rt in riser_times:
    riser_dur = 3.0
    i0 = max(int((rt - riser_dur) * SR), 0)
    i1 = min(int(rt * SR), N)
    sl = i1 - i0
    if sl <= 0:
        continue
    seg_t = np.linspace(0, riser_dur, sl, endpoint=False)

    # Rising filtered noise
    noise = rng.uniform(-1, 1, sl) * 0.04
    # Frequency sweep via amplitude envelope
    rise_env = seg_t / riser_dur  # 0 → 1
    rise_env = rise_env**2  # exponential rise
    # Tone sweep from low to high
    sweep_f = 200 + 2000 * rise_env
    sweep = np.sin(TAU * np.cumsum(sweep_f / SR)) * rise_env * 0.03

    riser_sig = (noise * rise_env + sweep) * 0.6
    mix_L[i0:i1] += riser_sig
    mix_R[i0:i1] += riser_sig * 0.9


# ═══════════════════════════════════════════════════════════════════════
# MASTER PROCESSING
# ═══════════════════════════════════════════════════════════════════════
print("Mastering...")

# Apply intensity curve to overall mix
intensity_curve = np.array([intensity(s) for s in t], dtype=np.float64)
# Smooth it
for i in range(1, N):
    intensity_curve[i] = intensity_curve[i - 1] * 0.9999 + intensity_curve[i] * 0.0001
mix_L *= 0.5 + 0.5 * intensity_curve
mix_R *= 0.5 + 0.5 * intensity_curve

# Fade in (first 4 seconds — gentle emergence)
fade_in = int(4.0 * SR)
mix_L[:fade_in] *= np.linspace(0, 1, fade_in)
mix_R[:fade_in] *= np.linspace(0, 1, fade_in)

# Fade out (last 8 seconds — stars fading away)
fade_out = int(8.0 * SR)
fo_env = np.linspace(1, 0, fade_out) ** 1.5  # gentle curve
mix_L[-fade_out:] *= fo_env
mix_R[-fade_out:] *= fo_env


# Soft clip
def soft_clip(x: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    return np.tanh(x / threshold) * threshold


mix_L = soft_clip(mix_L)
mix_R = soft_clip(mix_R)

# Normalize to 88% headroom
peak = max(np.max(np.abs(mix_L)), np.max(np.abs(mix_R)))
if peak > 0:
    mix_L *= 0.88 / peak
    mix_R *= 0.88 / peak

# Write WAV
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
print("Theme: Epic Space Adventure in D major")
print("Sections: Departure → Ascent → Journey → Triumph → Beyond")
