---
name: baozai-standup
description: 包仔（原创小笼包吉祥物）竖屏脱口秀系列的 IP 圣经与写稿流程：三幕专场结构、script_epNN.py 台词数据格式、punch/laugh/pause/chapter/AI 打断标记、时长估算与爆点设计。Use when 写或改包仔段子、规划新一集 EP、评估段子好不好笑、检查人设/音色/前作 callback 是否一致。不负责配音与渲染（见 qwen3-tts-voice、puppet-talk-render）。
---

# 包仔脱口秀 · 写稿

## Overview

固定原创 IP「小笼包 · 包仔」的竖屏单口喜剧系列。工程目录 `/Users/max/codebase/comedy`，一集从想法到成片分三段，各自有 skill：

1. **本 skill** — 定主题、写 `script_epNN.py`（台词 + 节奏标记）。
2. `qwen3-tts-voice` — 用锁定音色逐句生成 `audio/epNN/voice_full.wav` + `timing.json`。
3. `puppet-talk-render` — 2D 木偶舞台渲染、观众声混音、响度、封面、QA。

写稿前先读 [references/ip-bible.md](references/ip-bible.md)（人设、系列日志、已被否掉的写法），落笔时对照 [references/script-schema.md](references/script-schema.md)（字段、时长公式、自检清单）。

## 一集的产出步骤

1. 选题：一个「AI 时代普通人的具体处境」+ 一个包子视角的物理梗（漏汤、蒸笼、发酵、保质期）。
2. 定结构：三幕（例：职场 → 恋爱 → 自我），每幕一个转折，最后一幕必须给观点，不只是搞笑。
3. 写 `script_epNN.py`：`LINES = [dict(...), ...]`，字段与取值见 schema。EP04 是 112 句 / 2105 字 / 88s 停顿 ≈ 7 分 56 秒。
4. 自检：句长 ≤ 34 字、章卡句 `pause_before >= 1.25`、末句 `applause=True`、至少 2 处 callback 前作、1 处 AI 打断。
5. 交给配音与渲染 skill；成片后用 `puppet-talk-render/scripts/qa_episode.py --ep NN` 复核。

## 硬规则（来自用户反馈）

- **时长**：正片 5 分钟以上。60 秒一条被判「太短、没看点爆点」，EP04 8 分钟专场才通过。
- **内涵**：至少一段「笑着笑着不笑了」的落点（EP04：「我唯一没教它的，是我也会累」），且紧跟一个笑点把气氛拉回来，不要变成说教。
- **爆点**：每 20–30 秒一个 `punch=True`；至少一句能被单独截出来当标题的话（EP04：「你们真正该怕的，是停电」）。
- **意外**：让舞台上的 AI 真的开口打断一次以上（`who="ai"`），观众反应要跟着变。
- **时效**：用当下语境（降本增效、毕业、情绪价值、秒回、人机协同、绩效、周报黑话）。老梗（画饼、996 口号）会被直接否。
- **不卖惨**：自嘲可以，怨气不行；结尾留一点暖意。

## Resources

- [references/ip-bible.md](references/ip-bible.md) — 人设、世界观、音色、EP01–EP04 系列日志与 callback 网、平台规格、禁忌。
- [references/script-schema.md](references/script-schema.md) — `LINES` 字段全解、停顿/笑声取值表、时长估算公式、三幕模板、自检清单。
