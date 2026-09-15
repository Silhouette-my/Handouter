# Handouter

Handouter 把用户有权访问的智云课堂回放材料整理成**本地、可追溯的课程工作区**，再通过同一份 handoff 驱动用户选择的 Agent：CLI Agent 可以自动执行，GUI/Web Agent 则获得安全的 Prompt + 上传包。

> 当前阶段：**0.2.0 产品化验收候选**。用户已经实际跑通一门完整长课并生成讲义；当前重点从底层链路转向 Prompt/最终格式和普通用户 TUI。默认界面直接接受课程资产 ZIP 文件（支持拖入终端）和可指定输出目录，再展示 Prompt、转写稿 / Slides / 最终讲义；内部 raw ASR、manifest、state、alignment 仍保留用于恢复和核验，但不要求普通用户操作。

## 产品边界

```text
已授权智云回放页
      ↓  浏览器抓取脚本
/path/to/课程资产.zip   ← 可直接拖入 TUI
      ↓  handouter run / TUI
<output-dir>/<lecture-id>/
      ├── handoff/PROMPT.md
      ├── handoff/skill/          ← 本次任务实际需要的 Skill 模块
      ├── transcript/transcript.txt
      ├── slides/images/
      └── notes/                  ← verbatim / full / deep / summary 最终成果
              │
              ├─ GUI/Web Agent：生成安全 handoff ZIP，用户上传
              └─ CLI Agent：Codex / Claude Code 自动执行并校验
```

Handouter 内部仍会完成 ffmpeg、SenseVoice、PPT 时间事件、alignment、manifest/state 等确定性处理；这些属于实现细节，普通用户无需逐项配置。

Handouter **不会持有用户的 LLM API Key、不会内置通用付费 LLM 客户端，也不会把课程材料上传飞书或其他云服务**。只有用户明确选择 `Codex CLI` / `Claude CLI` 时，Handouter 才会启动本机已安装的 CLI Agent；默认 TUI 使用 `GUI handoff`，只准备可上传 bundle。CLI Agent/GUI Agent 是否把材料发送给其模型服务商，仍由用户自己的 Agent 配置决定。

## 可组合交付物与格式

一次任务可以同时选择多种最终成果，每种成果写入自己的 Markdown，不会拼在同一文件里：

| 交付物 | 默认成品 | 关键约束 |
| --- | --- | --- |
| `verbatim` | 忠实逐字版 | 按实际课堂顺序贴近原话，只清理 ASR 噪声、无意义口癖和机械结巴；自然分段 |
| `full` | 完整整理版 | 按实际课堂顺序保留几乎全部有效信息，去口语、去重复，仅合并相邻冗余表达 |
| `deep` | 深度讲义 | 沿实际课堂顺序在原位置深入解释，不重排章节逻辑；允许的补充明确标注 |
| `summary` | 5–10 分钟快速阅读版 | 唯一可以按主题重排的模式；正文为速览和少量主题，保留关键前提 |

底层 `transcript/transcript.txt` 始终作为 ASR 证据保存。四种模式统一使用以下呈现规则：

- 作业、小测、考试、小组作业、课程考核等实际要求，在正文前用始终可见的 `[!IMPORTANT]` 重点框汇总；保留更正和未定事项，没有依据时不编造。verbatim/full/deep 正文仍在原讲述位置保留相关讨论。
- 课程信息使用默认折叠的 `<details><summary>课程信息</summary>…</details>`。
- 每个主要章节（`##`）标题后用一个默认折叠的 `<details><summary>本章时间与来源</summary>…</details>` 汇总真实时间/来源；自然段、列表、表格和子小节共用所属章节的折叠框。未知时间明确标未知，非连续材料分列真实区间。
- 最后的待核对项使用默认折叠的 `<details><summary>待核对</summary>…</details>`；没有疑点时省略，影响作业或考核行动的未定事项仍在开头重点框可见。
- `clean` 保持折叠内证据简明；`traceable` 在折叠内提供更完整的 segment/PPT 对应依据，两者都不将内部处理日志和机器路径写入正文。`use_slides_as_source` 与 `embed_slides` 仍是独立选项。

上述规则由 `common/presentation.md` 随每次 handoff 物化。已有工作区需执行 `handouter prompt <workspace>` 或 TUI 的 **REFRESH PROMPT** 才会替换旧 Skill 快照；仅复用旧 bundle 不会自动更新规范。旧 notes 不会被重写。

