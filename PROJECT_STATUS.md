# 项目状态

更新：2026-09-14。阶段：**0.2.0 验收候选；验收前工程已完成，等待真实智云 + 真实 Agent 语义验收。**

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
handoff/PROMPT.md + sources.json
        ↓
用户自己的 Agent
        ↓
notes/<mode>-NNN.md
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
| Agent handoff | 已实现 | `full/deep/summary`；PPT 参考和嵌图分离；不自动运行 Agent |
| Agent 输出验证 | 已实现 | 输出位置、图片路径、嵌图策略、明显凭证泄漏；语义状态始终保留人工复核 |
| TUI | 已实现 | 优先 Textual；未安装时标准库 curses；任务由独立进程组运行，支持取消 |
| 环境诊断 | 已实现 | `doctor` 分开报告 core/media/asr/tui，不自动安装 |
| 安装 | 已实现并干净环境验证 | stdlib-only PEP 517 backend；`pip install --no-index .` / `-e .` 均成功 |
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
- TUI 复用 CLI：Textual 界面和 curses fallback 都不实现第二套业务逻辑；取消会终止任务进程组。
- `doctor` 在当前 Mac 上报告 core/media/asr 可用；Textual 未安装，但 curses fallback 可用。

### 打包

- 项目版本更新到 `0.2.0`。
- `handouter_build.py` 是 stdlib-only PEP 517 backend；核心安装不要求网络下载 setuptools/hatchling。
- 全新 venv 已验证：
  - `pip install --no-index .` 成功；
  - `pip install --no-index -e .` 成功；
  - 安装后 `handouter --help` 和 `doctor` 正常。

## 已执行验证

### 自动化

当前完整回归：**89 / 89 通过**。

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
- TUI 参数与 curses fallback；
- stdlib 构建 backend/wheel。

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
| Textual | 当前 `.venv` 未安装（非阻塞） |
| curses | 可用，TUI fallback |
| Git | 已初始化并关联 GitHub 远端：`https://github.com/Silhouette-my/Handouter` |

## 尚未通过的内容 = 正式验收本身

以下不是“待开发功能”，而是必须使用真实用户授权材料/真实 Agent 才能完成的验收：

1. 在真实智云回放页面验证 v1.4 导出字段：PPT 数量、时间字段状态、private 视频 URL 和缺图状态。
2. 用真实签名媒体 URL 跑 `build-asset`，验证校园内/外网络、403/过期链接行为。
3. 至少一门完整长课跑整课 ASR，检查内存、耗时、时间段单调性、取消行为。
4. 至少两门不同真实课程，让用户自己的 Agent 分别生成 `full/deep/summary`，人工检查遗漏、否定/限定、公式、ASR 错词、额外扩写和 PPT 错配。
5. 人工操作一次 TUI（建议同时测试取消）。

逐项步骤和通过标准见 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。

## 非验收阻塞项 / 后续增强

- 阶段级断点恢复目前仍是“失败清理临时目录后整任务重试”，没有复杂缓存 DAG。
- OCR 自动缓存、SRT/VTT、术语表、讲义版本 diff、CI、legacy 物理迁移可在真实验收后按需求推进。
- 根目录旧单课脚本未删除，以免破坏现有样例溯源；0.2.0 不调用它们。
