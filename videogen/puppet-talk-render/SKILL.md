---
name: puppet-talk-render
description: 包仔竖屏脱口秀的成片渲染：render.py 的 EPISODES 配置、2D 木偶口型/眨眼/呼吸/跳点、舞台道具与章卡/片头/AI 字幕样式、观众笑声掌声混音、-15 LUFS 响度归一、封面生成与 qa_episode.py 自动校验。Use when 渲染或重渲 EP、改画面/字幕/舞台、调笑声掌声、响度、做封面、查成片时长帧数与音画对位。
---

# 2D 木偶脱口秀渲染

## Overview

输入是配音好的 `audio/epNN/voice_full.wav` + `timing.json`（见 `qwen3-tts-voice`），输出 1080×1920/30fps 成片 + 封面。工程在 `/Users/max/codebase/comedy`，脚本用 `/Users/max/codebase/ComfyUI/.venv/bin/python`（需要 numpy/scipy/PIL）。

## 出片流程

一集一条命令（配音 → 成片 → 封面 → QA，全部串行，实测 ≈5min/集）：

```bash
cd /Users/max/codebase/comedy
/Users/max/codebase/ComfyUI/.venv/bin/python make_episode.py --ep 21 --ep 22   # 可一次排多集
# 只补封面：--skip-voice --only-cover ；只重渲画面：--skip-voice
```

手工分步（要单独调某一环时）：

```bash
# 1) 静帧抽查（每次只能传一个 --still，多个时间点要分开跑）
/Users/max/codebase/ComfyUI/.venv/bin/python render.py --ep 5 --still 0.8
# 2) 全片渲染：约 36–40fps 吞吐，3 分钟片子约 2.5min → 必须后台跑
/Users/max/codebase/ComfyUI/.venv/bin/python render.py --ep 5 > build/render_ep05.log 2>&1
# 3) 封面：压标题的 still 由 make_episode.py 选（35% 处最近的爆点句 +0.35s）
/Users/max/codebase/ComfyUI/.venv/bin/python make_cover.py build/still_ep05_46.4.png "主标题" "副标题" ep05_cover.png
# 4) 自动校验
/Users/max/codebase/ComfyUI/.venv/bin/python /Users/max/.qoder/skills/puppet-talk-render/scripts/qa_episode.py --ep 5
```

**响度归一已经在 `render.py` 的 `master_af()` 里自动做完**（EP06 起）：编码前先量 `build/epNN_mix.wav`
的 `loudnorm=I=-15:TP=-1.5:print_format=json`，按 `gain = -15 − input_i` 上限 +9dB 出一句静态
`volume=<gain>dB,alimiter=limit=0.794:level=false:attack=5:release=80`。要点：
- 增益只看响度不看峰值——超出天花板的是 0.05% 的瞬态，交给限幅器，实测成片 -15.5 LUFS / TP -1.4dB；
- 限幅器 ceiling 用 -2.5 dBFS，因为 AAC 编码会把真峰值顶高约 1dB；
- **`alimiter` 必须写 `level=false`**，它默认开自动电平，会额外多推约 8dB 把片子顶爆；
- 不要用 `loudnorm` 动态模式做最终归一，它的滑动窗会把笑声反应压扁。

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

## 情侣日常档：不写 EPISODES，写 `SCENE`

EP06 起的两角色集不进 `EPISODES` 表——`render.py:couple_episode()` 直接读剧本文件里的
`SCENE = dict(title="…", room="living", cover=("大字", "小字"))`，`room` 只有 `living`/`kitchen`
两个舞台（`ROOMS`，`render.py:65`）。默认 cast 是包仔（`cx=325,h=520`）+ 小满（`cx=755,h=470`），
`SCENE` 里给 `cast`/`names`/`crowd`/`hook`/`intro` 就覆盖。所以**加一集只需要一个剧本文件**。

双角色渲染要点：
- 每个角色的口型包络来自 `stem(voice, sr, timing, who)`——按 `timing.json` 的行窗口从 `voice_full.wav`
  里切出「只属于这个人的声音」，所以不依赖分轨文件，老集数也能跑；
- 说话人字幕按 `SPEAK_COLORS[who]` 染色，名牌 chip 贴在该角色那一侧（`who` 不在 cast 里时按前缀判断左右）；
- 呼吸/轻摆用 `phase=k*1.7` 错开，跳点 `punch_track(n, timing, who)` 只在该角色的爆点跳；
- 舞台上的角色 `cx` 要和台词里的站位感一致，别让她俩重叠。

## 必查项

- **静帧四连**：片头卡、章卡、AI 插话句、末句之后。`--still <秒>` 一次只生效一个时间点。
- **章卡与上一句字幕不能叠**：章卡占 `[start-1.25, start-0.12]`，上一句字幕延后 0.45s 才消失 → 章卡句的 `pause_before` 要 ≥ 1.25（QA 脚本会算重叠时长）。
- **末句要 `applause=True`**（有观众档）：`render.py` 只在最后一句带掌声时补 1.4s 音视频余量，否则收尾笑声被切。情侣档 `crowd=False`，不适用。
- **音画对位**：`qa_episode.py` 的 `av-sync` 与 `duration` 两项。
- **响度**：目标 -15 LUFS（EP06/EP21 实测 -15.5 LUFS / TP -1.4~-1.8 dB，`master_af()` 自动完成）。
- **3 分钟档**：`qa_episode.py` 的 `length` 项要求 150–215s；差多少按 ≈5.6 字/秒 补/删台词（60 字 ≈ 10.7s）。
- 渲染和出图不要同时跑；渲染期间改 `render.py` 不影响已在跑的进程。

## Resources

- [references/visual-system.md](references/visual-system.md) — 布局常量、动画频率、配色、关键函数索引、加新道具/新舞台的做法（含 ComfyUI FLUX 出图脚本模式）。
- [references/audio-mix.md](references/audio-mix.md) — 观众声各声部参数、笑声/掌声校准历史、正确的电平测量窗口。
- [scripts/qa_episode.py](scripts/qa_episode.py) — 一条命令跑完 12 项成片校验（`--ep N [--json]`），返回码非 0 表示有 FAIL。
- `/Users/max/codebase/comedy/make_episode.py` — 一集一条命令的总驱动（`--ep` 可重复；`--skip-voice` / `--only-cover`），逐集打印 句数/字数/台词秒数、QA 结论与汇总。
