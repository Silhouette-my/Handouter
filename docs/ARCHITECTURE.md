# Handouter 目标架构

状态：2026-09-15，**0.2.0 验收候选**。本页的核心职责、工作区、媒体、结构化 ASR、时间关联、handoff、输出验证和 TUI 已落地；剩余主要是 `ACCEPTANCE.md` 中的真实平台/整课/真实 Agent 验收，以及验收后的缓存、CI 和 legacy 迁移。实际状态以 `PROJECT_STATUS.md` 为准。

## 1. 两条责任边界

**程序负责确定性处理**：输入校验、授权资源获取、音频抽取、本地 ASR、分段与时间戳保存、PPT 映射、任务状态、交接材料、Skill module plan、Agent 调度与输出结构检查。

**用户自己的 Agent 负责语义处理**：术语纠错、去口癖、章节组织、推导解释、摘要及 Markdown 写作。Handouter 不实现通用 LLM API 客户端，也不持有用户 API Key；但用户明确选择本机 Codex/Claude CLI 时，可以由 Agent adapter 自动启动该 CLI。GUI/Web Agent 则使用同一 handoff 生成的安全上传包。

“本地执行 CLI Agent”不保证“模型在本地推理”。Agent 是否把材料发送给其服务商由用户自己的工具配置决定；GUI bundle 和 CLI handoff 都不包含登录 Cookie、签名视频地址或原始音频。

## 2. 普通用户表面与内部工作区分离

默认产品表面只暴露：浏览器抓取脚本、**课程资产 ZIP 文件路径**、输出目录、Prompt、`transcript.txt`、`slides/images/` 和 `notes/`。TUI 支持把 ZIP 直接拖入终端；新版资产 ZIP 可自动提供课程标题，并从回放页标识生成稳定 lecture ID；用户可以覆盖但不必理解内部协议。

`handouter run --asset /path/to/course.zip --output-dir ...` 与 TUI 是普通用户入口；`--input-dir` 仅保留为兼容旧 CLI 的扫描方式。`prepare/build-audio/build-media/build-asset` 保留为高级/调试入口。对已经完成 ASR 的长课，`handouter prompt <workspace>` 只刷新 handoff，旧任务归档，不重新处理音频。

内部 `raw.json / segments.json / manifest.json / state.json / alignment.json` 继续保留，因为它们承担断点恢复、审计和 validator 证据，但 TUI 不应把它们变成普通用户的配置负担。

## 3. 代码与课程材料分离

目标代码布局如下，先建实际需要的模块，不批量生成空壳：

```text
Handouter/
├── README.md / AGENTS.md / PROJECT_STATUS.md / CHANGELOG.md
├── pyproject.toml                 # 0.2.0；ASR 为可选依赖；Windows 条件依赖 windows-curses
├── handouter_build.py             # stdlib-only PEP 517 backend
├── src/handouter/
│   ├── cli.py                    # 首先完成可测 CLI
│   ├── workspace.py              # 每讲独立目录、manifest、状态
│   ├── importers.py              # 本地材料和导出 ZIP 规范化
│   ├── media.py                  # ffmpeg，与飞书无关
│   ├── asr.py                    # 首期一个 SenseVoice 后端即可
│   ├── alignment.py              # 时间区间关联
│   ├── handoff.py                # handoff / sources / module plan 物化
│   ├── skill_plan.py             # 渐进披露 Skill 模块路由
│   ├── agents/                   # manual bundle + Codex/Claude CLI adapters
│   ├── validation.py             # 工作区/Agent 输出结构检查
│   ├── doctor.py                 # 环境 readiness + platform
│   ├── platform_support.py       # macOS/Linux/Windows 进程组与取消策略
│   └── tui.py                    # 固定全屏 ASCII curses TUI；支持文件拖入与 Agent 选择
├── zhiyun_exporter.user.js       # v1.4 私有资产导出器（当前仍在根目录）
├── .agents/skills/zhiyun-lecture-notes/
│   ├── SKILL.md
│   └── references/
├── tests/                        # 小型合成夹具，不依赖真实课程
├── docs/
├── legacy/                       # 待迁移的单课写作脚本与飞书实验
└── workspace/                    # 本地课程材料，不进入 Git
```

