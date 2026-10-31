#!/usr/bin/env python3
"""QA one rendered episode: timing, frames, loudness, crowd reactions, AI voice, cover-frame gaps.

usage: qa_episode.py --ep 4 [--video PATH] [--root DIR] [--json]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 24000
PASS, WARN, FAIL = "ok  ", "warn", "FAIL"


class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, label, detail):
        self.rows.append((level, label, detail))

    def __bool__(self):
        return not any(r[0] == FAIL for r in self.rows)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def decode_audio(video):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)


def probe(video):
    _, out, _ = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                     "-show_entries", "format=duration", "-of", "json", str(video)])
    j = json.loads(out)
    s, f = j["streams"][0], j["format"]
    num, den = s["r_frame_rate"].split("/")
    return dict(w=int(s["width"]), h=int(s["height"]), fps=float(num) / float(den),
                frames=int(s["nb_frames"]), dur=float(f["duration"]))


def loudness(video):
    _, _, err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
                     "-af", "loudnorm=I=-15:TP=-1.5:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))
    return dict(i=float(j["input_i"]), tp=float(j["input_tp"]), lra=float(j["input_lra"]))


def rms_db(x, sr, a, b):
    seg = x[int(max(0, a) * sr):int(b * sr)]
    if len(seg) < 100:
        return None
    return 20 * np.log10(float(np.sqrt((seg ** 2).mean())) + 1e-9)


def centroid(x, sr, a, b):
    seg = x[int(a * sr):int(b * sr)]
    if len(seg) < 512:
        return None
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freq = np.fft.rfftfreq(len(seg), 1 / sr)
    return float((spec * freq).sum() / (spec.sum() + 1e-9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", type=int, required=True)
    ap.add_argument("--video", default=None)
    ap.add_argument("--root", default="/Users/max/codebase/comedy")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    tag = f"ep{args.ep:02d}"
    video = Path(args.video) if args.video else root / f"{tag}.mp4"
    r = Report()
    if not video.exists():
        r.add(FAIL, "video", f"{video} not found")
        print_report(r, args.json)
        return 1

    timing = json.loads((root / "audio" / tag / "timing.json").read_text())
    lines = timing["lines"]
    sys.path.insert(0, str(root))
    try:
        import importlib
        script = importlib.import_module(f"script_{tag}").LINES
    except Exception as e:
        script = None
        r.add(WARN, "script", f"cannot import script_{tag}: {e}")

    v = probe(video)
    r.add(PASS if v["w"] == 1080 and v["h"] == 1920 else FAIL, "resolution",
          f"{v['w']}x{v['h']} @ {v['fps']:g}fps")
    need = lines[-1]["end"] + (1.2 if lines[-1].get("applause") else 0.0)
    r.add(PASS if v["dur"] >= need else FAIL, "duration",
          f"{v['dur']:.1f}s video vs {lines[-1]['end']:.1f}s last line (need >= {need:.1f}s)")
    r.add(PASS if abs(v["frames"] - v["dur"] * v["fps"]) < 8 else FAIL, "frames",
          f"{v['frames']} frames vs {v['dur'] * v['fps']:.0f} expected")

    loud = loudness(video)
    if loud:
        ok = -16.5 <= loud["i"] <= -13.5 and loud["tp"] <= -1.0
        r.add(PASS if ok else FAIL, "loudness",
              f"{loud['i']:.1f} LUFS / TP {loud['tp']:.1f} dB / LRA {loud['lra']:.1f}")
    else:
        r.add(WARN, "loudness", "could not measure")

    if 150.0 <= v["dur"] <= 215.0:
        r.add(PASS, "length", f"{v['dur']:.0f}s 落在 3 分钟档（150–215s）")
    else:
        r.add(WARN, "length", f"{v['dur']:.0f}s 不在 3 分钟档：加/减台词，"
                             f"每 60 字 ≈ 10.7s（实测 ≈5.6 字/秒）")

    x = decode_audio(video)
    r.add(PASS if abs(len(x) / SR - v["dur"]) < 0.3 else FAIL, "av-sync",
          f"audio {len(x) / SR:.1f}s vs video {v['dur']:.1f}s")

    voice_db, react_db = [], []
    for i, l in enumerate(lines):
        d = rms_db(x, SR, l["start"] + 0.1, max(l["start"] + 0.15, l["end"] - 0.1))
        if d is not None:
            voice_db.append(d)
        if not (l.get("laugh", 0) or l.get("applause")):
            continue
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else l["end"] + 9
        room = nxt - l["end"] - 0.45
        best = None
        off = 0.0
        while off + 0.4 <= room:
            e = rms_db(x, SR, l["end"] + off, l["end"] + off + 0.4)
            if e is not None and (best is None or e > best):
                best = e
            off += 0.1
        if best is not None:
            react_db.append(best)
    if voice_db and react_db:
        gaps = np.array(react_db) - np.median(voice_db)
        med = float(np.median(gaps))
        lvl = PASS if -16 <= med <= -2 else (WARN if med >= -19 else FAIL)
        r.add(lvl, "crowd", f"reaction {med:+.1f} dB vs voice RMS "
                            f"(p25 {np.percentile(gaps, 25):+.1f} / p75 {np.percentile(gaps, 75):+.1f}, "
                            f"{len(gaps)} measurable cues)")

    ai = [l for l in lines if l.get("who") == "ai"]
    if ai:
        cen = {l["id"]: centroid(x, SR, l["start"] + 0.1, max(l["start"] + 0.15, l["end"] - 0.1))
               for l in lines}
        rows, bad = [], 0
        for l in ai:
            near = [cen[o["id"]] for o in lines
                    if o.get("who", "bao") == "bao" and abs(o["start"] - l["start"]) < 60
                    and cen.get(o["id"])]
            c = cen.get(l["id"])
            if not c or not near:
                continue
            rows.append(f"{l['id']} {c:.0f}Hz vs {np.mean(near):.0f}Hz nearby")
            if c > np.mean(near):
                bad += 1
        r.add(PASS if bad == 0 else WARN, "ai-voice",
              f"{len(ai)} AI line(s) expected below neighbouring speech; " + "; ".join(rows[:4]))

    if script is not None:
        long_lines = [l["id"] for l in script if len(l["text"]) > 40]
        r.add(PASS if not long_lines else WARN, "subtitle-fit",
              f"{len(script)} lines, longest {max(len(l['text']) for l in script)} chars"
              + (f"; over 40: {long_lines[:6]}" if long_lines else ""))
        # the AI chime and the applause tail both live inside build_mix's crowd branch,
        # so a crowd-free episode (小剧场) has nothing for these two to enforce
        if any(l.get("laugh") or l.get("applause") for l in script):
            ai_bad = [l["id"] for l in script if l.get("who") == "ai" and l.get("pause_before", 0) < 0.7]
            r.add(PASS if not ai_bad else WARN, "ai-chime",
                  f"AI lines need pause_before >= 0.7s for the chime"
                  + (f"; short: {ai_bad}" if ai_bad else ""))
            r.add(PASS if script[-1].get("applause") else WARN, "outro",
                  "last line applause=True keeps the 1.4s reaction tail")

    # chapter card sits 1.25s before its line; the previous subtitle lingers 0.45s
    clash = []
    for i, l in enumerate(lines):
        if not l.get("chapter") or i == 0:
            continue
        overlap = min(l["start"] - 0.12, lines[i - 1]["end"] + 0.45) - (l["start"] - 1.25)
        if overlap > 0.15:
            clash.append(f"{l['id']} {overlap:.2f}s")
    r.add(PASS if not clash else WARN, "chapter-card",
          f"{sum(1 for l in lines if l.get('chapter'))} chapter card(s) vs previous subtitle"
          + (f"; overlap: {clash}" if clash else "; no clash"))

    gaps = [(round(lines[i]["end"] + 0.45, 2), round(lines[i + 1]["start"] - 0.08, 2))
            for i in range(len(lines) - 1)
            if lines[i + 1]["start"] - lines[i]["end"] > 0.6]
    clean = [g for g in gaps if g[1] > g[0]]
    r.add(PASS if clean else WARN, "cover-frame",
          f"{len(clean)} subtitle-free window(s) >= 0.05s, e.g. {clean[:3]}")

    print_report(r, args.json)
    return 0 if r else 1


def print_report(r, as_json):
    if as_json:
        print(json.dumps([dict(level=a, check=b, detail=c) for a, b, c in r.rows],
                         ensure_ascii=False, indent=2))
        return
    for lvl, label, detail in r.rows:
        print(f"{lvl} {label:<13} {detail}")
    n = {PASS: 0, WARN: 0, FAIL: 0}
    for lvl, _, _ in r.rows:
        n[lvl] += 1
    print(f"summary: {n[PASS]} ok, {n[WARN]} warn, {n[FAIL]} fail")


if __name__ == "__main__":
    sys.exit(main())
