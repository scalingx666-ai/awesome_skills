---
name: baozai-video-pipeline
description: 包仔竖屏系列的端到端总控：从零建原创 IP 形象（FLUX 概念图 → rig.py 抠图补绘定骨架 → 舞台道具，含第二角色女包仔）、一集 EP 从写稿到成片的完整 runbook（命令序列、产物落点、实测耗时、过关标准）、批量出 EP（make_episode.py 一条命令排多集）、四个环节的数据流与故障定位。Use when 第一次搭这套环境、做新一集想一次走完、批量渲染 30 集、不知道某步产物在哪个目录、成片出问题要判断是稿/声/画/混音哪一环、要换形象或舞台；也用于判断该读 baozai-standup / qwen3-tts-voice / puppet-talk-render 中的哪一个。不负责写稿细则、配音参数、画面与混音参数（见那三个子 skill）。
---

# 包仔脱口秀端到端流程

## Overview

四个环节串成一条线：**形象（一次性）→ 稿 → 声 → 画+混音**。工程分散在三个目录：

| 目录 | 装什么 |
|------|--------|
| `/Users/max/codebase/ComfyUI` | FLUX.2 Klein 出图（概念图、舞台、道具）+ `.venv`（所有脚本共用这个 Python） |
| `/Users/max/codebase/tts` | Qwen3-TTS 权重、音色参考音频 `out/voices/v2_cheeky.wav` |
| `/Users/max/codebase/comedy` | 剧本、配音脚本、渲染脚本、成片 |

## 先决定读哪个 skill

| 要做的事 | 读 |
|----------|-----|
| 写/改台词、设计爆点、规划分幕 | `baozai-standup` |
| 配音、换音色、做 AI 机械音、观众笑声素材 | `qwen3-tts-voice` |
| 改画面/字幕/舞台/混音参数、响度归一、跑校验 | `puppet-talk-render` |
| 建形象、走完整一集、定位问题出在哪一环 | 本 skill |

## 一次性：建形象与舞台

已完成，只在**换形象/换舞台**时重做。步骤与坐标标定方法见 [references/ip-build.md](references/ip-build.md)。

```bash
cd /Users/max/codebase/ComfyUI && .venv/bin/python main.py --listen 127.0.0.1   # 只绑本机，后台跑
/Users/max/codebase/ComfyUI/.venv/bin/python make_ip_candidates.py   # 概念图 → output/ip/concepts/
/Users/max/codebase/ComfyUI/.venv/bin/python make_stage_vert.py      # 舞台 → output/ip/props/
cd /Users/max/codebase/comedy && /Users/max/codebase/ComfyUI/.venv/bin/python rig.py
/Users/max/codebase/tts/bin/python make_laugh.py            # 5 条笑声素材 → audio/crowd/
```

产物：`assets/char.png`（无脸身体 569×737）+ `assets/rig.json`（五官坐标）+ `assets/char_preview.png`（带脸预览）。**改完必须看 `char_preview.png` 确认脸没歪。**

## 每集 runbook

以 EP05 为例。两个解释器**不通用**：`P=/Users/max/codebase/ComfyUI/.venv/bin/python`（有 PIL，管出图/渲染/封面/校验），`T=/Users/max/codebase/tts/bin/python`（有 mlx_audio、**没有 PIL**，管配音/笑声素材）。

| # | 动作 | 命令 | 产物 | 实测耗时 | 过关标准 |
|---|------|------|------|----------|----------|
| 1 | 写稿 | 新建 `script_ep05.py` | 112 句左右 dict | — | 估时 ≥300s；过 `baozai-standup` 的 10 项自查 |
| 2 | 配音 | `$T gen_voice.py --ep 5` | `audio/ep05/lines/*.wav`、`voice_full.wav`、`timing.json` | 112 句 ≈ 6.4min（RTF≈1） | 抽 3 句听音色；`timing.json` 的 `total` 与估时差 <5% |
| 3 | 配画面 | 编辑 `render.py` 的 `EPISODES`（`render.py:40`） | — | — | 末句 `applause=True`；`intro` 不与首幕章卡挤在一起 |
| 4 | 静帧抽查 | `$P render.py --ep 5 --still 0.8`（**每个时间点单独跑一次**） | `build/still_ep05_*.png` | 秒级 | 片头卡 / 章卡 / AI 插话句 / 末句之后 四张都正常 |
| 5 | 全片渲染 | `$P render.py --ep 5 > build/ep05_render.log 2>&1`（**后台**） | `ep05.mp4`、`build/ep05_mix.wav` | 14390 帧 ≈ 7min（吞吐约 36fps） | 末行 `ffmpeg rc 0`（ffmpeg 报错看 `build/ffmpeg_ep05.log`）；帧数 = `int((total+tail)*30)`，`render.py:639` |
| 6 | 响度归一 | 先 `ffmpeg -i ep05.mp4 -af loudnorm=print_format=json -f null -` 量，再 `ffmpeg -c:v copy -af "volume=+<X>dB,alimiter=limit=0.841:level=false"` | `ep05.mp4`（覆盖） | <1min | -15 LUFS ± 1.5、TP ≤ -1 dB |
| 7 | 封面 | 从 `qa` 报出的无字幕空档抽帧 → `$P make_cover.py <still.png> <主标题> <副标题> <out.png>`（4 个位置参数） | `ep05_cover.png` | 秒级 | 眼睛是睁的、没有章卡压在上面 |
| 8 | 校验 | `$P /Users/max/.qoder/skills/puppet-talk-render/scripts/qa_episode.py --ep 5` | 12 项结果 | <1min | **0 fail**；warn 要逐条判断 |

