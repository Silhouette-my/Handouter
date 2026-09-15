# Handouter 0.2.0 正式验收清单

日期：2026-09-15。状态：**完整长课已跑通；当前验收重点转为新版 Prompt/格式和产品化 TUI。**

本清单只验收 0.2.0 的核心价值：**跨课程、证据可追溯、不覆写原始材料、能从智云资产稳定准备本地 Agent 交接包，并让 verbatim/full/deep/summary 各自保持正确的内容层级与课程原意。** CI 已作为工程质量门槛建立，但不能替代真实课程验收；OCR、复杂断点 DAG、云端分享等增强不混入当前验收。

## 当前验收进度

| 项目 | 当前状态 | 说明 |
| --- | --- | --- |
| 本地自动回归 | ✅ 当前可运行项通过 | 162 项：161 通过、1 项 Windows Job Object 实测在 Mac 跳过；含新增呈现模块及折叠内容检查；JS/doctor 通过 |
| GitHub Actions CI | ⏳ 待远端确认 | workflow 已扩为 Linux/macOS/Windows 三平台矩阵；需提交并 push 后确认三平台首次 run 均为 green |
| 真实智云 exporter | ⏳ 待验收 | 必须使用用户正常登录且有权限的真实回放页 |
| 真实 `build-asset` | ⏳ 待验收 | 合成私有 HTTP E2E 已通过，真实校园/CDN 媒体待测 |
| 完整长课 ASR | ✅ 主链路已跑通 | 用户已完成一门完整长课并生成讲义；仍建议补记资源占用和取消行为 |
| 两门课多交付物 Agent | 🟡 进行中 | 第一门已生成 `full/deep/summary` 并用于修正格式；产品入口现可一次选择 deep + summary + 可选 full，至少再测一门不同类型课程 |
| Agent interaction | 🟡 Codex 真实四模式生成通过 | 独立副本复用真实课程 ASR，Codex 生成四份新 notes，结构/哈希及 AI 语义核对通过；GUI、Claude、取消与 Windows 仍待验收 |
| TUI 人工操作/取消 | ⏳ 待新版体验验收 | 新版可选 GUI handoff / Codex CLI / Claude CLI；仍需真人操作与取消测试 |


## 0. 验收原则

- 只使用自己正常有权访问的课程，不绕过登录、权限或媒体授权。
- 原始资产 ZIP、音频、PPT、转写和旧讲义验收前后都不得被覆盖。
- 资产 ZIP 可能含签名视频 URL，按私有材料处理，不提交 Git、不直接交给 Agent。
- CLI 的 `handoff_ready` 只表示材料和 Prompt 就绪；只有用户自己的 Agent 实际写出 Markdown 后才有“讲义输出”。
- `validate` / `validate-note` 是结构与安全检查，不替代语义人工复核。
- 若任一步只完成部分材料，记录为部分成功，不写“整课通过”。

## 1. 环境预检

在项目根目录：

```bash
PYTHONPATH=src .venv/bin/python -m handouter doctor
PYTHONPATH=src .venv/bin/python -m handouter agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
node --check zhiyun_exporter.user.js
```

通过条件：

- `ok_core=true`、`ok_media=true`；要跑 ASR 时 `ok_asr=true`；TUI 的 curses 后端可用。macOS/Linux 应显示系统/stdlib curses；Windows 应显示 `windows-curses` 版本或明确安装提示。
- 自动化测试全部通过。
- `handouter agents` 正确报告 manual bundle 与本机 Codex/Claude CLI 可用性；不存在某个 CLI 时只标 unavailable，不应让 core 失败。
- userscript JS 语法通过。
- 当前提交对应的 GitHub Actions CI 为 green；CI 失败时先修回归，再继续真实课程验收。

若要验证干净安装：

macOS/Linux：

```bash
python3 -m venv /tmp/handouter-accept
/tmp/handouter-accept/bin/python -m pip install --no-index .
/tmp/handouter-accept/bin/python -m handouter doctor
```

Windows：

```powershell
py -3.11 -m venv .venv-accept
.\.venv-accept\Scripts\python.exe -m pip install .
.\.venv-accept\Scripts\python.exe -m handouter doctor
```

macOS/Linux core install 不应访问 PyPI；Windows 普通安装允许获取条件依赖 `windows-curses`。若要求 Windows 完全离线，应提前准备本地 wheelhouse。

## 2. 真实智云导出器验收

选择一门自己有权访问、PPT 数量容易人工确认的回放。安装/更新 `zhiyun_exporter.user.js` v1.4+ 后打开回放页，必要时先展开右侧 PPT 列表。

验收：

