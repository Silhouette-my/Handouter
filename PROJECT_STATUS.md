# 项目状态

### 统一安装入口

- 新增 Windows setup/start `.cmd` 与 macOS `.command` 入口，共用 `setup_handouter.py`：复用项目虚拟环境，安装 ASR extra，按需通过 winget/Homebrew 安装 FFmpeg。
- 安装结束前实际导入 ASR 原生依赖、执行合成音频 fbank、检查依赖冲突；失败不报告安装成功。无需手动激活环境；首次模型下载仍发生在转写时。
- 自动安装流程以模拟测试验证；Windows 双击安装、真实新环境下载和完整课程运行仍需实机验收。

更新：2026-09-15。阶段：**0.2.0 产品化验收候选；完整长课已由用户实际跑通，当前重点是 Prompt/格式约束、普通用户 TUI 与双端运行反馈。**

### 双端运行进度反馈

- `handouter run` 和 TUI 共用阶段事件；CLI 进度写入 stderr，stdout 保持最终 JSON，TUI 在运行页顶部显示当前进度。
- 当前阶段覆盖资产检查、音频提取、ASR 转写、工作区生成和最终交付；详细的 ASR 内部百分比仍由 SenseVoice 后端决定，当前显示阶段完成度。

### 当前提示词规则：课堂顺序、考核重点框与 HTML 折叠

- 仅 summary 可以按主题重排；verbatim/full/deep 正文按实际课堂顺序，deep 在原位置深入解释，不把课程说明等移至尾部。
- 作业、小测、考试、小组任务和课程考核要求在正文前以可见 `[!IMPORTANT]` 框汇总；保留更正和未定事项，正文仍保留原讲述位置。
- 课程信息和每个主要章节（`##`）的真实时间/来源用默认折叠的 HTML `details`；每章一个，段落、列表、表格和子小节共用。未知时间不编造，非连续区间分列。clean 简明，traceable 在折叠内提供更完整依据。最终待核对清单也默认折叠，无疑点时省略；考核行动相关未定事项仍在开头可见。
- 新增公共 `presentation.md` 并进入 module plan、wheel 和手工模板；validator 允许折叠内来源信息，仍检查全文凭证、图片与双轨 ASR，不对旧 workspace 强加新格式。
- 本轮 162 项测试：161 通过、1 项 Windows Job Object 实测跳过；JS/doctor/diff 检查通过。尚未按这版规则重新生成真实长课；下述此前成品的验收结果不能替代新格式验收。已有工作区须 REFRESH PROMPT 才会更新 Skill 快照。

### 新版四模式真实 Codex CLI 验收

- 用户提供的测试 ZIP 与已有讲次 ID 及全部 142 张 PPT 哈希一致；复制到独立验收目录，复用 517 个 ASR 段，刷新为四模式 clean/嵌图/禁止联网。
- Codex CLI 真实完成四份新版本；退出码 0，runner 的全部输出及篡改检查通过，默认多输出 `validate-note` 四份均通过、无 warnings。
- 独立 AI 语义核对通过：verbatim 保留原话风格与顺序，full 明显去口语且保留信息，deep 梳理知识关系，summary 为 8 条速览/6 个主题。材料疑点仍保留，程序继续 `semantic_review: required`，不代表教师或外部事实确认。
- 原始 workspace 156 个文件、验收副本 152 个受保护文件与源 ZIP 均未改动。详细本地记录：`output/acceptance-20260915-001/REVIEW.md`。
- 本轮复用已有 ASR，未重跑下载/转写；GUI 上传、Claude CLI、Windows/取消及第二门不同课程仍待验收。CLI 内部子代理启动失败后以单 Agent 完成，内部并行能力未通过验收。

### 接管审查后修复

- 已修复 POSIX 父进程先退出导致取消后备清理跳过的问题；真实合成父子进程已验证子进程忽略 SIGTERM 时仍会被结束。
- Windows TUI 使用 Job Object 管理任务后代，业务执行前加入 Job，结束/取消时由 TUI 关闭保留句柄；加入失败会拒绝启动业务。真实 Windows Job API、嵌套 Job 和完整用户体验仍待验证。
- GUI bundle fallback 不再删除并发占用的目标；复制失败时核对本次创建文件的身份，避免清理已被替换的文件。
- `prompt --mode` 可以覆盖旧多模式选择；默认 `validate-note` 检查全部成品并聚合 state，指定 `--output` 仍只检查单文件。
- 本轮全量 156 项：155 通过、1 项仅 Windows 可运行的 Job Object 集成测试跳过；JS、doctor、diff 检查通过。未运行真实 Agent、未重跑课程、未提交。

