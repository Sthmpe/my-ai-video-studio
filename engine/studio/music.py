"""Original procedural background music (no samples, no licensing issues).

Synthesises a bouncy marimba/pluck lead + walking bass + soft pad in a pentatonic scale.
Every track is generated from a seed, so output is unique, original and royalty-free.
"""
from __future__ import annotations
import numpy as np
import soundfile as sf
from pathlib import Path

SR = 44100
MOODS = {  # bpm, root midi, scale
    "playful": (112, 60, [0, 2, 4, 7, 9]),
    "wonder": (84, 57, [0, 2, 4, 7, 9]),
    "tense": (100, 55, [0, 3, 5, 7, 10]),
    "anime_edit": (120, 50, [0, 3, 5, 7, 10]),
}


def _hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def _pluck(freq, dur, vel=0.5):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t * 7.0)
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t * 18) \
        + 0.15 * np.sin(2 * np.pi * freq * 2 * t)
    return vel * env * tone


def _pad(freq, dur, vel=0.12):
    t = np.arange(int(SR * dur)) / SR
    env = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.6)
    return vel * env * (np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 1.003 * t))


def compose(seconds: float, out: Path, mood: str = "playful", seed: int = 7) -> Path:
    bpm, root, scale = MOODS.get(mood, MOODS["playful"])
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    n = int((seconds + 2) * SR)
    mix = np.zeros(n + SR * 3, dtype=np.float64)

    def put(sig, at):
        i = int(at * SR)
        mix[i:i + len(sig)] += sig[: len(mix) - i]

    notes = [root + 12 + s for s in scale] + [root + 24 + s for s in scale[:3]]
    idx = 2
    t, bar = 0.0, 0
    chords = [0, 5 % len(scale), 3, 4]
    while t < seconds + 1:
        deg = chords[bar % 4]
        base = root - 12 + scale[deg % len(scale)]
        for b in range(4):  # bass: root / fifth
            put(_pluck(_hz(base + (7 if b % 2 else 0)), beat * 0.9, 0.35), t + b * beat)
            if mood == "anime_edit":
                drum_t = np.arange(int(SR * 0.22)) / SR
                kick = np.sin(2 * np.pi * (48 * drum_t + 3 * (1 - np.exp(-32 * drum_t))))
                put(0.7 * kick * np.exp(-22 * drum_t), t + b * beat)
                if b % 2:
                    snare = rng.standard_normal(len(drum_t)) * np.exp(-36 * drum_t)
                    put(0.23 * snare, t + b * beat)
        put(_pad(_hz(root + scale[deg % len(scale)]), beat * 4.2), t)
        put(_pad(_hz(root + scale[(deg + 2) % len(scale)]), beat * 4.2, 0.08), t)
        for e in range(8):  # eighth-note melody with rests
            if rng.random() < 0.25:
                continue
            idx = int(np.clip(idx + rng.choice([-2, -1, -1, 1, 1, 2]), 0, len(notes) - 1))
            put(_pluck(_hz(notes[idx]), beat, 0.32), t + e * beat / 2)
        t += 4 * beat
        bar += 1
    mix = mix[: int(seconds * SR)]
    # simple echo for space
    d = int(0.28 * SR)
    mix[d:] += 0.25 * mix[:-d]
    fade = int(1.5 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix[:int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR))
    mix /= max(1e-9, np.abs(mix).max()) / 0.8
    sf.write(str(out), mix.astype(np.float32), SR)
    return out
