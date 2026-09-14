# Handouter

Handouter 把用户有权访问的智云课堂回放材料整理成**本地、可追溯的课程工作区**，再把明确的 Prompt 与 Skill 交给用户自己的 Agent 生成 Markdown 讲义。

> 当前阶段：**0.2.0 验收候选**。浏览器资产 ZIP、ffmpeg 音频抽取、SenseVoice 结构化转写、PPT 时间事件、时间区间关联、标准工作区、三档 Agent handoff、输出结构校验和 TUI 均已实现。尚未宣称通过真实智云登录态、整门课程和真实 Agent 的最终语义验收；正式验收步骤见 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。

## 产品边界

```text
已授权智云回放页
      ↓  zhiyun_exporter.user.js v1.4
私有资产 ZIP（PPT + 时间 + private/source.json）
      ↓  build-asset
ffmpeg 音频抽取 / 校验
      ↓
本地 SenseVoice
raw.json + segments.json + transcript.txt
      ↓
PPT 展示事件 × ASR 时间区间关联
      ↓
workspace/<lecture-id>/
      ↓
handoff/PROMPT.md + sources.json + Skill
      ↓
用户自己的 Agent
      ↓
full / deep / summary Markdown
      ↓
validate-note（结构检查，语义仍需人工验收）
```

Handouter **不会默认调用付费 LLM API，不会自动接管用户 Agent，也不会把课程材料上传飞书或其他云服务**。本地 Agent 不等于本地模型：用户自己的 Agent 是否把材料发送给其模型服务商，由用户自行配置和确认。

## 三档讲义

| 模式 | 用途 | 关键约束 |
| --- | --- | --- |
| `full` | 去口癖的忠实整理逐字稿 | 保留讲授顺序、例子、限定、推导和问答，不压缩成摘要 |
| `deep` | 系统化深度讲义 | 可重组和解释；新增推导/例子必须与教师内容区分 |
| `summary` | 快速理解课程 | 保留核心结论及成立条件，不凭空制造考点或作业 |

`use_slides_as_source` 与 `embed_slides` 是两个独立选项：可以让 Agent 参考 PPT 核对公式和术语，但最终输出不插图。

## 安装与环境检查

核心包没有第三方运行依赖，并使用仓库内的标准库 PEP 517 backend，因此全新 venv 可以在**不访问 PyPI**的情况下安装：

```bash
python3 -m venv .venv-clean
.venv-clean/bin/python -m pip install --no-index .
.venv-clean/bin/handouter --help
```

开发态 editable 安装同样不需要下载构建工具：

```bash
.venv-clean/bin/python -m pip install --no-index -e .
```

ASR 需要 `funasr` 和 `torch`；Textual 是可选的高级 TUI 后端。macOS/Unix 在未安装 Textual 时自动使用 Python 标准库 `curses` 后备 TUI。

```bash
PYTHONPATH=src .venv/bin/python -m handouter doctor
```

`doctor` 分开报告 core / media / ASR / TUI 是否可用，不会自动安装或修改环境。

## 推荐：从新版智云资产 ZIP 一键准备

先在已登录、自己有权访问的回放页面运行 `zhiyun_exporter.user.js` v1.4+，得到资产 ZIP。ZIP 本身可能包含临时签名视频地址，属于**私有输入**，不要提交 Git 或直接交给 Agent。

```bash
PYTHONPATH=src .venv/bin/python -m handouter build-asset \
  "/path/to/课程资产包.zip" \
  --lecture-id "course-85721-sub-1965580" \
  --course-title "课程名称" \
  --workspace-root workspace \
  --mode deep \
  --device auto
```

`build-asset` 会：

1. 只在内存中读取 `private/source.json` 的媒体地址；
2. 导入 PPT 图片和安全时间字段，不解包 `private/`；
3. 用 ffmpeg 抽音频，拒绝覆盖，先校验时长再实际解码抽样；坏 stream-copy 会自动退回 AAC；
4. 本地运行 SenseVoice，保存原始结果、标准化时间段和纯文本；
5. 按真实时间区间关联 PPT 展示事件，不把时间关联宣传为语义精准对齐；
6. 建立独立工作区并生成 Agent handoff；
7. 最后运行结构验证。

