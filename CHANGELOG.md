# 变更记录

## 2026-09-15 — 双端运行进度反馈

- `handouter run` 增加阶段进度条，写入 stderr，不污染机器可读的 JSON stdout。
- TUI 复用同一进度事件，在运行页顶部显示当前阶段、百分比和取消提示。
- 覆盖资产检查、音频提取、SenseVoice 转写、工作区生成和最终交付阶段。

## 2026-09-15 — 章节来源折叠与最终核对折叠

- 按用户澄清，将时间/来源粒度修正为每个主要章节（`##`）一个默认折叠框；段落、列表、表格和子小节共用章节来源，不逐自然段标注。
- 最终待核对清单放入默认关闭的 HTML `details`，无疑点时省略；影响作业和考核行动的未定事项继续保留在开头可见重点框。
- 同步生成 Prompt、Skill 模块、手工模板、项目约束和验收要求；未改写既有 notes，新格式真实长课验收仍待刷新 Prompt 后执行。

## 2026-09-15 — 课堂顺序、考核重点框与逐段折叠来源

- 按用户要求统一 verbatim/full/deep 为实际课堂顺序；deep 保留深度但不重排章节，只有 summary 可按主题重组。
- 新增公共 `references/common/presentation.md`：作业、小测、考试、小组任务和考核要求在正文前使用可见 `[!IMPORTANT]` 框；课程信息、逐段真实时间/来源使用默认折叠的 HTML `details`，未知和非连续来源明确处理。
- 同步自动 Prompt、手工 fallback、各模式/格式/执行模块及项目约束；公共模块按每次 handoff 物化并随 wheel 打包，保持薄 Skill 入口。
- clean 可读性告警区分折叠内容、可见 summary 和 open 状态；安全/图片检查仍扫描全文，双轨 ASR 不能藏在折叠内规避校验。旧 workspace 不因缺少新格式被追溯判错。
- 验证：162 项测试中 161 通过、1 项 Windows 专属测试跳过；JS 语法、doctor、diff 检查通过。未重生成现有真实 notes，新规则仍需刷新 Prompt 后实际验收；未提交。

## 2026-09-15 — 真实课程新版四模式 Codex CLI 验收

- 使用用户授权的真实 ZIP，核对讲次与全部 142 张 PPT 哈希后，在独立副本复用 517 个 ASR 段，刷新四模式 clean/嵌图 handoff，真实调用 Codex CLI 生成新版本。
- 四份 notes 的 runner/hash 检查及默认多输出结构校验全部通过；独立 AI 语义核对通过，仍保留各版源材料待核对项，不替代教师确认。
- 原始 workspace 156 个文件、测试副本 152 个受保护文件与源 ZIP 均未变化。完整报告与机器可读证据保存在忽略的 `output/acceptance-20260915-001/`。
- CLI 生成约 31 分 20 秒；其内部子代理启动失败后单 Agent 完成。未重跑 ASR、未测试 GUI/Claude/Windows/取消，不代表第二门不同课程或完整产品验收完成。本轮未修改生产代码、未提交。

## 2026-09-15 — 接管审查后的取消、发布与校验修复

- POSIX 取消后即使 Handouter 根进程已退出，仍对原进程组执行 SIGKILL 后备清理；TUI 等待清理线程结束，异常启动日志线程时也会收尾。
- Windows TUI 任务增加 Job Object（`KILL_ON_JOB_CLOSE`）：bootstrap 在启动业务前加入 Job，TUI 持有唯一保留句柄，任务退出或取消时关闭 Job 清理后代；无法建立 Job 时明确失败，不启动业务。保留 CTRL_BREAK / taskkill 辅助取消路径。
- GUI bundle 在 hard-link 不可用时，排他创建失败不会删除其他任务的目标；自身复制失败时核对文件身份后清理，保留已经替换的文件。
- `prompt --mode` 显式选择现在优先于工作区旧 modes；优先级为 `--modes` → `--mode` → 旧选择，省略选择仍沿用原配置。
- `validate-note` 默认检查全部 expected outputs；多成品结果包含 `outputs` 路径映射和 `reports` 分模式报告，聚合退出码与 state。显式 `--output` 和单成品任务保持原单文件 JSON；结构通过仍要求人工语义复核。
- 验证：macOS 全量 **156 项，155 通过、1 项 Windows Job Object 实测跳过**；含真实合成 POSIX 父子进程取消、managed CLI bootstrap、bundle 并发/失败清理、刷新优先级和多输出校验回归。JS 语法、doctor 与 diff 检查通过。
- 未运行真实外部 Agent 或真实课程生成；Windows Job Object 实际 API/嵌套 Job 行为仍待 Windows runner / 真机验收，未提交或发布。

