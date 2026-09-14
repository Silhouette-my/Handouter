# Handouter 目标架构

状态：2026-09-14，**0.2.0 验收候选**。本页的核心职责、工作区、媒体、结构化 ASR、时间关联、handoff、输出验证和 TUI 已落地；剩余主要是 `ACCEPTANCE.md` 中的真实平台/整课/真实 Agent 验收，以及验收后的缓存、CI 和 legacy 迁移。实际状态以 `PROJECT_STATUS.md` 为准。

## 1. 两条责任边界

**程序负责确定性处理**：输入校验、授权资源获取、音频抽取、本地 ASR、分段与时间戳保存、PPT 映射、任务状态、交接材料、输出文件结构检查。

**用户自己的 Agent 负责语义处理**：术语纠错、去口癖、章节组织、推导解释、摘要及 Markdown 写作，遵守本项目 Skill。MVP 只导出提示词和材料，不自动启动 Agent、不读取用户 Agent 的 API Key、不引入通用 LLM 客户端抽象。

“本地执行 Agent”不保证“模型在本地推理”。交接前说明材料可能被用户 Agent 发送给其所配置的服务商；默认不交接登录 Cookie、签名视频地址或原始音频。

## 2. 代码与课程材料分离

目标代码布局如下，先建实际需要的模块，不批量生成空壳：

```text
Handouter/
├── README.md / AGENTS.md / PROJECT_STATUS.md / CHANGELOG.md
├── pyproject.toml                 # 0.2.0；ASR/Textual 为可选依赖
├── handouter_build.py             # stdlib-only PEP 517 backend
├── src/handouter/
│   ├── cli.py                    # 首先完成可测 CLI
│   ├── workspace.py              # 每讲独立目录、manifest、状态
│   ├── importers.py              # 本地材料和导出 ZIP 规范化
│   ├── media.py                  # ffmpeg，与飞书无关
│   ├── asr.py                    # 首期一个 SenseVoice 后端即可
│   ├── alignment.py              # 时间区间关联
│   ├── handoff.py                # 交接包和提示词，不调用 LLM
│   ├── validation.py             # 工作区/Agent 输出结构检查
│   ├── doctor.py                 # 环境 readiness
│   └── tui.py                    # Textual + curses fallback，统一调用 CLI
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

## 3. 每个讲次独立工作区

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
│   ├── PROMPT.md                 # 明确材料路径、模式、Skill 和输出位置
│   ├── sources.json              # 来源/分块/缺失记录
│   └── outline.md                # 可选；不能伪装为已经覆盖全文
├── notes/                        # Agent 生成版本，不覆盖 raw
└── state.json                    # 各处理阶段状态和错误
```

实际工作区按输入按需创建：已有 TXT 只需要 `transcript.txt`；ASR 链路增加 `raw.json/segments.json`，媒体链路增加 `audio/source.m4a`，同时存在可用 ASR 时间与 PPT 时间时生成 `slides/alignment.json`。浏览器资产 ZIP 的 `private/source.json` **只存在于源 ZIP**；`build-asset` 仅在内存读取媒体 URL，不把 private 文件复制进 workspace。交接包默认引用工作区内安全材料，不引用音频或签名 URL。

## 4. 最小数据契约

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

## 5. 三种讲义与两种 PPT 策略

`mode = full | deep | summary`。`use_slides_as_source` 与 `embed_slides` 分开：深度无图版可读取 PPT 来核对术语和公式，但不嵌入图片。用户明确要求完全忽略 PPT 时才关闭前者。

`full` 不扩写成教科书、不删除技术案例与问答、不把否定或不确定措辞改成肯定；`deep` 可重组解释，但额外推导必须标成补充；`summary` 可省略次要展开，但保留结论适用条件。所有模式中的考核要求仅在材料明确提供时出现，未提及不等于没有作业。

每个章节或必要段落记录来源段 ID/时间范围。输出结构检查与语义质量审查分开：程序能检查路径、范围、来源 ID、缺失块等，不能仅凭字数比例证明忠实完整。

## 6. Agent 交接流程

1. 校验材料清单，显示缺失项与时间戳精度。
2. 根据用户模式生成确定性的 `PROMPT.md`；优先让 Agent 明确读取 Skill 路径，不假设所有 Agent 都自动发现 `.agents/skills`。
3. Agent 先阅读索引和原始证据，再按时间/主题处理分块。每块记录来源段 ID；上下文不足时使用阶段性工作文件继续，不能只读头尾就声称全文覆盖。
4. Agent 写入新的 `notes/<mode>-<run-id>.md`，不改原始材料或上次讲义。
5. 用户显式导入/确认结果后，程序检查图片链接、来源覆盖记录、模式要求，显示待人工复核项。

系统已自动生成 Prompt/来源索引并记录 `materials/handoff/agent_output/validation` 状态，且在提交工作区前完成材料 hash 与路径结构验证。Agent 生成后可用 `validate-note` 检查预期输出位置、图片路径、PPT 嵌图策略和明显凭证泄漏；即使结构通过也保持 `semantic_review: required`。Handouter 不自动启动用户 Agent。

## 7. TUI 的职责

TUI 是业务层的界面，不是第二套流水线。显示输入、当前阶段、进度、日志、失败原因、重试/取消、模式选择、PPT 开关和交接位置即可。初期不用数据库、账户系统或 Web 服务。

TUI 已实现并复用同一套 CLI：安装 Textual 时使用完整表单，未安装时使用 Python 标准库 curses。长任务运行在独立进程组中，取消会向整个进程组发送终止信号，并在必要时强制结束，避免“UI 已取消但 ffmpeg/FunASR 仍在后台运行”。

## 8. 安全、重跑与网络

目标是原始目录只读、输出新版本、临时文件写完校验再原子提交。ZIP 导入要有隔离目标、路径约束、文件类型/总解压量限制和元数据校验；不直接解包覆盖代码目录。下载成功与失败分别记录，失败占位不能当作有效图片。

ZIP importer 采用新目录、排他创建、索引最后写入与可捕获异常清理；`service.prepare_lecture()` 在同一文件系统临时讲次目录中完成复制、handoff 和验证，成功后再改名提交，失败清理半成品。媒体也先写临时文件，除 `ffprobe` 外还实际解码开头/尾部样本；stream-copy 校验失败时再尝试 AAC。图片 importer 目前以文件头和大小为主，不等同于完整畸形图片安全审计；整个流程仍不等于断电恢复或并发事务系统。

授权与资源获取使用用户正常可访问的会话，不绕过课程权限。签名 URL 在日志、manifest、Prompt 和错误提示中脱敏。校园资源与模型下载分别配置代理策略，而不是无条件清除全部代理。

0.2.0 的失败恢复策略是：正式工作区不提交半成品，失败后清理临时产物并整任务重试。更细的阶段缓存、输入哈希驱动断点 DAG 和多模型路由属于真实验收后的增强，不阻塞当前验收。
