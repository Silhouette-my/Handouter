# Handouter 路线图

日期：2026-09-15。当前版本：**0.2.0 产品化验收候选**。完整长课已由用户实际跑通；当前迭代聚焦 Prompt/最终讲义格式与“资产 ZIP 文件→TUI→输出成果”的普通用户路径。

## M0：审计与安全边界 — 已完成

- [x] 区分旧单课样例、可复用工具和生产主链路。
- [x] 修复旧脚本语法阻断；飞书 Playwright 改为按需导入。
- [x] 建立 README / AGENTS / PROJECT_STATUS / CHANGELOG / AUDIT / ARCHITECTURE。
- [x] 重写 Agent Skill，删除“绝对完整/精准时序/固定考核区”等无证据承诺。
- [x] 原始课程材料不作为自动测试写入目标；旧 builder 不作为生产入口。

## M1：已有材料 → 标准工作区 → Agent handoff — 已完成

- [x] `src/handouter/` 包和统一 CLI。
- [x] 每讲独立 workspace、manifest/state、SHA-256、相对路径、notes 版本策略。
- [x] 纯 TXT / 结构化 segments / raw ASR / 可选音频 / 可选 PPT 输入。
- [x] `verbatim/full/deep/summary` 进入同一 handoff 协议，并支持一次 Prompt 选择多个独立交付物；逐字版与完整整理版已拆分。
- [x] `use_slides_as_source` 与 `embed_slides` 分开。
- [x] 自动生成 `handoff/PROMPT.md`、`sources.json` 与按任务物化的 `handoff/skill/`；默认不运行外部 Agent，用户显式选择 CLI Agent 时可自动执行。
- [x] 工作区结构验证、hash 检查、PPT 缺图/未知时间/回翻事件检查。
- [x] Agent 输出 `validate-note`：路径、图片、嵌图策略、凭证泄漏；语义仍明确 required review。
- [x] 两门合成课程跨课隔离测试；旧《高级机器学习》127 张 PPT 可进入新工作区。

## M2：智云资产 → 媒体 → ASR → 时间关联 — 验收前实现完成

- [x] `zhiyun_exporter.user.js` v1.4：未知时间 null，不按数值大小猜单位；缺图显式状态。
- [x] 公共 PPT 元数据与私有媒体 URL 分离；`private/source.json` 只留在私有资产 ZIP。
- [x] 包内 `handouter.importers` 作为唯一 ZIP 生产 importer；根目录旧命令仅兼容代理。
- [x] ZIP 路径/重名/符号链接/体积/图片头限制；保留 unknown、missing、revisit。
- [x] `media.py`：本地/授权 HTTP(S) 媒体抽音频，不覆写、不清代理、copy/AAC fallback。
- [x] ffprobe 后增加实际解码抽样校验，避免“容器看似正常但音频帧损坏”。
- [x] `asr.py`：SenseVoice + FSMN-VAD，持久化 raw/segments/txt 和运行参数。
- [x] 实际 2 分钟音频 MPS 验证：8 个有效 timed segments。
- [x] `alignment.py`：PPT occurrence 与 ASR segment 仅按时间区间关联；跨页可多关联。
- [x] `build-asset`：私有媒体 URL 仅内存使用，最终进入同一 workspace/handoff。
- [x] 合成本地 HTTP 资产 E2E 全链路真实执行并验证签名不泄漏。
- [x] 用户已实际跑通一门完整长课并生成 full/deep/summary，证明长课主链路可用。
- [ ] 继续记录不同智云页面/媒体格式、校内外网络、403/过期链接的兼容矩阵。

## M3：产品化 TUI、macOS/Windows 双端运行与可复现安装 — 已实现核心适配，Windows 待真实 runner 验收

- [x] 默认 TUI 为标准库 curses 的固定全屏 ASCII 仿 GUI；Source / Deliverables / Options / Actions / Status 面板始终可见，不再使用逐项问答向导。
- [x] 普通用户只看到抓取脚本、资产 ZIP 文件路径、输出目录、交付物/格式和用户成果路径；高级 raw/state/alignment 参数移出普通界面。
- [x] Full polished notes、Deep notes、Summary notes 和 Verbatim transcript 使用独立复选框，可同时选择。
- [x] 普通用户入口推荐 `handouter run --asset /path/to/course.zip --output-dir ... --modes ...`；TUI 支持直接拖入 ZIP，`--input-dir` 仅保留兼容旧 CLI 扫描方式。
- [x] `Tab`/`↑↓` 导航、`Space` 多选、`Enter` 编辑/执行；普通界面左右键切换选项，文本编辑模式左右键移动光标并支持 Home/End/Backspace/Delete；提供 F5/P/Q 快捷键。
- [x] “只更新 Prompt”复用既有长课材料；多种输出按模式独立递增版本号，不重新跑 ffmpeg/ASR。
- [x] TUI 不复制业务逻辑，统一调用 handouter CLI；macOS/Linux 使用系统 curses，Windows 通过条件依赖 `windows-curses` 运行同一套 ASCII UI。
- [x] Agent interaction 可选 `GUI handoff / Codex CLI / Claude CLI`；GUI 为默认，CLI 模式自动执行本机 Agent。
- [x] 长任务使用跨平台任务树：macOS/Linux 新 session + SIGTERM/SIGKILL；Windows `CREATE_NEW_PROCESS_GROUP` + CTRL_BREAK_EVENT / `taskkill /T /F`。
- [x] Windows Terminal 路径解析支持盘符、引号、UNC、file URI；macOS/Linux 保留 POSIX 拖拽行为；portable lecture ID 拒绝 Windows 非法文件名/设备名。
- [x] stdlib-only PEP 517 backend；wheel 同时携带浏览器 userscript 与 Agent Skill，Windows wheel METADATA 声明 `windows-curses` 条件依赖。
- [x] GitHub Actions 改为 Linux/macOS/Windows 三平台矩阵；Windows 自动安装 ffmpeg、安装条件依赖并运行 doctor。
- [x] 多选专项回归覆盖 deep+summary、可选 full、独立输出和独立版本号。
- [ ] macOS 人工启动新版 ASCII TUI，确认 ZIP 拖入、中文路径编辑、输出目录、多选交付物、只更新 Prompt 和取消手感符合真实使用习惯。
- [ ] 在 Windows 11 + Windows Terminal 上真实验收 `windows-curses` TUI、Explorer 拖入、中文/空格路径、ffmpeg、任务树取消与 Codex/Claude CLI `.cmd/.exe` 调用。
- [ ] 首次 push 后确认 GitHub `windows-latest` / `macos-latest` / `ubuntu-latest` 三平台 CI 全绿。

