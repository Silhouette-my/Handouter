# Handouter 0.2.0 验收前审计

日期：2026-09-14。状态：**验收候选**。本文记录当前仍成立的风险和已经关闭的旧问题；实际功能状态以 `PROJECT_STATUS.md` 为准，正式验收以 `ACCEPTANCE.md` 为准。

## 结论

项目已经从“单门《高级机器学习》脚本集合”演进为一条独立的本地主链路：

```text
智云资产 ZIP / 本地媒体 / 本地音频 / 已有转写
        ↓
媒体与 PPT 安全导入
        ↓
本地 SenseVoice（可选）
        ↓
标准工作区 + 时间证据
        ↓
Agent handoff + progressive Skill plan
        ↓
GUI handoff ZIP  /  Codex·Claude CLI 自动执行
        ↓
结构/篡改校验 + 人工语义验收
```

0.2.0 的主要工程阻断已经解决；现在不能靠更多合成测试替代的，是**真实智云字段/签名媒体、完整长课和真实 Agent 的语义验收**。

## 已关闭的高影响问题

### 1. 旧 `pipeline.py` 名义与行为不符

状态：**生产链路已绕开，legacy 保留。**

旧 `pipeline.py` 仍只会选取/调用本课固定 Markdown 和 builder，不能代表新课程流水线。0.2.0 的生产入口为 `src/handouter/cli.py`；旧文件不再被新 service/TUI 调用，也不用于验收。

### 2. 讲义正文和课程知识硬编码

状态：**从生产链路移除。**

`build_*.py` / `generate_*.py` 等仍保留历史样例和溯源，但语义写作现在交给用户自己的 Agent + 通用 Skill。新代码不会把《高级机器学习》的课程标题、章节、讲师背景或考核信息写进通用生成逻辑。

### 3. PPT ZIP 时间元数据丢失

状态：**已修复并统一实现。**

生产 importer 位于 `handouter.importers`：优先读取 `slides_meta.json`，统一整数毫秒，未知时间为 null，保留缺图、重复展示和未引用图片；拒绝路径穿越、重名/Unicode 歧义、符号链接、加密成员和超限资源。根目录 `download_slides.py` 的 ZIP 分支仅为兼容包装，不再维护第二套生产实现。

### 4. ASR 只输出 TXT、没有时间证据

状态：**已修复。**

`handouter.asr` 保存：

- `transcript/raw.json`：FunASR 原始结果、模型、版本、参数、设备；
- `transcript/segments.json`：标准化 start/end 毫秒或 null；
- `transcript/transcript.txt`：便于 Agent/人工阅读。

仓库真实 2 分钟音频已在 MPS 上运行成功；纯标点 VAD 噪声从标准 segments 过滤但 raw 仍保留。

### 5. 没有自动 Agent 交接协议

状态：**已修复。**

`handoff/PROMPT.md` 与 `sources.json` 自动生成，绑定课程材料、可组合交付物、PPT 策略和新的 notes 输出路径；`sources.json.skill.modules` 进一步给出本次唯一 Skill module plan，并把对应模块物化到 `handoff/skill/`。

默认/GUI 路径不运行模型，只生成安全 bundle；用户显式选择 Codex/Claude CLI 时 Handouter 可自动执行本机 Agent。自动执行后会复核课程材料、handoff/control files、旧 notes 与新输出；结构通过仍标记 `semantic_review: required`，不冒充语义已验收。

### 6. 浏览器导出器猜时间单位、未知时间伪零

状态：**代码已修复，真实平台语义待验收。**

v1.4 删除 `>10000` 就除以 1000 的启发式：

- `created` 数值按已知秒字段处理；
- `HH:MM:SS(.sss)` 显式解析；
- 其他无法确认单位的数值字段不猜，保存 raw 值并标 `unknown_numeric_unit`；
- 完全未知时间为 null。

这解决了代码层的数据伪造问题，但仍要在真实智云页面验证实际字段名称/含义。

### 7. 签名 URL / Cookie 传播到公共材料

状态：**主链路已隔离。**

v1.4 公共 `slides_meta.json` 不再保存图片 URL，视频/page URL 放进 ZIP 的 `private/source.json`。`build-asset` 只在内存读取媒体 URL；private 文件不解包、不复制到 workspace、不写入 Prompt/manifest/sources。合成网络 E2E 已实际搜索验证签名字符串未泄漏。

### 8. 音频抽取依赖旧飞书脚本、可覆盖、清代理

状态：**已建立独立主链路。**

`handouter.media` 与飞书无关：不清 proxy 环境、不覆盖目标、先写临时文件；支持 stream-copy / AAC fallback。验收前测试发现“ffprobe 时长正常但 AAC 帧损坏”这一真实边界，因此当前还会实际解码开头/尾部样本，坏 copy 不会进入 ASR。

旧 `zhiyun_to_feishu.py` 仍作为 legacy 实验存在，不属于 0.2.0 主流程。

### 9. 无可复现安装 / TUI 依赖阻塞

状态：**macOS/Linux 核心安装已解决；Windows 已加入条件依赖与 CI，真实 runner 待验收。**