## 当前主链路

```text
zhiyun_exporter.user.js v1.4+
        ↓
私有资产 ZIP
        ↓
handouter build-asset
        ↓
ffmpeg 音频抽取与解码校验
        ↓
SenseVoice raw.json / segments.json / transcript.txt
        ↓
PPT 展示事件 + 时间区间关联
        ↓
标准 workspace + manifest/state
        ↓
handoff/PROMPT.md + sources.json + handoff/skill/
        ↓
     Agent interaction
      ↙             ↘
GUI handoff ZIP    Codex / Claude CLI 自动执行
      ↘             ↙
notes/deep-NNN.md + summary-NNN.md + 可选 full-NNN.md
        ↓
validate-note + 人工语义验收
```

## 能力现状

| 环节 | 状态 | 验收前实现 |
| --- | --- | --- |
| 浏览器导出 | 已实现，真实站点待正式复测 | v1.4：未知时间为 null，不再按 `>10000` 猜毫秒；PPT 失败显式标记；签名媒体信息写入 `private/source.json` |
| 资产 ZIP 导入 | 已实现 | 路径/大小/重名/图片头限制；未知时间、缺图、重复展示保留；private 不进入工作区 |
| 媒体抽音频 | 已实现 | `src/handouter/media.py`；不覆写、不清代理、copy/AAC fallback、ffprobe + 实际解码抽样校验 |
| 本地 SenseVoice | 已实现并真实短音频验证 | 保存 `raw.json`、`segments.json`、`transcript.txt`；模型/版本/参数记录；纯标点 VAD 噪声不进入标准 segments |
| PPT/ASR 时间关联 | 已实现 | 区间相交，允许跨页和回翻；未知时间保持 unknown；不声称语义精准对齐 |
| 标准工作区 | 已实现 | 每讲独立目录、SHA-256、manifest、state、来源类型、版本化 notes |
| Agent handoff | 已实现并根据真实长课优化 | 一次 Prompt 可同时选择 `deep`、`summary` 和可选 `full`；新增 `clean/traceable`；Prompt 可单独刷新而无需重跑 ASR |
| 分层 Skill | 已实现 | `SKILL.md` 变为薄路由；`sources.json.skill.modules` 按 mode/format/PPT/长课/多输出选择模块，并物化到 `handoff/skill/` |
| Agent interaction | Codex 真实四模式生成通过；GUI/Claude 待验收 | GUI/manual 生成安全上传 ZIP；Codex/Claude CLI 可非交互自动执行。运行后校验 workspace/control hash、旧 notes 与全部 expected outputs |
| Agent 输出验证 | 已实现并扩展格式检查 | 输出位置、图片路径、嵌图策略、凭证泄漏；clean 工程元信息告警、full 双轨表直接报错；语义仍需人工复核 |
| TUI | 产品入口已收敛，macOS 已实测 / Windows 已代码适配 | 同一套 curses ASCII GUI；Windows 通过条件依赖 `windows-curses`；支持 ZIP 拖入、多交付物、GUI handoff/Codex/Claude Agent 选择、Prompt-only、任务取消；已有 ready workspace 会智能续跑到 bundle/Agent，不重复 ASR |
| 环境诊断 | 已实现 | `doctor` 报告当前 platform，并分开报告 core/media/asr/tui；Windows curses 会显示 `windows-curses` 版本/安装提示，不自动安装系统依赖 |
| 安装 | macOS 已干净环境验证；Windows wheel 元数据已适配 | stdlib-only build backend；macOS/Linux core 可 `--no-index`；Windows wheel 声明 `windows-curses>=2.4; sys_platform == 'win32'` |
| 旧飞书/单课 builder | legacy | 不属于 0.2.0 主链路 |

## 本次验收前工程完成项

### 媒体 / ASR / 对齐

