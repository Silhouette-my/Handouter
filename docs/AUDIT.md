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
Agent handoff
        ↓
用户自己的 Agent
        ↓
结构校验 + 人工语义验收
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

`handoff/PROMPT.md` 与 `sources.json` 自动生成，绑定 Skill、课程材料、三档模式、PPT 两策略和新的 notes 输出路径。CLI 明确 `agent_was_run: false`；Handouter 不冒充已经生成讲义。

Agent 输出后提供 `validate-note`，但结构通过仍标记 `semantic_review: required`。

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

状态：**核心安装与 TUI fallback 已解决。**

- stdlib-only `handouter_build.py` 允许全新 venv `pip install --no-index .` 和 `-e .`；无需联网拉 setuptools。
- Textual 是可选高级 TUI；未安装时自动使用标准库 curses。
- `doctor` 分开报告 core/media/asr/tui readiness，不自动重装用户环境。

## 当前仍需正式验收的问题

### A. 真实智云页面协议

合成 JS 契约只能证明 v1.4 不再猜时间，不能证明当前智云页面真正暴露的是哪个字段、单位以及所有页面结构都兼容。必须按 `ACCEPTANCE.md` 在授权页面验证 PPT 数量、timeStatus、private 视频 URL、缺图汇总。

### B. 真实校园媒体与过期链接

合成本地 HTTP 链路已通过，但真实 CDN/m3u8/mp4 的 Range、Referer、代理、zju-connect、403 和签名过期行为必须实测。过期应失败并要求重新导出，不能产出假成功音频。

### C. 完整长课 ASR

2 分钟真实音频已验证，不等于 1–3 小时整课的内存、耗时、MPS 稳定性和取消边界已经通过。整课验收还要检查 segment 时间范围和长期运行行为。

### D. 真实 Agent 语义质量

自动程序能检查来源文件、图片链接和明显凭证泄漏，但无法证明：

- full 没有遗漏或改写限定；
- deep 的补充解释没有冒充教师原话；
- summary 没删掉结论成立的前提；
- ASR 术语纠错和 PPT 对照符合课程原意。

至少两门不同真实课程 × 三模式必须人工抽样。

### E. TUI 人工取消

Textual/curses 都已实现进程组取消逻辑并有代码级回归，但仍应在一个可丢弃的长 ASR 任务上人工按取消，确认系统进程确实结束。

## 非阻塞技术债

- 项目尚未初始化 Git/CI，不能依赖版本历史恢复并行改动；正式继续迭代前建议初始化版本控制。
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
| `.agents/skills/zhiyun-lecture-notes/` | 用户 Agent 的通用讲义规范 |
| `tests/` | 合成/离线回归；当前 89 项 |
| `pipeline.py` / `build_*.py` / `generate_*.py` / `clean*.py` | 单课 legacy，不是生产入口 |
| `zhiyun_to_feishu.py` | legacy 飞书实验；主链路不调用 |
| 根目录课程音频/PPT/讲义 | 私有历史样例；验收前不物理迁移 |

## 审计边界

验收前工程已经实际运行：89 项回归、真实 ffmpeg、本地 2 分钟 SenseVoice、合成私有网络资产 E2E、干净 venv 离线安装。没有登录真实智云完成 v1.4 页面验收，没有跑整门 3 小时 ASR，没有自动运行用户 Agent，也没有逐句核验旧样例讲义。

因此当前最准确结论是：**工程已进入正式验收阶段，而不是“所有真实场景已经通过”。**
