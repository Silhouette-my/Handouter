# PPT / 智云资产 ZIP 导入协议

更新：2026-09-14，适用于 Handouter 0.2.0。**生产实现位于 `src/handouter/importers.py`**；根目录 `download_slides.py -z` 只是兼容旧命令的包装。完整课程推荐直接使用 `handouter prepare --slides-zip` 或 `handouter build-asset`。

## 推荐使用

### 只导入 PPT 到交接工作区

```bash
PYTHONPATH=src .venv/bin/python -m handouter prepare \
  --lecture-id lecture-001 \
  --course-title "课程名称" \
  --transcript /path/to/transcript.txt \
  --slides-zip /path/to/资产包.zip
```

### 新版智云资产 ZIP 一键处理

```bash
PYTHONPATH=src .venv/bin/python -m handouter build-asset \
  /path/to/资产包.zip \
  --lecture-id lecture-001 \
  --course-title "课程名称"
```

`build-asset` 会从 ZIP 的 `private/source.json` **只在内存中**读取视频 URL，PPT importer 不会把 `private/`、媒体签名 URL 或 page URL 解包到工作区。

旧兼容接口仍可用：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python download_slides.py \
  --zip /path/to/资产包.zip \
  --output-dir /new/path/slides
```

输出目录必须不存在；不会覆盖已有课程材料。

## v1.4 浏览器资产格式

新版 `zhiyun_exporter.user.js` 导出：

```text
课程资产.zip
├── slides/
│   └── slide_001.jpg ...
├── slides_meta.json
├── course_info.json              # 公共安全课程摘要
└── private/
    └── source.json               # 视频/page URL；私有，不交给 Agent
```

`slides_meta.json` 不保存图片签名 URL。时间字段约定：

- 明确时间：`timestamp` + `seconds`；
- 未知时间：二者为 null；
- 无法确认单位的原始数值：保留 `timeStatus=unknown_numeric_unit`、`sourceField`、`rawTimeValue` 供诊断，但不会被 importer 猜成秒/毫秒；
- 图片下载状态：`status=ok|missing_image`。

旧资产仍兼容 `timestamp/time/switchTime` 时钟字符串和明确为秒的 `seconds`，但多个时间字段若互相矛盾会拒绝导入。

## 时间与展示事件

时间统一为**整数毫秒**：

| 字段 | 含义 |
| --- | --- |
| `start_ms` | 展示开始；未知为 null；真实零秒为 0 |
| `end_ms` | importer 不猜末尾，通常为 null；后续 alignment 可用下一次事件开始推导临时区间 |
| `timestamp_kind` | `metadata` / `filename` / `unknown` |
| `occurrence_id` | 展示事件 ID，而非唯一 PPT 图片 ID |

老师回翻同一张 PPT 时，同一图片可以对应多个 occurrence；不得为了“页码递增”删除回翻事件。完全没有元数据的旧 ZIP 才会兼容文件名 `slide__00-02-05.jpg`；普通文件名没有时间则保持 unknown。

## 图片与缺失

支持 JPEG、PNG、WebP，以**实际文件头**确定输出后缀，而不是盲信 ZIP 内扩展名。当前仅做文件头/体积级验证，不代表完整畸形图片安全解码审计。

元数据引用缺图时保留事件并标 `missing_image`；未被元数据引用的图片也保留为 `unreferenced_image`，不赋予虚构时间。

## ZIP 安全边界

生产 importer：

- 不使用 `extractall()`；
- 拒绝绝对路径、`..`、反斜线/跨平台歧义路径；
- 拒绝符号链接、加密成员、大小写/Unicode 重名；
- 最多 10,000 成员；
- 总未压缩体积 ≤ 512 MiB；
- 单图 ≤ 32 MiB；
- PPT 元数据 ≤ 8 MiB；
- `private/source.json` 读取上限 1 MiB，且只允许唯一 HTTP(S) `videoUrl`；
- 新目录排他写入；可捕获失败清理本次新产物。

这些保护不等于抵御恶意本地并发写入或强制断电的事务系统。

## 隐私边界

整个浏览器资产 ZIP 应视为私有文件，因为 `private/source.json` 可能含短期签名媒体 URL。Handouter 的公共工作区只保存：

- PPT 图片；
- 安全时间/缺失诊断；
- 本地抽取音频；
- ASR 结果；
- handoff。

不会把 `private/source.json`、完整 URL、Cookie、API Key 复制进 manifest/Prompt/sources。合成 E2E 已使用私有签名参数实际搜索确认未泄漏；真实智云仍按 `ACCEPTANCE.md` 验收。

## 与 ASR 的关联

当工作区同时有 `transcript/segments.json` 和 PPT 时间事件时，生成 `slides/alignment.json`。该文件只表示时间区间相交：

- 跨页句子可以关联多张 PPT；
- 未知 ASR/PPT 时间保持 unavailable；
- 不把时间相交表述成语义“精准对应”。

## 验证状态

当前完整项目回归为 **89 / 89 通过**。其中 `tests/test_slide_import.py` 继续覆盖 35 项 ZIP 专项回归；另外的 importer、浏览器契约、workspace、媒体、ASR、TUI、安装等测试共同构成 89 项。

尚需真实验收：智云 v1.4 页面字段、真实 CDN/m3u8/mp4、整课 ASR 和真实 Agent 讲义语义，详见 [ACCEPTANCE.md](ACCEPTANCE.md)。