## 分层 Skill：按任务渐进披露

`SKILL.md` 现在只是薄入口。Handouter 会根据这次实际选择生成 `sources.json.skill.modules`，并把**仅本次需要的模块**复制到 `handoff/skill/`：

```text
handoff/skill/
├── SKILL.md
└── references/
    ├── common/       # evidence / writing / presentation / completion
    ├── modes/        # 只带本次选择的 verbatim / full / deep / summary
    ├── formats/      # clean 或 traceable 二选一
    ├── slides/       # ignore / source-only / embed 三选一
    └── execution/    # 仅在需要时加入 long-course / multi-output
```

Prompt 不再重复整套写作规则，只保存**本次任务实例信息、输出路径、材料路径和 module plan**。CLI Agent、GUI bundle 与手工 Prompt 全部复用同一个 `sources.json.skill.modules`，避免不同执行方式各自维护一套规则。

## Agent 交互：CLI 全自动 / GUI 手动交接

先查看本机可用后端：

```bash
PYTHONPATH=src .venv/bin/python -m handouter agents
```

两种产品路径共享完全相同的 handoff：

- **GUI/Web Agent（TUI 默认 `GUI handoff`）**：Handouter 生成 `handoff/gui-handoff-NNN.zip`。包内包含 Prompt、sanitized sources、转写、按配置选择的 Slides，以及本次 Skill 模块；明确排除原始音频、raw ASR、private URL/Cookie、state/manifest 和旧 notes。用户把 ZIP 上传给 ChatGPT/Claude 等 GUI Agent，并让它先读 `handoff/PROMPT.md`。
- **CLI Agent**：选择 `Codex CLI` 或 `Claude CLI` 后，Handouter 会调用本机已有 CLI Agent，工作目录设为讲次 workspace，等待生成全部 `expected_outputs`，随后检查输出、工作区 hash 和旧讲义 hash。结构通过后仍保留 `semantic_review: required`。

已有 workspace 也可单独执行：

```bash
# GUI/Web Agent 上传包
PYTHONPATH=src .venv/bin/python -m handouter bundle output/<lecture-id>

# CLI Agent 自动生成
PYTHONPATH=src .venv/bin/python -m handouter agent-run \
  output/<lecture-id> --agent codex
```

普通 `handouter run` 为保持脚本兼容默认 `--agent none`；TUI 则默认 `GUI handoff`，也可以切到 Codex/Claude CLI。`run` 和 `prompt` 均可直接追加 `--agent manual|codex|claude`。

## 安装与环境检查

项目使用仓库内的 stdlib-only PEP 517 backend，因此**没有构建期第三方依赖**。macOS/Linux 的 core install 仍可完全离线：

```bash
python3 -m venv .venv-clean
.venv-clean/bin/python -m pip install --no-index .
.venv-clean/bin/handouter --help
```

Windows 的 ASCII TUI 需要条件依赖 `windows-curses`，普通安装会按平台自动拉取：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m handouter doctor
```

若 Windows 机器需要完全离线安装，应提前把 `windows-curses` wheel 放入本地 wheelhouse，再使用 `--no-index --find-links <wheelhouse>`。macOS/Linux 使用系统/stdlib curses；Windows 使用 `windows-curses`，但上层 TUI 代码仍是同一套。

ASR 仍需要 `funasr` 和 `torch`。Windows + NVIDIA 建议安装与本机 CUDA 环境匹配的 PyTorch build；未启用 CUDA 时仍可回退 CPU。ffmpeg/ffprobe 继续通过 PATH 检测，Windows 可用例如：

```powershell
winget install Gyan.FFmpeg
```

开发态环境检查：

```bash
PYTHONPATH=src .venv/bin/python -m handouter doctor
```

`doctor` 会额外报告当前平台，并分开报告 core / media / ASR / TUI 是否可用，不会自动安装或修改环境。

运行 `handouter run` 时，阶段进度条写入 stderr，最终结果 JSON 仍写入 stdout，方便终端查看或脚本解析。TUI 会在运行页顶部显示同一进度，包括资产检查、音频提取、ASR、工作区生成和最终交付。

## 推荐使用方式：直接选择资产 ZIP → 输出目录

安装后，抓取脚本随包提供；源码开发态也可以直接使用根目录的 `zhiyun_exporter.user.js`。在已登录、自己有权访问的智云回放页面运行脚本，得到一个课程资产 ZIP。普通用户直接把这个**文件路径**交给 Handouter，不需要再创建或理解 input 目录：

```bash
PYTHONPATH=src .venv/bin/python -m handouter run \
  --asset "/path/to/课程资产.zip" \
  --output-dir output \
  --modes deep summary

