# Handouter 0.2.0 正式验收清单

日期：2026-09-14。状态：**验收前工程完成，等待真实用户授权材料与真实 Agent 验收。**

本清单只验收 0.2.0 的核心价值：**跨课程、证据可追溯、不覆写原始材料、能从智云资产稳定准备本地 Agent 交接包，并让三档讲义保持课程原意。** 不把 CI、OCR、复杂断点 DAG、云端分享等后续增强混入当前验收。

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
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
node --check zhiyun_exporter.user.js
```

通过条件：

- `ok_core=true`、`ok_media=true`；要跑 ASR 时 `ok_asr=true`；TUI 至少有 Textual 或 curses 一种后端。
- 自动化测试全部通过。
- userscript JS 语法通过。

若要验证干净安装，使用新的临时 venv：

```bash
python3 -m venv /tmp/handouter-accept
/tmp/handouter-accept/bin/python -m pip install --no-index .
/tmp/handouter-accept/bin/handouter --help
```

核心安装不应访问 PyPI。

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
  --mode deep \
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

## 5. 两门真实课程 × 三档 Agent 语义验收

至少选两门内容明显不同的课，防止旧《高级机器学习》硬编码污染结果。每门至少生成一次 `full/deep/summary`；PPT 条件建议覆盖：参考+不嵌图、参考+嵌图、完全忽略 PPT。

Agent 使用工作区 `handoff/PROMPT.md`，不要运行旧 `pipeline.py` / `build_*.py` 代替语义生成。

生成后：

```bash
PYTHONPATH=src .venv/bin/python -m handouter validate-note \
  workspace-accept/<lecture-id> --update-state
```

人工抽样至少覆盖开头、中段、结尾、公式/数字密集处、教师自我纠正/否定处、PPT 回翻处。

### full

通过条件：保留原讲述顺序、案例、限定、问答；只清理无意义口癖/噪声；不得把否定改肯定、把“可能”改成定论、把大量正文压缩成摘要。

### deep

通过条件：核心内容、公式、推导、案例和权衡可学习；课程外扩展明确标注为补充；不能把 Agent 常识冒充教师所讲；PPT 插图与附近内容相关。

### summary

通过条件：能快速理解本讲主题和结论；压缩次要细节但保留结论成立的前提；不凭空生成考点、考试范围或作业要求。

### 共通否决项

以下任一出现则本轮语义验收不通过：

- 关键知识明显遗漏或章节只处理头尾；
- 数值、公式、否定、适用条件被改错；
- 混入另一门课程/旧样例的固定内容；
- 没有来源的讲者身份、履历、考核信息被捏造；
- 不确定 ASR 词被擅自“纠正”为没有证据的词；
- PPT 错配且被写成“精准时序”；
- 登录信息、签名 URL、Cookie、API Key 出现在讲义或工作记录中。

## 6. TUI 人工验收

运行：

```bash
PYTHONPATH=src .venv/bin/python -m handouter tui
```

当前 `.venv` 没有 Textual 时应自动进入 curses fallback；安装 Textual 后可另测完整表单版。

通过条件：

- [ ] 能选择资产 ZIP / TXT / 音频 / 媒体输入，三档模式和 PPT 策略能映射到 CLI。
- [ ] 长任务期间界面/日志仍响应。
- [ ] 取消后底层任务进程组结束。
- [ ] 失败后没有正式半成品讲次目录；修正输入后可重新运行。
- [ ] 成功只提示 handoff ready，不提示“讲义生成完成”。

## 7. 验收结果记录模板

```text
日期：
机器/系统：
Handouter 版本：0.2.0
课程 A：
课程 B：
智云导出：PASS / FAIL
真实 build-asset：PASS / FAIL
整课 ASR：PASS / FAIL
full：PASS / FAIL
 deep：PASS / FAIL
summary：PASS / FAIL
TUI + cancel：PASS / FAIL
发现的问题：
人工复核样本：
最终结论：ACCEPT / REJECT / CONDITIONAL
```

所有关键项通过后，0.2.0 才从“验收候选”改为“已验收”。