- 新增 `src/handouter/media.py`：本地或授权 HTTP(S) 媒体抽音频；临时文件验证后提交；已有目标拒绝覆盖。
- 音频成功标准从“ffprobe 有时长”升级为“有时长 + 开头/尾部可实际解码”。远程 stream-copy 若产生坏 AAC/M4A，会自动尝试 AAC 转码。
- 新增 `src/handouter/asr.py`：SenseVoice + FSMN-VAD；保留原始 FunASR 结果，标准化句段使用整数毫秒。FunASR stdout 被重定向到 stderr，保证 CLI stdout 是纯 JSON。
- 新增 `src/handouter/alignment.py`：按时间交叠将 ASR segment 与 PPT occurrence 关联；跨页句段允许关联多次展示事件。

### 智云资产协议

- `zhiyun_exporter.user.js` 升至 v1.4.0：
  - 已知 `created` 明确按秒；时钟字符串直接解析；其他数值时间字段不再猜单位，而标记 `unknown_numeric_unit`；
  - 无时间为 null，不再伪造 `00:00:00`；
  - 每页图片写 `ok/missing_image`；
  - 公共 `slides_meta.json` 不写图片 URL；
  - 页面/视频地址写在资产 ZIP 的 `private/source.json`，提示整个 ZIP 作为私有输入保存。
- 新增包内 `handouter.importers`；根目录 `download_slides.py` 仅兼容旧命令，不再维护第二套 ZIP 生产实现。
- `build-asset` 只在内存读取 private 视频 URL；工作区、Prompt、manifest 不保存该签名地址。

### 工作区 / Agent / TUI

- `prepare/build-audio/build-media/build-asset` 最终都进入同一个 `prepare_lecture()` 工作区协议。
- manifest `source_type` 区分 `local_existing_materials / local_audio_asr / media_asr / zhiyun_asset_zip`。
- `validate-note` 新增 Agent 输出结构检查；通过后只标记 `semantic_review: required`，不会自动宣称讲义正确。
- TUI 复用同一套全屏 ASCII/CLI 逻辑：macOS/Linux 使用系统 curses；Windows 使用 `windows-curses`。macOS/Linux 取消使用进程组 SIGTERM→SIGKILL，并等待后备清理；Windows 使用进程组控制事件和 taskkill，并通过 Job Object 在任务退出后清理残留后代。
- `doctor` 在当前 Mac 上报告 core/media/asr/tui 可用，并新增 `platform` 字段；Windows 会将 TUI 依赖识别为 `windows-curses`。

### 产品化 Prompt / TUI（完整长课反馈后）

- 普通用户入口推荐 `handouter run --asset /path/to/course.zip --output-dir ...`：直接传课程资产 ZIP 文件，输出目录自由指定；`--input-dir` 仅保留为兼容旧 CLI 的扫描方式。
- 默认 TUI 不再暴露高级输入类型、raw/state/alignment 配置，只展示抓取脚本、输入/输出目录、Prompt、转写稿、Slides 和 Notes；界面采用固定 ASCII 面板而不是逐项问答。
- Full polished notes、Deep notes、Summary notes 和 Verbatim transcript 均为独立复选框，可同时选择；`verbatim` 负责忠实逐字整理，`full` 负责高覆盖率去口语/去冗余的完整整理正文。
- `clean / traceable` 均使用课程信息、每章时间/来源及最终待核对折叠框；clean 保持证据简明，traceable 在折叠内提供更完整映射。
- 根据真实 `full-001.md` 反馈，将原有逐字语义迁为 `verbatim`；新的 `full` 明确要求保留有效信息但主动去口语、去重复、合并相邻冗余复述，并按语义而非 ASR/VAD segment 组织段落。`verbatim/full` 都禁止原始 ASR 双栏复制。
- `deep` 默认不再输出“讲义元信息/材料说明”等工程前言；补充内容必须显式区分，装饰性 Mermaid/ASCII/宽表格受到约束。
- `summary` 统一为 `本讲速览` + 3–8 个主题小节，目标 5–10 分钟快速阅读。
- 新增 `handouter prompt <workspace>` / TUI“只更新 Prompt”：复用已有长课的 transcript/slides，不重新跑 ffmpeg/ASR；旧 Prompt、sources 和旧 Skill plan 一并归档到 `handoff/history/`，每种交付物按自己的 `NNN` 独立递增。
- Skill 改为渐进披露：common + 选中的 mode + format + slide strategy + 条件 execution 模块；Prompt 本身只保留任务实例和 module plan，不再重复整套写作规范。
- 新增 Agent interaction layer：`handouter bundle` 为 GUI/Web Agent 生成安全上传包；`agent-run` / `run --agent codex|claude` 可自动执行本机 CLI Agent。TUI 默认 `GUI handoff`，也可切换 Codex/Claude。
- GUI bundle 排除 audio/raw ASR/private/state/manifest/旧 notes；CLI Agent 自动运行后检查课程材料、handoff/control files 和旧 notes 未被篡改，再逐个验证新输出。
- TUI `RUN` 增加智能续跑：同 lecture 的 workspace 已 `materials/handoff ready` 且配置一致时，GUI 模式直接生成 bundle，CLI 模式直接 `agent-run`；若勾选项/格式/PPT 策略变化，则只 refresh Prompt，再进入 Agent，不重复 ffmpeg/ASR。失败后 STATUS 会保留真实错误摘要，而不是只显示退出码。

