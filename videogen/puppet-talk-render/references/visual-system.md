# 视觉系统

## 画布与站位常量（`render.py:25`–`38`）

| 常量 | 值 | 含义 |
|------|----|------|
| `W,H,FPS` | 1080×1920, 30 | 竖屏规格 |
| `CH_H` / `CH_FEET` / `CH_CX` | 700 / 1660 / 515 | 角色高、脚底基线、中心 x |
| `MIC_H` / `MIC_CX` | 470 / 862 | 麦克风 |
| `SUB_Y` | 1690 | 字幕基线（两行时向上排） |
| 机器人 | 高 302，中心 x=158 | 舞台左侧，`key_white` 抠图 |
| 爱心 | 高 54 | 机器人头顶上方 26px |

舞台图取 `stage_vert.png` 的 `0,0,1024,1720` 再 `cover()` 到 1080×1920，并做 0.4px 高斯模糊，避免贴图边缘锐利穿帮。

## 动画参数

| 动作 | 频率/幅度 | 出处 |
|------|-----------|------|
| 呼吸 | 0.27Hz，高 ±1%、宽 ∓0.4% | `render.py:422` |
| 左右摇摆 | 0.13Hz，±2.5px | `render.py:423` |
| 眨眼 | 每 2.0–4.6s 一次，3 帧（0.35/0.0/0.45 开合度） | `blink_track` `render.py:114` |
| 笑点跳点 | 句尾 -0.10s 起 0.42s，上移 11px + 挤压 3% | `punch_track` `render.py:127` |
| 机器人 bob | 0.33Hz，±3px | `render.py:430` |
| AI 青光 | **2.4Hz**，alpha 0.35–0.75 | `render.py:432` |
| 爱心 | 0.29Hz，±7px + 6% 缩放 | `render.py:438` |

青光频率不要超过 3Hz：既是光敏风险，也会在 30fps 下拍频闪烁。

## 口型包络（`load_envelope` `render.py:94`）

45ms 窗 RMS → dB → `clip((db+42)/26,0,1)^0.75` → 攻击 0.55 / 释放 0.22 一阶平滑 → 每帧嘴张开度。`who="ai"` 的句子强制 `amt=0`（机器人说话，包仔闭嘴听），这是「AI 真的在说话」最有用的一个视觉信号。

## 字幕与文字层

- 字号从 54（punch 60）每次 -2 递减，直到 ≤ 2 行且宽度 ≤ `W-170`（`fit_text` `render.py:178`）；描边 6px `(28,20,16)`。
- 颜色：普通白、`punch` 琥珀 `(255,234,172)`、AI 青 `(110,214,255)`（更早用 `(150,232,255)`，在浅色背景上几乎发白，已弃用）。
- AI 句额外在字幕上方画「AI 领导」胶囊（`SUB_Y-74 … SUB_Y-26`）。
- 字幕窗口：`[start-0.08, end+0.45]`。
- 片头卡 0.10–1.40s（标题 88px / 副标题 46px，band 570–870）；章卡在章首句前 1.25–0.12s（编号 72px 琥珀 / 标题 52px，band 604–836）；章标签常驻左上 `(36,118)`，在集数标签 `(36,34)` 下方。

## 关键函数索引

| 功能 | 位置 |
|------|------|
| 每集配置 | `render.py:40` |
| 白底抠图（保留最大连通块 + 0.8px 羽化） | `key_white` `render.py:58` |
| 静态层（舞台/灯牌/角色/麦克风/机器人/阴影/青光） | `build_static` `render.py:266` |
| 单帧合成 | `frame_image` `render.py:397` |
| 眼睛/嘴绘制、抠图与补绘 | `rig.py:46`、`rig.py:61`、`rig.py:18`、`rig.py:37` |
| 混音 | `build_mix` `render.py:568` |
| 余量与总淡出 | `render.py:635`、`render.py:601` |

## 加新道具 / 新舞台

1. 用本地 ComfyUI（`127.0.0.1:8188`）+ FLUX.2 Klein 出图，模板见 `/Users/max/codebase/ComfyUI/make_ai_lead.py`：改 `PROMPT`、`width/height`、`noise_seed`、`filename_prefix`，POST `/prompt`，轮询 `/history/{pid}`，`/view` 下载。约 68s/张（1024²，4 步）。
2. Prompt 关键约束：`flat 2D cartoon mascot`、`thick clean soft black outlines`、`flat pastel colors, no shading`、`full body, centered, generous margin`、`plain pure white background, no text`。换风格时保留这几句，否则 `key_white` 抠不干净。
3. 存到 `/Users/max/codebase/ComfyUI/output/ip/props/`，在 `EPISODES` 里引用；`key_white` 会自动裁到内容包围盒，再按目标高度缩放。
4. 角色本体换姿势：改 `rig.py` 的 `SRC` 与 `EYES`/`MOUTH` 坐标后重跑，会覆盖 `assets/char.png` 与 `rig.json`。**先备份**，坐标错了脸就歪。

## 性能与坑

- 1080×1920@30 实测吞吐约 36fps；EP04（14390 帧）约 7 分钟。必须后台跑，别用前台 2 分钟超时。
- 字体加载是逐帧热点：一律走 `_font()` 缓存（`render.py:170`），章标签走 `_TAG_CACHE`。
- 帧以 raw RGB24 管道喂 ffmpeg（`-fps_mode passthrough`、CRF 20、preset medium、AAC 192k、`+faststart`）；PIL 图必须 `.convert("RGB")` 再 `tobytes()`。
- `--still` 是单值参数，多个 `--still` 只有最后一个生效；要抽查多个时间点就多次调用。
- `--limit N` 渲前 N 帧做快速测试，输出名带 `_test`，不会覆盖母带。