## 2026-09-15 — verbatim / full 输出层级拆分

- 新增 `verbatim` 逐字版：继承原 `full` 的忠实整理目标，尽量贴近课堂原话，只清理 ASR 噪声、无意义口癖、机械结巴和明显重复碎片。
- 重新定义 `full` 为完整整理版：保留几乎全部有效信息，但主动去除口语脚手架、重复铺垫、自我重复和冗余复述，允许跨相邻 segment 合并改写为自然书面表达；不压缩成 summary。
- `verbatim` / `full` 都明确禁止“一 ASR/VAD segment 一段”。逐字版按连续话题/问答/例子自然分段；full 先跨 segment 聚合语义，再按微主题和推理阶段形成段落。
- Prompt 新增两种高覆盖率输出的显式定位，分层 Skill 新增 `references/modes/verbatim.md` 并重写 `full.md`；multi-output 规则禁止两种模式互相污染。
- TUI 新增独立 `Full polished notes` 与 `Verbatim transcript` 复选框；CLI `--mode/--modes` 新增 `verbatim`，两种成品可同时生成并独立版本化。
- 新增 full/verbatim 模块、Prompt 定位、TUI 映射和 wheel 打包回归；macOS 本机完整回归 **140 / 140** 通过。

## 2026-09-15 — macOS / Windows 双端适配第一阶段

### 平台运行层

- 新增 `src/handouter/platform_support.py`：统一任务进程组创建与取消。macOS/Linux 使用 `start_new_session + SIGTERM/SIGKILL`；Windows 使用 `CREATE_NEW_PROCESS_GROUP`，优先 `CTRL_BREAK_EVENT`，超时后 `taskkill /PID <pid> /T /F`，避免 ffmpeg/FunASR/CLI Agent 子进程残留。
- TUI 子进程管道固定按 UTF-8 解码并设置 `PYTHONUTF8=1`；Agent runner 和 ffmpeg/ffprobe 调用同样使用 UTF-8 + replacement fallback，降低 Windows 系统代码页导致中文课程名/日志解码失败的风险。
- GUI handoff bundle 继续优先 hard-link 排他发布；Windows 可移动盘、网络盘等不支持 hard-link 时安全退回 exclusive-create copy，仍不覆盖既有 bundle。

### Windows 路径 / TUI / 打包

- `normalize_terminal_path()` 按平台分流：macOS/Linux 保留 POSIX 拖拽转义逻辑；Windows 不再使用 POSIX `shlex`，支持 `C:\\...`、带引号路径、UNC (`\\\\server\\share`) 和 `file:///C:/...`。
- `lecture_id` 改为跨平台可移植命名：拒绝 `:*?\"<>|` 等 Windows 非法字符，以及 `CON/NUL/PRN/AUX/COM1..9/LPT1..9` 保留设备名。
- `pyproject.toml` 新增条件依赖 `windows-curses>=2.4; sys_platform == 'win32'`；自定义 PEP 517 backend 同步将 runtime dependency 写入 wheel `METADATA`。
- `doctor` 新增 `platform` 字段；Windows TUI 检查显示 `windows-curses` 版本或安装提示。
- GitHub Actions 扩展为 `ubuntu-latest / macos-latest / windows-latest` 三平台矩阵；Windows runner 自动安装 ffmpeg、安装 `windows-curses` 条件依赖并运行 doctor。真实 Windows runner 需本批改动 push 后首次确认。