第 6 步的增益不是常数，每次都要先量。第 5、6 步之间不要改 `render.py`，改了不生效（进程已加载）。

## 情侣日常档（EP06 起）与批量出片

第二角色与家庭舞台的一次性建设：

```bash
# 女包仔概念图 → 抠图定骨架（--pad 0：擦除框正好等于补绘椭圆，睫毛才留得下来）
$P rig.py --who girl --src /Users/max/codebase/ComfyUI/output/ip/concepts/girl_b.png \
   --eyes '421,447,59,61;606,446,60,62' --mouth '515,510,45,10' --pad 0   # → assets/char_girl.png + rig_girl.json
cd /Users/max/codebase/tts && $T make_girl_voice.py    # 造音色→克隆→按 F0 比值验收→ out/voices/girl_locked.wav + girl_voice.json
# 舞台：home_living.png / home_kitchen.png → /Users/max/codebase/ComfyUI/output/ip/props/
```

一集只需要一个剧本文件：`script_epNN.py` 里写 `SCENE = dict(title, room, cover)` + `LINES`，
`render.py:couple_episode()` 自动接上舞台和两个角色，**不用改任何引擎代码**。

```bash
cd /Users/max/codebase/comedy
$P make_episode.py --ep 21 --ep 22 --ep 23 ...   # 配音→成片→封面→QA，串行
```

实测（M1 Pro 32GB）：`gen_voice.py` 62–72 句 ≈ 190–230s（RTF≈1，每集重新 load 模型），
`render.py` 6000 帧 ≈ 130–150s（响度归一已在编码里自动做完），封面 + QA ≈ 30s
⇒ **一条链 ≈ 5–6min/集**。同时开两条链能摊平到 ≈2.5–3min/集，30 集约 90 分钟。

**并发上限就是二**。三条链同时跑时三个 MLX 进程（各约 4GB）互相饿到 6–16s/句，并在半集中途死掉，
剩下的只有半套 `lines/*.wav`、没有 `timing.json`。所以 `make_episode.py` 的配音固定带 `--resume`：
`lines/{id}.text` 边车险住当前文本，缺句/改句才重生成。挂了先查 `build/voice_epNN.log`，
再等**在跑的链少于两条**，用同一批 `--ep` 重排队即可，已完成的集不受影响。渲染日志在
`build/render_epNN.log`，ffmpeg 报错看 `build/ffmpeg_epNN.log`。

## 数据流

```
script_epNN.py ──gen_voice.py──> audio/epNN/{lines/*.wav, voice_full.wav, timing.json}
                                          │                       │
   ComfyUI 出图 ──> assets/char.png ──render.py<───────────────────┘
   （rig.py 标定）      │  ├─ build/epNN_mix.wav（观众声 + 人声）
                       └──> epNN.mp4 ──ffmpeg 响度──> epNN.mp4 ──qa_episode.py──> 交付
```

`timing.json` 是稿与画面之间**唯一**接口：`{total, sample_rate, lines:[{id, text, start, end, duration, punch, laugh, applause, who, chapter}]}`。它坏了先查 `gen_voice.py`，不要改 `render.py`。

## 故障定位

| 症状 | 出在哪环 | 处置 |
|------|----------|------|
| 两句话挤在一起/字幕重叠 | 稿 | `pause_after` 太小，见 `baozai-standup` 的停顿表 |
| 章卡压住上一句字幕 | 稿 | 章卡句 `pause_before ≥ 1.25`（QA 的 `chapter-card` 项会算） |
| 笑声听不见 / 盖过台词 | 混音 | 见 `puppet-talk-render` 的 audio-mix，改 `_laugh`/`_claps` 增益 |
| 响度顶爆、削顶 | 归一 | `alimiter` 漏了 `level=false` |
| 脸歪、五官错位、眨眼位置不对 | 形象 | `rig.json` 坐标错，重跑 `rig.py` 并看 `char_preview.png` |
| AI 那句听起来还是人 | 配音 | `gen_voice.py` 的 `robotize()` 没生效，用频谱质心验证（QA 的 `ai-voice`） |
| 结尾笑声被切一刀 | 渲染 | 末句没 `applause=True`，`render.py:635` 不补 1.4s 余量 |
| 时长/帧数对不上 | 渲染 | `timing["total"]` 与 `voice_full.wav` 实际长度不一致 |
| `ModuleNotFoundError`：`mlx_audio` 或 `PIL` | 环境 | 走错了解释器。配音用 `T`，画面用 `P`，两个 venv 不互通 |
| 换台机器全跑不通 | 环境 | 全是绝对路径，见下 |

## 移植注意

这套 skill 里的路径写死了本机布局（`/Users/max/codebase/{comedy,tts,ComfyUI}`），且 `assets/char.png`、`v2_cheeky.wav`、FLUX 权重都不在仓库里。别人拿去要改：`render.py` 顶部的 `ROOT/PROPS`、`gen_voice.py` 的 `MODEL/REF`、`qa_episode.py` 的 `--root`，并重新跑一遍建形象与锁音色。

## Resources

- [references/ip-build.md](references/ip-build.md) — 概念图 prompt 配方、`build_alpha` 抠图为什么用「边界泛洪 + 最大连通块」、五官坐标怎么标定、换形象的检查清单。
- 三个子 skill：`baozai-standup`、`qwen3-tts-voice`、`puppet-talk-render`（含 `scripts/qa_episode.py`）。
