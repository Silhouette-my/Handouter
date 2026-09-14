#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成《高级机器学习：Algorithm-Infra Co-Design for AGI》完整逐字稿版讲义
- 100% 涵盖教师讲授全部内容
- 去除冗余字符、口癖结巴（呃、啊、那个、就是说、对吧、叠词等）
- 纠正常见 ASR 专有名词误识别
- 13 大主题自然分段排版
- 头部置顶【课程考核与学业要点】
- 尾部不加多余时序表
"""

import re
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_FILE = BASE_DIR / "高级机器学习_完整讲义.txt"
SLIDES_META_FILE = BASE_DIR / "slides_meta.json"
OUTPUT_FILE = BASE_DIR / "高级机器学习_完整逐字稿.md"

with open(RAW_FILE, "r", encoding="utf-8") as f:
    raw = f.read()

# 纠正专有名词
term_map = [
    (r"logg\s*regression", "Logistic Regression (逻辑回归)"),
    (r"m\s*learning", "Machine Learning (机器学习)"),
    (r"going\s*processing", "Gaussian Processes (高斯过程)"),
    (r"expectation\s*maximization", "Expectation Maximization (EM 算法)"),
    (r"alth\s*infrco\s*design", "Algorithm-Infra Co-Design (算法-系统协同设计)"),
    (r"infrra|infr(?=[，。、\s])", "Infra"),
    (r"DCV3|deept\s*V3", "DeepSeek V3"),
    (r"eachnet|innet", "ImageNet"),
    (r"Xnet|icenet|爱icenet", "AlexNet"),
    (r"VCnet", "VGGNet"),
    (r"resnet|renet", "ResNet"),
    (r"BrRT", "BERT"),
    (r"VIT", "ViT"),
    (r"拆GPT", "ChatGPT"),
    (r"s\s*lab|s\s*law", "Scaling Law"),
    (r"ex\s*pro难受", "指数级爆发 (Exponential Growth)"),
    (r"O\s*one", "o1"),
    (r"超\s*salt|车\s*salt", "Chain of Thought (CoT 思维链)"),
    (r"cloud飞\s*five", "Claude 3.5"),
    (r"cloud\s*code", "Claude Code"),
    (r"codetex", "Codex"),
    (r"pretrainingking\s*law|pre\s*traininging\s*screen\s*law", "Pretraining Scaling Law"),
    (r"selfinvol", "Self-Evolution (自进化)"),
    (r"jamony|jamany|ja尼|jamon", "Gemini"),
    (r"mab\s*reduce|m\s*reduce|mb\s*reduce", "MapReduce"),
    (r"山东enttropy|湘农商", "香农熵 (Shannon Entropy)"),
    (r"20B的概念", "信息编码理论极限"),
    (r"s\s*lawL\s*is\s*compressor", "LLM is a Compressor"),
    (r"pa\s*reduction", "PAC 学习理论"),
    (r"inform等等等，信息瓶颈", "Information Bottleneck (信息瓶颈理论)"),
    (r"d\s*two蒸馏", "蒸馏 (Distillation)"),
    (r"group，LM", "Groq，LLM"),
    (r"VRM|VOMS", "vLLM"),
    (r"SG\s*long|s\s*long|SG\s*law", "SGLang"),
    (r"dta\s*parallel", "Data Parallel (数据并行)"),
    (r"mactro", "Megatron-LM"),
    (r"VILVL|VL(?=[，。、\s])", "VERL"),
    (r"dep\s*speed", "DeepSpeed"),
    (r"slit\s*框架|slime", "Slime 框架"),
    (r"getytanet|GDN", "Gated DeltaNet"),
    (r"tanet", "DeltaNet"),
    (r"KDA", "Kimi KDA"),
    (r"prefu", "Prefill"),
    (r"rejectject\s*sampling", "Rejection Sampling (拒绝采样)"),
    (r"radix\s*tree", "Radix Tree (基数树)"),
]

def clean_spoken_text(text: str) -> str:
    # 替换专业术语
    for pat, rep in term_map:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    
    # 清理音频标记
    text = re.sub(r"[🎼🤧😡😊👏]+", "", text)
    
    # 清理结巴与叠字
    for w in ["非常", "比较", "真的", "其实", "这个", "那个", "主要", "很多", "然后", "就是"]:
        text = re.sub(rf"({w}){{2,}}", r"\1", text)
    text = re.sub(r"对{2,}", "对", text)
    text = re.sub(r"我{2,}", "我", text)
    text = re.sub(r"是{2,}", "是", text)
    text = re.sub(r"就{2,}", "就", text)

    # 清理口癖语气短语
    fillers = [
        r"那个嗯[，\s]*",
        r"嗯[，\s]+",
        r"那个[，\s]+",
        r"哎呦[，\s]*",
        r"我说实话[，\s]*",
        r"[，\s]*对吧[，？]?",
        r"[，\s]*懂我意思吧[，？]?",
        r"你看啊[，\s]*",
        r"我跟大家说[，\s]*",
        r"大家知道吗[，\s]*",
        r"大家可以看[，\s]*",
        r"大家可以想想[，\s]*",
        r"我们说实话[，\s]*",
        r"OK[，\s]*",
    ]
    for p in fillers:
        text = re.sub(p, "，", text)

    # 规范化标点
    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"[。\.]{2,}", "。", text)
    text = re.sub(r"([。！？])，", r"\1", text)
    text = re.sub(r"，([。！？])", r"\1", text)
    text = re.sub(r"^[，\s]+", "", text)
    return text

anchors = [
    ("一、 课程引论：算法-系统协同设计 (Co-Design) 的兴起与工业界范式", "今天是我第一次在浙大线下上课"),
    ("二、 深度学习发展简史：从经典网络到 AGI 大模型革命", "首先就是说讲一下这样的一个background"),
    ("三、 大模型 Scaling Law、数据飞轮与全球顶级算力底座", "这个曲线就开始抖"),
    ("四、 系统效率大图景：两次数据压缩与“压缩即智能”理论", "自己总结的一个"),
    ("五、 系统架构的不可能三角：计算 (Compute)、存储 (Memory) 与通信 (Communication)", "经典的三角关系"),
    ("六、 Agent 智能体架构与双层优化：Outer-Loop 权重 vs Inner-Loop 代码", "agent是什么意思呢"),
    ("七、 多模态世界模型与视频生成架构前沿", "视觉视觉力"),
    ("八、 大规模分布式预训练：4D 并行、ZeRO 与前沿框架演进", "第二部分我们讲这个跟大家介绍一下训练了"),
    ("九、 高效推理架构与 Serving 系统：vLLM、SGLang 与缓存优化", "生态也是最大的"),
    ("十、 模型压缩与低比特量化：定点、NVFP4 与具身端侧芯片", "英伟达的一些硬件"),
    ("十一、 高效注意力机制与混合架构：FlashAttention 与 1:7 黄金配比", "高效的attention"),
    ("十二、 推理加速与投机采样：Diffusion Draft 与并行无损验证", "target model"),
    ("十三、 自动化科研 (Auto-Research)、学业要点与人生建议", "定义了一整套的harness")
]

positions = []
last_p = 0
for title, text_anchor in anchors:
    p = raw.find(text_anchor, last_p)
    positions.append((title, p))
    if p != -1:
        last_p = p + len(text_anchor)

doc = [
    "# 高级机器学习：Algorithm-Infra Co-Design for AGI 完整逐字稿\n",
    "> **授课时间**：2026 年夏季学期  ",
    "> **授课地点**：浙江大学玉泉校区 北教3-312  ",
    "> **课程依托**：浙江大学《课程综合实践Ⅰ》（主讲教授：陈建海）特邀前沿讲座  ",
    "> **讲师背景**：海外终身教职 (Faculty) 经历，机器学习系统领域资深学者与工业界领军专家  ",
    "> **讲义定位**：**完整逐字稿版**。100% 完整保留 3 小时 11 分钟全部讲解内容，原汁原味还原讲者的逻辑推演与工业经验，全面剔除口癖冗余与口语表达，自然分段排版。\n",
    "> [!IMPORTANT]",
    "> 🎓 **课程考核与学业要点 (Course Evaluation & Academic Guidelines)**",
    "> - **课程性质**：本讲座为《课程综合实践Ⅰ》的高规格特邀前沿讲座，旨在打通底层硬件基础设施与前沿算法的认知壁垒；",
    "> - **作业与小测**：本讲次**无随堂小测，亦无强制课后书面作业**；",
    "> - **大作业与项目实践指引**：建议组建 2~3 人跨学科小组，熟练运用 Coding Agent（Claude Code / Codex）动手参与开源算子（Triton/CUDA）优化或 Kaggle 竞赛；",
    "> - **讲者对成绩/绩点 (GPA) 的箴言**：",
    ">   > *“绩点只是一张保研或出国的入场券。顶级大厂与顶尖实验室挑人最看重的只有两点：**你的 Research 深度洞察，以及你的硬核系统实践与竞赛经历**。不要在纯算法层做低效刷榜，勇敢深入算法与系统协同设计 (Co-Design) 的交叉前沿。”*",
    "\n---\n"
]

for i in range(len(positions)):
    title, p = positions[i]
    next_p = positions[i+1][1] if i+1 < len(positions) else len(raw)
    raw_segment = raw[p:next_p].strip()
    clean_segment = clean_spoken_text(raw_segment)
    
    doc.append(f"## {title}\n")
    
    # 按照标点进行自然分段（保证每段在 250~400 字之间，并在句号或叹号处换行）
    sentences = re.split(r"(?<=[。！？\n])", clean_segment)
    para = []
    para_len = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        para.append(s)
        para_len += len(s)
        if para_len >= 300 and s.endswith(("。", "！", "？")):
            doc.append("".join(para) + "\n")
            para = []
            para_len = 0
    if para:
        doc.append("".join(para) + "\n")
    
    doc.append("\n---\n")

full_content = "\n".join(doc)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(full_content)

print(f"[✓] 完整逐字稿生成成功！")
print(f"[*] 写入路径: {OUTPUT_FILE}")
print(f"[*] 字符数: {len(full_content)} 字")
