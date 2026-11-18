"""Optional Real-ESRGAN x2 frame enhancement (RRDBNet, BSD-3 weights). Reported as *enhancement*, never as native resolution."""
from __future__ import annotations
import torch, torch.nn as nn, torch.nn.functional as F
import numpy as np
from .paths import MODELS


class RDB(nn.Module):
    def __init__(self, nf=64, gc=32):
        super().__init__()
        self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1); self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
        self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1); self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
        self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1); self.lrelu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x)); x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1))); x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        return self.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, nf, gc=32):
        super().__init__(); self.rdb1 = RDB(nf, gc); self.rdb2 = RDB(nf, gc); self.rdb3 = RDB(nf, gc)

    def forward(self, x):
        return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(self, scale=2, nf=64, nb=23, gc=32):
        super().__init__()
        self.scale = scale
        in_ch = 3 * (4 if scale == 2 else 16 if scale == 1 else 1)
        self.conv_first = nn.Conv2d(in_ch, nf, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(nf, gc) for _ in range(nb)])
        self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1); self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
        self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1); self.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        feat = F.pixel_unshuffle(x, 2) if self.scale == 2 else x
        feat = self.conv_first(feat)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


_net = {}


def load(dtype=torch.bfloat16):
    if "m" not in _net:
        sd = torch.load(str(MODELS / "realesrgan/RealESRGAN_x2.pth"), map_location="cpu", weights_only=True)
        sd = sd.get("params_ema", sd.get("params", sd))
        m = RRDBNet(scale=2); missing = m.load_state_dict(sd, strict=False)
        assert not missing.missing_keys, missing.missing_keys[:5]
        _net["m"] = m.eval().to(dtype)
    return _net["m"]


@torch.no_grad()
def upscale_frames(frames: list[np.ndarray], dtype=torch.bfloat16) -> list[np.ndarray]:
    m = load(dtype); out = []
    for f in frames:
        x = torch.from_numpy(f).permute(2, 0, 1)[None].to(dtype) / 255.0
        y = m(x).clamp(0, 1)[0].permute(1, 2, 0).float().numpy()
        out.append((y * 255).round().astype(np.uint8))
    return out