- stdlib-only `handouter_build.py` 不需要联网拉 setuptools；macOS/Linux 全新 venv 可 `pip install --no-index .`。
- 普通用户 TUI 使用同一套 curses ASCII 界面：macOS/Linux 使用系统 curses；Windows wheel 声明 `windows-curses>=2.4; sys_platform == 'win32'`，自定义 backend 会把该条件依赖写入 `METADATA`。
- `doctor` 新增 platform 字段并分开报告 core/media/asr/tui readiness；Windows 会显示 `windows-curses` 版本或安装提示。
- GitHub Actions 已扩为 Linux/macOS/Windows 三平台矩阵；真实 Windows runner 需 push 后确认，当前不把纯函数模拟测试扩大为“Windows 已通过”。

## 当前仍需正式验收的问题

### A. 真实智云页面协议

合成 JS 契约只能证明 v1.4 不再猜时间，不能证明当前智云页面真正暴露的是哪个字段、单位以及所有页面结构都兼容。必须按 `ACCEPTANCE.md` 在授权页面验证 PPT 数量、timeStatus、private 视频 URL、缺图汇总。

### B. 真实校园媒体与过期链接

合成本地 HTTP 链路已通过，但真实 CDN/m3u8/mp4 的 Range、Referer、代理、zju-connect、403 和签名过期行为必须实测。过期应失败并要求重新导出，不能产出假成功音频。

### C. 完整长课运行边界

用户已实际跑通一门完整长课并生成三种成品，证明主链路可以完成长任务；仍需补记内存/耗时，并人工测试取消边界。分层 Skill 会在 segments 足够多或纯 TXT 足够长时自动加入 `execution/long-course.md`。

### D. 真实 Agent 语义质量

自动程序能检查来源文件、图片链接和明显凭证泄漏，但无法证明：

- full 没有遗漏或改写限定；
- deep 的补充解释没有冒充教师原话；
- summary 没删掉结论成立的前提；
- ASR 术语纠错和 PPT 对照符合课程原意。

至少两门不同真实课程、覆盖多种交付物组合必须人工抽样。

### E. Agent interaction 真实 E2E

GUI bundle 的内容/隐私边界与 Codex/Claude adapter 已有合成回归。2026-09-15 按用户授权，Codex 在独立真实课程副本中完成新版四模式生成，结构/哈希及独立 AI 语义核对通过。仍需验收 GUI 上传、Claude、取消和 Windows 宿主行为；材料疑点和人工语义复核边界保留，最新证据以 `PROJECT_STATUS.md` 为准。

### F. TUI 人工取消

ASCII curses TUI 已实现跨平台任务树取消逻辑并有代码级回归：macOS/Linux 新 session + SIGTERM/SIGKILL；Windows `CREATE_NEW_PROCESS_GROUP` + CTRL_BREAK_EVENT / `taskkill /T /F`。仍应分别在 macOS 和 Windows 的可丢弃长任务上人工取消，确认 ffmpeg/FunASR 以及后续 CLI Agent 子进程都结束。

## 非阻塞技术债

- Git 与最小 GitHub Actions CI 已建立；release/tag 尚待按 `docs/RELEASE.md` 在真实验收节点执行。
- 当前失败恢复是“临时产物清理 + 整任务重试”，不是阶段级 DAG/断点缓存。
- ZIP 图片做文件头/大小检查，不等同于针对所有畸形图像的安全解码审计。
- 自动 OCR、术语表、SRT/VTT、章节来源覆盖率、讲义版本 diff 尚未产品化。
- legacy `build_clean_verbatim_and_summary.py` 和 Skill 历史副本仍有 `\\m` DeprecationWarning；不影响 0.2.0 主链路，为避免修改历史公式内容暂未清理。

## 当前文件定位

| 文件/目录 | 当前定位 |
| --- | --- |
| `src/handouter/` | 0.2.0 生产代码 |
| `zhiyun_exporter.user.js` | 浏览器授权资产导出器 v1.4 |
| `download_slides.py` | 旧 CLI 兼容包装；ZIP 逻辑代理 `handouter.importers` |
| `.agents/skills/zhiyun-lecture-notes/` | 薄 Skill 入口 + progressive-disclosure reference modules |
| `src/handouter/agents/` | GUI bundle 与 Codex/Claude CLI interaction adapters |
| `tests/` | 合成/离线回归；当前 141 项（macOS 本机），含 Agent adapters、GUI bundle、Skill module plan、ZIP/TUI/多输出/格式约束、Windows 路径/进程/doctor/portable workspace/文件名 |
| `pipeline.py` / `build_*.py` / `generate_*.py` / `clean*.py` | 单课 legacy，不是生产入口 |
| `zhiyun_to_feishu.py` | legacy 飞书实验；主链路不调用 |
| 根目录课程音频/PPT/讲义 | 私有历史样例；验收前不物理迁移 |

## 审计边界

当前工程已有真实 ffmpeg、本地短音频 SenseVoice、合成网络资产 E2E、离线安装和用户完整长课运行记录。最新自动化回归与真实 Codex 四模式生成结果见 `PROJECT_STATUS.md`；Codex 本轮复用已有 ASR，不能扩大为重新跑通媒体下载/ASR。Windows 真机/runner、GUI 上传、Claude、取消、第二门不同课程及更多智云页面/媒体兼容性仍待验收。独立 AI 语义核对不替代教师确认与源材料疑点核实。

因此当前最准确结论是：**主链路已经过真实长课验证，项目正在从“能跑通”转向 Prompt/格式和普通用户体验收敛。**
