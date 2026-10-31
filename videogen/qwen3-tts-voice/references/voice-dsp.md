# 角色变声 DSP 与客观验证

## 包仔的 AI 领导（现行配方）

```
asetrate=19680,aresample=24000,atempo=1.2195122,highpass=f=120,lowpass=f=7000,aecho=1.0:0.85:18:0.22
```

| 段 | 作用 | 算法 |
|----|------|------|
| `asetrate=19680` | 降调 | `24000 × 2^(-3.4/12) ≈ 19680`，约 **-3.4 半音**，同时拉长时长 |
| `aresample=24000` | 回到工程采样率 | 必须紧跟 `asetrate`，否则后续滤镜按错采样率算 |
| `atempo=1.2195122` | 补回时长 | `atempo = 24000 / asetrate`，只改速度不改音高 |
| `highpass=f=120` | 去掉降调后的浑浊低频 | 降调会把基频推到 100Hz 附近 |
| `lowpass=f=7000` | 削高频空气感 → 电子味 | 调低更「机器」，调高更清楚 |
| `aecho=1.0:0.85:18:0.22` | 金属尾巴 | 参数依次是 `in_gain:out_gain:delay_ms:decay`；**`in_gain` 必须写 1.0**，默认 0.6 会让 AI 句比人声小一截 |

改音高只改 `asetrate`，并把 `atempo` 同步改成 `24000/asetrate`；升调用 `asetrate > 24000`（此时 `atempo < 1`）。

## 其他角色配方（同一模型、同一参考音频出，再 DSP）

| 角色 | 链 |
|------|----|
| 小女孩 / 少年 | `asetrate=29000,aresample=24000,atempo=0.8276` |
| 低沉大叔 / 旁白 | `asetrate=20400,aresample=24000,atempo=1.1765,highpass=f=90` |
| 电话 / 对讲机 | `highpass=f=300,lowpass=f=3400,aecho=1.0:0.8:30:0.3,volume=1.5` |
| 回忆 / 内心独白 | `lowpass=f=5200,aecho=1.0:0.7:60:0.35,volume=0.8` |
| 广播 / 系统音 | 现行 AI 配方 + `volume=1.1` |

原则：变声只做「音色差」，不要做「语气差」——语气靠文本和标点，模型自己会念。

## 客观验证

处理完不要只靠耳朵，跑三个数：

1. **频谱质心**（判断是否更「闷/金属」）：AI 句应明显低于相邻人声句。包仔实测 AI 1916 / 2256 Hz，相邻人声 2500–2770 Hz。

   ```python
   import numpy as np
   def centroid(x, sr):
       s = np.abs(np.fft.rfft(x * np.hanning(len(x))))
       f = np.fft.rfftfreq(len(x), 1 / sr)
       return float((s * f).sum() / (s.sum() + 1e-9))
   ```

2. **峰值 / RMS**：AI 句峰值应与相邻句同量级（实测 0.49 vs 0.52–0.60）。若明显偏小，先查 `aecho` 的 `in_gain`。
3. **说话人 embedding 余弦**：`model.extract_speaker_embedding(mx_array, 24000)`，与 `REF` 比较，锁音阶段要求 ≥ 0.99；变声后会自然下降，变声句不必卡这个阈值。

成片级的自动检查（时长、响度、AI 音色、观众反应）见 `puppet-talk-render/scripts/qa_episode.py`。

## 坑

- `atempo` 与 `asetrate` 顺序错了会得到「又慢又低沉」或「又快又尖」。
- 变声后必须重新裁静音（`gen_voice.py` 里 `robotize()` 末尾又调了一次 `trim_silence`），否则句尾回声会把时间轴顶长。
- 时间轴要用**变声后**的长度；先写 timing 再变声会导致字幕比声音晚。
- AI 句超过 20 字容易糊：回声叠加 + 降调会让尾音黏在一起，长句拆成两句更好。
- 听不清时优先把 `lowpass` 提到 8000，而不是加 `volume`——加音量只会把回声一起放大。