### 打包 / 双端运行

- 项目版本更新到 `0.2.0`。
- `handouter_build.py` 是 stdlib-only PEP 517 backend；不要求联网下载 setuptools/hatchling。wheel METADATA 现在会写入项目 runtime dependencies。
- 正常 wheel 同时携带 `zhiyun_exporter.user.js`、Agent adapters、progressive Skill；安装后不依赖源码仓库的 `.agents/`。
- macOS clean venv 已验证 `pip install --no-index .`、`handouter --help`、`doctor` 正常。
- Windows 条件依赖为 `windows-curses>=2.4; sys_platform == 'win32'`；普通 `pip install .` 会自动安装，完全离线场景需要本地 wheelhouse。
- Windows 路径适配覆盖盘符路径、带引号拖拽路径、UNC、`file:///C:/...`；不再用 POSIX `shlex` 解释 `C:\\...`。
- GUI bundle 在 APFS/NTFS 等可用 hard-link 时保持排他原子发布；不支持 hard-link 的 Windows 可移动盘/网络盘会安全退回 exclusive-create copy。
- GitHub Actions 已改为 Linux/macOS/Windows 三平台矩阵；Windows 真实 runner 仍需本批改动 push 后首次执行确认。

## 已执行验证

### 自动化

当前完整回归：**162 项，161 通过、1 项跳过（macOS 本机；跳过项需要 Windows Job Object API）**。

覆盖：

- 旧 13 项兼容冒烟；
- 35 项 ZIP 导入安全/时间协议回归；
- M1 跨课程工作区与 handoff；
- 浏览器导出时间契约；
- 包级 importer/private 隔离；
- ASR 结果规范化；
- 媒体真实 ffmpeg 集成及坏 copy → AAC fallback；
- PPT 跨页时间关联；
- Agent 输出验证；
- 全屏 ASCII TUI 参数映射、多交付物复选框与 curses 交互基础；
- 多输出 handoff、独立输出文件与各模式独立版本号；
- progressive Skill module plan / materialization / refresh history；
- GUI handoff bundle 的隐私边界与 PPT 条件打包；
- Codex/Claude CLI adapter 命令构造、输出缺失、workspace 篡改和旧 notes 保护；
- stdlib 构建 backend/wheel 与 Windows 条件依赖 METADATA；
- Windows/macOS 路径兼容：Windows drive/quoted path/UNC/file URI，POSIX 拖拽路径回归；
- 跨平台任务树：POSIX process group 与 Windows `CREATE_NEW_PROCESS_GROUP` / `taskkill /T /F`；
- portable lecture ID：拒绝 Windows 非法字符与 CON/NUL/COM/LPT 等保留设备名；
- Windows doctor / `windows-curses` 诊断与 GUI bundle hard-link fallback。

旧 `build_clean_verbatim_and_summary.py` 及 Skill 历史副本仍有 `\\m` 无效转义 DeprecationWarning；它们属于 legacy，本轮没有为消除 warning 改动课程公式字符串。

### 真实本机运行

1. 仓库 `test_clip_2min.m4a`：SenseVoice 在 M4 Pro / MPS 上实际运行成功；过滤纯标点 VAD 噪声后得到 **8 个有效句段，8 个均有 start/end 时间**。单次包含模型/VAD加载约 6 秒级。
2. 合成网络资产 E2E：
   - 本地 HTTP 提供带私有签名参数的媒体 URL；
   - 资产 ZIP 含 PPT + `private/source.json`；
   - `build-asset → ffmpeg → AAC fallback → SenseVoice → PPT → alignment → handoff → validate` 全部通过；
   - 结果为 8 个 timed segments、1 张 PPT、8 条 alignment；
   - 私有签名字符串未出现在工作区；
   - Agent 输出不存在，证明程序未自动运行 Agent。