### 验证

- 新增 Windows drive/quoted/UNC/file-URI 路径、POSIX 拖入回归、Windows/Unix 进程组策略、`taskkill /T /F`、Windows doctor、portable lecture ID、GUI bundle hard-link fallback 和 wheel dependency metadata 测试。
- macOS 本机完整回归 **141 / 141** 通过；`node --check zhiyun_exporter.user.js`、`doctor`、`git diff --check`、macOS clean venv `pip install --no-index .` 与 wheel `Requires-Dist` 检查均通过。
- 当前尚未宣称真实 Windows 运行通过；下一步以 GitHub `windows-latest` 和用户 Win11/NVIDIA 机器实测结果为准。

## 2026-09-15 — 全屏 ASCII TUI 与多交付物 handoff

### TUI / 产品交互

- 普通用户 TUI 固定为 Python 标准库 `curses` 的全屏 ASCII 仿 GUI；Source / Deliverables / Options / Actions / Status 面板始终可见，不再使用逐项问答式 shell wizard，也不再依赖 Textual。
- Deep notes、Summary notes 与 Clean transcript 改为独立复选框，可同时选择；清理逐字稿是额外可选成品，底层 `transcript/transcript.txt` 仍始终保留为 ASR 证据。
- TUI 支持方向键/Tab 导航、Space 多选、Enter 编辑/执行，以及 F5 运行、P 只刷新 Prompt、Q 退出；长任务仍由独立进程组执行并可取消。
- 删除普通 TUI 的 `Input Dir / SCAN ZIP` 概念：`Asset ZIP` 直接接受文件路径，支持把 Finder 中的 `.zip` 拖入终端；绝对 ZIP 路径不再依赖默认 `input/` 是否存在。
- 新文本编辑器在编辑模式内占用 `←/→` 做光标移动，并支持 Home/End/Backspace/Delete/Ctrl-A/E/U/K；普通界面的左右键仍只切换 clean/traceable 和 ASR 设备。
- 拖入路径会规范化终端常见的单/双引号、反斜杠转义空格和 `file://` URI；中文/全角字符按终端显示宽度裁剪与定位光标，避免 97×30 等较窄窗口出现框线错位。
- `RUN` 改为智能续跑：若同 lecture workspace 已经 `materials/handoff ready`，配置一致时直接继续到 GUI bundle 或 CLI Agent；配置变化时只 refresh Prompt，不重复 ffmpeg/ASR。失败后 STATUS 保留真实错误摘要，不再只显示 `code 2`。

### 多输出 handoff

- handoff schema 新增 `modes` 与 `expected_outputs`，一个 Prompt 可同时要求 Agent 生成多个独立 Markdown；保留 `mode` / `expected_output` 单数兼容字段，避免破坏既有工作区和旧工具。
- `handouter run` / `handouter prompt` /高级材料入口新增 `--modes`；未传时继续兼容原 `--mode`。
- `deep`、`summary`、`full` 各自独立版本化：例如已有 `deep-001.md` 时，刷新为 deep+summary+full 会指向 `deep-002.md`、`summary-001.md`、`full-001.md`。
- Prompt 明确交付物数量、各文件目标和“不得把多种笔记拼进同一 Markdown”；`product_artifacts` 与 workspace validator 同步支持多输出。

### 验证

- 新增多选交付物、可选清理逐字稿、ASCII TUI `--modes` 映射、多输出 Prompt、Prompt-only 独立版本号专项回归。
- 当前完整回归 **123 / 123** 通过；覆盖绝对 ZIP、拖拽/中文路径、智能续跑、Agent interaction、progressive Skill、GUI bundle 原子发布和 CLI Agent 校验。`node --check zhiyun_exporter.user.js`、`doctor`、`git diff --check`、离线 clean install、packaged userscript/Skill 和 Markdown 链接检查均通过。

## 2026-09-14 — 产品化 TUI、Prompt 格式约束与可重复 Prompt 迭代

### 普通用户路径

