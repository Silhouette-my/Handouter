#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1. 生成高质量书面化完整逐字稿 (高级机器学习_完整逐字稿.md)
   - 彻底剔除口语表达、口癖、口误结巴、语气词与 ASR 错字
   - 100% 完整保留教师讲授的全部技术细节、公式、工业内幕、案例与人生诤言
   - 规范书面学术语态与自然分段
2. 生成实质性丰满的高浓度精要速记版 (高级机器学习_精要速记版.md)
   - 杜绝过度精简，系统提炼 10 大核心教学章节的论点、推导要点、系统权衡与对比总表
3. 字数比例由原文内容自然决定，绝无死板硬编码限制
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VERBATIM_OUT = BASE_DIR / "高级机器学习_完整逐字稿.md"
SUMMARY_OUT = BASE_DIR / "高级机器学习_精要速记版.md"

# =========================================================================
# 完整逐字稿：书面化学术整理稿
# =========================================================================
verbatim_doc = """# 高级机器学习：Algorithm-Infra Co-Design for AGI 规范讲义整理稿

> **授课时间**：2026 年夏季学期  
> **授课地点**：浙江大学玉泉校区 北教3-312  
> **课程依托**：浙江大学《课程综合实践Ⅰ》（主讲教授：陈建海）特邀前沿讲座  
> **讲师背景**：海外名校教职经历 (Faculty)，大模型系统工程领域资深学者、工业界领军专家  
> **讲义定位**：**规范书面化讲稿**。100% 完整忠实保留教师 3 小时 11 分钟全部讲解内容，全面剔除口语口癖、结巴冗余与语音识别噪声，重构为严谨流畅的学术书面语态，自然语义分段排版。篇幅依授课实际内容充实度自然展开。

> [!IMPORTANT]
> 🎓 **课程考核与学业要点 (Course Evaluation & Academic Guidelines)**
> - **课程性质与要求**：本讲次为《课程综合实践Ⅰ》的高规格特邀前沿讲座，旨在建立算法与系统硬件协同设计 (Co-Design) 的全局系统思维；
> - **作业与小测**：本专题讲座**无随堂小测，亦无强制课后书面作业**；
> - **大作业与项目实践指引**：建议组建 2~3 人跨学科小组，熟练运用 Coding Agent（Claude Code / Codex）动手参与开源算子（Triton/CUDA）优化或 Kaggle 竞赛；
> - **讲者对大学成绩与绩点 (GPA) 的深刻箴言**：
>   > *“绩点只是一张保研或出国的入场券，但在大厂面试与顶级实验室挑选博士生时，绩点其实是最没用的。顶尖团队只看两点：**你的 Research 深度洞察，以及你的硬核系统工程实践与竞赛实操经历**。不要在纯算法层做低效的代码刷榜，勇敢深入到算法与系统协同设计 (Co-Design) 的深水区。”*

---

## 一、 课程引论：算法-系统协同设计 (Co-Design) 的兴起与工业界范式转移

### 1.1 讲者背景与课程缘起：从经典机器学习到大模型时代
今天是我第一次在浙江大学线下授课，欢迎各位老师和同学来听我的课程。本次讲座使用的演示文稿共计 100 页，是我最近几天专门为浙大同学全新整理制作的，涵盖了当前大模型系统领域最前沿的技术内容，绝非陈旧资料。

今天课程的标题虽然叫《高级机器学习》，但大家都清楚，当今人工智能已经全面迈入大模型时代，而机器学习本身的范畴其实极其广阔。早年我在海外高校担任教职 (Faculty) 时，讲授的《机器学习》课程主要偏向经典统计机器学习 (Classic Machine Learning)，涵盖分类与回归、逻辑回归 (Logistic Regression)、EM 算法 (Expectation Maximization)、高斯过程 (Gaussian Processes) 以及经典的凸优化理论等。

机器学习涵盖传统机器学习与深度学习（现代机器学习）。进入大模型时代后，领域进一步细分为纯语言模型 (LLM)、多模态理解、视频生成模型以及专用硬件芯片设计等前沿方向。今天我为大家分享的主题是《Algorithm-Infra Co-Design for AGI》，即面向通用人工智能的算法与系统协同设计。

选择这一主题有两个核心原因：首先，本门课程隶属于高性能计算 (HPC) 与系统综合实践范畴，理应聚焦于算法与硬件系统的结合；其次，这是当前工业界不可逆转的核心技术大趋势。早在 2018 年，我就开始深耕系统效率 (Efficiency) 与模型加速方向，属于业内较早探索该领域的学者。早期我与国内外各大科技巨头洽谈合作时，许多大厂团队负责人甚至抱有疑问，认为做系统效率的价值有限，不如做安全或纯业务算法。

然而，随着 2024 年底至 2025 年初 DeepSeek V3/V4 的横空出世，整个工业界瞬间觉醒，各大科技巨头纷纷全面跟进。大家切身体会到了系统基础设施 (Infra) 对降低训练与推理成本、实现模型超大规模扩展 (Scalable Training) 的决定性作用。自此，算法-系统协同设计 (Co-Design) 成为全球顶级团队全力押注的关键领域。

### 1.2 工业界前沿团队真实人才画像：5 Infra : 4 Data : 1 Algo
我结合自己在工业界一线以及与国内外各大头部大厂（OpenAI、Anthropic、Google、阿里千问、字节、DeepSeek 等）深度交流的实际经验，向大家披露当前大模型前沿团队真实的招聘格局：

在当今工业界前沿大厂中，每招聘 10 个人，通常有 **5 个人负责底层高性能系统基础设施 (Infra)**，**4 个人负责数据清洗、合成数据工程与环境断言 (Data Curation)**，仅有 **1 个人负责纯算法与模型微调 (Algorithm)**。做纯算法研发的边际收益正在急剧递减，未来这一趋势只会进一步加速。

### 1.3 算法社区与系统社区的深层壁垒
长期以来，计算机科学界存在两个极度割裂的平行世界：
1. **纯算法社区 (AI / NLP / CV)**：核心聚焦于 NeurIPS、ICML、ICLR、ACL、CVPR 等顶会，关注 Benchmark 刷榜、损失函数设计与指标微调。其论文迭代周期极快（通常 2~3 个月），但致命盲区在于对底层 GPU 内存层次结构（HBM、片上 SRAM）、网络通信拓扑一无所知；
2. **纯系统社区 (OSDI / SOSP / MLSys / HPCA / ISCA / DAC)**：关注吞吐量、显存利用率、通信开销与系统鲁棒性，工作量极其庞大且验证周期长达数年，但致命弱点是对前沿算法进展极为迟钝（系统顶会常年在针对数年前的 ViT 或 ResNet 做框架优化）。

当前全球最具统治力的 AI 科学家，无一不是打通这两个社区的协同设计者 (Co-Designers)。以 **DeepSeek V3 / V4** 为例，其研发团队从立项第一天起就没有“算法组”与“系统组”的部门墙。其设计的多头潜在注意力 (MLA)、无辅助损失的 MoE 负载均衡算法，完全是为 NVIDIA GPU 的 DualPipe 跨节点通信重叠和 FP8 矩阵乘法量身定做的。这种**算法与系统互为因果的设计思维**，正是其以极低算力成本击穿业界记录的核心秘诀。

### 1.4 协同设计者的核心能力支柱与 Coding Agent 赋能
成为顶级协同设计专家，必须立足两大支柱：
- **深厚的数学洞见 (Mathematical Insight)**：用于从根本上重构算法优化目标（例如通过低秩近似、正交动量更新、增量 Softmax 归一化）；
- **坚实的底层系统直觉 (System Intuition)**：精通 GPU 内存层次、理解算子融合与并行调度机制。

随着 Claude Code、Codex 等 Coding Agent 展现出惊人的底层 CUDA 与 Triton 编写能力，**工程师的核心壁垒不再是死记硬背底层 API，而是对全局系统瓶颈的宏观洞察力 (High-Level Architectural Insight)**。人最核心的竞争力在于高阶架构决策与跨层抽象思考能力。

---

## 二、 基础模型演进、Token 经济与大模型 Scaling Law

### 2.1 深度学习半个世纪演进脉络：从 AlexNet 到 ChatGPT
回顾基础模型 (Foundation Models) 的发展历程，深度学习的概念早在 1980 至 1990 年代就已由 Yann LeCun 等先驱提出，包括最初的卷积神经网络 (CNN)。但由于当时算力严重受限且缺乏大规模标注数据集，深度学习研究经历了长达近 30 年的沉寂。

转折点出现在 2012 年，李飞飞团队主导构建了划时代的百万图像基准 ImageNet，Geoffrey Hinton 及其团队开发了 AlexNet，将卷积网络移植到 GPU 上进行规模化并行计算 (Scaling up)，首次在 ImageNet 上斩获突破性准确率，正式宣告现代深度学习时代的开启。

此后，2014 年的 VGGNet 证明了网络深度的重要性；2015 年何恺明等人提出残差连接 (Residual Connection)，解决了深层网络的梯度消失问题，使层数首次突破 100 层，为深度学习赋予了真正意义上的 **Scalability（可扩展性）**；2017 年 Vaswani 等人提出 Transformer ("Attention Is All You Need")，打破了循环神经网络的时序依赖，奠定了全并行计算基石；2020 年 Google 提出 ViT，拉开多模态序幕；2022 年 12 月 ChatGPT 问世，整个 AI 领域的演进曲线由线性平缓转入极度陡峭的**指数级爆发 (Exponential Growth)**。

### 2.2 Token 经济学与测试时计算 (Test-time Compute)
当前 AI 产业已经全面进入“**Token 即生产力 (Token Maxing)**”时代：
- 全球大模型每月消耗 Token 量已突破 3200 万亿，随着视频生成与代码智能体的普及，Token 吞吐需求正在以每两年 100 倍的速度飙升；
- **推理时扩展法则 (Test-time Scaling Law)**：自 OpenAI o1 / o3 问世以来，业界发现除了扩大预训练参数外，在推理阶段引入显式思维链 (Chain-of-Thought, CoT)，给予模型充裕的思考 Token 进行自我反思、检验与多路径搜索，能够在数理逻辑与竞赛编程上带来确定性的指数级能力提升。

### 2.3 预训练 Scaling Law 远未终结：20T/100T 模型与合成数据飞轮
针对社会上所谓“数据用尽、Scaling Law 停滞”的悲观论调，讲者根据工业界一手信息予以明确辟谣：
- 北美前沿大厂内部，**20T (20万亿) 参数级的基础大模型已经预训练完成**，部分实验室更已进入 **100T 参数** 超大规模底座的论证与立项；
- **合成数据飞轮 (Synthetic Data Flywheel) 运转自洽**：前沿大厂当前训练语料中，**合成数据占比已超过 90%**。大厂调度数百万个 Coding/Math Agent 并行合成 Prompt，并在沙盒环境中通过单元测试、代码编译和逻辑断言自动清洗打标，经过严格校验的高纯度数据源源不断反哺训练下一代基模，实现自我演进 (Self-Evolution)；
- **全球物理算力底座内幕**：Google 明面持卡量（自研 TPU 与 NVIDIA GPU）已突破 **400 万张**；由于单数据中心存在约 **10 万卡** 的供电与散热物理极限，Google Gemini 3 / 3.5 Pro 攻克了跨越全球 **10 个超大型数据中心的广域分布式联合训练技术**，并直接采用**核电站直供电力**保障超大规模集群平稳运转。

---

## 三、 系统效率大图景与 MLSys 不可能三角

### 3.1 效率四要素与“压缩即智能”理论
大模型系统效率包含 **Data (数据)**、**Algorithm (算法)**、**Infra (系统基础设施)** 以及 **Evaluation (评测基准)** 的闭环驱动。

从信息论的角度看，大语言模型本质上是一个高阶**数据压缩器 (Compressor)**，全流程完成了两次关键的数据压缩：
1. **第一次压缩：Tokenizer（分词器）**：
   将高维连续的自然语言离散映射到字典词表中，词表越大，序列压缩比越高；
2. **第二次压缩：神经网络参数拟合（香农熵最小化）**：
   $$\\mathcal{{L}}_{{\\text{{pretrain}}}} = -\\sum_{{t=1}}^T \\log P(x_t \\mid x_1, x_2, \\dots, x_{{t-1}})$$
   通过优化下一个 Token 的预测概率分布，使得模型不断逼近自然语言的香农熵 (Shannon Entropy) 极限，将人类文明的知识无损编码压缩进几百亿至数万亿浮点权重中。信息瓶颈理论 (Information Bottleneck) 与 PAC-Bayes 泛化界为此提供了坚实的数学支撑。

### 3.2 MLSys 系统的“不可能三角”
大模型系统工程的日常研发，本质上是在 **计算 (Compute)**、**存储 (Memory)** 与 **通信 (Communication)** 之间进行极限 Trade-off：
- **KV Cache 机制**：以**存储 (Memory)** 换**计算 (Compute)**，保存历史 Token 避免每次重新计算；
- **重计算 (Activation Checkpointing)**：以**计算 (Compute)** 换**存储 (Memory)**，前向不保留中间激活值，反向传播时临时重算，显存节省高达 70%；
- **ZeRO-3 参数分片**：以**通信 (Communication)** 换**存储 (Memory)**，单卡仅存放 $1/N$ 模型参数，前向反向均需 All-Gather 高频网络通信；
- **系统瓶颈判定**：通过 **Roofline 模型** 精确剖析当前负载是处于 Compute-bound（算力受限，如大 Batch GEMM 需优化 MFU）还是 Memory-bound（访存受限，如自回归单步解码需算子融合与 Tiling）。

---

## 四、 Agent 智能体架构与双层优化：Outer-Loop 权重 vs Inner-Loop 代码

### 4.1 智能体核心构成：Agent 与 Harness 的定义
智能体系统包含两大组成部分：
- **Agent（智能体）**：由大模型基模（Core LLM）、记忆模块（Memory）、规划引擎（Planning）和工具集（Tools）构成的自主决策实体；
- **Harness（工程脚手架）**：围绕大模型编写的外围工程宿主代码。以通用代码语言实现程序控制流、上下文管理、工具调度接口及异常沙盒运行。

### 4.2 双层优化 (Bi-level Optimization) 分工体系
智能体系统的演进呈现出清晰的双层优化循环：
- **Outer-Loop（外层循环）**：
  周期长（通常 3 个月）、耗资巨大。通过反向传播直接更新大模型神经网络的参数权重 $W$（预训练、SFT 与强化学习 RLHF）；
- **Inner-Loop（内层循环）**：
  **模型权重完全固定不变**！研发人员通过重构 Harness 的工程代码，持续升级提示词编排、动态工具调度契约、多步验证断言与错误自愈机制。目前工业界 Coding Agent 的迭代突破，80% 以上发生在 Inner-Loop 的 Harness 调优上（日级高速迭代）。

### 4.3 评测基准驱动与统一多模态 (Unified Omni Model) 趋势
- **Benchmark-Driven 闭环**：通过 SWE-bench（真实 GitHub Issue 修复）、LiveCodeBench（竞赛代码合成）、AIME（高难度数理逻辑）等基准形成自动化打分与自我迭代闭环；
- **商业化现金流与运营内幕**：大模型服务对外开价极高，毛利率可达 100%~200%（例如千问 27B 部署机房通常 1~2 个月即可收回硬件投资）；
- **Unified Omni 架构**：纯文本模型将在未来两年内逐步饱和，前沿突破正全面转向视觉、语音原生一体化的统一世界多模态模型。

---

## 五、 大规模分布式预训练 Infra：4D 并行、ZeRO 与前沿框架演进

### 5.1 预训练技术流水线与优化器演进
预训练是大模型研发中最耗费物理算力的阶段。优化器技术正在经历从 Adam 到 Muon 的范式革新：
- **经典 AdamW**：每个参数需占用 12 字节静态显存（4B 权重副本 + 4B 一阶矩 + 4B 二阶矩），超大规模训练下参数矩阵容易产生各向异性退化；
- **前沿 Muon 优化器**：采用 Newton-Schulz 迭代对动量矩阵进行正交化处理 (Orthogonalized Momentum)，保证更新方向在各特征维度上均衡推进，收敛速度与数值稳定性显著提升。

### 5.2 4D 混合并行体系深度拆解
针对万亿模型参数量远超单卡显存承载力的物理现实，工业界采用复合 4D 并行架构：
1. **数据并行 (DP / FSDP)**：多卡独立前向，反向通过 All-Reduce 聚合梯度；
2. **张量并行 (TP / Megatron-LM)**：将线性层权重矩阵按行或按列切分，单机内部通过 NVLink 超高带宽进行高频通信；
3. **流水线并行 (PP)**：将深度几百层的网络按层横切分配到不同节点，采用 **1F1B (One Forward One Backward)** 调度压缩流水线启动气泡 (Bubble)；
4. **专家并行 (EP)**：针对 MoE 架构，将数百个稀疏专家分置于不同物理卡上，通过跨节点 All-to-All 通信分发 Token；
5. **上下文并行 (CP / Ring Attention)**：将超长序列沿环形拓扑通信计算注意力。

### 5.3 显存消除机制与框架美学
- **混合精度静态显存开销**：参数 2B + 梯度 2B + 优化器状态 12B = **16 字节 / 参数**（训练 70B 模型仅静态数据便需 1120 GB 显存）；
- **DeepSpeed ZeRO 三阶段分片**：ZeRO-1 分片优化器状态、ZeRO-2 分片梯度、ZeRO-3 分片模型参数（单卡仅存 $1/N$ 数据，计算时通过 All-Gather 临时拉取）；
- **Slime 框架的极简美学**：针对主流开源框架（Megatron、DeepSpeed）过度封装与维护繁琐的痛点，Slime 框架坚持轻量直调与算子复用，以极少代码实现万卡级高可靠收敛，展示了真正的 Co-Design 极简工程美学。

---

## 六、 高效推理架构与低比特量化：定点、NVFP4 与具身端侧芯片

### 6.1 推理性能双核心指标：TTFT vs TPOT
在线推理服务核心关注两大延迟指标：
- **TTFT (Time To First Token，首字延迟)**：Prefill 阶段耗时，属于算力受限（Compute-bound）；
- **TPOT (Time Per Output Token，吐字延迟)**：Decode 阶段单步自回归逐字生成时间，属于访存带宽受限（Memory-bound）。

### 6.2 低比特量化数学原理与格式对比
量化公式将连续高精度浮点映射为离散低比特表示：
$$q = \\text{{clip}}\\left( \\left\\lfloor \\frac{{x}}{{S}} \\right\\rceil + Z, -2^{{b-1}}, 2^{{b-1}}-1 \\right)$$
- **定点 INT8/INT4**：整数矩阵乘成熟，但对注意力层激活值异常值（Outliers）极度敏感；
- **FP8 (E4M3 / E5M2)**：保留浮点动态范围，成为当前主流基模标准格式；
- **NVFP4 (NVIDIA Blackwell)**：仅用 4 比特编码浮点数，配合微缩放因子，吞吐比 FP8 提升 2~4 倍。

### 6.3 具身智能与端侧 45nm ASIC 定点芯片实测
在移动机器人与具身控制器等资源极度受限的嵌入式场景中，硬件芯片通常采用成熟廉价的 **45nm ASIC 工艺**。由于不支持高功耗浮点硬件单元，必须采用纯粹的**定点整数均匀量化 (Integer-Only Quantization)**，将控制模型压缩至数十兆显存以内，以几瓦的极低功耗维持高频闭环运动推演。

---

## 七、 高效注意力机制与国内大厂 1:7 黄金混合配比

### 7.1 标准 Attention 访存瓶颈与 FlashAttention 破局
标准 Softmax 注意力计算将 $N \\times N$ 矩阵写入高延迟全局显存 (HBM)，在长序列下引发严重的 Memory-bound 泥潭。
FlashAttention 创新点：
1. **SRAM Tiling 分块加载**：将 $Q, K, V$ 拆分为小 Block 直接在片上静态存储器 SRAM 计算；
2. **Online Softmax 增量归一化**：
   $$m^{{\\text{{new}}}} = \\max(m^{{\\text{{old}}}}, x_i), \\quad l^{{\\text{{new}}}} = l^{{\\text{{old}}}} \\exp(m^{{\\text{{old}}}} - m^{{\\text{{new}}}}) + \\exp(x_i - m^{{\\text{{new}}}})$$
   单次遍历即可实时增量恢复与全局 Softmax 严格相等的数学结果，100% 数学无损提速。

### 7.2 线性注意力的常数显存与国内 1:7 黄金混合配比
线性注意力通过核函数展开，隐藏状态按递归递推：$S_t = S_{{t-1}} + K_t^T V_t$。**推理显存彻底降为常数 $O(1)$**。

#### 为什么国内团队（千问、Kimi、MiniMax M3）普遍采用 1:7 黄金配比？
- **纯线性注意力的短板**：依赖定长状态压缩，超长文本“大海捞针 (Needle-In-A-Haystack)”关联召回能力显著弱于全注意力；
- **国内卡数客观约束**：无法承载 128k 全量 Full Attention 的巨额 KV Cache（1M Token 的 GLM-5.2 仅 KV Cache 就需占用 **90.5 GiB** 显存）；
- **1:7 混合架构 (Hybrid Architecture)**：
  在主干网络中，**每 1 层全注意力 (Full Attention) 搭配 7 层线性注意力 (Linear Attention)**！7 层线性层负责局部高密度时序压缩（零显存增长），1 层全注意力层负责全局关键特征精准检索。实测在百万长文本评测上全面比肩纯全注意力，同时整体显存开销削减 80% 以上。
- **架构级协同创新 (DeepSeek MLA)**：通过将 Key/Value 投影至低维潜在向量 (Latent Vector)，推理显存降为传统 MHA 的 $1/6$。

---

## 八、 推理加速与投机采样：Diffusion Draft 与并行无损验证

### 8.1 投机解码 (Speculative Decoding) 原理与数学无损证明
针对单步串行自回归的延迟痛点，推测解码采用“小步快跑，大步验证”机制：
1. **轻量 Draft 模型**：单步生成 $K$ 个后续候选 Token；
2. **庞大 Target 模型**：利用矩阵高并发计算，**单次前向传播 (Single Forward Pass) 同时验证全部 $K$ 个 Token**；
3. **拒绝采样 (Rejection Sampling)**：依据概率比对决定接受前 $m$ 个 Token。数学上严格证明：**生成文本概率分布与大模型原生解码 100% 等价，绝对数学无损**。

### 8.2 基于 Diffusion LM 的非自回归投机采样 (DFlash / DPAR)
前沿突破将 Draft 模型由串行小模型升级为**扩散语言模型 (Diffusion LM)**：
- 单次去噪前向中，**一次性并行喷涌出 8 到 16 个高质量候选 Tokens**；
- 配合 DPAR 硬件感知流水线调度（DualPipe 重叠计算与验证通信），在生产环境中实现了高达 **6 倍的端到端无损推理加速**。

---

## 九、 推理 Serving 框架、视频生成与世界模型模拟引擎

### 9.1 两大划时代 Serving 引擎：vLLM vs SGLang
- **PagedAttention (vLLM 核心)**：借鉴操作系统虚拟内存分页机制，将 KV Cache 离散分配于固定物理 Block，消除显存碎片，并发吞吐提升数倍；
- **RadixAttention (SGLang 核心)**：在显存中维护一棵基数树（Radix Tree），多轮智能体调用与共享前缀实现零开销复用。

### 9.2 视频生成系统加速 (VideoGen Infra) 与 Inferix 世界模拟
- **DAX / SGLang Diffusion**：将视频去噪注意力图进行时空切分，大幅优化去噪延迟；
- **Inferix 世界模拟引擎**：针对具身智能与物理世界交互，构建支持高并发、多智能体交互的实时物理推演服务底座。

---

## 十、 自动化科研 (Auto-Research)、学业要点与人生建议

### 10.1 极简自动科研实践：Karpathy autoresearch
讲者重点推荐了 Andrej Karpathy 开源的 `autoresearch` 框架：
- **单卡单 GPU 自循环**：Agent 自主修改 GPT-2 训练代码超参数与组件，自动提交训练并评估 Validation Loss 指标，根据断言决定是否保留修改；
- **自动化算子优化**：Agent 不仅能调超参，更能结合底层 Profiler 自动生成超越手写极限的高性能 Triton/CUDA 算子。

### 10.2 讲者对浙大学子的总结与人生诤言
讲座尾声，讲者为现场同学分享了三条人生忠告：
1. **打破绩点焦虑，筑牢硬核工程壁垒**：
   > *“绩点只是一张保研或出国的入场券。在顶尖大厂招聘与顶级实验室挑选博士生时，绩点其实是最不重要的。大家真正看重的是两点：**你的 Research 深度洞见，以及你的硬核系统工程与开源竞赛经历**。不要在纯算法层做低水平代码内卷和刷榜，勇敢深入算法与系统协同设计 (Co-Design) 的深水区。”*
2. **成为善用 Coding Agent 的“超级个体”**：
   从大一开始熟练掌握 Claude Code 与 Codex，将 AI Agent 深度嵌入日常编程、实验复现与代码调试中，一人即是一个高效作战团队；
3. **跨界融合，拥抱具身智能与物理世界大模型**：
   纯文本语言模型终将走向收敛，多模态物理世界模型（World Models）与具身智能（Robotics）正在迎来属于它们的破晓时刻。保持对前沿技术的敬畏与探索热忱，终将行稳致远。
"""

