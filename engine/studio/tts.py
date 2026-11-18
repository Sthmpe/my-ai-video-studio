"""Narration with Kokoro-82M (Apache-2.0) via ONNX Runtime — fully local, CPU."""
from __future__ import annotations
import threading
import numpy as np
import soundfile as sf
from pathlib import Path
from .paths import MODELS

SR = 24000
_lock = threading.Lock()
_sess = None
_vocab = None


def _load():
    global _sess, _vocab
    with _lock:
        if _sess is None:
            import onnxruntime as ort
            _sess = ort.InferenceSession(str(MODELS / "kokoro/onnx/model_quantized.onnx"),
                                         providers=["CPUExecutionProvider"])
            import json
            tok = json.load(open(MODELS / "kokoro/tokenizer.json"))
            _vocab = tok["model"]["vocab"]
    return _sess, _vocab


_be = {}


def _phonemize(text: str, lang: str) -> str:
    # espeakng-loader ships libespeak-ng + data in a wheel, so no apt/root needed.
    import espeakng_loader
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    if lang not in _be:
        from phonemizer.backend import EspeakBackend
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        _be[lang] = EspeakBackend(lang, preserve_punctuation=True, with_stress=True)
    return _be[lang].phonemize([text])[0].strip()


_ja = {}


def _phonemize_ja(text: str) -> str:
    # misaki's Japanese G2P (pyopenjtalk + fugashi/unidic-lite): the phoneme set Kokoro's JA voices were trained on.
    if "g" not in _ja:
        from misaki import ja
        _ja["g"] = ja.JAG2P()
    return _ja["g"](text)[0]


LANG_VOICES = {"en": ["af_heart", "af_bella", "bf_emma", "am_michael", "am_puck", "bm_george"],
               "ja": ["jf_alpha", "jf_nezumi", "jm_kumo"]}


def lang_of_voice(voice: str) -> str:
    return "ja" if voice.startswith("j") else "en"


def synth(text: str, out: Path, voice: str = "af_heart", speed: float = 1.0, lang: str | None = None) -> float:
    """Writes a wav, returns duration in seconds. Language follows the voice (j* voices => Japanese)."""
    sess, vocab = _load()
    lang = lang or lang_of_voice(voice)
    if lang.startswith("ja"):
        ph = _phonemize_ja(text)
    else:
        ph = _phonemize(text, "en-gb" if voice.startswith("b") else "en-us")
    ids = [vocab[c] for c in ph if c in vocab][:500]
    voices = np.fromfile(MODELS / f"kokoro/voices/{voice}.bin", dtype=np.float32).reshape(-1, 1, 256)
    style = voices[min(len(ids), len(voices) - 1)]
    inp = {"input_ids": np.array([[0, *ids, 0]], dtype=np.int64), "style": style,
           "speed": np.array([speed], dtype=np.float32)}
    audio = sess.run(None, inp)[0].astype(np.float32).squeeze()
    sf.write(str(out), audio, SR)
    return len(audio) / SR
