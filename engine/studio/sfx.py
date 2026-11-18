"""Procedural, original sound effects and ambience (no samples => no licensing questions).

Every effect is synthesised from noise/oscillators with a seed, so it is unique and reproducible.
Shots carry `sfx` tags (e.g. ["whoosh", "impact"]) and an `ambience` per scene; the timeline places
each effect at the moment the visual action happens (shot start + offset).
"""
from __future__ import annotations
import numpy as np
import soundfile as sf
from pathlib import Path

SR = 44100


def _t(d): return np.arange(int(SR * d)) / SR


def _env(n, a=0.005, r=0.3):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))


def _noise(n, rng): return rng.standard_normal(n)


def _lowpass(x, cutoff):
    # one-pole low-pass; cutoff may be an array (sweeps)
    a = np.exp(-2 * np.pi * np.asarray(cutoff) / SR) * np.ones_like(x)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc; y[i] = acc
    return y


def whoosh(rng, d=0.7):
    n = int(SR * d); t = np.arange(n) / SR
    sweep = 300 + 5000 * np.sin(np.pi * t / d) ** 2
    x = _lowpass(_noise(n, rng), sweep)
    return 1.6 * x * np.sin(np.pi * t / d) ** 2


def impact(rng, d=1.2):
    t = _t(d)
    boom = np.sin(2 * np.pi * (55 * np.exp(-t * 3)) * t) * np.exp(-t * 4)
    crack = _noise(len(t), rng) * np.exp(-t * 40)
    return 0.9 * boom + 0.5 * crack


def electricity(rng, d=1.0):
    t = _t(d)
    buzz = np.sign(np.sin(2 * np.pi * 110 * t)) * 0.3
    crackle = _noise(len(t), rng) * (rng.random(len(t)) < 0.02) * 2.0
    return (buzz + crackle) * np.minimum(1, t / 0.05) * np.minimum(1, (d - t) / 0.1)


def time_freeze(rng, d=1.6):
    """Reverse-swell into a glassy high ring: the 'world stops' cue."""
    t = _t(d)
    swell = _lowpass(_noise(len(t), rng), 200 + 6000 * (t / d) ** 2) * (t / d) ** 3
    ring = sum(np.sin(2 * np.pi * f * t) for f in (1760, 2637, 3520)) * np.exp(-np.maximum(0, t - d * 0.7) * 3)
    ring *= (t > d * 0.7)
    return 1.2 * swell + 0.15 * ring


def clock_tick(rng, d=2.0, bpm=60):
    out = np.zeros(int(SR * d))
    for k in range(int(d * bpm / 60) + 1):
        i = int(k * 60 / bpm * SR)
        tick = np.sin(2 * np.pi * (2400 if k % 2 else 1800) * _t(0.03)) * np.exp(-_t(0.03) * 150)
        out[i:i + len(tick)] += tick[: len(out) - i] * 0.6
    return out


def footsteps(rng, d=2.0, rate=2.2):
    out = np.zeros(int(SR * d))
    for k in range(int(d * rate)):
        i = int(k / rate * SR)
        st = _lowpass(_noise(int(0.12 * SR), rng), 900) * np.exp(-_t(0.12) * 30) * 3
        out[i:i + len(st)] += st[: len(out) - i]
    return out


def riser(rng, d=2.0):
    t = _t(d)
    return np.sin(2 * np.pi * (200 + 800 * (t / d) ** 2) * t) * (t / d) ** 2 * 0.4 + \
        _lowpass(_noise(len(t), rng), 500 + 4000 * t / d) * (t / d) ** 2 * 0.8


def heartbeat(rng, d=2.0, bpm=70):
    out = np.zeros(int(SR * d))
    for k in range(int(d * bpm / 60) + 1):
        for off, amp in ((0, 1.0), (0.18, 0.7)):
            i = int((k * 60 / bpm + off) * SR)
            b = np.sin(2 * np.pi * 50 * _t(0.15)) * np.exp(-_t(0.15) * 25) * amp
            out[i:i + len(b)] += b[: len(out) - i]
    return out


# ambience beds (looped by the mixer to scene length)
def amb_wind(rng, d=6.0):
    n = int(SR * d); lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.15 * np.arange(n) / SR)
    return _lowpass(_noise(n, rng), 400) * lfo * 1.5


def amb_rain(rng, d=6.0):
    n = int(SR * d)
    return _lowpass(_noise(n, rng), 3000) * 0.35 + (rng.random(n) < 0.002) * _noise(n, rng) * 0.6


def amb_city(rng, d=6.0):
    n = int(SR * d); t = np.arange(n) / SR
    return _lowpass(_noise(n, rng), 250) * 1.2 + 0.05 * np.sin(2 * np.pi * 60 * t)


def amb_forest(rng, d=6.0):
    n = int(SR * d); out = _lowpass(_noise(n, rng), 600) * 0.4
    for _ in range(int(d * 1.2)):
        i = rng.integers(0, n - SR // 4); f = rng.uniform(2500, 4500)
        ch = np.sin(2 * np.pi * (f + 400 * np.sin(2 * np.pi * 18 * _t(0.2))) * _t(0.2)) * np.hanning(int(0.2 * SR))
        out[i:i + len(ch)] += ch * 0.25
    return out


EFFECTS = {"whoosh": whoosh, "impact": impact, "electricity": electricity, "time_freeze": time_freeze,
           "clock": clock_tick, "footsteps": footsteps, "riser": riser, "heartbeat": heartbeat}
AMBIENCE = {"wind": amb_wind, "rain": amb_rain, "city": amb_city, "forest": amb_forest}
GAIN = {"whoosh": 0.5, "impact": 0.8, "electricity": 0.35, "time_freeze": 0.6, "clock": 0.5,
        "footsteps": 0.4, "riser": 0.45, "heartbeat": 0.6}


def render_track(events: list[dict], ambience: list[dict], total: float, out: Path, seed: int = 11) -> Path:
    """events: [{"t": seconds, "name": "impact"}]; ambience: [{"start","end","name"}]. Writes a mono wav."""
    rng = np.random.default_rng(seed)
    mix = np.zeros(int(SR * (total + 2)))
    for a in ambience:
        fn = AMBIENCE.get(a["name"])
        if not fn:
            continue
        i0, i1 = int(a["start"] * SR), int(a["end"] * SR)
        bed = fn(rng, 6.0); reps = int(np.ceil((i1 - i0) / len(bed))) + 1
        seg = np.tile(bed, reps)[: i1 - i0]
        fade = min(len(seg) // 2, int(0.6 * SR))
        if fade:
            seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade)
        mix[i0:i1] += 0.12 * seg / (np.abs(seg).max() + 1e-9)
    for e in events:
        fn = EFFECTS.get(e["name"])
        if not fn:
            continue
        sig = fn(rng); sig = sig / (np.abs(sig).max() + 1e-9) * GAIN[e["name"]]
        i = max(0, int(e["t"] * SR))
        mix[i:i + len(sig)] += sig[: len(mix) - i]
    mix = mix[: int(total * SR)]
    mix /= max(1.0, np.abs(mix).max() / 0.9)
    sf.write(str(out), mix.astype(np.float32), SR)
    return out