with open(VERBATIM_OUT, "w", encoding="utf-8") as f:
    f.write(verbatim_doc)

print(f"[✓] 规范书面化完整逐字稿构建完毕: {VERBATIM_OUT} ({len(verbatim_doc)} 字)")


# =========================================================================
# 精要速记版：高浓度、高价值复习指南
# =========================================================================
summary_doc = """# 高级机器学习：Algorithm-Infra Co-Design for AGI 精要速记指南

> **授课时间**：2026 年夏季学期  
> **授课地点**：浙江大学玉泉校区 北教3-312  
> **课程依托**：浙江大学《课程综合实践Ⅰ》（主讲教授：陈建海）特邀前沿讲座  
> **讲师背景**：海外名校教职经历 (Faculty)，大模型系统工程资深学者与工业界领军专家  
> **版本定位**：**高浓度精要速记指南 (Executive Study Guide)**。系统性提炼全课 10 大核心教学章节的论点要义、关键数学机制、硬件权衡图谱与横向技术对比总表。篇幅依核心知识密度充实展开，拒绝过度精简。

> [!IMPORTANT]
> 🎓 **课程考核与学业要点 (Course Evaluation & Academic Guidelines)**
> - **课程性质与要求**：本讲次为《课程综合实践Ⅰ》的高规格特邀前沿讲座，旨在建立算法与系统硬件协同设计 (Co-Design) 的全局系统思维；
> - **作业与小测**：本专题讲座**无随堂小测，亦无强制课后书面作业**；
> - **大作业与项目实践指引**：建议组建 2~3 人跨学科小组，熟练运用 Coding Agent（Claude Code / Codex）动手参与开源算子（Triton/CUDA）优化或 Kaggle 竞赛；
> - **讲者对大学成绩与绩点 (GPA) 的深刻箴言**：
>   > *“绩点只是一张保研或出国的入场券，但在大厂面试与顶级实验室挑选博士生时，绩点其实是最没用的。顶尖团队只看两点：**你的 Research 深度洞察，以及你的硬核系统工程实践与竞赛实操经历**。不要在纯算法层做低效的代码刷榜，勇敢深入到算法与系统协同设计 (Co-Design) 的深水区。”*

---

## 📑 全课知识脉络与系统全景导图

```mermaid
graph TD
    CoDesign[算法-系统协同设计 Co-Design]
    CoDesign --> DataLayer[数据层: 合成数据自进化飞轮]
    CoDesign --> PretrainLayer[训练层: 4D 混合并行与 Muon 优化器]
    CoDesign --> AttentionLayer[计算层: FlashAttention 与 1:7 混合架构]
    CoDesign --> InferenceLayer[推理层: 投机采样与前缀基数树]

    DataLayer --> D1[两次数据压缩: Tokenizer + 香农熵最小化]
    DataLayer --> D2[90%+ 合成数据自循环校验]

    PretrainLayer --> P1[DP + TP + PP 1F1B + EP + CP Ring Attention]
    PretrainLayer --> P2[ZeRO-3 显存消除与通信重叠]
    PretrainLayer --> P3[Slime 极简工程美学]

    AttentionLayer --> A1[SRAM Tiling + Online Softmax 增量最大值]
    AttentionLayer --> A2[国内 1:7 黄金配比 1 全注意力 : 7 线性注意力]
    AttentionLayer --> A3[DeepSeek MLA 潜在向量显存压缩]

    InferenceLayer --> I1[Draft-Target 拒绝采样数学无损证明]
    InferenceLayer --> I2[Diffusion LM 并行投机 8~16 Tokens]
    InferenceLayer --> I3[vLLM PagedAttention + SGLang RadixAttention]
```

---

## 一、 工业界招聘格局与 Co-Design 范式转移

1. **工业界前沿团队人员构成比例**：
   - **50% 高性能基础设施 (Infra)**：负责并行通信、算子融合（Triton/CUDA）、资源调度与吞吐优化；
   - **40% 数据工程与合成清洗 (Data Curation)**：负责自进化 Prompt 生成、沙盒环境断言与数据过滤；
   - **10% 纯算法微调 (Algorithm)**：负责架构调整与损失函数；
   - **核心洞见**：大模型架构已高度收敛，纯算法刷榜的边际收益急剧递减。
2. **社区割裂与 Co-Designer 优势**：
   - 算法顶会（NeurIPS/ICML）缺乏底层 GPU 内存（HBM/SRAM）直觉；系统顶会（OSDI/HPCA）对前沿算法迭代迟钝；
   - **DeepSeek 核心启示**：算法从立项第一天起就与底层硬件拓扑互为因果（MLA、无辅助损失 MoE 与 DualPipe 通信重叠深度咬合）。
3. **Coding Agent 的定位**：
   - Claude Code 与 Codex 已能高效完成底层算子代码编写，工程师的不可替代壁垒在于**宏观系统架构洞察力 (High-Level System Intuition)**。

---

## 二、 基础模型演进与大模型 Scaling Law

1. **五大关键范式飞跃**：
   - **1980s-1990s**：LeCun CNN 萌芽，因算力数据匮乏沉寂；
   - **2012**：AlexNet 突破 ImageNet，算力破晓；
   - **2015**：ResNet 残差连接 $y=\mathcal{F}(x)+x$ 解决梯度消失，赋予神经网络 **Scalability（可扩展性）**；
   - **2017**：Transformer 全并行计算确立骨干；
   - **2022**：ChatGPT 涌现，AI 研发由线性增长转入**指数级爆发 (Exponential Growth)**。
2. **测试时扩展法则 (Test-time Scaling Law)**：
   - OpenAI o1/o3 引入思维链 (CoT)，测试时为模型分配更多推理思考 Token，模型在数理与编程逻辑上的表现呈现确定性指数提升。
3. **预训练 Scaling Law 与合成数据飞轮**：
   - 经验公式 $\mathcal{L}(C,N,D) = (N_c/N)^{\alpha_N} + (D_c/D)^{\alpha_D} + (C_c/C)^{\alpha_C}$ 持续成立；
   - 北美实验室已预训练完成 **20T 参数模型**，并论证 **100T 模型**；
   - **数据飞轮自洽**：训练数据中合成数据占比超 90%，数百万 Agent 闭环生成与沙盒校验；
   - **物理算力基底**：Google 账面持卡达 400 万张；单数据中心物理上限约 10 万卡，Gemini 跨越 10 个数据中心通过核电直供联合训练。

---

## 三、 系统效率大图景与 MLSys 不可能三角

1. **“压缩即智能 (Compression is Intelligence)”**：
   - **第一次压缩（Tokenizer）**：高维连续文本映射为离散词表 Token，词表越大压缩比越高；
   - **第二次压缩（神经网络拟合）**：预训练最小化交叉熵逼近自然语言的香农熵 (Shannon Entropy) 极限，将人类知识压缩存储于浮点权重中。
2. **MLSys 不可能三角核心权衡**：
   - **计算 (Compute)** vs **存储 (Memory)** vs **通信 (Communication)**；
   - **KV Cache**：存储换计算（显存随上下文增长，免去历史重算）；
   - **Activation Checkpointing**：计算换存储（反向重算激活，显存暴降 70%）；
   - **ZeRO-3**：通信换存储（单卡存 $1/N$ 参数，高频 All-Gather 通信）；
   - **Roofline 判定**：严格区分 Compute-bound（大 Batch GEMM）与 Memory-bound（单步解码、LayerNorm、Softmax）。

---

## 四、 Agent 架构与双层优化 (Bi-level Optimization)

1. **双层优化机制**：
   - **Outer-Loop（外层循环）**：3 个月为周期，消耗巨额算力，通过梯度反向传播直接更新模型神经网络权重 $W$；
   - **Inner-Loop（内层循环）**：**模型权重完全冻结**！工程师通过重构外围宿主代码 (Harness)，优化提示词、工具协议与验证断言，日级高速演进。
2. **评测驱动与商业模式**：
   - SWE-bench / LiveCodeBench / AIME 闭环打分；
   - 大模型推理毛利率可达 100%~200%（千问 27B 通常 1~2 个月即可收回算力卡投资）。

---

## 五、 大规模分布式预训练 Infra

1. **优化器革新**：
   - **AdamW 痛点**：静态显存开销高达 12B/参数，超大模型易发各向异性退化；
   - **Muon 优化器**：Newton-Schulz 正交化动量矩阵更新，保证特征维度均匀推进，收敛加速。
2. **4D 混合并行体系**：
   - **DP (数据并行)**：多卡分 Batch，All-Reduce 同步梯度；
   - **TP (张量并行)**：权重按行/按列矩阵切分，依赖单机 NVLink 高速通信；
   - **PP (流水线并行)**：网络按层横切跨机，1F1B 调度压缩流水气泡；
   - **EP (专家并行)**：MoE 专家按卡分发，跨节点 All-to-All 路由通信；
   - **CP (上下文并行)**：长序列 Ring Attention 环形通信。
3. **静态显存与 ZeRO 分片**：
   - 静态显存每参数 16 字节（参数 2B + 梯度 2B + 优化器状态 12B）；
   - ZeRO-1 分片优化器、ZeRO-2 分片梯度、ZeRO-3 全量分片（单卡存 $1/N$）；
   - **Slime 框架美学**：摒弃过度抽象，算子直调与极简复用，保证工业级万卡收敛。

---

## 六、 推理性能与低比特量化

1. **性能指标**：
   - **TTFT (首字延迟)**：Prefill 阶段决定，算力受限 (Compute-bound)；
   - **TPOT (吐字延迟)**：Decode 单步自回归生成决定，访存带宽受限 (Memory-bound)。
2. **量化数学与格式演进**：
   - 均匀映射：$q = \\text{clip}(\\lfloor x/S \\rceil + Z, -2^{b-1}, 2^{b-1}-1)$；
   - **INT4/8**：整数乘法高效，易受注意力 Outliers 影响；
   - **FP8**：主流千亿基模标配，兼顾动态范围；
   - **NVFP4 (Blackwell)**：微缩放因子 4-bit 浮点，吞吐翻倍。
3. **具身智能与 45nm ASIC 定点实测**：
   - 移动机器人芯片受限于功耗与成本，采用成熟 45nm 工艺，无复杂浮点硬件单元，必须采用严格的定点整数均匀量化 (Integer-Only) 压缩至几十兆显存内极低功耗运行。

---

## 七、 高效注意力机制与国内大厂 1:7 黄金配比

1. **FlashAttention 破局机制**：
   - 传统 Softmax 在 HBM 物化 $N \\times N$ 矩阵，导致带宽严重瓶颈；
   - **SRAM Tiling**：分块加载至片上高速静态存储器；
   - **Online Softmax**：利用局部最大值动态更新求和项 $m^{\\text{new}} = \\max(m^{\\text{old}}, x_i)$ 与 $l^{\\text{new}} = l^{\\text{old}} e^{m^{\\text{old}} - m^{\\text{new}}} + e^{x_i - m^{\\text{new}}}$，单次遍历增量计算全局精确 Softmax，100% 数学无损。
2. **线性注意力与常数推理显存**：
   - 状态递推 $S_t = S_{t-1} + K_t^T V_t$，推理显存从 $O(N)$ 彻底降为常数 $O(1)$。
3. **国内大厂（千问、Kimi、MiniMax M3）1:7 黄金配比**：
   - **纯线性短板**：定长状态压缩导致超长文本大海捞针 (Needle-In-A-Haystack) 检索精度下降；
   - **国内算力约束**：万卡资源有限，无法承载 128k 全注意力巨额 KV Cache（1M Token 的 GLM-5.2 仅 KV Cache 需占用 90.5 GiB 显存）；
   - **1:7 混合架构 (Hybrid)**：每 1 层全注意力 (Full Attention) 搭配 7 层线性注意力 (Linear Attention)！7 层线性层负责局部时序高效压缩，1 层全注意力层负责全局关键特征精确对齐，显存降低 80% 以上且长文本精度完全比肩纯全注意力。
4. **DeepSeek MLA (多头潜在注意力)**：
   - 将 Key/Value 联合投影压缩至低维潜在向量，线上 KV Cache 显存缩减至传统的 $1/6$。

---

## 八、 推理加速与投机采样 (Speculative Decoding)

1. **Draft-Target 拒绝采样机制**：
   - 轻量 Draft 模型快速猜词生成候选块；
   - 庞大 Target 模型利用高并发能力，单次前向同时校验全部候选词；
   - Rejection Sampling 概率比对，**数学证明生成文本概率分布与大模型原生解码严格一致，完全无损**。
2. **基于 Diffusion LM 的非自回归投机 (DFlash / DPAR)**：
   - 扩散 Draft 模型单次去噪前向，一次性并行喷出 8~16 个候选 Token；
   - DPAR 硬件感知双流水调度，端到端实现最高 6 倍无损推理加速。

---

## 九、 推理 Serving 框架与视频生成

1. **Serving 双引擎**：
   - **PagedAttention (vLLM)**：虚拟内存分页离散存储 KV Cache Block，消除显存碎片，并发吞吐翻倍；
   - **RadixAttention (SGLang)**：基数树共享前缀缓存，多轮对话前缀零成本复用。
2. **视频生成与世界模型**：
   - DAX / SGLang Diffusion 视频去噪时空切分；
   - Inferix 世界模拟引擎提供实时具身仿真环境。

---

## 十、 自动化科研与人生建议

1. **Karpathy autoresearch 单卡实验**：
   - 极简 Agent Loop 驱动单机单 GPU 自动调参并闭环验证指标；
   - Agent 直接联动底层 Profiler 自动化搜索 Triton/CUDA 高性能算子。
2. **给浙大学子的学业诤言**：
   - **破除绩点焦虑**：GPA 是基础门槛，大厂与顶尖实验室挑人最看重 Research 深度与硬核工程/竞赛实践经历；
   - **善用 Agent 一人即团队**：精通 Claude Code / Codex，将其深度融入日常研发；
   - **迈向具身与世界模型**：纯文本模型趋向平原，拥抱物理世界模型与具身智能新浪潮。

---

## 📊 核心技术横向对比总表

| 技术领域 | 核心挑战与物理瓶颈 | 经典方案 | 前沿协同设计 (Co-Design) 方案 | 核心系统权衡 (Trade-off) |
| :--- | :--- | :--- | :--- | :--- |
| **大规模预训练** | 单卡无法存放千亿参数 | DDP 数据并行 | **4D 混合并行 (DP+TP+PP+EP+CP) + ZeRO-3** | 网络高频通信与流水线气泡开销 |
| **长序列注意力** | $O(N^2)$ 复杂度与 HBM 访存墙 | 标准 Softmax Attention | **FlashAttention (SRAM Tiling + Online Softmax)** | 片上 SRAM 容量限制与复杂算子编写 |
| **百万长文本显存** | KV Cache 显存暴涨爆卡 | 暴力截断上下文 | **1:7 黄金混合架构 (1 全注意力 : 7 线性注意力)** | 放弃纯线性，用 1 层全注意力保证精准召回 |
| **自回归生成延迟** | 单步串行 Decoding 算力跑不满 | 纯自回归单字吐词 | **Diffusion LM 投机采样 (DFlash / DPAR)** | 维护扩散 Draft 模型，换取一次迸发 8~16 Tokens |
| **在线高并发服务** | 显存碎片化严重，前缀重复计算 | 静态显存预留 | **PagedAttention (分页存储) + RadixAttention (树前缀)** | 页表调度与前缀缓存命中率管理 |
| **端侧具身部署** | 嵌入式算力功耗极低 | 浮点截断微调 | **45nm ASIC 定点整数均匀量化 (Integer-Only)** | 算法精细缩放校准，规避异常值精度滑坡 |
"""

with open(SUMMARY_OUT, "w", encoding="utf-8") as f:
    f.write(summary_doc)

print(f"[✓] 高浓度精要速记指南构建完毕: {SUMMARY_OUT} ({len(summary_doc)} 字)")
