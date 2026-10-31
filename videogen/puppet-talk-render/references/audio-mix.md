# 观众声与响度（audio mix）

代码都在 `render.py:482-607`（`_shift/_concat/_ir/_laugh/_claps/_murmur/_chime/_duck/build_mix`）。全部是程序合成，不引入任何外部音效素材，唯一的外部输入是 `make_laugh.py` 用包仔自己音色生成的 5 条笑声。

## 信号流

```
audio/epNN/voice_full.wav        纯人声（qwen3-tts-voice 产出，24kHz mono）
  └─ render.py main:635          末句 applause → 尾部补 1.4s 静音
      └─ build_mix:568           叠观众床 → build/epNN_mix.wav
          └─ ffmpeg aac 192k     合进 mp4（此时 LUFS 大约在 -20）
              └─ volume + alimiter   静态归一到 -15 LUFS
```

`EPISODES[ep]["crowd"]=False` 时 `build_mix` 直接返回人声（EP01 就是这么出的，所以 QA 里观众声那项没有参考值）。

## 各声部参数

| 声部 | 函数 | 参数 | 触发时机 |
|------|------|------|----------|
| 底噪人声床 | `_murmur:542` | 对数高斯谱峰 520Hz（σ=0.6 octave），0.11Hz+0.23Hz 双正弦起伏，峰值 **0.010** | 全片常驻 |
| 笑声 | `_laugh:503` | 层数 `6+5*level`，每条 take 随机重采样因子 0.84–1.18（变调+变压），起点随机 `0–(0.9+0.25*level)s`，单层增益 0.25–1.0；干声 0.55 + FFT 卷积混响 0.8；归一后总增益 **`0.128+0.051*level`** | 该句 `end+0.06s`，`laugh=1/2/3` |
| 掌声 | `_claps:519` | 900–6500Hz 带通噪声 × 指数衰减（70–140）做 16 个 clap 变体，密度 **42 次/秒**，加 400–2600Hz「 roar」0.06；头尾淡入 0.14s / 淡出 0.5s；峰值 **0.46**，时长 **1.95s** | 该句 `end+0.10s`，`applause=True` |
| 混响 IR | `_ir:493` | 0.6s 指数衰减（-5.0/s）噪声，前 14ms 清零（保留直达声），Hann 9 点平滑，能量归一 | 只作用于笑声 |
| AI 提示音 | `_chime:553` | 987.77Hz（衰减 6.5/s）+ 0.55×1318.5Hz（衰减 8.5/s），6ms 起振，峰值 **0.12** | `who=="ai"` 的句子 `start-0.45s` |
| 让路（duck） | `_duck:562` | 人声整流 → 40ms 窗 RMS → `1-0.65*clip(env/0.05)` → 90ms 平滑 | 乘在整条观众床上 |

最后 `out = voice + bed`，尾部 0.6s `linspace(1,0)**1.2` 主淡出，峰值若 >0.96 则整体缩放。

三个"隐式约束"，改参数前先看：
- **0.05 是 duck 的人声满度参考**。配音响度变了（比如换了语速或做了 DSP），`env/0.05` 就饱和或失灵，观众声会顶掉台词或全程消失。
- **爆点后要留口**。笑声从本句 `end+0.06s` 起，单次事件缓冲 `1.35+0.35*level+0.9` = 2.6–3.3s，且每条 take 再随机错位，所以下一句起点（= 本句 `pause_after`）越早，越会被笑声压台词。写稿时 `laugh>=2` 建议 `pause_after>=0.85`。
- **`_chime` 提前 0.45s，AI 句 `pause_before` 必须 ≥0.7**，否则提示音落在上一句尾音上。

## 笑声素材

`/Users/max/codebase/comedy/make_laugh.py` → `audio/crowd/laugh_{0..4}.wav`（5 条，24kHz mono，1.12–1.64s）。文本就是 `哈哈哈哈哈` / `哈 哈 哈 哈` / `嘿嘿哈哈哈哈哈` 五种断句，用 Base 克隆 `v2_cheeky` 参考音频。

- 一定要 `trim()` 掐头去尾，不然随机起点会把静音叠进观众床。
- 5 条已经够：`_laugh` 里随机取源 + 随机变调 + 随机错位 + 随机增益，最多 21 层同时响，听起来就是"一屋子人"。要更像可以加到 8 条，成本是重新生成一次（约 20s）。
- 想换成"真实观众"素材也行，但保持 24kHz mono、峰值归一、每条 1–3s，文件名 `laugh_*.wav` 就会被 `CROWD.glob` 收进去。

## 电平怎么量（踩过的坑）

第一版校验脚本量的是 `end+0.15 … end+0.75` 这一小段的 RMS，测出 -11.5dB，误判成"笑声太响"。原因：

1. `_laugh` 里每条 take 起点随机在 0–1.15s 之间，**反应是"渐起"的**，前 0.75s 只有一两层在响；
2. 爆点句后 0.45s 内常常已经是下一句人声，把台词算进了"观众声"。

正确做法（`qa_episode.py` 的 `crowd` 项）：在每个 `laugh/applause`  cue 之后，**在下一个 cue 到达之前**的窗口里，用 0.4s 滑动窗取 RMS **最大值**（这就是"反应最响的那一下"），再和全片人声 RMS 比；只有存在余量（下一句不会进来）的 cue 参与统计。取所有 cue 的中位数：

| 集 | 观众声相对人声 RMS（中位） |
|----|---------------------------|
| EP02 | -12.2 dB |
| EP03 | -12.9 dB |
| EP04 | -13.3 dB |

这是已验收的基准，QA 阈值按它定：**-16 … -2 dB 为 PASS**，≥-19 dB（明显听不见观众）为 WARN，更糟 FAIL。要整体调，改 `_laugh` 的 `0.128+0.051*level`（笑声）和 `_claps` 的 `0.46`（掌声），一处改完三层同步；不要靠改 `_duck` 的 0.65 来"让它响"，那会让台词和观众一起糊。

## 响度归一

竖屏平台（抖音/B站/小红书）比电视台宽松，但混在信息流里 -20 LUFS 会明显比邻片小声，所以定 **-15 LUFS、TP ≤ -1 dB**。

```bash
# 1) 量：用最终成片（或 mix.wav）测 Integrated
ffmpeg -i ep05.mp4 -af loudnorm=print_format=json -f null - 2>&1 | tail -12
# 2) 静态增益 + 限幅（视频流 copy，不重编码）
ffmpeg -y -i ep05.mp4 -c:v copy \
  -af "volume=5.6dB,alimiter=limit=0.841:level=false:attack=5:release=80" \
  -c:a aac -b:a 192k ep05_norm.mp4 && mv ep05_norm.mp4 ep05.mp4
```

- `volume` = `target_I - measured_I`，四舍五入到 0.1dB；EP04 的 `build/ep04_mix.wav` 实测 **I -20.63 LUFS / TP -2.11 dB / LRA 2.5**，用 +5.6dB → 成片 -15.1 LUFS / -1.50 dBTP。
- **`alimiter` 默认 `level=true`**，它会自己做自动增益，实测多推约 8dB，直接把片子顶到 -12 LUFS 且削顶。必须写 `level=false`。这条是 EP04 唯一的返工原因。
- `limit=0.841` ≈ -1.5 dBFS 天花板。AAC 编码后 TP 会漂高 ~0.6dB（EP04 最终 -0.86dB），仍在安全区。
- 不用 `loudnorm` 动态模式做最终归一：它的滑动窗会把笑声反应压扁，听起来"没劲"。
