---
name: zhiyun-lecture-notes
description: >-
  Automated end-to-end pipeline to convert Zhejiang University (ZJU) Zhiyun Classroom
  replay packages or recordings into textbook-grade, in-depth illustrated lecture notes
  with PPT alignment and local SenseVoice transcription. Trigger this skill whenever the user
  mentions "智云课堂", "生成图文笔记", "课程转写", "整理讲义", or provides a Zhiyun package ZIP / video URL.
---

# 智云课堂全自动图文深度讲义 Skill (ZJU Zhiyun Lecture Notes)

本 Skill 将浙江大学智云课堂的录像/资产包转化为**高精度的教材级图文深度讲义**。

---

## 核心工作流 (Workflow)

```
1. 资产接收 (ZIP 包或目录)
       ↓
2. 音轨高速抽取 (ffmpeg 绕过网络代理流式抽取)
       ↓
3. 本地 SenseVoice 离线转写 (FunASR + VAD + ITN，~37x 实时速度)
       ↓
4. 口语化清洗与自然语义分段 (过滤重复词、语气词、噪音标签)
       ↓
5. PPT 切换时间戳与讲解内容时序对齐 (Timestamp Matching)
       ↓
6. 万字级教材深度图文讲义编排生成 (拒绝过度精简，保留所有推导与内幕)
```

---

## 一、 快速使用指南

当用户提供以下任一输入时触发本流程：
- **输入 A**：从智云小助手或 Tampermonkey 导出的资产包 `*.zip`；
- **输入 B**：智云视频流链接（含 `auth_key`）及 PPT 图片目录 `slides/`；
- **输入 C**：已有本地音频 `course_audio.m4a` 及 PPT 导出的 `ppt_list.json`。

### 执行命令
直接在工作目录运行内置的 Pipeline：
```bash
python3 .agents/skills/zhiyun-lecture-notes/scripts/pipeline.py -z [资产包.zip]
```
或者分步运行：
```bash
# 1. 抽取音轨
python3 -c "import zhiyun_to_feishu; zhiyun_to_feishu.extract_audio(url, 'course_audio.m4a')"

# 2. 运行 SenseVoice 转写 (使用已配置的 Python 虚拟环境)
.venv/bin/python3 run_sensevoice.py

# 3. 下载并对齐 PPT
python3 download_slides.py -j ppt_list.json
```

---

## 二、 讲义生成规范与三大模式 (Quality Standards & Modes)

流水线支持三种定位截然不同的输出模式，并通过参数 `--slides / --no-slides` 控制是否在正文中插入 PPT：

1. **深度教材版 (`--mode deep`) [推荐默认]**：
   - **篇幅由原始文本深度自然决定**：不设死板字数上限或下限，全面覆盖教师讲授的所有核心知识点；
   - **教材级推导与系统剖析**：保留完整的数学推导公式（LaTeX）、底层系统硬件架构图（Mermaid）、工业界实战内幕与权衡哲学；
   - **单调递增时序对齐**：幻灯片按照时间戳单调递增插入对应章节，杜绝时序倒流；
2. **完整逐字稿版 (`--mode full`)**：
   - **去除冗余字符与口语表达**：全面过滤口头禅（“呃”、“啊”、“那个”、“就是说”、“对吧”等）、结巴叠字与语音识别噪音；
   - **自然语义分段**：按照讲述逻辑划分为章节与标准段落，100% 完整保留教师原始讲授信息；
3. **精简速记版 (`--mode summary`)**：
   - 提炼核心考点、知识图谱、核心技术架构对比总表，适合快速查阅与期末速记。

---

## 三、 结构与版式强约束 (Layout & Structure Constraints)

1. **头部置顶【课程考核与学业要点】专区**：
   - 所有讲义模式均必须在文档头部置顶 `[!IMPORTANT]` 提示框；
   - 重点列明：课程性质、作业与小测要求、期末/大作业考核方式、小组合作实践要求及讲者关于成绩/绩点 (GPA) 的针对性建议；
2. **严禁在文末生成冗余时序对照表**：
   - 幻灯片信息已在正文中以图文时序块自然展现，正文结束即全文完结，禁止在尾部追加冗长的时序索引附录表；
3. **主流 Agent 与未来 API 升级兼容**：
   - 采用纯标准 Prompt + Skill 体系，无缝适配 Antigravity、Claude Code、Cursor 与 Windsurf 等各大 Agent；
   - 脚本中内置 `BaseLLMClient` 抽象层，为后续直接接入外部 LLM API 预留扩展桩。

---

## 四、 常用命令行参数速查

```bash
# 1. 交互式运行（自动提示选择模式与是否配图）
python3 pipeline.py

# 2. 生成深度教材版（配图）
python3 pipeline.py -m deep --slides

# 3. 生成深度纯文本版（不配图）
python3 pipeline.py -m deep --no-slides

# 4. 生成完整整理逐字稿（去口语分段）
python3 pipeline.py -m full

# 5. 生成精简速记版
python3 pipeline.py -m summary
```
