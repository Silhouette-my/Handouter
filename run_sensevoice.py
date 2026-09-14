#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SenseVoice 本地极速转写脚本
"""

import sys
import time
import os
import argparse
from pathlib import Path

def transcribe(audio_path: str, output_txt: str = None, device: str = "auto"):
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    import torch

    if not os.path.exists(audio_path):
        print(f"[x] 音频文件不存在: {audio_path}")
        sys.exit(1)

    if device == "auto":
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

    print(f"[*] 使用计算设备: {device.upper()}")
    print(f"[*] 正在加载 SenseVoice-Small 模型（首次运行需下载约 200MB 权重）...")
    t_start = time.time()

    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device=device,
        disable_update=True
    )
    print(f"[✓] 模型加载就绪，耗时: {time.time() - t_start:.2f} 秒\n")

    print(f"[*] 开始转写音频: {audio_path} ...")
    t0 = time.time()

    res = model.generate(
        input=audio_path,
        cache={},
        language="zh",
        use_itn=True,
        batch_size_s=60,
        merge_vad=True,
    )
    cost = time.time() - t0

    if not res or len(res) == 0:
        print("[!] 未能识别到有效文本。")
        return

    # 提取并清理文本
    raw_text = res[0]["text"]
    clean_text = rich_transcription_postprocess(raw_text)

    print(f"[✓] 转写完成！总耗时: {cost:.2f} 秒")
    print(f"[*] 识别字数: {len(clean_text)} 字")

    print("\n" + "=" * 62)
    print("【转写效果试读】:")
    print("=" * 62)
    preview = clean_text[:600]
    print(preview + ("...\n" if len(clean_text) > 600 else "\n"))
    print("=" * 62)

    if not output_txt:
        output_txt = str(Path(audio_path).with_suffix(".txt"))

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(clean_text)

    print(f"\n[✓] 完整转写稿已保存至: {output_txt}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SenseVoice 极速本地转写")
    parser.add_argument("audio", nargs="?", default="test_clip_2min.m4a", help="要转写的音频文件")
    parser.add_argument("-o", "--output", help="输出 txt 路径")
    parser.add_argument("-d", "--device", default="auto", choices=["auto", "cpu", "mps", "cuda"])

    args = parser.parse_args()
    transcribe(args.audio, args.output, args.device)
