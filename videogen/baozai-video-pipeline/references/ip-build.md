# 建形象与骨架（一次性）

目标：把一张扩散模型出的概念图，变成**可编程的木偶**——身体贴图 + 五官坐标。渲染时逐帧重画眼睛和嘴，所以 8 分钟里长相 100% 一致。

## 1. 出概念图

`/Users/max/codebase/ComfyUI/make_ip_candidates.py`，一次出多个候选（`bao` / `hedgehog` / `mushroom`），存到 `output/ip/concepts/`。

Prompt 分两段，后半段 `TAIL` 是**所有形象共用**的风格锁：

```
flat 2D cartoon mascot character, thick clean soft outlines, flat pastel colors,
no shading, simple black dot eyes, tiny mouth, soft pink blush, tiny stubby limbs,
wearing a small black bow tie, deadpan cute expression, yuru-chara style,
full body, centered, generous margin, plain warm cream background, no text
```

前半段只写"是什么"：

```
a small round steamed soup dumpling mascot creature, pleated top like a little bun
hairstyle, creamy white body, one tiny soup drop on its cheek,
```

每句都在后面被代码依赖，别随手删：

| 短语 | 为什么必须有 |
|------|--------------|
| `thick clean soft outlines` | 轮廓是封闭黑边，`build_alpha` 靠它挡住泛洪，否则身体内部被吃掉 |
| `flat pastel colors, no shading` | 没有渐变 → 色差阈值能一刀切；有阴影就会切出洞 |
| `full body, centered, generous margin` | 抠图后包围盒完整，四边留白才不会切到手脚 |
| `plain warm cream background` | 背景是纯色且贴近角色本色，抠完边缘不会留一圈白毛边 |
| `no text` | 图上带字就废了，得重跑 |

改风格可以换主体描述，**`TAIL` 不要动**。

调用方式（所有出图脚本同一个模式）：读 `bench_flux2_klein.json`，改节点 `"3"` 的 `text`、`"4"` 的 `width/height`、`"7"` 的 `noise_seed`、`"12"` 的 `filename_prefix`，POST `http://127.0.0.1:8188/prompt`，轮询 `/history/{pid}`，`/view` 下载。1024² 约 68s/张。多候选时给每个候选换 `label` 但**同一个 seed**，这样差异只来自描述文本。

## 2. 抠图：`build_alpha`（`rig.py:18`）

不用「全局色差阈值」，用**边界泛洪**：

```python
bgish = np.abs(rgb - rgb[5, 5]).sum(2) < 95      # 与背景色够近
seed  = 只取图像四条边上的 bgish                 # 从边界起步
outside = ndimage.binary_propagation(seed, mask=bgish, structure=np.ones((3,3)))
alpha   = ~outside
# 再取最大连通块，把飘在外面的碎片扔掉
```

差别在于：角色**身上**也有和背景同色的米白（肚子高光）。全局阈值会把肚子抠穿；从边界泛洪则被封闭黑边挡住，进不去。容差 `95` 是故意放宽的——顺便把概念图里画在脚下的**地面投影**一起吃掉，省得 puppet 带一块假影子。

`ndimage.label` 后只保留最大连通块：小碎片（掉出来的汤滴、噪点）会让 puppet 周围有鬼影。

## 3. 抹五官：`inpaint`（`rig.py:37`）

概念图自带眼睛和嘴，但渲染时要用 `draw_eye`/`draw_mouth` 逐帧重画（眨眼、口型），所以底图上的五官必须先擦干净，否则动画脸和静态脸会叠成重影。

做法：按 `EYES`/`MOUTH` 坐标外扩 10–14px 建 mask → `distance_transform_edt` 取最近非 mask 像素做初始填充 → 迭代 80 次「mask 内用高斯模糊(σ=1.3)结果覆盖」→ 收敛成平滑的米白面皮。

**只擦 mask 内**，所以迭代次数少了会在洞边缘留一圈糊痕；80 次是实测干净的下限。

## 4. 标定五官坐标

`rig.py:14` 的 `EYES`/`MOUTH` 写在**原概念图坐标系**（1024×1024），不是裁剪后的：

```python
EYES = [(414, 482, 52, 57), (615, 482, 54, 57)]   # cx, cy, w, h
MOUTH = (515, 535, 52, 14)                        # cx, cy, w, h
```

找坐标的可靠办法：把概念图叠一层 32px 网格再放大看，或直接在图上用 `d.line` 画十字试错。两个眼宽差 2px 是原图本身左右不对称，照抄即可（`draw_eye` 会按各自尺寸画）。

`main()` 里裁完会输出 `origin = (bbox[0], bbox[1])`，并把坐标减去 origin 写进 `rig.json`——**渲染只读 `rig.json`**，所以改了 `rig.py` 常量必须重跑 `rig.py`，不能只改 json。

验收只看一张图：`assets/char_preview.png`（身体 + 重画的 neutral 五官）。眼睛位置偏 5px 以上，眨眼就会看起来像脸在抖。顺手看 `char_states.png` 的四格表情（口型 0.0/0.35/0.75 + 闭眼）。

## 5. 剩下的素材

- 舞台 / 麦克风 / AI 机器人贴图：见 `puppet-talk-render` 的 `references/visual-system.md`「加新道具 / 新舞台」。
- 观众笑声 `audio/crowd/laugh_{0..4}.wav`：`make_laugh.py`，用锁好的音色念「哈哈哈哈哈」，一次性。参数见 `qwen3-tts-voice`。

## 换形象检查清单

1. 备份 `assets/char.png`、`assets/rig.json`（`rig.py` 会直接覆盖）。
2. 新图存到 `concepts/`，改 `SRC` 指向它。
3. 重标 `EYES`/`MOUTH`，跑 `rig.py`，看 `char_preview.png`。
4. 若新形象宽高比变了（原为 569×737）：`render.py` 的 `CH_H=700`/`CH_FEET=1660`/`CH_CX=515` 要重算，否则脚不站在地面上。
5. 跑 `render.py --ep N --still <爆点秒>` 确认口型和跳点还贴脸。
6. **红线**：形象必须自创，不得二创他人角色；对外发布时说明观众笑声是合成的。