成功状态是 `handoff_ready`，并明确返回 `agent_was_run: false`。Handouter 不会把“交接准备完成”冒充“讲义已经生成”。

## 其他输入方式

已有转写：

```bash
PYTHONPATH=src .venv/bin/python -m handouter prepare \
  --lecture-id lecture-001 \
  --course-title "课程名称" \
  --transcript /path/to/transcript.txt \
  --slides-zip /path/to/asset.zip \
  --mode full
```

已有本地音频：

```bash
PYTHONPATH=src .venv/bin/python -m handouter build-audio /path/to/audio.m4a \
  --lecture-id lecture-001 --course-title "课程名称"
```

本地视频或用户有权访问的 HTTP(S) 媒体：

```bash
PYTHONPATH=src .venv/bin/python -m handouter build-media /path/to/video.mp4 \
  --lecture-id lecture-001 --course-title "课程名称"
```

只转写或只抽音频也有独立命令：`transcribe`、`extract-audio`。

## 工作区

```text
workspace/<lecture-id>/
├── manifest.json
├── state.json
├── audio/
│   └── source.m4a                 # 可选，不交给 Agent
├── transcript/
│   ├── raw.json                   # 原始 ASR + 模型/参数
│   ├── segments.json              # start_ms/end_ms；未知则 null
│   └── transcript.txt
├── slides/
│   ├── images/
│   ├── index.json                 # 展示事件；允许老师回翻旧页
│   └── alignment.json             # 仅时间区间关联
├── handoff/
│   ├── PROMPT.md
│   └── sources.json
└── notes/
```

原始输入不被覆盖。新讲义使用 `notes/<mode>-NNN.md`，既有输出不会被重写。

## Agent 生成后的检查

Agent 按 `handoff/PROMPT.md` 和 `.agents/skills/zhiyun-lecture-notes/SKILL.md` 生成讲义后：

```bash
PYTHONPATH=src .venv/bin/python -m handouter validate-note \
  workspace/<lecture-id> --update-state
```

它检查输出位置、Markdown 图片路径、PPT 嵌图策略和明显的凭证泄漏，但会明确保留 `semantic_review: required`：**结构校验不等于课程内容正确。**

## TUI

```bash
PYTHONPATH=src .venv/bin/python -m handouter tui
```

装有 Textual 时使用完整表单界面；没有 Textual 时使用标准库 curses。长任务由独立 CLI 子进程执行，取消会终止进程组，而不是仅隐藏 UI 状态。

## 验证状态

2026-09-14 的验收前工程检查：

- **89 项自动化测试通过**；
- `node --check zhiyun_exporter.user.js` 通过；
- 真实仓库 2 分钟音频在 M4 Pro / MPS 上运行 SenseVoice 成功，过滤纯标点 VAD 噪声后得到 **8 个有效、全部带时间的句段**；
- 使用本地 HTTP 媒体 + 私有签名参数 + 合成资产 ZIP 真实跑通 `build-asset → ffmpeg → SenseVoice → PPT → alignment → handoff → validate`；签名参数未出现在工作区；
- 全新 venv 中 `pip install --no-index .` 和 `pip install --no-index -e .` 均成功；
- 旧《高级机器学习》样例材料曾在临时目录标准化为 127 个 PPT 事件 / 127 张图片 / 0 缺图。

这些验证仍**不能替代真实智云页面字段、真实签名媒体、整课 ASR 和两门真实课程三档 Agent 讲义的人工语义验收**。下一步只按 [正式验收清单](docs/ACCEPTANCE.md) 执行，不再继续堆新功能。

## 旧代码边界

根目录 `pipeline.py`、`build_*.py`、`generate_*.py`、`clean*.py` 是单课程历史实验；`zhiyun_to_feishu.py` 是旧飞书方案。不要把它们作为 0.2.0 主链路，也不要批量运行它们来“验收”，因为部分脚本会覆盖既有样例讲义。

当前生产入口是 `src/handouter/`；根目录 `download_slides.py` 仅保留为兼容包装，ZIP 生产实现位于 `handouter.importers`。