- [ ] 页面识别到正确课程和大致正确的 PPT 数量。
- [ ] 导出的 ZIP 中有 `slides/`、`slides_meta.json`、`course_info.json`、`private/source.json`。
- [ ] `slides_meta.json` 不包含图片签名 URL/Cookie。
- [ ] `private/source.json` 中存在当前可访问的媒体 URL；该文件只保存在资产 ZIP 内。
- [ ] 明确时钟时间被保存为毫秒/秒；无法确认单位的数值字段标成 unknown，而不是被猜成错误时间。
- [ ] 没有时间的 PPT 为 null，不伪造为 0 秒。
- [ ] 下载失败图片为 `missing_image`，ZIP 汇总数字与人工观察相符。

建议保留一份截图或只记录数量/状态，不把真实签名 URL贴进验收报告。

## 3. `build-asset` 真实链路验收

对上一步的资产 ZIP：

```bash
PYTHONPATH=src .venv/bin/python -m handouter build-asset \
  "/path/to/真实课程资产包.zip" \
  --lecture-id "real-course-001" \
  --course-title "真实课程名称" \
  --workspace-root workspace-accept \
  --modes deep summary \
  --device auto
```

通过条件：

- [ ] 输出 JSON 可被 `json.load()` 直接解析；第三方日志只出现在 stderr。
- [ ] 状态为 `handoff_ready`，`agent_was_run=false`。
- [ ] `audio/source.m4a` 可由 ffmpeg 实际解码；若 copy 不可用，允许自动回退 AAC。
- [ ] `transcript/raw.json` 保留模型、版本、参数和原始结果。
- [ ] `segments.json` 的时间为整数毫秒或 null，不出现负值/逆序。
- [ ] `slides/index.json` 保留 PPT 回翻、缺图和未知时间状态。
- [ ] `slides/alignment.json` 只做时间关联；跨页句段允许关联多张 PPT。
- [ ] `manifest.json` 的 `source_type` 为 `zhiyun_asset_zip`。
- [ ] 运行 `handouter validate workspace-accept/real-course-001` 返回 `ok=true`。
- [ ] 在整个工作区搜索不到资产 ZIP 中的完整签名媒体 URL、Cookie/API Key 等私有字符串。

若 URL 已过期/403，应明确失败并提示重新从已授权页面导出，而不是产出空音频/假成功工作区。

## 4. 整课 ASR 与长任务验收

至少选择一门完整课程（建议 1h 以上，最终再验证约 3h 样例）。

记录：输入时长、设备、处理耗时、segment 数、峰值内存的粗略观察、是否发生模型/媒体重试。

通过条件：

- [ ] 整课完成后 raw/segments/txt 三份证据都存在。
- [ ] 大多数有效段有合理起止时间；无时间字段保持 null。
- [ ] 句段总体按课程时间推进，没有大面积回跳或超出音频时长。
- [ ] 纯标点/纯噪声 VAD 片段不进入标准讲义证据，但原始 ASR 仍保留。
- [ ] ASR 失败时不会留下看似完整的正式 workspace。
- [ ] TUI/进程取消测试中，取消后 ffmpeg/FunASR 子进程确实结束，没有后台继续计算。

## 5. Agent interaction 与分层 Skill 验收

### Progressive Skill

准备任意新 handoff 后检查：

- [ ] `handoff/skill/SKILL.md` 存在，`sources.json.skill.entry` 指向它。
- [ ] `sources.json.skill.modules` 只包含本次需要的 common + mode + format + slide strategy；未选 full 时不加载 `modes/full.md`，clean/traceable 不同时加载。
- [ ] 多输出时存在 `execution/multi-output.md`；长课（大量 segments 或长 TXT）存在 `execution/long-course.md`。
- [ ] Prompt 只列任务实例、材料/输出路径和 module plan，不重新复制所有模式的完整规则。
- [ ] Prompt-only 刷新时旧 Skill plan 与旧 Prompt/sources 一起归档，新 plan 与新 options 一致。

### GUI/Web Agent

```bash
PYTHONPATH=src .venv/bin/python -m handouter bundle output/<lecture-id>
```

- [ ] 生成 `handoff/gui-handoff-NNN.zip`，上传后 Agent 能先读取 `handoff/PROMPT.md` 并找到全部 module/material 路径。
- [ ] bundle 包含 transcript、所选 Skill modules，以及开启 PPT 来源时需要的 slide index/images；关闭 PPT 时不带 slide evidence。
- [ ] bundle 不含 `audio/`、`transcript/raw.json`、private URL/Cookie、`state.json`、`manifest.json` 或既有 `notes/`。
- [ ] bundle 内 `sources.json` 的 `raw_asr_path` 已清空；工作区原 `sources.json` 不被修改。
- [ ] 旧 handoff 没有 module plan 时明确要求先刷新 Prompt，而不是生成残缺 bundle。