- 新增 `handouter run --input-dir ... --output-dir ...`：用户只需要把浏览器资产 ZIP 放进输入目录并指定成果目录；单 ZIP 自动选择，多 ZIP 要求明确选择。新版 ZIP 会自动读取课程标题并从 `tenant/course/sub` 生成稳定讲次 ID，两者仍允许手动覆盖。
- 重做普通用户 TUI 为**固定全屏 ASCII curses 仿 GUI**：Source / Deliverables / Options / Actions / Status 面板始终可见，不再使用逐项问答式 shell wizard；raw ASR、manifest、state、alignment 等内部文件不再要求普通用户配置。
- Deep notes、Summary notes 与 Clean transcript 改为独立复选框：deep/summary 可同时选择，清理逐字稿独立可选；一个 Prompt 要求 Agent 将每种成果写入各自 Markdown。
- 新增 TUI“扫描 ZIP”“查看 Prompt”“显示成果路径”“只更新 Prompt”。Prompt-only 会复用已有 transcript/slides，不重新运行 ffmpeg/SenseVoice，多种交付物按各自已有文件独立递增版本号。
- wheel 现在同时携带 `zhiyun_exporter.user.js` 和 `zhiyun-lecture-notes` Skill/手工 Prompt fallback；安装后不依赖源码仓库 `.agents/`。
- 默认 `input/`、`output/`、`outputs/` 加入 `.gitignore`，避免私有资产、转写和讲义被意外提交。

### Prompt 与最终格式

- 新增 `format_profile=clean|traceable`，默认 `clean` 面向直接阅读：正文不显示 seg/occ、内部 JSON 路径和处理统计；`traceable` 只在主要章节保留一条简短可见来源。
- 根据完整长课真实 `full-001.md` 反馈，`full` 明确禁止“原始 ASR vs 精修稿”双栏、逐 segment 表和重复原始 ASR，只输出单栏清理逐字稿。
- `deep` 约束为核心观点→课堂解释/推导→例子/条件，补充内容必须标明；默认禁止装饰性 Mermaid/ASCII/超宽正文表格和工程型“讲义元信息”前言。
- `summary` 统一为 `本讲速览`（5–10 条）+ 3–8 个主题小节，目标 5–10 分钟阅读。
- `validate-note` 新增格式检查：full 双轨格式直接报错；clean 模式对可见 seg/occ、内部路径和工程元信息发出 warning。
- 新增 `handouter prompt <workspace>`：旧 Prompt/sources 自动归档到 `handoff/history/`；支持 `--modes deep summary full` 多输出，每种模式独立选择下一个 `notes/<mode>-NNN.md`，既有讲义和材料不覆盖。
- handoff schema 新增 `modes` / `expected_outputs`，同时保留 `mode` / `expected_output` 单数兼容字段，避免破坏既有工作区和旧工具。

### 验证

- 完整回归增加到 **104 / 104** 通过；新增输入/输出目录、资产自动识别、Prompt-only、ASCII TUI 多选、多输出 handoff、独立版本号、格式约束与 packaged asset 回归。
- 在用户已经跑通的完整长课工作区副本上实测 Prompt-only：旧 `full-001.md` 保持不变，新 Prompt 指向 `full-002.md`；旧双轨 full 被新版 validator 正确判为格式偏航。
- 全新 wheel 安装后实际确认 packaged userscript 和 packaged Skill 均可发现。

## 2026-09-14 — GitHub CI 与验收基线补充

- 确认仓库已初始化 Git、`main` 已关联 `origin/main`，并已有 0.2.0-rc 基线提交；私有课程媒体、PPT、`.venv` 等仍由 `.gitignore` 排除。
- 新增 `.github/workflows/ci.yml`：在 Ubuntu / Python 3.11 上运行完整 `unittest` 回归，检查 `zhiyun_exporter.user.js` 语法，确保 ffmpeg/ffprobe 可用，并在全新 venv 中使用 `pip install --no-index .` 验证零网络核心安装。
- CI 最后执行 `git diff --exit-code`，防止测试或构建步骤静默修改 tracked 文件。
- 同步 `PROJECT_STATUS.md` 与 `docs/ROADMAP.md`；release/tag 尚待真实验收前建立 `v0.2.0-rc1`，正式验收通过后再发布 `v0.2.0`。