迁移旧文件前先解除相邻文件和当前目录依赖；更新调用点、文档与图片链接后再移动。尤其不能只搬 Markdown 而不保留 `slides/` 相对路径。

## 4. 每个讲次独立工作区

同一门课的不同回放不能共用 `course_audio.m4a` 之类的全局文件名。讲次键优先由 tenant/course/sub 标识组成；本地输入使用稳定任务 ID，中文课程标题只用于展示。

```text
workspace/<lecture-id>/
├── manifest.json                 # 版本化、无凭证、相对路径
├── audio/                        # 可选抽取/规范化音频；不交给 Agent
├── transcript/
│   ├── raw.json                  # 原始 ASR 结果与运行参数
│   ├── segments.json             # 统一时间段格式
│   └── transcript.txt            # 便于人读，不替代时间段数据
├── slides/
│   ├── index.json                # 幻灯片展示事件与图片关联
│   ├── alignment.json            # 可选：ASR segment × PPT 时间区间关联
│   └── images/
├── handoff/
│   ├── PROMPT.md                 # 本次任务实例、材料位置、module plan、输出位置
│   ├── sources.json              # 来源/options/expected_outputs/skill.modules
│   ├── skill/                    # 本次实际需要的 Skill 入口与模块安全副本
│   ├── gui-handoff-NNN.zip       # 可选：GUI/Web Agent 上传包
│   └── history/                  # Prompt 刷新历史
├── notes/                        # Agent 生成版本，不覆盖 raw
└── state.json                    # 各处理阶段状态和错误
```

实际工作区按输入按需创建：已有 TXT 只需要 `transcript.txt`；ASR 链路增加 `raw.json/segments.json`，媒体链路增加 `audio/source.m4a`，同时存在可用 ASR 时间与 PPT 时间时生成 `slides/alignment.json`。浏览器资产 ZIP 的 `private/source.json` **只存在于源 ZIP**；`build-asset` 仅在内存读取媒体 URL，不把 private 文件复制进 workspace。交接包默认引用工作区内安全材料，不引用音频或签名 URL。

## 5. 最小数据契约

`manifest.json` 至少包含 `schema_version`、`lecture_id`、`course_title`、`source_type`、脱敏的课程标识、输入文件清单、相对路径、SHA-256、音频时长（未知为 null）、ASR 配置、创建时间。`manifest` 记录稳定事实，`state.json` 记录运行状态，避免两份真相。

时间单位统一为 **整数毫秒**。规范化转写段示例（示意数据）：

```json
{
  "id": "seg-0001",
  "start_ms": 12000,
  "end_ms": 18000,
  "text": "这里是识别原文。",
  "timestamp_kind": "sentence_or_vad",
  "speaker": null
}
```

ASR 原始结果单独保留；不声称 VAD 区间是逐字精确时间。没有时间戳时允许 `start_ms`/`end_ms` 为 null，并明确降低为无精确对照模式；不能根据字数均匀摊时间。模型没有返回的 confidence/speaker 不得编造。

浏览器字段必须有明确单位协议：禁止用“数值大于 10000 就当毫秒”等启发式猜单位。v1.4 已删除该规则：已知 `created` 按秒解释，时钟字符串显式解析；其他无法确认单位的数值字段保留 raw 值并标记 `unknown_numeric_unit`，无时间则为 null。正式验收仍需在真实智云页面确认实际字段语义；importer 不会逆向猜测未知单位。

PPT 的规范对象应当区分“图片身份”和“展示事件”：例如 `slide_id`、`occurrence_id`、`start_ms`、`end_ms`、`image_path`。教师回翻旧页时，图片可以复用，但展示事件不能去重删除；单调的是时间，不是原始页码。未知结束时间保留 null，不能像旧脚本那样任意补 180 秒。