# 同时生成完整整理版和忠实逐字版：
PYTHONPATH=src .venv/bin/python -m handouter run \
  --asset "/path/to/课程资产.zip" \
  --output-dir output \
  --modes full deep summary verbatim
```

新版 ZIP 会自动从 `course_info.json` 读取课程标题，并从回放页的 `tenant_code/course_id/sub_id` 生成稳定讲次 ID；两者仍可用 `--course-title` / `--lecture-id` 手动覆盖。`--input-dir` 只保留给旧 CLI/批量扫描习惯，不是 TUI 的默认交互。默认格式就是 `clean`。成果位于：

```text
output/<lecture-id>/
├── handoff/PROMPT.md              # 给本地 Agent
├── transcript/transcript.txt      # 转写稿
├── slides/images/                 # Slides
└── notes/                         # 最终讲义
```

内部的 `raw.json / segments.json / alignment.json / manifest.json / state.json` 仍保留在同一讲次工作区，用于恢复和质量核验，但普通用户无需操作。

`--agent none` / `manual` 不会启动外部 Agent，因此 `agent_was_run=false`；选择 `--agent codex|claude` 时则会自动执行对应本机 CLI Agent，并在返回 JSON 中给出 `validation_ok` / `validation_errors`。无论哪种方式，语义质量仍需人工复核。

### 已跑过长课后，只改 Prompt

调整讲义模式、PPT 策略或格式**不需要重新跑两三个小时 ASR**：

```bash
PYTHONPATH=src .venv/bin/python -m handouter prompt \
  output/<lecture-id> \
  --modes full deep summary verbatim \
  --format-profile clean
```

旧 Prompt 会自动归档到 `handoff/history/`。每种交付物独立版本化：例如已有 `full-001.md` 而还没有逐字版时，新 Prompt 可以同时指向下一版 `full-002.md` 与新的 `verbatim-001.md`，互不覆盖。

只切换到一种交付物可用 `--mode verbatim`；同时传入 `--modes` 时以 `--modes` 为准。两者都省略则保留当前选择。

## 其他输入方式

已有转写：

```bash
PYTHONPATH=src .venv/bin/python -m handouter prepare \
  --lecture-id lecture-001 \
  --course-title "课程名称" \
  --transcript /path/to/transcript.txt \
  --slides-zip /path/to/asset.zip \
  --modes full
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

## 内部工作区（高级用户 / 调试）

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

Agent 按 `handoff/PROMPT.md`、`handoff/sources.json` 和本次物化的 `handoff/skill/` 模块生成讲义后：

```bash
PYTHONPATH=src .venv/bin/python -m handouter validate-note \
  workspace/<lecture-id> --update-state
```

它检查输出位置、Markdown 图片路径、PPT 嵌图策略和明显的凭证泄漏，但会明确保留 `semantic_review: required`：**结构校验不等于课程内容正确。**

默认检查这次 handoff 的全部交付物，任何一份缺失或无效都会返回非零退出码。多成品 JSON 的 `outputs` 保存路径，`reports` 保存分模式结果，`--update-state` 写入聚合状态。只检查一个文件时使用 `--output notes/deep-001.md`；显式单文件和单成品任务保留原有单文件 JSON。

## TUI：普通用户主入口

```bash
PYTHONPATH=src .venv/bin/python -m handouter tui
```

TUI 是固定全屏的 **ASCII 仿 GUI**，不是逐项提问的 shell 向导。界面始终同时显示 Source / Deliverables / Options / Actions / Status 面板，不要求用户理解 raw ASR、manifest、state 或 alignment。

