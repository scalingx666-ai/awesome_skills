# TTS 环境与资产

## 目录

```
/Users/max/codebase/tts/
├── bin/                     # uv venv（Python 3.12.15）
├── models/
│   ├── Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16/   # 造音色（4.2G）
│   └── Qwen3-TTS-12Hz-1.7B-Base-bf16/          # 克隆/锁音（4.2G）
├── out/
│   ├── voices/{v1_soft,v2_cheeky,v3_deadpan}.wav   # 音色候选
│   ├── mushu/               # 锁音验证样本
│   └── bench/               # 速度基准输出
├── voice_candidates.py      # VoiceDesign 造候选
├── lock_voice.py            # Base 克隆 + 说话人相似度验证
├── tts.py / bench_tts.py    # 单句冒烟测试 / RTF 基准
```

依赖：`mlx-audio 0.6.3`、`mlx 0.32.4`、`numpy 2.5.4`、`scipy 1.18.1`、`modelscope 1.40.2`。

## 重建环境

```bash
cd /Users/max/codebase/tts
uv venv --python 3.12 && uv pip install mlx-audio modelscope
```

## 重新拉权重（HF 直连在本机不通，走 ModelScope）

```bash
/Users/max/codebase/tts/bin/python - <<'PY'
from modelscope import snapshot_download
for repo, dst in [("mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16", "models/Qwen3-TTS-12Hz-1.7B-Base-bf16"),
                  ("mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16", "models/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16")]:
    snapshot_download(repo, local_dir=dst)
PY
```

先确认仓库在 ModelScope 上存在同名镜像；找不到就让用户确认来源，不要擅自从别的站点的链接下载。

## 关键常量（`/Users/max/codebase/comedy/gen_voice.py` 顶部）

```python
TTS      = Path("/Users/max/codebase/tts")
MODEL    = TTS / "models/Qwen3-TTS-12Hz-1.7B-Base-bf16"
REF      = TTS / "out/voices/v2_cheeky.wav"
REF_TEXT = "大家好，我是今天的脱口秀演员。你们可能看不出来，我其实特别紧张。"
SR       = 24000
```

`REF` 与 `REF_TEXT` 是音色的身份证：**任何一集都不许改**。要改就当作新 IP 重走锁音流程。

## 加一个新角色/新 IP

1. 复制 `voice_candidates.py`，改 `VOICES` 字典（key = 文件名，value = 中文音色描述），跑一次，人耳挑。
2. 复制 `lock_voice.py`，改 `REF`/`REF_TEXT`/`LINES`，跑一次，看每行 `sim_vs_ref`；全部 ≥ 0.99 才算稳。
3. 描述里给「年龄感 + 音色质地 + 语速 + 尾音 + 情绪底色」五要素，例如包仔的 `v2_cheeky`：
   `清亮俏皮的少年音，语速偏快，尾音上扬，透着机灵和坏笑`。
4. 只描述声音，不要在 `instruct` 里写台词内容；`text` 用一段将来真会出现的开场白，试听才有意义。

## 冒烟测试

```bash
cd /Users/max/codebase/comedy && /Users/max/codebase/tts/bin/python - <<'PY'
import sys; sys.path.insert(0, "/Users/max/codebase/tts")
from mlx_audio.tts.utils import load_model
m = load_model("/Users/max/codebase/tts/models/Qwen3-TTS-12Hz-1.7B-Base-bf16")
r = list(m.generate(text="测试一下，我还是我。",
                    ref_audio="/Users/max/codebase/tts/out/voices/v2_cheeky.wav",
                    ref_text="大家好，我是今天的脱口秀演员。你们可能看不出来，我其实特别紧张。",
                    lang_code="chinese"))
print(len(r), r[0].sample_rate)
PY
```
