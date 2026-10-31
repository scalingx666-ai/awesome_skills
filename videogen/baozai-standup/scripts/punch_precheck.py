"""Pre-TTS punch cadence check for 包仔 couple episodes.

Estimates each line's start time from char count / per-voice rate + the two pauses, then
flags an opening with no highlight (首爆 > 15s) or a lull between highlights (> 32s) and
names the line that would split it best. Estimates only: qa_episode.py measures the truth
from timing.json after TTS.
"""
import argparse
import importlib
import pathlib
import sys

# measured from delivered episodes: 小满 speaks slower than 包仔, elders slower still
RATE = {"bao": 5.4, "girl": 5.0, "bao_mom": 4.6, "girl_mom": 4.6, "ai": 5.0}
FIRST, LULL, MIN_GAP = 15.0, 32.0, 3


def timeline(lines):
    t = 0.0
    for l in lines:
        t += l.get("pause_before", 0.0)
        l["_start"] = t
        t += len(l["text"]) / RATE.get(l.get("who", "bao"), 5.2)
        t += l.get("pause_after", 0.0)
    return t


def report(ep, root):
    sys.path.insert(0, str(root))
    m = importlib.import_module(f"script_ep{ep:02d}")
    lines = [dict(l) for l in m.LINES]
    total = timeline(lines)
    chars = sum(len(l["text"]) for l in lines)
    idx = [i for i, l in enumerate(lines) if l.get("punch")]
    ps = [lines[i] for i in idx]
    note = f"ep{ep:02d} {len(lines)}句/{chars}字 {total:.0f}s "
    if not ps:
        return note + "NO PUNCH"
    head = ps[0]["_start"]
    lo, hi, worst = 0.0, head, head
    for a, b in zip(ps, ps[1:]):
        if b["_start"] - a["_start"] > worst:
            worst, lo, hi = b["_start"] - a["_start"], a["_start"], b["_start"]
    if total - ps[-1]["_start"] > worst:
        worst, lo, hi = total - ps[-1]["_start"], ps[-1]["_start"], total
    tight = [(lines[a]["id"], lines[b]["id"]) for a, b in zip(idx, idx[1:]) if b - a < MIN_GAP]
    bad = []
    if head > FIRST:
        bad.append(("开场", 0.0, head))
    elif worst > LULL:
        bad.append(("空档", lo, hi))
    fix = ""
    if bad:
        why, b0, b1 = bad[0]
        cands = [l for l in lines if not l.get("punch") and b0 + 4 < l["_start"] < b1 - 2]
        cands.sort(key=lambda l: abs(l["_start"] - (b0 + b1) / 2))
        if cands:
            c = cands[0]
            fix = f" -> {why}改 punch={c['id']} @{c['_start']:.0f}s「{c['text'][:14]}…」"
    return (note + f"{len(ps)}punch 首爆{head:.0f}s 最大空档{worst:.0f}s"
            + (f" 相邻过近{tight}" if tight else "")
            + ("" if not bad and not tight else "  NEEDS" + fix))


ap = argparse.ArgumentParser()
ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/Users/max/codebase/comedy"))
ap.add_argument("ep", type=int, nargs="+")
args = ap.parse_args()
for e in args.ep:
    print(report(e, args.root), flush=True)
