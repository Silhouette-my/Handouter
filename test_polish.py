import re

with open("高级机器学习_完整讲义.txt") as f:
    raw = f.read()

# Test on first segment
p1 = raw.find("今天是我第一次在浙大线下上课")
p2 = raw.find("首先就是说讲一下这样的一个background")
sample = raw[p1:p2]

def clean_to_written(text: str) -> str:
    # 替换专有名词
    replacements = [
        ("logg regression", "Logistic Regression (逻辑回归)"),
        ("m learning", "Machine Learning (机器学习)"),
        ("going processing", "Gaussian Processes (高斯过程)"),
        ("expectation maximization", "Expectation Maximization (EM 算法)"),
        ("alth infrco design", "Algorithm-Infra Co-Design (算法-系统协同设计)"),
        ("DCV3", "DeepSeek V3"),
        ("eachnet", "ImageNet"),
        ("innet", "ImageNet"),
        ("Xnet", "AlexNet"),
        ("icenet", "AlexNet"),
        ("VCnet", "VGGNet"),
        ("resnet", "ResNet"),
        ("BrRT", "BERT"),
        ("VIT", "ViT"),
        ("拆GPT", "ChatGPT"),
        ("s lab", "Scaling Law"),
        ("s law", "Scaling Law"),
        ("cloud飞 five", "Claude 3.5"),
        ("cloud code", "Claude Code"),
        ("codetex", "Codex"),
        ("jamony", "Gemini"),
        ("jamany", "Gemini"),
        ("mab reduce", "MapReduce"),
        ("山东enttropy", "香农熵 (Shannon Entropy)"),
        ("湘农商", "香农熵"),
        ("20B的概念", "编码理论极限"),
        ("s lawL is compressor", "LLM is a Compressor"),
        ("pa reduction", "PAC 学习理论"),
        ("inform等等等，信息瓶颈", "Information Bottleneck (信息瓶颈理论)"),
        ("group，LM", "Groq，LLM"),
        ("VRM", "vLLM"),
        ("VOMS", "vLLM"),
        ("SG long", "SGLang"),
        ("s long", "SGLang"),
        ("dta parallel", "数据并行 (Data Parallel)"),
        ("mactro", "Megatron-LM"),
        ("VILVL", "VERL"),
        ("dep speed", "DeepSpeed"),
        ("slit 框架", "Slime 框架"),
        ("slime", "Slime 框架"),
        ("getytanet", "Gated DeltaNet"),
        ("tanet", "DeltaNet"),
        ("KDA", "Kimi KDA"),
        ("prefu", "Prefill"),
        ("rejectject sampling", "Rejection Sampling (拒绝采样)"),
        ("radix tree", "Radix Tree (基数树)"),
        ("动胞态", "多模态"),
        ("短游期", "短周期"),
        ("commit", "Community (社区)"),
        ("commitbze", "Bridge (打通桥梁)"),
        ("哭大", "CUDA"),
        ("treatton", "Triton"),
        ("进学习", "深度学习"),
        ("基忆学习", "机器学习"),
        ("机忆学习", "机器学习"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text

print("Raw sample length:", len(sample))