### CLI Agent

先执行 `handouter agents`。选择一门**可丢弃或已有备份**的课程，至少真实运行一个：

```bash
PYTHONPATH=src .venv/bin/python -m handouter agent-run \
  output/<lecture-id> --agent codex
# 或 --agent claude
```

- [ ] CLI 非交互完成，不额外要求用户复制 Prompt。
- [ ] Agent 只创建 `expected_outputs`；旧 notes、transcript/slides、manifest、handoff/skill 不被修改。
- [ ] CLI 返回 0 但目标文件缺失时 Handouter 仍判失败。
- [ ] Agent 修改课程证据、handoff/control files 或旧 notes 时被 hash 检查发现。
- [ ] 全部输出逐个 `validate-note`；结构通过仍保持 `semantic_review: required`。
- [ ] 默认 `validate-note <workspace> --update-state` 检查全部 expected outputs；任一缺失时返回非零并记录聚合失败。`--output` 只检查指定文件，不能据此宣布所有成品通过。
- [ ] TUI 取消自动 Agent 时，Agent 子进程也随同整个进程组结束。

2026-09-15 已按用户授权，通过 Handouter 真实调用 Codex CLI 完成一门课程的新版四模式生成；结构/哈希及独立 AI 语义核对通过，材料疑点保留。该测试复用了已有 ASR；Claude、GUI 上传、取消和 Windows 真机仍待验收。详细本地记录为 `output/acceptance-20260915-001/REVIEW.md`，不以此代替教师确认或第二门不同类型课程测试。

## 6. 两门真实课程 × 多交付物 Agent 语义验收

### 最新呈现要求（需重新生成验收）

- [ ] verbatim/full/deep 正文顺序与实际课堂一致；deep 深入解释但不重排，只有 summary 可按主题重组。
- [ ] 全课出现的作业、小测、考试、小组任务和课程考核要求，在正文前的可见 `[!IMPORTANT]` 重点框中汇总；保留教师更正、限制和未定事项。无依据时不编造要求。
- [ ] 课程信息使用默认折叠的 HTML `<details>`；每个主要章节（`##`）标题后有一个时间/来源折叠，段落、列表、表格和子小节共用，不逐自然段标注。
- [ ] 最终待核对清单放在默认关闭的 `<details><summary>待核对</summary>…</details>` 内；无疑点时省略，考核行动相关未定事项仍在开头重点框可见。
- [ ] 时间来自真实 segments，未知明确标注；summary 等跨非连续来源时分列区间，不伪造连续覆盖。列表/表格的折叠内能区分各条来源。
- [ ] 实际阅读器中正文始终可见，重点框突出；折叠框不带 `open`，展开后可读。阅读器不支持 alert 样式时仍显示清楚的重点引用块。

此前四模式验收采用当时规则；它不代表新增顺序/重点框/折叠格式已经真实生成验收。已有 notes 保留，后续先刷新 handoff 再生成独立新版本。

至少选两门内容明显不同的课，防止旧《高级机器学习》硬编码污染结果。每门至少验证 deep 和 summary，并至少一次同时生成 `verbatim` 与 `full`，确认两者在内容覆盖相近的前提下，逐字版保留课堂原话风格，而 full 明显去口语/去冗余。PPT 条件建议覆盖：参考+不嵌图、参考+嵌图、完全忽略 PPT。

Agent 使用工作区 `handoff/PROMPT.md`，不要运行旧 `pipeline.py` / `build_*.py` 代替语义生成。

生成后：

```bash
PYTHONPATH=src .venv/bin/python -m handouter validate-note \
  workspace-accept/<lecture-id> --update-state
```

人工抽样至少覆盖开头、中段、结尾、公式/数字密集处、教师自我纠正/否定处、PPT 回翻处。

### verbatim

通过条件：保留原讲述顺序、案例、限定、问答与有意义的口语节奏；只清理 ASR 噪声、无意义口癖、机械结巴和明显重复碎片。不得把多个独立观点压成摘要。最终成品是单栏可读逐字版，但**不能按 ASR/VAD segment 一段一段机械换行**，应按连续话题、问答、例子和推导步骤形成自然段。

### full

通过条件：核心信息覆盖应接近逐字版，但表达必须明显更书面、更紧凑。需要删除重复铺垫、重复复述、无信息量的转折/指代和口语脚手架，合并连续同义表达，同时保留每处独有的限定、例子、公式、条件和自我纠正。段落必须先跨 segment 聚合语义单元，再按微主题/推理阶段组织；不得一 segment 一段，也不得压缩成 summary。

