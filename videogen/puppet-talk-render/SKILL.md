---
name: puppet-talk-render
description: 包仔竖屏脱口秀的成片渲染：render.py 的 EPISODES 配置、2D 木偶口型/眨眼/呼吸/跳点、舞台道具与章卡/片头/AI 字幕样式、观众笑声掌声混音、-15 LUFS 响度归一、封面生成与 qa_episode.py 自动校验。Use when 渲染或重渲 EP、改画面/字幕/舞台、调笑声掌声、响度、做封面、查成片时长帧数与音画对位。
---

# 2D 木偶脱口秀渲染

## Overview

输入是配音好的 `audio/epNN/voice_full.wav` + `timing.json`（见 `qwen3-tts-voice`），输出 1080×1920/30fps 成片 + 封面。工程在 `/Users/max/codebase/comedy`，脚本用 `/Users/max/codebase/ComfyUI/.venv/bin/python`（需要 numpy/scipy/PIL）。

## 出片流程

```bash
cd /Users/max/codebase/comedy
# 0) 先在 render.py 的 EPISODES 里加这一集的配置（见下）
# 1) 静帧抽查（每次只能传一个 --still，多个时间点要分开跑）
/Users/max/codebase/ComfyUI/.venv/bin/python render.py --ep 5 --still 0.8
# 2) 全片渲染：约 36fps 吞吐，8 分钟片子约 7 分钟 → 必须后台跑
/Users/max/codebase/ComfyUI/.venv/bin/python render.py --ep 5 > build/ep05_render.log 2>&1
# 3) 响度归一（视频流直接 copy，只重编音频）
ffmpeg -y -i ep05.mp4 -c:v copy \
  -af "volume=5.6dB,alimiter=limit=0.841:level=false:attack=5:release=80" \
  -c:a aac -b:a 192k ep05_norm.mp4 && mv ep05_norm.mp4 ep05.mp4
# 4) 封面：从「无字幕空档」抽一帧再压标题
ffmpeg -y -ss <t> -i ep05.mp4 -frames:v 1 build/ep05_cover_base.png
/Users/max/codebase/ComfyUI/.venv/bin/python make_cover.py build/ep05_cover_base.png "标题" "包仔 · 副标题" ep05_cover.png
# 5) 自动校验
/Users/max/codebase/ComfyUI/.venv/bin/python /Users/max/.qoder/skills/puppet-talk-render/scripts/qa_episode.py --ep 5
```

第 3 步的 `5.6dB` 不是常数：先量 `build/ep05_mix.wav`（`ffmpeg -i ... -af loudnorm=print_format=json -f null -`），把整体推到 -15 LUFS、峰值 ≤ -1.5 dBFS 为准。**`alimiter` 必须写 `level=false`**，它默认开自动电平，会额外多推约 8dB 把片子顶爆。

## EPISODES 配置（`render.py:40`）

```python
5: dict(stage=PROPS / "stage_vert.png", title="EP05 · 主题",
        hook=None, badge=False, crowd=True, sign="包仔开放麦",
        robot=PROPS / "ai_lead.png", heart=False,
        intro=("片头标题", "片头副标题")),
```

| 键 | 含义 |
|----|------|
| `title` | 左上角常驻集数标签 |
| `hook` | `None` 或 `{"text","t0","t1"}`：中上方红色横幅钩子（EP01 用过，现在默认不用） |
| `badge` | 是否给角色挂工牌 |
| `crowd` | 是否叠观众声（关掉就只出人声） |
| `sign` | 霓虹灯牌文字，`None` 则不画 |
| `robot` | 舞台左侧 AI 机器人贴图路径，`None` 不画 |
| `heart` | 机器人头顶爱心（EP03 恋爱篇专用） |
| `intro` | 片头卡 `(标题, 副标题)`，出现在 0.10–1.40s；不要就和第一幕章卡挤在一起 |

## 必查项

- **静帧四连**：片头卡、章卡、AI 插话句、末句之后。`--still <秒>` 一次只生效一个时间点。
- **章卡与上一句字幕不能叠**：章卡占 `[start-1.25, start-0.12]`，上一句字幕延后 0.45s 才消失 → 章卡句的 `pause_before` 要 ≥ 1.25（QA 脚本会算重叠时长）。
- **末句要 `applause=True`**：`render.py:635` 只在最后一句带掌声时补 1.4s 音视频余量，否则收尾笑声被切。
- **音画对位**：`qa_episode.py` 的 `av-sync` 与 `duration` 两项。
- **响度**：目标 -15 LUFS（EP04 实测 -15.2 LUFS / TP -0.9 dB）。
- 渲染和出图不要同时跑；渲染期间改 `render.py` 不影响已在跑的进程。

## Resources

- [references/visual-system.md](references/visual-system.md) — 布局常量、动画频率、配色、关键函数索引、加新道具/新舞台的做法（含 ComfyUI FLUX 出图脚本模式）。
- [references/audio-mix.md](references/audio-mix.md) — 观众声各声部参数、笑声/掌声校准历史、正确的电平测量窗口。
- [scripts/qa_episode.py](scripts/qa_episode.py) — 一条命令跑完 12 项成片校验（`--ep N [--json]`），返回码非 0 表示有 FAIL。