## M4：Agent interaction 与渐进披露 Skill — 已实现，待真实 Agent E2E 验收

- [x] `SKILL.md` 收敛为薄入口；common/modes/formats/slides/execution 模块按 `sources.json.skill.modules` 渐进披露。
- [x] 每次 handoff 只复制本次真正需要的 Skill 模块到 `handoff/skill/`；Prompt、CLI Agent、GUI bundle 共用同一 module plan。
- [x] GUI/manual adapter 生成可上传 `gui-handoff-NNN.zip`，排除 audio/raw ASR/private/state/manifest/旧 notes，并对 bundle sources 做脱敏。
- [x] Codex adapter 使用非交互 `codex exec`；Claude adapter 使用 `claude --print`；不读取用户 API Key。
- [x] CLI Agent 自动执行后复核 workspace hash、handoff/control files、旧 notes 与全部 expected outputs；结构通过仍要求语义人工复核。
- [x] `handouter agents / bundle / agent-run` 与 `run/prompt --agent ...` 已接入；TUI 可切 GUI/Codex/Claude。
- [x] 本机实际检测到 Codex/Claude CLI，命令参数按真实 help 实现；mock 自动执行测试通过。
- [ ] 用一个可丢弃真实课程实际运行一次 Codex 或 Claude CLI Agent，确认权限、取消、耗时和模型服务商侧体验。
- [ ] 用 GUI/Web Agent 上传一次生成的 handoff ZIP，确认 Prompt/相对路径/图片引用均可直接工作。

## M5：真实 Agent 语义 / 格式验收 — 进行中

这一步不能由单元测试或格式检查替代。第一门完整长课已经跑通 full/deep/summary，并暴露了格式问题，已形成新版约束；产品入口现已支持一次选择多个独立交付物。

- [x] 第一门完整长课运行 `full/deep/summary`。
- [x] handoff / TUI 支持一次选择 deep + summary + 可选 full，且各自独立版本化输出。
- [x] 根据真实结果修正：新增 `verbatim` 保留忠实逐字整理；`full` 改为高覆盖率完整整理版，重点去口语/冗余并按语义重组段落；两者均禁止 ASR 双栏与 segment 机械分段。
- [x] 增加 `clean/traceable` 格式和 validator 格式偏航检查。
- [x] 增加 Prompt-only 重生成与历史归档，不重复 ASR；支持一次请求多种交付物，各自输出独立 Markdown。
- [x] 新增课堂顺序/考核重点框/每章 HTML 折叠规范：仅 summary 可重排，其余保留实际讲述顺序；公共 presentation 模块进入统一 plan。
- [ ] 按新规范刷新 handoff 并生成新版本，验收顺序、正文前重点框、课程信息与每章真实时间折叠及阅读器显示；此前成品不追溯视为已通过新格式。
- [ ] 至少再用一门内容类型明显不同的真实课程验证上述格式是否稳定。
- [ ] 覆盖 PPT：参考不嵌图、参考且嵌图、完全忽略三种条件。
- [ ] 人工抽样开头/中段/结尾、公式数字、否定限定、自我纠正、PPT 回翻。
- [ ] 检查无旧课程硬编码污染、无无来源履历/考核、无私有 URL/Cookie/API Key。
- [ ] `validate-note` 通过后仍需人工给出 ACCEPT / REJECT / CONDITIONAL。

完整标准见 [ACCEPTANCE.md](ACCEPTANCE.md)。

## 验收后增强（不阻塞 0.2.0）

- [ ] 阶段级缓存与断点 DAG，而不是当前“失败清理后整任务重试”。
- [ ] OCR 缓存、课程术语表、SRT/VTT。
- [ ] 更细的来源覆盖率/章节 provenance 与讲义版本 diff。
- [x] 建立三平台 GitHub Actions CI：Python 3.11 回归、JS 语法、ffmpeg、平台安装/doctor、tracked-file dirty 检查。
- [ ] 真实平台兼容矩阵；至少记录校内/校外、不同课程页面/媒体格式的真实验收结果。
- [ ] 验收后再物理迁移 `legacy/`，删除 Skill `scripts/` 重复副本和旧无效转义 warning。
- [x] Git 版本历史已建立并关联 GitHub 远端。
- [ ] release/tag 流程：真实验收前 `v0.2.0-rc1`，通过后 `v0.2.0`。

## 暂不投入

当前不做云端账户、数据库、课程分享平台、复杂 RAG、多 ASR 自动路由、通用 LLM API/密钥托管、飞书云端主流程。CLI Agent 自动执行只适配用户已经安装/登录的本机 Agent，不演变成 Handouter 自己的模型网关。