## 2026-09-14 — 0.2.0 验收前工程完成

### 主链路

- 新增 `media.py`、`asr.py`、`alignment.py`、`importers.py`、`doctor.py`、`tui.py`，将浏览器资产 ZIP、音频抽取、SenseVoice、PPT 时间事件、标准工作区和 Agent handoff 串成同一条本地主链路。
- 新增 `build-audio`、`build-media`、`build-asset`、`extract-audio`、`transcribe`、`validate-note`、`doctor`、`tui` CLI；原 `prepare/validate` 保留。
- `build-asset` 只在内存读取 `private/source.json` 的视频 URL；签名地址不写入工作区、manifest、Prompt 或 sources。
- manifest 增加来源类型，区分已有材料、本地音频 ASR、媒体 ASR 和智云资产 ZIP。

### 媒体与 ASR

- ffmpeg 输出改为新文件 + 临时产物 + 原子提交；不清除代理变量。copy/AAC 双路径后增加真实音频解码抽样验证，修复“ffprobe 时长正常但 AAC 帧已损坏”仍被当成功的问题。
- SenseVoice 保存 `raw.json + segments.json + transcript.txt`，记录 FunASR 版本、模型、设备和参数；纯标点 VAD 噪声不进入标准 segments，但仍保留在 raw。
- FunASR 的 stdout 输出重定向到 stderr，保证 Handouter CLI stdout 始终可作为 JSON 解析。
- PPT/ASR 关联仅按真实时间区间相交，保留跨页、多展示事件和 unknown；不声称语义精准对齐。

### 浏览器资产协议

- `zhiyun_exporter.user.js` 升至 v1.4.0：未知时间写 null；删除 `>10000` 猜毫秒；无法确认单位的数值字段保留原值并标 unknown；缺图写 `missing_image`。
- 公共 slide 元数据不再携带图片 URL；视频/page URL 写入 ZIP 的 `private/source.json`。整个资产 ZIP 被明确视为私有输入。
- 根目录 `download_slides.py` 改为 `handouter.importers` 的兼容包装，ZIP 生产逻辑只维护一份。

### TUI、输出验证与安装

- TUI 复用同一 CLI：有 Textual 时使用完整表单；无 Textual 时自动使用标准库 curses。长任务运行在独立进程组，取消会实际终止 ffmpeg/FunASR 子进程。
- 新增 `validate-note`：检查预期 Markdown、图片路径、PPT 嵌图策略与明显凭证泄漏；即使结构通过仍标记语义人工复核 required。
- 新增 stdlib-only `handouter_build.py` PEP 517 backend；全新 venv 已验证 `pip install --no-index .` 与 `pip install --no-index -e .` 均成功，不需要下载 setuptools。

### 验证

- 自动化回归 **89/89 通过**；包含真实 ffmpeg 集成、坏 copy→AAC fallback、浏览器时间契约、包内 private 隔离、TUI fallback、Agent 输出验证和 wheel/editable 构建。
- 仓库 2 分钟真实音频在 M4 Pro/MPS 上运行 SenseVoice 成功，过滤纯标点噪声后得到 8 个有效且全部带时间的句段。
- 使用本地 HTTP 私有媒体 URL + 合成智云资产 ZIP 真实跑通 `build-asset → ffmpeg → SenseVoice → PPT → alignment → handoff → validate`；得到 8 timed segments、1 张 PPT、8 条 alignment，签名字符串未泄漏，Agent 输出未被自动创建。
- 新增 `docs/ACCEPTANCE.md`，将剩余工作收敛为真实智云、整课 ASR、两门课程三档 Agent 语义和 TUI 人工验收。

### 已知非阻塞项

