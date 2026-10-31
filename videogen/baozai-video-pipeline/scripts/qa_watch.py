#!/usr/bin/env python3
"""边等边验：谁新出片就跑谁的 13 项 QA，结果缓存到 build/qa/，全绿才记账。

用法：qa_watch.py [--once] [--budget 560]
退出码 0 = ep06–35 全部 mp4+cover+QA 绿；1 = 预算用尽还没齐。
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv \
    else Path("/Users/max/codebase/comedy")
QA = Path.home() / ".qoder/skills/puppet-talk-render/scripts/qa_episode.py"
P = "/Users/max/codebase/ComfyUI/.venv/bin/python"
CACHE = ROOT / "build" / "qa"


def green(ep):
    f = CACHE / f"ep{ep:02d}.ok"
    return f.exists() and f.read_text().strip() == str(
        (ROOT / f"ep{ep:02d}.mp4").stat().st_size if (ROOT / f"ep{ep:02d}.mp4").exists() else "-")


def check(ep):
    """返回 (状态, 一行说明)。状态 in ok/skip/fail。"""
    tag = f"ep{ep:02d}"
    mp4, cover = ROOT / f"{tag}.mp4", ROOT / f"{tag}_cover.png"
    if not mp4.exists():
        return "skip", f"{tag} 还没出片"
    if subprocess.call(["pgrep", "-f", f"render.py --ep {ep}"], stdout=subprocess.DEVNULL) == 0:
        return "skip", f"{tag} 正在渲"
    if not cover.exists():
        return "fail", f"{tag} 有片没封面"
    if green(ep):
        return "ok", f"{tag} 已绿"
    r = subprocess.run([P, str(QA), "--ep", str(ep)], capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("summary:")), "?")
    fails = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("FAIL")]
    if r.returncode == 0:
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / f"{tag}.ok").write_text(str(mp4.stat().st_size))
        return "ok", f"{tag} {line}"
    return "fail", f"{tag} {line} 未过项={fails or '?'}（{mp4.stat().st_size}B）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget", type=int, default=560)
    args = ap.parse_args()
    t0 = time.time()
    while True:
        states = {}
        for ep in range(6, 36):
            st, msg = check(ep)
            states[ep] = (st, msg)
            if st == "fail":
                print(msg, flush=True)
        ok = sum(1 for st, _ in states.values() if st == "ok")
        pend = [f"ep{e:02d}" for e, (st, _) in states.items() if st != "ok"]
        print(f"[{time.time()-t0:4.0f}s] 绿 {ok}/30  未齐 {len(pend)}: {' '.join(pend[:12])}"
              f"{' …' if len(pend) > 12 else ''}", flush=True)
        if ok == 30:
            print("ALL 30 GREEN")
            return 0
        if args.once or time.time() - t0 > args.budget:
            return 1
        time.sleep(20)


if __name__ == "__main__":
    sys.exit(main())
