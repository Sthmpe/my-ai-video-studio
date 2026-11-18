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
    # pass 1: boomerang (optional) + slow-mo + motion interpolation at native (small) resolution
    mid = out.with_suffix(".mid.mp4")
    vf1 = f"{pre}setpts=PTS*{stretch:.4f},minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1[v]"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-filter_complex", vf1, "-map", "[v]",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", str(mid)])
    # pass 2: pad to the exact slot length (interpolation drops the tail), upscale, grade
    vf2 = (f"tpad=stop_mode=clone:stop_duration=3,scale={width}:{height}:flags=lanczos,unsharp=5:5:0.6,"
           f"eq=saturation=1.12:contrast=1.04,format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mid), "-vf", vf2, "-frames:v", str(round(length * FPS)), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    mid.unlink(missing_ok=True)


def join_with_transitions(clips: list[Path], lengths: list[float], out: Path, seed: int = 3,
                          xf: float = XF, transitions: list[str] | None = None):
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
        tr = rnd.choice(transitions or TRANSITIONS)
        off = acc - xf
        lab = f"[x{i}]"
        fg.append(f"{prev}[{i}:v]xfade=transition={tr}:duration={xf}:offset={off:.3f}{lab}")
        prev, acc = lab, acc + lengths[i] - xf
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fg), "-map", prev,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(out)])


def _ts(t: float) -> str:
    h, rem = divmod(t, 3600); m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


_WEAK = {"a", "an", "the", "of", "is", "are", "was", "and", "or", "to", "in", "on", "at", "for", "with", "its",
         "it", "that", "this", "but", "so", "as", "by", "from", "their", "his", "her", "our", "your", "my", "than"}


def chunk_words(text: str, n: int = 4) -> list[str]:
    """Chunk each sentence separately (see _chunk_sentence)."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        out += _chunk_sentence(sent, n)
    return out


def _chunk_sentence(text: str, n: int = 4) -> list[str]:
    """Split narration into subtitle chunks of <= n words, breaking at punctuation and never
    stranding a function word ("its fur is a / tiny ecosystem") at the end of a chunk."""
    words, out, i = text.split(), [], 0
    while i < len(words):
        j = i
        while j < len(words) and j - i < n:
            j += 1
            if re.search(r"[.!?;:]$", words[j - 1]) or (j - i >= 2 and words[j - 1].endswith(",")):
                break
        # back off over trailing function words unless the chunk ended on punctuation
        if j < len(words) and not re.search(r"[.!?;:,]$", words[j - 1]):
            k = j
            while k - i > 1 and words[k - 1].lower().strip(",.") in _WEAK:
                k -= 1
            j = k
        if len(words) - j == 1 and j - i < n + 1:   # never leave a single orphan word
            j += 1
        out.append(" ".join(words[i:j])); i = j
    return out


def write_ass(cues: list[tuple[float, float, str]], title: str, total: float, out: Path, vertical=True,
              size: tuple[int, int] | None = None, end_card: str | None = None, credit: str | None = None):
    if size:
        globals_W, globals_H = size
    else:
        globals_W, globals_H = (W, H) if vertical else (H, W)
    vertical = globals_H > globals_W
    fs = 88 if vertical else (60 if globals_W > globals_H else 76)
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {globals_W}
PlayResY: {globals_H}
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
    if end_card:
        lines.append(f"Dialogue: 2,{_ts(total-2.6)},{_ts(total-0.2)},Title,,0,0,0,,{{\\fad(300,200)}}{end_card}")
    lines.append(f"Dialogue: 0,{_ts(total-3.2)},{_ts(total-0.3)},Credit,,0,0,0,,{{\\fad(300,300)}}"
                 + (credit or "Made with My AI Video Studio · 100% AI-generated visuals, voice & music"))
    out.write_text(hdr + "\n".join(lines) + "\n")
    # SRT sidecar for platforms that accept caption files
    def srt_ts(t):
        h, r = divmod(t, 3600); m, sec = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int(round((sec % 1) * 1000)):03d}"
    out.with_suffix(".srt").write_text("".join(f"{i}\n{srt_ts(a)} --> {srt_ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1)))


def mix_audio(narr: Path, music: Path, out: Path, total: float, sfx: Path | None = None, music_gain: float = 0.55):
    """Duck music under voice (sidechain), add the SFX/ambience layer, normalise loudness to -16 LUFS."""
    if sfx:
        fc = (f"[1:a]volume={music_gain}[m];[0:a]asplit[n1][n2];[m][n1]sidechaincompress=threshold=0.03:ratio=8:"
              "attack=15:release=400[ducked];[2:a]volume=1.0[fx];[ducked][n2][fx]amix=inputs=3:duration=first:normalize=0,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total:.2f}[a]")
        inputs = ["-i", str(narr), "-i", str(music), "-i", str(sfx)]
    else:
        fc = (f"[1:a]volume={music_gain}[m];[0:a]asplit[n1][n2];[m][n1]sidechaincompress=threshold=0.03:ratio=8:"
              "attack=15:release=400[ducked];[ducked][n2]amix=inputs=2:duration=first:normalize=0,"
              f"loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total:.2f}[a]")
        inputs = ["-i", str(narr), "-i", str(music)]
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[a]", "-ar", "44100", str(out)])


def final_render(video: Path, audio: Path, ass: Path, out: Path):
    vf = f"subtitles={ass}:fontsdir={FONTS},vignette=PI/6"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio), "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)])


def probe_size(path) -> tuple[int, int]:
    import json as _j
    o = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=width,height", "-of", "json", str(path)])
    st = _j.loads(o)["streams"][0]
    return st["width"], st["height"]