对齐先用区间相交关联转写段与幻灯片事件。跨页句子可以关联多张图并标注边界不确定性；不以“图片顺序递增”冒充已实现语义精准匹配。

## 6. 可组合交付物、阅读格式与两种 PPT 策略

一个 handoff 可以同时选择四类交付物：`verbatim` 逐字版、`full` 完整整理版、`deep` 深度讲义、`summary` 精简版。`verbatim` 尽量贴近课堂原话；`full` 保留信息覆盖但主动去口语、去重复并重写自然段落。两者都不替代始终保留的 `transcript/transcript.txt` 原始转写证据。每种交付物写入自己的 `notes/<mode>-NNN.md`，并按模式独立递增版本号。

`format_profile = clean | traceable`。两者都使用默认折叠的 HTML `details` 保存课程信息及每个主要章节的真实时间/来源及最终待核对清单；clean 简明，traceable 在折叠内补充更完整的 segment/PPT 对应依据。作业、小测、考试、小组作业与考核要求在正文前以可见重点框汇总，且不取代原位置的课堂讨论。`use_slides_as_source` 与 `embed_slides` 分开：可参考 PPT 核对术语和公式而不嵌图，明确忽略 PPT 时才关闭前者。

`verbatim` 只做轻度清理并保持课堂原话风格；`full` 允许跨相邻 segment 合并、去除口语铺垫和重复复述，但不得删除独有信息或把不确定措辞改成肯定。verbatim/full/deep 均沿实际课堂顺序自然分段，deep 在原位置深入解释，不能按新逻辑重排。只有 summary 可按主题重组、压缩次要展开，仍须保留结论适用条件。

每个主要章节（`##`）标题后使用一个时间/来源折叠框，引用真实句段/VAD 区间；段落、列表、表格和子小节共用。未知时间明确标未知，非连续来源分别列出。最终待核对清单默认折叠，无疑点时省略；影响考核行动的未定事项仍在开头重点框可见。公共 presentation 模块统一定义重点框与折叠语法。validator 仅以默认可见内容做阅读格式告警，仍检查折叠内的凭证、图片和双轨 ASR；不能自动证明讲述顺序、考核信息完整或每章语义对齐。旧 workspace 不会因缺少新格式被追溯判错，新格式须刷新 Prompt 后按相应快照验收。

## 7. 渐进披露 Skill 与统一 module plan

`SKILL.md` 是薄路由入口，不再重复 verbatim/full/deep/summary/格式/PPT 的所有规则。Handouter 根据本次配置计算 `sources.json.skill.modules`，并把入口和**仅本次需要的模块**复制到 `handoff/skill/`：

```text
references/common/       evidence / writing / presentation / completion
references/modes/        只选择本次的 deep / summary / full
references/formats/      clean 或 traceable
references/slides/       ignore / source-only / embed
references/execution/    条件式 long-course / multi-output
```

`skill.modules` 是 Prompt、CLI Agent、GUI bundle 和手工 fallback 的唯一 module plan。长课模块由 segment 数或 transcript 大小触发；多输出模块只在一次任务请求多个交付物时加入。自定义单文件 Skill 仍兼容：没有内置 reference tree 时 module list 可为空，只物化入口文件。

## 8. Agent interaction：同一 handoff，两种传输方式

1. 校验材料并生成 `PROMPT.md`、`sources.json`、`handoff/skill/` 和 `expected_outputs`。
2. **GUI/Web Agent**：`manual` adapter 生成 `gui-handoff-NNN.zip`。包内镜像 Prompt 所引用的安全路径，包含 transcript、可选 segments/slides 和选中的 Skill 模块；排除 audio、raw ASR、private URL/Cookie、state/manifest 和已有 notes。
3. **CLI Agent**：Codex adapter 使用非交互 `codex exec`，Claude adapter 使用 `claude --print`；工作目录限定在讲次 workspace。Handouter 不读取 API Key，而使用用户已经安装/登录的 CLI。
4. CLI Agent 完成后，Handouter 重新验证 workspace hash、handoff/control files、已有 notes，并逐个校验所有 `expected_outputs`。退出码 0 但输出缺失同样判失败。
5. 结构通过后仍写 `semantic_review: required`；自动执行不等于自动证明课程语义正确。

