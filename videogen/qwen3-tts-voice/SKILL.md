---
name: qwen3-tts-voice
description: 用本地 Qwen3-TTS（MLX，Apple Silicon）生成固定音色中文配音：VoiceDesign 造音色、Base 克隆锁音、逐句生成 + 静音裁剪 + 停顿时间轴 timing.json、机器人/角色变声 DSP、说话人 embedding 相似度与频谱验证。Use when 生成配音、换音色、语速停顿不对、TTS 报错或漂移、做 AI 角色的机械音、给观众做笑声素材。
---

# 本地 Qwen3-TTS 锁定音色配音

## Overview

一套「先造音色、再永久克隆」的本地配音流程，跑在 M1 Pro 上，无需联网推理。包仔系列用它把 112 句台词变成 `voice_full.wav` + `timing.json`，供 `puppet-talk-render` 做口型与字幕。

- 环境：`/Users/max/codebase/tts`（uv venv，Python 3.12.15，mlx-audio 0.6.3，mlx 0.32.4）
- 模型：`models/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`（造音色）、`models/Qwen3-TTS-12Hz-1.7B-Base-bf16`（克隆）
- 输出：24kHz 单声道 int16 wav

## 三步锁音（新 IP 时才做）

1. 造候选：`voice_candidates.py` → `model.generate_voice_design(text, instruct, language="chinese")`，`instruct` 是一句中文音色描述。产出 `out/voices/*.wav`，**人耳试听**后选一个。
2. 克隆验证：`lock_voice.py` → `model.generate(text=..., ref_audio=REF, ref_text=REF_TEXT, lang_code="chinese")`，再用 `model.extract_speaker_embedding(audio, 24000)` 与参考音频算余弦。**≥ 0.99 才算锁住**（包仔实测 0.992–0.994）。
3. 固定 `REF` 与 `REF_TEXT` 两个常量，之后所有集都不许改；改音色 = 换 IP，需用户同意。

## 加第二个角色（女包仔「小满」）

`cd /Users/max/codebase/tts && /Users/max/codebase/tts/bin/python make_girl_voice.py`
→ `out/voices/girl_locked.wav` + `girl_voice.json`（含 `ref_text` 与 `pitch_factor`）。三个坑：

1. **说话人 embedding 分不出"是不是同一个人"**：这套栈里任意两个中文声的余弦都在 0.95–0.99，
   用它当"和男主不同"的门槛永远过不了。它只能当**稳定性**指标（同一音色逐句 ≥0.95）。
2. **区分度要用中位 F0 比值**：`voice_pitch.py <wav>` 打印 dur / f0 中位数 / p25 / p75 / 浊音占比 / 频谱质心
   （自相关法，60–500Hz 搜基频，`ac[pick] < 0.3*ac[0]` 当清音门）。女声目标：`median_f0(女)/median_f0(男) ≈ 1.30`，低于 1.25 判"听不出是两个人"。
3. **Base 克隆会把音高拽回参考说话人的音区**：393Hz 的 VoiceDesign 参考，克隆出来的句子只有 316–343Hz
   （比值掉到 1.06）。所以验收要量**克隆后的行**，再算
   `pitch_factor = clamp(1.30 × male_f0 / median(clone_f0), 1.0, 1.30)`（实测 1.0955），
   由 `gen_voice.py` 的 `retune()` 逐句套 `asetrate={SR*f},aresample={SR},atempo={1/f}`（保时长上抬音高）。

两个角色的实测语速不同：**包仔 ≈5.2–5.7 字/秒，小满 ≈4.9–5.0 字/秒**（按 5.4 / 5.0 分角色规划，别混算），
比脱口秀档的 4.7 字/秒快，估时长别沿用老数字。台本里 `who` 取 `bao`/`girl`，
`VOICES` 里没有的角色（`bao_mom`/`girl_mom`）走"借主角音色 + `PITCH` 下压"，
`PITCH = {"bao_mom": 0.80, "girl_mom": 0.82}`——不新增音色，只加变声。

按这套速率，情侣日常档 870 字 + 32s 停顿 ≈ 3 分 05 秒（EP06 实测 197.7s、EP21 实测 201.8s）。

## 生成一集配音

```bash
cd /Users/max/codebase/comedy
/Users/max/codebase/tts/bin/python gen_voice.py --ep 5            # 后台跑，112 句约 6 分钟
/Users/max/codebase/tts/bin/python gen_voice.py --ep 7 --resume   # 只补跑缺失/文本改过的句子
```

产出 `audio/epNN/lines/{id}.wav`、`voice_full.wav`（末尾自动 +0.35s）、`timing.json`。逐句字段与停顿语义见 `baozai-standup/references/script-schema.md`。

`--resume` 认的是 `lines/{id}.text` 边车（写 wav 的同时写它当初的文本）：文本一致才复用，改过一个字就重生成。所以中途挂掉的集能接着跑，`timing.json` 和 `voice_full.wav` 每次都整体重建。老 wav 没有边车，`make_episode.py` 的 `prime_resume()` 用 mtime 判定（wav 比 `script_epNN.py` 新 = 出自当前文本）补写。

实测：单句生成 1.8–5.7s（约等于实时），语音长度 ≈ 5.4 汉字/秒；模型加载一次约 10s 级，别为省时间反复重启进程。**同时最多跑两条配音链**——三个 MLX 进程（每个常驻约 4GB）会互相饿到 6–16s/句并在半集中途死掉。

## AI / 机器人角色声

同一锁定音色生成后再 DSP（`gen_voice.py` 里 `robotize()`，对 `who="ai"` 的自动生效）：

```
asetrate=19680,aresample=24000,atempo=1.2195122,highpass=f=120,lowpass=f=7000,aecho=1.0:0.85:18:0.22
```

约降 4 个半音再拉回原时长，加高通/低通与短回声。`aecho` 的第一参数 `in_gain` 必须显式写 `1.0`（默认 0.6 会让 AI 句子明显偏小声）。验证看频谱质心：AI 句应低于相邻句（包仔实测 1916/2256 Hz vs 2500–2770 Hz）。

## 观众笑声素材

`make_laugh.py` 用同一锁定音色念「哈哈哈哈哈」等 5 条 takes 存进 `audio/crowd/laugh_*.wav`；叠多少层、变调多少由渲染端随机化（见 `puppet-talk-render`）。**不要**用网络音效包，音色会和全片脱节。

## 常见坑

- 改完 `script_epNN.py` 必须重启生成进程：模块已导入，热改无效。
- 复用旧 wav 时，`who` 要在「生成 / 复用」分支**外面**取：只在生成分支里赋值，会让复用句挂着上一句的说话人进 `timing.json`，字幕颜色全错。
- 一次生成一整段长文本会漂移/吞字 → 坚持一句一生成。
- `r.audio` 是 MLX array，用 `np.asarray(r.audio.tolist(), dtype=np.float32)` 转，别直接 `np.array()`。
- 采样率断言 24000；换模型要一起改 `SR` 与 `robotize` 里的 `asetrate`。
- 数字、英文缩写、时间读法不稳（"36度5" 可以，"007" 会念怪）→ 直接在文本里改写法。
- 停顿只靠 `pause_before/after`，不要在文本里塞空格。
- 与 ComfyUI 出图同时跑会抢内存，串行执行。

## Resources

- [references/tts-env.md](references/tts-env.md) — 环境重建、模型下载（ModelScope）、目录与常量位置、加新音色。
- [references/voice-dsp.md](references/voice-dsp.md) — 变声参数逐项解释、其他角色声配方、如何用频谱/嵌入做客观验证。
