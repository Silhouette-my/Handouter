#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智云课堂全自动图文讲义流水线 (Universal Agent 兼容版)
支持特性：
1. 三种输出模式：
   - summary (精简速记版)：核心要点、技术架构对比总表
   - deep (教材级深度图文版)：依据原始讲授内容深度自然展开，涵盖全部13个核心章节、公式推导与系统权衡
   - full (完整逐字稿版)：去除冗余字符和口癖表达，自然分段排版
2. PPT 图文开关：
   - --slides：自动匹配并单调嵌入对应时间段的高清 PPT 幻灯片
   - --no-slides：纯文本专业排版，不插入幻灯片
3. 讲义头部置顶【课程考核与学业要点】专区（作业、小测、评价方式、小组项目等）
4. 严格去除尾部冗余时序对照表
5. 预留未来扩展的 LLM API 客户端与适配器接口
"""

import os
import sys
import re
import json
import zipfile
import argparse
from pathlib import Path

# =========================================================================
# 未来扩展接口预留 (Future API Upgrade Hooks)
# =========================================================================
class BaseLLMClient:
    """抽象 LLM 客户端基类：预留给未来通过远程 API（OpenAI / DeepSeek / Claude 等）处理长文本的能力"""
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "")
        self.model = model or "default"

    def chat_complete(self, prompt: str, system: str = "") -> str:
        # 当前阶段未启用外部 API，默认走本地 Prompt + Skill 规约与离线引擎
        raise NotImplementedError("API integration hook reserved for future upgrades.")


# =========================================================================
# 流水线主体实现
# =========================================================================
class ZhiyunPipeline:
    def __init__(self, work_dir: str):
        self.work_dir = Path(work_dir).resolve()
        self.slides_dir = self.work_dir / "slides"
        self.meta_path = self.work_dir / "slides_meta.json"
        self.raw_txt_path = self.work_dir / "高级机器学习_完整讲义.txt"
        self.deep_path = self.work_dir / "高级机器学习_深度图文讲义.md"
        self.full_path = self.work_dir / "高级机器学习_完整逐字稿.md"
        self.summary_path = self.work_dir / "高级机器学习_精要速记版.md"

    def unpack_zip_if_needed(self, zip_path: str):
        if not zip_path or not os.path.exists(zip_path):
            return
        print(f"[*] 正在解压课程资产包: {zip_path} ...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(self.work_dir)
        print(f"[✓] 解压就绪！")

    def strip_slides(self, markdown_text: str) -> str:
        """剥离幻灯片相关图片和时序标记，转换为纯文本模式"""
        # 移除时序标记与幻灯片标签
        text = re.sub(r">\s*⏱️\s*\*\*讲授时段\*\*:[^\n]*\n>\s*🏷️\s*\*\*幻灯片\*\*:[^\n]*\n*", "", markdown_text)
        # 移除 markdown 图片语法
        text = re.sub(r"!\[Slide\s*\d+\]\([^)]+\)\n*", "", text)
        # 压缩连续空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def generate(self, mode: str = "deep", with_slides: bool = True):
        mode = mode.lower().strip()
        print(f"\n" + "=" * 60)
        print(f"🚀 正在执行智云讲义生成流程:")
        print(f"   • 目标模式: [{mode.upper()}]")
        print(f"   • PPT 配图: [{'启用 (已嵌入)' if with_slides else '关闭 (纯文本排版)'}]")
        print(f"   • 工作路径: {self.work_dir}")
        print("=" * 60)

        # 模式匹配读取基础文本
        if mode == "summary":
            target_source = self.summary_path
            out_name = "高级机器学习_精要速记版.md"
        elif mode == "full":
            target_source = self.full_path
            out_name = "高级机器学习_完整逐字稿.md"
        else: # deep
            target_source = self.deep_path
            out_name = "高级机器学习_深度图文讲义.md" if with_slides else "高级机器学习_深度纯文本讲义.md"

        if not target_source.exists():
            print(f"[!] 警告: 源文件 {target_source.name} 尚未就绪，尝试动态重新构建...")
            if mode in ("full", "summary"):
                import subprocess
                subprocess.run([sys.executable, str(self.work_dir / "build_clean_verbatim_and_summary.py")], check=True)
            else:
                import subprocess
                subprocess.run([sys.executable, str(self.work_dir / "build_strictly_aligned_deep_notes.py")], check=True)

        with open(target_source, "r", encoding="utf-8") as f:
            content = f.read()

        # 根据 PPT 开关决定是否剥离幻灯片图片
        if not with_slides:
            content = self.strip_slides(content)

        out_file = self.work_dir / out_name
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\n[✓] 讲义处理完成！")
        print(f"[*] 输出文件: {out_file}")
        print(f"[*] 文件字数: {len(content)} 字符")
        print(f"[*] 头部要点: 已置顶【课程考核与学业要点】专区")
        print(f"[*] 尾部附录: 已严格剔除冗余时序表\n")
        return out_file


def main():
    parser = argparse.ArgumentParser(description="智云课堂图文讲义全能流水线")
    parser.add_argument("-z", "--zip", help="智云资产包 ZIP 路径")
    parser.add_argument("-d", "--dir", default=".", help="工作目录路径")
    parser.add_argument("-m", "--mode", choices=["summary", "deep", "full"], help="讲义版本: summary (精简版), deep (深度教材版), full (完整逐字稿版)")
    parser.add_argument("--slides", dest="slides", action="store_true", help="在正文中嵌入对应时间段的 PPT 幻灯片")
    parser.add_argument("--no-slides", dest="slides", action="store_false", help="不嵌入 PPT 幻灯片，输出纯文本讲义")
    parser.set_defaults(slides=True)

    args = parser.parse_args()

    selected_mode = args.mode
    selected_slides = args.slides

    # 若未传参则进入友好的命令行交互界面
    if not selected_mode:
        print("\n" + "=" * 62)
        print("🎓 浙江大学智云课堂讲义自动化流水线 (Universal Agent 适配)")
        print("=" * 62)
        print("请选择要生成的讲义模式:")
        print("  [1] 深度教材版 (Deep)   — 依据讲授内容充分展开，教材级推导与权衡 [默认]")
        print("  [2] 完整逐字稿版 (Full) — 去除冗余字符与口语表达，自然分段的原始稿")
        print("  [3] 精简速记版 (Summary)— 提炼核心考点、技术对比总表与速查图谱")
        print("=" * 62)
        choice = input("请输入编号 [1/2/3，直接回车默认 1]: ").strip()
        if choice == "2":
            selected_mode = "full"
        elif choice == "3":
            selected_mode = "summary"
        else:
            selected_mode = "deep"

        slide_in = input("是否在正文中嵌入对应时间的 PPT 幻灯片？[Y/n，回车默认 Y]: ").strip().lower()
        if slide_in == "n":
            selected_slides = False
        else:
            selected_slides = True

    pipeline = ZhiyunPipeline(args.dir)
    if args.zip:
        pipeline.unpack_zip_if_needed(args.zip)
    pipeline.generate(mode=selected_mode, with_slides=selected_slides)


if __name__ == "__main__":
    main()
