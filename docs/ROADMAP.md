# Handouter 路线图

日期：2026-09-14。当前版本：**0.2.0 验收候选**。验收前工程已完成；未勾选项主要是必须使用真实智云/真实 Agent 才能完成的验收，或验收后的增强。

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
- [x] `full/deep/summary` 进入同一 handoff 协议。
- [x] `use_slides_as_source` 与 `embed_slides` 分开。
- [x] 自动生成 `handoff/PROMPT.md` 和 `sources.json`；不自动运行用户 Agent。
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
- [ ] **正式验收**：真实智云回放字段、真实签名媒体/403、完整长课 ASR。步骤见 `ACCEPTANCE.md`。

## M3：TUI 与可复现运行 — 验收前实现完成

- [x] TUI 不复制业务逻辑，统一调用 handouter CLI。
- [x] Textual 高级界面实现。
- [x] 未安装 Textual 时自动回退标准库 curses。
- [x] 长任务独立进程组；取消会终止底层 ffmpeg/FunASR。
- [x] `doctor` 分开报告 core/media/asr/tui readiness。
- [x] stdlib-only PEP 517 backend；核心包可 `pip install --no-index .`。
- [x] editable 离线安装通过。
- [ ] **正式验收**：人工启动一次 TUI，并在真实/可丢弃长任务上测试取消。

## M4：真实 Agent 语义验收 — 待执行

这一步不能由单元测试或格式检查替代。

- [ ] 至少两门内容明显不同的真实课程。
- [ ] 每门运行 `full/deep/summary`。
- [ ] 覆盖 PPT：参考不嵌图、参考且嵌图、完全忽略三种条件。
- [ ] 人工抽样开头/中段/结尾、公式数字、否定限定、自我纠正、PPT 回翻。
- [ ] 检查无旧课程硬编码污染、无无来源履历/考核、无私有 URL/Cookie/API Key。
- [ ] `validate-note` 通过后仍需人工给出 ACCEPT / REJECT / CONDITIONAL。

完整标准见 [ACCEPTANCE.md](ACCEPTANCE.md)。

## 验收后增强（不阻塞 0.2.0）

- [ ] 阶段级缓存与断点 DAG，而不是当前“失败清理后整任务重试”。
- [ ] OCR 缓存、课程术语表、SRT/VTT。
- [ ] 更细的来源覆盖率/章节 provenance 与讲义版本 diff。
- [ ] 真实平台兼容矩阵与 CI。
- [ ] 验收后再物理迁移 `legacy/`，删除 Skill `scripts/` 重复副本和旧无效转义 warning。
- [ ] Git 版本历史和 release/tag 流程。

## 暂不投入

当前不做云端账户、数据库、课程分享平台、复杂 RAG、多 ASR/LLM 自动路由、自动接管用户 Agent、飞书云端主流程。先完成真实验收再决定产品扩展。
