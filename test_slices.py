with open("高级机器学习_完整讲义.txt") as f:
    raw = f.read()

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

for i in range(len(positions)):
    title, p = positions[i]
    next_p = positions[i+1][1] if i+1 < len(positions) else len(raw)
    length = next_p - p if p != -1 else 0
    print(f"{title}: pos={p}, length={length}")