- 已完成本地 Git 仓库初始化与 GitHub 远端开源仓库建立（`Silhouette-my/Handouter`）；CI 待进一步接入。
- legacy 单课脚本仍保留并有两处 `\\m` DeprecationWarning。
- 没有复杂阶段缓存 DAG；失败时清理临时产物后整任务重试。
- 真实智云字段、签名媒体、整课长音频和真实 Agent 的语义质量尚待正式验收，不能由合成测试替代。

## 2026-09-14 — M1 标准工作区与 Agent 交接 CLI

### 新增

- 新建 `src/handouter/` 核心包：`workspace.py`、`handoff.py`、`validation.py`、`service.py`、`cli.py`。现有 UTF-8 转写与可选 PPT 可以进入独立讲次工作区，生成版本化 manifest、SHA-256、PPT 事件索引、Agent Prompt 与来源索引。
- `prepare` 使用临时目录完成材料复制、handoff 与结构验证后再改名；已有目标拒绝覆盖，失败清理半成品。源 transcript/PPT 只读复制，不运行旧 `pipeline.py` / builder / 飞书流程。
- 三档 `full/deep/summary` 进入同一交接协议；`use_slides_as_source` 与 `embed_slides` 分离。纯 TXT 明确标记无结构化 ASR 句段时间，不均摊或伪造时间。
- `validate` 校验输入 hash、PPT 相对路径、缺图、未知时间、重复展示、交接状态和模板占位符。修复首轮测试发现的“同一图片多次展示导致唯一图片数误计”问题。
- 新增最小 `pyproject.toml`；核心 M1 无第三方运行依赖。当前开发态仍使用 `PYTHONPATH=src`，未因现有 `.venv` 缺 pip 而重装环境。
- 新增 `tests/test_handoff_workspace.py` 13 项回归：两门课程隔离、不覆写输入、PPT 两开关、时间冲突失败清理、无图降级、私有 URL/Cookie 不传播、回翻事件、篡改检测和 CLI 状态语义。

### 验证

完整测试套件 **61/61 通过**（13 项旧冒烟 + 35 项 ZIP 导入 + 13 项 M1）。另用仓库现有《高级机器学习》TXT、独立 `slides_meta.json` 和 127 张 PPT 在系统临时目录完成一次 M1 标准化冒烟：127/127 图片事件可进入新工作区，缺图/未知时间均为 0，验证通过且没有生成 Agent 输出。CLI 只报告 `handoff_ready` 与 `agent_was_run: false`；本轮没有调用真实 Agent、ASR、课程网站、飞书或旧讲义 builder。

### 未完成

尚无锁文件/干净环境安装验证；尚未让两门真实课程分别用三种模式完成 Agent 语义验收；浏览器导出数值时间单位、音频本地主链路、结构化 ASR 时间、TUI 仍属于后续 M2/M3。

## 2026-09-14 — 接续复核、PPT ZIP 导入修复与回归补充

本条记录本次实际修改；下面的首轮审计、语法修复和 Skill 改写在本次接续前已经存在，不计作重复完成。

### 修复

- `download_slides.py` 的 ZIP 分支优先读取 `slides_meta.json`，修复合成导出包中 `125` 秒导入后变成 `0` 的可复现错误；支持时间别名及一致性验证、整数毫秒、未知时间为 null。
- 缺图保留原引用与独立状态；同一图片的重复展示事件不合并；未被元数据引用的图片明确保留。实际图片头决定输出后缀，不将 PNG 字节继续命名为 JPEG。
- 增加新输出目录、排他文件创建、路径/重名/符号链接/加密成员/数量和体积检查，以及可捕获写入失败时的本次产物清理。不解包 `course_info.json`，不复制元数据中的 URL/Cookie 等任意字段。
- 增加 ZIP 的 `--output-dir`；无效显式 ZIP 和其他导入错误以非零状态退出，不回退到其他输入。旧 `-j` 下载分支未完成同等治理。

### 新增与文档整理

