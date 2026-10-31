"""Sync punch flags from script_epNN.LINES into audio/epNN/timing.json.

`punch` is a visual marker only -- gen_voice copies it into timing.json and never uses it for
duration -- so a highlight fix does not need re-synthesis or even a TTS process. Text or
speaker mismatches do need re-synthesis and abort here.

Detect drift by comparing the per-line punch sets, never by mtime: a running gen_voice imports
the script early, so its timing.json can be *newer* than the edit it does not contain.
"""
import argparse
import importlib
import json
import pathlib
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/Users/max/codebase/comedy"))
ap.add_argument("--ep", type=int, nargs="+")
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()
sys.path.insert(0, str(args.root))

for e in args.ep:
    tp = args.root / f"audio/ep{e:02d}/timing.json"
    if not tp.exists():
        continue
    timing = json.loads(tp.read_text())
    want = {str(l["id"]): l for l in importlib.import_module(f"script_ep{e:02d}").LINES}
    changed = []
    for l in timing["lines"]:
        w = want[l["id"]]
        if l["text"] != w["text"]:
            sys.exit(f"ep{e:02d} {l['id']} 台词与剧本不一致，必须重配音")
        if l.get("who", "bao") != w.get("who", "bao"):
            sys.exit(f"ep{e:02d} {l['id']} 说话人不一致，必须重配音")
        if bool(l.get("punch")) != bool(w["punch"]):
            l["punch"] = bool(w["punch"])
            changed.append(l["id"])
    if not changed:
        print(f"ep{e:02d} 一致")
        continue
    print(f"ep{e:02d} punch 不一致 {changed}")
    if args.dry_run:
        continue
    tp.write_text(json.dumps(timing, ensure_ascii=False, indent=2))
    for f in (args.root / f"ep{e:02d}.mp4", args.root / f"ep{e:02d}_cover.png"):
        if f.exists():
            # moved out of the root so `ls ep*.mp4` counts still mean delivered episodes
            f.rename(args.root / "build" / f"{f.stem}.prev{f.suffix}")
    print(f"  旧成片挪进 build/，渲染 worker 会重渲这一集")
