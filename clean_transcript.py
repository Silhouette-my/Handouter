#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能清洗与自然分段脚本：针对 SenseVoice 转写稿进行口语去噪、分段与结构化排版
"""

import re
import sys

def clean_text(raw: str) -> str:
    # 1. 剔除开场调音/闲聊
    # 找到正课开始的标志："今天是我第一次在浙大线下上课" 或 "欢迎大家来"
    start_pos = raw.find("今天是我第一次在浙大线下上课")
    if start_pos != -1:
        text = raw[start_pos:]
    else:
        text = raw

    # 2. 清除 SenseVoice 音频事件标记与表情
    text = re.sub(r"[🎼🤧😡😊👏]+", "", text)

    # 3. 规范化标点
    text = re.sub(r"[。\.]{2,}", "。", text)
    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"[？\?]{2,}", "？", text)
    text = re.sub(r"[！!]{2,}", "！", text)
    text = re.sub(r"^[，。、；\s]+", "", text)

    # 4. 去除高频口癖词和结巴重复
    # 重复叠词精简：如 "非常非常" -> "非常", "这个这个" -> "这个"
    for word in ["非常", "比较", "真的", "其实", "这个", "那个", "主要", "很多"]:
        text = re.sub(rf"({word}){{2,}}", r"\1", text)
    
    # 结巴重复单字：如 "我我我" -> "我", "对对对" -> "对"
    text = re.sub(r"我{2,}", "我", text)
    text = re.sub(r"对{2,}", "对", text)
    text = re.sub(r"是{2,}", "是", text)
    text = re.sub(r"就{2,}", "就", text)

    # 去除纯口癖语气填充
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
        r"基本基本",
    ]
    for pattern in fillers:
        text = re.sub(pattern, "，", text)

    # 再次清理多余标点
    text = re.sub(r"[，\s]{2,}", "，", text)
    text = re.sub(r"([。！？])，", r"\1", text)
    text = re.sub(r"，([。！？])", r"\1", text)
    text = re.sub(r"^[，\s]+", "", text)

    return text

def format_paragraphs(text: str) -> str:
    # 句子切分
    sentences = re.split(r"(?<=[。！？\n])", text)
    
    # 主题章节锚点配置（按顺序匹配）
    sections = [
        ("今天是我第一次在浙大线下上课", 
         "# 高级机器学习：Algorithm-Infra Co-design for AGI 讲义\n\n## 一、课程背景与算法-系统协同设计 (Co-Design) 的兴起\n"),
        
        ("首先讲一下这样的一个background", 
         "\n## 二、深度学习发展简史：从经典网络到大模型\n"),
        
        ("这个曲线就开始抖", 
         "\n## 三、大模型 Scaling Law 与数据飞轮 (Data Flywheel)\n"),
        
        ("这是我自己总结的一个big picture", 
         "\n## 四、系统效率大图景：数据、模型与 Infra 三位一体\n"),
         
        ("经典的三角关系", 
         "\n## 五、系统架构的“不可能三角”：计算、内存与通信\n"),
        
        ("agent是什么意思呢", 
         "\n## 六、Agent 架构与双层优化 (Bi-level Optimization)\n"),
        
        ("attention", 
         "\n## 七、高效注意力机制与混合架构 (FlashAttention / Sparse / Linear)\n"),
        
        ("定点量化", 
         "\n## 八、模型压缩与量化技术 (INT / FP8 / 具身智能与端侧部署)\n"),
        
        ("target model", 
         "\n## 九、推理加速前沿：投机采样与并行验证 (Speculative Decoding)\n"),
    ]

    sec_idx = 0
    formatted_chunks = []
    current_para = []
    current_len = 0

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue

        # 检查是否命中章节锚点
        if sec_idx < len(sections):
            anchor, header = sections[sec_idx]
            if anchor in s_clean:
                if current_para:
                    formatted_chunks.append("".join(current_para))
                    current_para = []
                    current_len = 0
                formatted_chunks.append("\n" + header + "\n")
                sec_idx += 1

        current_para.append(s_clean)
        current_len += len(s_clean)

        # 自然段落控制：每 180~280 字符分一段，保证易读性
        if current_len >= 200 and s_clean.endswith(("。", "！", "？")):
            formatted_chunks.append("".join(current_para) + "\n\n")
            current_para = []
            current_len = 0

    if current_para:
        formatted_chunks.append("".join(current_para) + "\n")

    result = "".join(formatted_chunks)
    # 标点与格式微调
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result

def main():
    with open("高级机器学习_完整讲义.txt", "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_text(raw)
    structured = format_paragraphs(cleaned)

    out_path = "高级机器学习_精简整理讲义.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(structured)

    print(f"[✓] 清洗与自然分段完成！输出文件: {out_path}")
    print(f"[*] 原始字数: {len(raw)} -> 清洗后字数: {len(structured)}")

if __name__ == "__main__":
    main()