- `tests/test_slide_import.py`：35 项合成 ZIP 回归，涵盖元数据、时间、缺图、重复展示、路径/大小限制、图片头、源 ZIP 不变、失败清理及实际 CLI 成功/失败。
- `docs/SLIDE_IMPORT.md`：现有导入接口、过渡记录结构、隐私和失败边界，不将其描述成完整课程 importer。
- 同步 `README.md`、`PROJECT_STATUS.md`、`docs/AUDIT.md`、`docs/ROADMAP.md`、`docs/ARCHITECTURE.md`。
- 新增导出器风险记录：隔离执行原函数时 `{time:11400}` 得到 `00:00:11`，而 `{created:11400}` 得到 `03:10:00`；无时间字段被填为零。尚未核实真实平台字段单位，未擅自修改 JS。

### 验证

原有 13 项加新增 35 项，**48 项离线测试通过**。ZIP 导入与其 CLI 使用真实临时 ZIP 文件，不是全 mock，但不涉及真实课程账号或网络。JS 语法、导入器 CLI help 通过；原始 127 张 PPT 全部存在、127 条 OCR、时间记录无倒序，音频经 ffprobe 再测为 11494.120500 秒。

收尾验证：8 个原始媒体、元数据、转写和既有 Markdown 文件的 SHA-256 与本次开始时一致；10 份当前文档的本地 Markdown 链接无断链；Skill `scripts/` 的 3 对旧副本仍与根目录对应文件相同，未改动或删除。

### 未做与限制

没有移动旧脚本或课程资源，没有初始化 Git、安装/升级依赖、下载课程/模型、重新转写或生成讲义。未实现 TUI、完整课程 manifest、自动 Agent 交接或来源覆盖验证。ZIP 文件头检查不等于完整图片解码；未实现断电恢复或完整原子事务；导出端已经错误的时间不能靠 importer 自动恢复。原有 `\\m` 无效转义警告仍保留于旧样例脚本。

## 2026-09-14 — 项目审计、文档分层与最小阻断修复

### 修复

- `zhiyun_to_feishu.py`：补齐 `debug_shot` 路径表达式缺失的右括号。
- `zhiyun_to_feishu.py`：Playwright 改为 `upload_to_feishu()` 内按需导入，使本地 `extract_audio()` 不被可选浏览器依赖阻断；缺依赖时给出明确异常。
- `generate_structured_notes.py`：补齐输出路径右括号，并增加缺失的 `from pathlib import Path`。

### 新增与更新

- README、AGENTS、PROJECT_STATUS、本变更记录、`.gitignore`。
- `docs/AUDIT.md`：当前能力、问题证据、源文件/单课实验/私有资产分类与迁移建议。
- `docs/ARCHITECTURE.md`：目标职责、工作区、材料契约、时间证据、Agent 交接与 TUI 设计。
- `docs/ROADMAP.md`：依赖有序的开发任务与验收条件。
- 重写 `zhiyun-lecture-notes` Skill，移除对旧硬编码脚本的通用执行推荐、强制虚构考核信息的格式要求，以及未经验证的完整性/时序/速度保证。
- 原 Skill 完整稿存档至 `docs/archive/SKILL.before-2026-09-14.md`；新增可手动填写的 `references/HANDOFF_PROMPT.md`。
- `tests/test_legacy_smoke.py`：13 项离线测试，无真实下载、模型加载、云端上传或课程材料覆写。

### 验证

13 项离线测试通过；21 个旧 Python 文件语法通过；导出器 JS 语法检查通过；ASR/旧飞书 CLI help 通过；Torch/Torchaudio 可导入；127 张 PPT 均存在、时间元数据无倒序。收尾比对确认 8 个原始音频、元数据、转写与既有 Markdown 文件的 SHA-256 完全未变；10 份文档及本地链接检查通过。

### 本轮未做

未物理迁移旧脚本/课程资源，未删除重复脚本，未初始化 Git，未安装或升级依赖，未实现通用 pipeline/TUI/自动交接，未下载课程或重新运行整课 ASR，未改写现有课程讲义。旧飞书 CLI 默认上传行为未改变；ZIP 时间丢失等问题保留在后续开发清单中。