- TUI 第一项就是 `Asset ZIP` 文件路径；可按 `Enter` 进入编辑后直接把 `.zip` 文件拖进终端，也可以在该字段聚焦时直接拖入；
- 拖入路径会按平台处理 macOS Terminal/iTerm 与 Windows Terminal 常见格式：macOS 支持引号、反斜杠空格和 `file://`；Windows 支持 `C:\...`、带引号路径、UNC (`\\server\share`) 和 `file:///C:/...`，不会再用 POSIX `shlex` 破坏反斜杠；ZIP 读取成功后自动填写课程标题和讲次 ID；
- `↑/↓` 或 `Tab`：在字段、复选框和按钮间移动；
- `Space`：勾选/取消 Full polished notes、Deep notes、Summary notes、Verbatim transcript、PPT 参考/嵌图等；
- `←/→`：在普通界面切换 clean/traceable、ASR 设备；**进入文本编辑模式后则用于移动光标**，不会再被全局快捷键抢占；同时支持 Home/End、Backspace/Delete、Ctrl-A/E/U/K；
- `Enter`：编辑当前路径/名称或执行按钮；`F5`：运行完整处理；`P`：只刷新 Prompt；`Q`：退出；
- Full、Deep、Summary 和 Verbatim 可以同时勾选；其中 Verbatim 保留课堂原话风格，Full 则重点去口语、去重复并改善段落；
- `Agent` 可在 `GUI handoff / Codex CLI / Claude CLI` 间切换。GUI handoff 只生成安全上传包；CLI 模式会继续自动生成讲义并做结构/篡改校验；
- 长任务取消会清理后代：macOS/Linux 使用新 session + SIGTERM/SIGKILL，即使根进程先退出也等待后备清理；Windows TUI 任务在启动业务前加入 Job Object，任务结束时统一清理后代，并保留 `CTRL_BREAK_EVENT` / `taskkill /T /F` 取消路径。若系统不允许建立 Job，任务会明确失败；Windows 真机行为仍待验收。

## 验证状态

2026-09-15 的产品化验收检查：

- **162 项自动化测试：161 通过、1 项 Windows Job Object 集成测试在 Mac 上跳过**；覆盖跨平台路径、取消、bundle 竞争、多输出及新增折叠呈现兼容检查；新格式真实生成与 Windows 实际运行仍待验证；
- `node --check zhiyun_exporter.user.js` 通过；
- 真实仓库 2 分钟音频在 M4 Pro / MPS 上运行 SenseVoice 成功，过滤纯标点 VAD 噪声后得到 **8 个有效、全部带时间的句段**；
- 使用本地 HTTP 媒体 + 私有签名参数 + 合成资产 ZIP 真实跑通 `build-asset → ffmpeg → SenseVoice → PPT → alignment → handoff → validate`；签名参数未出现在工作区；
- macOS 全新 venv 中 `pip install --no-index .` 成功；wheel 元数据已包含 `windows-curses>=2.4; sys_platform == 'win32'` 条件依赖；
- 旧《高级机器学习》样例材料曾在临时目录标准化为 127 个 PPT 事件 / 127 张图片 / 0 缺图；
- 用户已实际跑通一门完整长课并生成 `full/deep/summary`；这次真实产出也暴露并推动修复了 `full` 双栏膨胀、clean 讲义工程元信息过多等格式问题；
- 新版 Prompt 在该长课工作区副本上验证：已有 `full-001.md` 时只刷新 Prompt 会指向 `full-002.md`，不会重新 ASR；旧双轨 `full-001.md` 会被新版 validator 明确判为格式偏航；
- 分层 Skill / GUI bundle / Agent adapter 专项回归通过；2026-09-15 按用户授权，真实 Codex CLI 在独立副本中复用一门课的 ASR，完成新版四模式 notes。结构/哈希及独立 AI 语义核对通过，源材料疑点保留；GUI、Claude、取消和 Windows 仍待真实验收；
- GitHub Actions 已扩为 `ubuntu-latest / macos-latest / windows-latest` 三平台矩阵。Windows runner 尚待这批改动 push 后首次真实 CI 验证，因此当前不宣称“真实 Windows 环境已通过”。

当前重点已经从“链路能否跑通”转向**真实课程的 Prompt/格式迭代和 TUI 用户体验**。

## 旧代码边界

根目录 `pipeline.py`、`build_*.py`、`generate_*.py`、`clean*.py` 是单课程历史实验；`zhiyun_to_feishu.py` 是旧飞书方案。不要把它们作为 0.2.0 主链路，也不要批量运行它们来“验收”，因为部分脚本会覆盖既有样例讲义。

当前生产入口是 `src/handouter/`；根目录 `download_slides.py` 仅保留为兼容包装，ZIP 生产实现位于 `handouter.importers`。