### deep

通过条件：沿实际课堂顺序解释核心内容、公式、推导、案例和权衡，不按新知识逻辑重排；允许的课程外扩展明确标注为补充，不能冒充教师所讲。PPT 与附近内容相关。课程信息和每章时间/来源放入默认折叠框；作业与考核重点框始终可见。

### summary

通过条件：能快速理解本讲主题和结论；开头有 5–10 条 `本讲速览`，主体通常 3–8 个主题；压缩次要细节但保留结论成立的前提；不凭空生成考点、考试范围或作业要求；默认不为装饰生成 Mermaid/ASCII 思维导图。

### 共通否决项

以下任一出现则本轮语义验收不通过：

- 关键知识明显遗漏或章节只处理头尾；
- 数值、公式、否定、适用条件被改错；
- 混入另一门课程/旧样例的固定内容；
- 没有来源的讲者身份、履历、考核信息被捏造；
- 不确定 ASR 词被擅自“纠正”为没有证据的词；
- PPT 错配且被写成“精准时序”；
- 登录信息、签名 URL、Cookie、API Key 出现在讲义或工作记录中。

## 7. TUI 人工验收

运行：

```bash
PYTHONPATH=src .venv/bin/python -m handouter tui
```

TUI 应直接进入固定全屏 ASCII 仿 GUI。macOS/Linux 使用系统 curses；Windows 使用 `windows-curses`，两端必须保持同一业务交互。普通用户 TUI 不展示 TXT/音频/媒体等高级入口，这些保留在 CLI；界面不能退化成逐项 `input()` 式问答向导。

通过条件：

- [ ] 能看到/定位随包提供的浏览器抓取脚本。
- [ ] Asset ZIP 直接接受文件路径并支持拖入终端；输出目录可指定；绝对 ZIP 路径不依赖 `input_dir` 是否存在。
- [ ] macOS 拖入/粘贴路径可处理引号、反斜杠空格和 `file://`；Windows Terminal/Explorer 可处理 `C:\\...`、带引号路径、UNC (`\\\\server\\share`) 和 `file:///C:/...`。课程标题和讲次 ID 能从新版资产 ZIP 自动识别/生成，并允许用户覆盖。
- [ ] Full polished notes、Deep notes、Summary notes 和 Verbatim transcript 为独立复选框，并正确映射到 CLI `--modes`；full 与 verbatim 可同时选择。
- [ ] 文本字段进入编辑模式后，`←/→` 能移动光标而不是切换全局选项；Home/End/Backspace/Delete 正常，中文路径显示不破坏框线。
- [ ] `clean/traceable`、PPT 参考/嵌图策略能映射到 CLI。
- [ ] Agent interaction 可在 `GUI handoff / Codex CLI / Claude CLI` 间切换；GUI 为默认且完成后直接显示 bundle 路径。
- [ ] 成功后只突出 Prompt、转写稿、Slides、Notes 和本次目标讲义路径，不要求用户理解 raw/state/alignment。
- [ ] “只更新 Prompt”不重新运行 ffmpeg/FunASR，旧 Prompt 有历史归档；verbatim/full/deep/summary 按各自已有文件独立递增版本号，不覆盖既有输出。
- [ ] 长任务期间界面/日志仍响应；macOS/Linux 取消后进程组结束；Windows 取消后 ffmpeg/FunASR/CLI Agent 子进程树也结束，不残留后台进程。
- [ ] 特别检查根进程先退出、后代仍运行的场景：POSIX 后备清理继续执行；Windows Job 在根退出后仍能清理后代。Job 加入失败时明确报错且不启动业务；在 Windows runner/用户宿主下确认嵌套 Job 兼容性。
- [ ] 失败后没有正式半成品讲次目录；修正输入后可重新运行。
- [ ] 成功只提示 handoff ready / Prompt ready，不提示“讲义生成完成”。

## 8. 验收结果记录模板

```text
日期：
机器/系统：
平台：macOS / Windows / Linux
终端：Terminal / iTerm / Windows Terminal / 其他
Handouter 版本：0.2.0
课程 A：
课程 B：
智云导出：PASS / FAIL
真实 build-asset：PASS / FAIL
整课 ASR：PASS / FAIL
full：PASS / FAIL
 deep：PASS / FAIL
summary：PASS / FAIL
GUI handoff：PASS / FAIL
CLI Agent：PASS / FAIL
TUI + cancel：PASS / FAIL
发现的问题：
人工复核样本：
最终结论：ACCEPT / REJECT / CONDITIONAL
```

所有关键项通过后，0.2.0 才从“验收候选”改为“已验收”。
