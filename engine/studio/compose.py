"""Editing & rendering: slow-mo/interpolate AI clips, cinematic transitions, grade, subtitles, music mix."""
from __future__ import annotations
import subprocess, random, re
from pathlib import Path

W, H, FPS = 1080, 1920, 24
XF = 0.5  # transition seconds
TRANSITIONS = ["fade", "smoothleft", "smoothright", "circleopen", "dissolve", "fadeblack", "smoothup", "zoomin"]
FONTS = "/usr/share/fonts/opentype/inter"


def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-1500:])


def render_shot(raw: Path, out: Path, length: float, width: int = W, height: int = H):
    """raw = 8fps AI clip (2s). Stretch to `length` seconds with motion interpolation, upscale, grade."""
    src_len = 2.0
    pre = ""
    if length > 5.0:  # boomerang to get a 4s base so stretch stays natural
        pre = "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[bm];[bm]"
        src_len = 4.0
    else:
        pre = "[0:v]"
    stretch = length / src_len
    vf = (f"{pre}setpts=PTS*{stretch:.4f},minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1,"
          f"scale={width}:{height}:flags=lanczos,unsharp=5:5:0.6,eq=saturation=1.12:contrast=1.04,"
          f"format=yuv420p[v]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-filter_complex", vf, "-map", "[v]",
         "-t", f"{length:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])


def join_with_transitions(clips: list[Path], lengths: list[float], out: Path, seed: int = 3):
    """Chain xfade. Each clip file is (slot + XF) long except the last, so slots stay on the narration clock."""
    rnd = random.Random(seed)
    if len(clips) == 1:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clips[0]), "-c", "copy", str(out)])
        return
    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
    fg, prev, acc = [], "[0:v]", lengths[0]
    for i in range(1, len(clips)):
        tr = rnd.choice(TRANSITIONS)
        off = acc - XF
        lab = f"[x{i}]"
        fg.append(f"{prev}[{i}:v]xfade=transition={tr}:duration={XF}:offset={off:.3f}{lab}")
        prev, acc = lab, acc + lengths[i] - XF
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fg), "-map", prev,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)])


def _ts(t: float) -> str:
    h, rem = divmod(t, 3600); m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunk_words(text: str, n: int = 4) -> list[str]:
    words = text.split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= n or re.search(r"[.!?;:]$", w) or (len(cur) >= 2 and w.endswith(",")):
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def write_ass(cues: list[tuple[float, float, str]], title: str, total: float, out: Path, vertical=True):
    fs = 88 if vertical else 60
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W if vertical else H}
PlayResY: {H if vertical else W}
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Sub,Inter,{fs},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,{330 if vertical else 90},1
Style: Title,Inter,{fs+30},&H0000E5FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,9,3,8,60,60,{300 if vertical else 120},1
Style: Credit,Inter,40,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,{110 if vertical else 30},1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [f"Dialogue: 0,{_ts(0.4)},{_ts(3.6)},Title,,0,0,0,,{{\\fad(400,500)}}{title}"]
    for a, b, t in cues:
        lines.append(f"Dialogue: 1,{_ts(a)},{_ts(b)},Sub,,0,0,0,,{{\\fad(60,60)}}{t.upper()}")
    lines.append(f"Dialogue: 0,{_ts(total-3.2)},{_ts(total-0.3)},Credit,,0,0,0,,{{\\fad(300,300)}}"
                 "Made with My AI Video Studio · 100% AI-generated visuals, voice & music")
    out.write_text(hdr + "\n".join(lines) + "\n")


def mix_audio(narr: Path, music: Path, out: Path, total: float):
    """Duck music under narration (sidechain), normalise loudness."""
    fc = ("[1:a]volume=0.55[m];[0:a]asplit[n1][n2];[m][n1]sidechaincompress=threshold=0.03:ratio=8:"
          "attack=15:release=400[ducked];[ducked][n2]amix=inputs=2:duration=first:normalize=0,"
          f"loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total:.2f}[a]")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(narr), "-i", str(music), "-filter_complex", fc,
         "-map", "[a]", "-ar", "44100", str(out)])


def final_render(video: Path, audio: Path, ass: Path, out: Path):
    vf = f"subtitles={ass}:fontsdir={FONTS},vignette=PI/6"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio), "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)])