旧 workspace 若没有新 `skill.modules`，GUI bundle 不会静默生成残缺包，而会要求先运行 `handouter prompt <workspace>` 刷新 handoff。

## 9. TUI 的职责

TUI 是业务层的界面，不是第二套流水线。普通用户界面固定为 curses 绘制的全屏 ASCII 仿 GUI：macOS/Linux 使用系统/stdlib curses，Windows 通过条件依赖 `windows-curses` 提供同一 API；Source / Deliverables / Options / Actions / Status 面板始终同时可见，不使用逐项问答式 shell wizard。

Full polished notes、Deep notes、Summary notes 与 Verbatim transcript 使用独立复选框，可同时选择；阅读格式、PPT 策略、ASR 设备和 Agent interaction 使用单选/开关。Agent 默认 `GUI handoff`，也可切换 `Codex CLI / Claude CLI`。`Asset ZIP` 是直接文件路径而不是目录：macOS/Linux 规范化引号、反斜杠空格和 `file://`；Windows 单独解析盘符路径、带引号路径、UNC 和 `file:///C:/...`，不使用 POSIX `shlex` 解释 `C:\...`。普通界面用 `Tab`/`↑↓` 导航、`Space` 切换复选框、`←→` 切换选项；**文本编辑模式内 `←→` 改为移动光标**，并支持 Home/End/Backspace/Delete/Ctrl-A/E/U/K。

长任务使用 `platform_support.py` 统一启动与取消：macOS/Linux `start_new_session` 后按进程组 SIGTERM→SIGKILL，后备清理不因根进程退出而跳过。Windows TUI 创建带 `KILL_ON_JOB_CLOSE` 的 Job Object，将句柄定向继承给任务 bootstrap；bootstrap 先加入 Job 并关闭自己的句柄，再启动 CLI 业务，TUI 持有保留句柄并在任务结束时关闭以清理后代。建立/加入 Job 失败则不启动业务。`CREATE_NEW_PROCESS_GROUP`、CTRL_BREAK 和超时 taskkill 保留为辅助取消路径，不能单独代替 Job 的后代管理。TUI 等待取消清理线程完成。子进程管道统一 UTF-8/`PYTHONUTF8=1`；Windows Job 实际兼容性仍需真机/runner 验证。

## 10. 安全、重跑与网络

目标是原始目录只读、输出新版本、临时文件写完校验再原子提交。ZIP 导入要有隔离目标、路径约束、文件类型/总解压量限制和元数据校验；不直接解包覆盖代码目录。下载成功与失败分别记录，失败占位不能当作有效图片。

ZIP importer 采用新目录、排他创建、索引最后写入与可捕获异常清理；`service.prepare_lecture()` 在同一文件系统临时讲次目录中完成复制、handoff 和验证，成功后再改名提交，失败清理半成品。媒体也先写临时文件，除 `ffprobe` 外还实际解码开头/尾部样本；stream-copy 校验失败时再尝试 AAC。图片 importer 目前以文件头和大小为主，不等同于完整畸形图片安全审计；整个流程仍不等于断电恢复或并发事务系统。

授权与资源获取使用用户正常可访问的会话，不绕过课程权限。签名 URL 在日志、manifest、Prompt 和错误提示中脱敏。校园资源与模型下载分别配置代理策略，而不是无条件清除全部代理。

0.2.0 的失败恢复策略是：正式工作区不提交半成品，失败后清理临时产物并整任务重试。更细的阶段缓存、输入哈希驱动断点 DAG 和多模型路由属于真实验收后的增强，不阻塞当前验收。
