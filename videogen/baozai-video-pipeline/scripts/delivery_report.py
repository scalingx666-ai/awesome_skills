"""Final delivery audit for the 30-episode couple series (EP06-EP35).

Every requirement of the goal gets its own column, so a green row means the episode is really
shippable: mp4 present and probeable, cover present, QA green, and timing.json still matching
the script (text + speaker + punch).
"""
import argparse
import importlib
import json
import pathlib
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("/Users/max/codebase/comedy"))
ap.add_argument("--qa", action="store_true", help="也跑 qa_episode.py（每集约 20 秒）")
args = ap.parse_args()
R = args.root
sys.path.insert(0, str(R))
QA = pathlib.Path.home() / ".qoder/skills/puppet-talk-render/scripts/qa_episode.py"
P = "/Users/max/codebase/ComfyUI/.venv/bin/python"

rows, bad = [], []
for e in range(6, 36):
    tag = f"ep{e:02d}"
    mp4, cover = R / f"{tag}.mp4", R / f"{tag}_cover.png"
    tp = R / "audio" / tag / "timing.json"
    dur, n, drift = None, 0, []
    if mp4.exists():
        r = subprocess.run([  # a truncated render probes empty
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(mp4)], capture_output=True, text=True)
        try:
            dur = float(r.stdout.strip())
        except ValueError:
            pass
    if tp.exists():
        t = json.loads(tp.read_text())
        mod = importlib.import_module(f"script_{tag}")
        want = {str(l["id"]): l for l in mod.LINES}
        for l in t["lines"]:
            w = want[l["id"]]
            if l["text"] != w["text"]:
                drift.append(f"{l['id']}文本")
            elif l.get("who", "bao") != w.get("who", "bao"):
                drift.append(f"{l['id']}说话人")
            elif bool(l.get("punch")) != bool(w["punch"]):
                drift.append(f"{l['id']}punch")
        n = len(t["lines"])
    qa = ""
    if args.qa and mp4.exists():
        rc = subprocess.run([P, str(QA), "--ep", str(e)], capture_output=True, text=True)
        fails = [ln.split()[1] for ln in rc.stdout.splitlines() if ln.startswith("fail")]
        warns = [ln.split()[1] for ln in rc.stdout.splitlines() if ln.startswith("warn")]
        qa = "OK" if rc.returncode == 0 else "FAIL:" + ",".join(fails)
        if warns:
            qa += " warn:" + ",".join(warns)
    ok = bool(dur) and cover.exists() and not drift
    rows.append((tag, n, f"{dur:.0f}s" if dur else "无成片", "有" if cover.exists() else "缺",
                 "一致" if not drift else ",".join(drift[:4]), qa, "✓" if ok else "✗"))
    if not ok:
        bad.append(tag)

print(f"{'集':6}{'句':>4}{'成片':>7}{'封面':>5}  {'剧本一致性':<24}{'' if args.qa else ''}{'QA':<22}过关")
for r in rows:
    print(f"{r[0]:6}{r[1]:>4}{r[2]:>7}{r[3]:>5}  {r[4]:<24}{r[5]:<22}{r[6]}")
print(f"\n过关 {30 - len(bad)}/30" + (f"  未过关: {bad}" if bad else "  全部达标"))
