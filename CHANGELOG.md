# 变更记录

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

- 项目仍未初始化 Git/CI；legacy 单课脚本仍保留并有两处 `\\m` DeprecationWarning。
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
