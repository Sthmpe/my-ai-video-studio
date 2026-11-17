"""Keyless, fully local script writer fallback: Qwen2.5-Instruct (Apache-2.0) via transformers (CPU)."""
from __future__ import annotations
import os, threading
import torch

MODEL = os.environ.get("STUDIO_LOCAL_LLM", "Qwen/Qwen2.5-3B-Instruct")
_lock, _m = threading.Lock(), None


def chat(messages: list[dict], max_new_tokens: int = 2200) -> str:
    global _m
    with _lock:
        if _m is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(MODEL)
            mod = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.bfloat16)
            _m = (tok, mod.eval())
    tok, mod = _m
    ids = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    with torch.no_grad():
        out = mod.generate(**ids, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7, top_p=0.9)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