3. 旧《高级机器学习》TXT + 127 张 PPT 曾在临时目录完成标准化：127 events / 127 images / missing 0 / unknown time 0。
4. 用户已实际运行一门完整长课并成功产出 `full/deep/summary`。该真实产出证明长课主链路可用，同时暴露了格式问题：旧 `full` 形成 20 万字符级 ASR/精修双栏表，`deep` 可见工程来源较多；本轮已针对这两个问题收紧 Prompt/Skill/validator。
5. 在上述长课工作区的临时副本上测试新版 Prompt-only：已有 `full-001.md` 时新目标为 `full-002.md`，旧 Prompt 归档，transcript/slides 不重跑；旧双轨 full 会被新版 validator 拒绝。
6. 当前机器实际检测到 `/opt/homebrew/bin/codex` 与 `/opt/homebrew/bin/claude`；adapter 已按真实 help 实现并完成 mock 回归。2026-09-15 经用户授权，Codex 已真实生成新版四模式讲义，结果见本页顶部验收记录；Claude 仍未真实生成。
7. clean venv 安装后验证：分层 Skill 模块、`handouter.agents` 包与 module planning 均可从 wheel 正常读取。

## 当前环境快照

| 项目 | 结果 |
| --- | --- |
| 项目版本 | 0.2.0 |
| 主要开发 Python | 3.11.16 |
| clean venv 验证 | Python 3.13.7，核心安装成功 |
| funasr | 1.4.15 |
| torch | 2.14.0 |
| modelscope | 1.40.0 |
| ffmpeg / ffprobe | 可用 |
| TUI | 当前 Mac 使用 stdlib curses；Windows 使用条件依赖 `windows-curses`，同一套 ASCII UI |
| Git | 已初始化并关联 GitHub 远端：`https://github.com/Silhouette-my/Handouter`；`main` 已有 0.2.0-rc 基线提交 |
| Codex CLI | 本机 `/opt/homebrew/bin/codex` 可发现；真实四模式生成通过，取消及 Windows 等场景仍待验收 |
| Claude CLI | 本机 `/opt/homebrew/bin/claude` 可发现；adapter 已实现，真实生成待用户验收 |
| CI | 已改为 `ubuntu-latest / macos-latest / windows-latest` 矩阵；Windows 自动安装 ffmpeg、普通安装拉 `windows-curses` 并运行 doctor；待 push 后真实 runner 首次确认 |

## 尚未通过的内容 = 正式验收本身

以下不是“待开发功能”，而是必须使用真实用户授权材料/真实 Agent 才能完成的验收：

1. 继续积累真实智云回放页面的兼容性样本：PPT 数量、时间字段状态、private 视频 URL、缺图/过期行为。
2. 至少再选择一门内容类型明显不同的真实课程，验证新版 `clean/traceable` Prompt 与 `full/deep/summary` 格式约束是否稳定。
3. 对已经跑通的完整长课补记内存/耗时数据，并人工测试一次长任务取消；完整长课链路本身已由用户实际跑通。
4. 人工操作新版“产品化 TUI”：拖入 ZIP 文件、编辑路径、Agent 模式切换、指定输出目录、只更新 Prompt、成果路径展示和取消。
5. Codex 已完成一次真实四模式生成；继续验收 `GUI handoff` 上传、Claude 生成，以及 CLI 子进程取消、Windows 权限和不同宿主环境行为。
6. 新版 Prompt/Skill 生成的讲义仍需人工抽检遗漏、否定/限定、公式、ASR 错词、额外扩写和 PPT 错配；validator 只检查明显格式偏航。

逐项步骤和通过标准见 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。

## 非验收阻塞项 / 后续增强

- 阶段级断点恢复目前仍是“失败清理临时目录后整任务重试”，没有复杂缓存 DAG。
- OCR 自动缓存、SRT/VTT、术语表、讲义版本 diff、legacy 物理迁移可在真实验收后按需求推进。
- Git release/tag 尚未建立；建议真实验收前把当前主干标记为 `v0.2.0-rc1`，验收通过后再发布 `v0.2.0`。
- 根目录旧单课脚本未删除，以免破坏现有样例溯源；0.2.0 不调用它们。
