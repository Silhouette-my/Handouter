#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浙江大学智云课堂 -> 音轨提取 -> 自动上传飞书妙记
"""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path

# 飞书浏览器持久化配置目录（保存登录 Cookie，首次扫码后无需重复登录）
DEFAULT_PROFILE = Path.home() / ".config" / "feishu_minutes_profile"


def extract_audio(video_url: str, output_path: str):
    """通过 ffmpeg 从视频直链（MP4 或 m3u8）中仅抽取音频（带实时进度显示）"""
    print(f"[*] 正在从视频直链中抽取纯音频...")
    print(f"[*] 目标保存路径: {output_path}")
    print("[*] 提示: 1080P 录像文件较大(约1~3GB)，ffmpeg 正在以多倍速流式过滤视频并拉取音轨，请稍候...\n")

    headers = (
        "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36\r\n"
        "Referer: https://interactivemeta.cmc.zju.edu.cn/\r\n"
    )

    # 浙大内网与流媒体服务器严禁走代理，清除代理环境变量以强制直连
    env = os.environ.copy()
    for k in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        env.pop(k, None)

    # 优先尝试 stream copy（无损复制）
    cmd_copy = [
        "ffmpeg", "-y",
        "-rw_timeout", "15000000",       # 15 秒超时，避免网络假死
        "-headers", headers,
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", video_url,
        "-vn",
        "-c:a", "copy",
        "-stats",
        output_path
    ]

    # 直接将 stderr 继承给终端，使用户能实时看到 time=... speed=... 进度
    res = subprocess.run(cmd_copy, env=env)
    if res.returncode != 0:
        print("\n[!] copy 封装未完全兼容，自动转码为 AAC...")
        cmd_transcode = [
            "ffmpeg", "-y",
            "-rw_timeout", "15000000",
            "-headers", headers,
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", video_url,
            "-vn",
            "-c:a", "aac",
            "-b:a", "128k",
            "-stats",
            output_path
        ]
        res_transcode = subprocess.run(cmd_transcode, env=env)
        if res_transcode.returncode != 0:
            print(f"\n[x] 音频提取失败！", file=sys.stderr)
            sys.exit(1)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n[✓] 音频抽取成功！最终音频大小: {file_size_mb:.2f} MB\n")


def upload_to_feishu(audio_path: str, headless: bool = False):
    """通过 Playwright 自动化将音频上传至飞书妙记"""
    audio_full_path = str(Path(audio_path).resolve())
    if not os.path.exists(audio_full_path):
        print(f"[x] 找不到音频文件: {audio_full_path}", file=sys.stderr)
        sys.exit(1)

    # 飞书是旧的可选云端工作流；本地音频抽取不应依赖 Playwright。
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "飞书上传需要额外安装 Playwright 及其浏览器；"
            "本地音频抽取和本地转写不需要此依赖。"
        ) from exc

    print(f"[*] 准备上传音频: {Path(audio_full_path).name}")
    print(f"[*] 用户数据保存路径: {DEFAULT_PROFILE}")
    os.makedirs(DEFAULT_PROFILE, exist_ok=True)

    with sync_playwright() as p:
        # 使用持久化配置启动浏览器
        browser_ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(DEFAULT_PROFILE),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = browser_ctx.new_page()
        print("[*] 正在打开飞书妙记 (https://minutes.feishu.cn)...")
        page.goto("https://minutes.feishu.cn", timeout=60000)

        # 等待页面加载基本元素
        page.wait_for_timeout(3000)

        # 检测是否需要扫码登录
        login_btn = page.locator("text=登录").first
        signup_btn = page.locator("text=注册").first
        if "login" in page.url or login_btn.is_visible() or signup_btn.is_visible():
            print("\n" + "=" * 62)
            print("👉 检测到未登录飞书，请在弹出的浏览器窗口中扫码登录！")
            print("👉 登录成功后无需做任何操作，脚本会自动继续检测...")
            print("=" * 62 + "\n")
            # 飞书扫码后通常会跳转到企业专属域名（如 xxx.feishu.cn/minutes/me 或 meetings.feishu.cn）
            # 只要包含 /minutes 且不在登录认证页，即表示登录成功
            page.wait_for_url(
                lambda u: ("/minutes" in u or "feishu.cn" in u) and "login" not in u and "passport" not in u and "accounts" not in u,
                timeout=180000
            )
            print("[✓] 登录成功！")
            page.wait_for_timeout(3000)

        # 确保进入妙记专属地址
        if "/minutes" not in page.url:
            print("[*] 正在直接导航至飞书妙记主页 (https://meetings.feishu.cn/minutes/me)...")
            try:
                page.goto("https://meetings.feishu.cn/minutes/me", timeout=60000)
                page.wait_for_timeout(5000)
            except Exception:
                pass

        # 检查是否有新标签页弹出（有些版本点击后会在新窗口打开）
        if len(browser_ctx.pages) > 1:
            page = browser_ctx.pages[-1]

        page.wait_for_timeout(3000)
        print(f"[*] 当前页面 URL: {page.url}")
        print("[*] 正在定位妙记上传入口...")

        uploaded = False

        # 策略 1：检查隐藏的 input[type="file"]
        file_inputs = page.locator('input[type="file"]')
        if file_inputs.count() > 0:
            try:
                file_inputs.first.set_input_files(audio_full_path)
                uploaded = True
                print("[*] 已通过文件选择器挂载音频...")
            except Exception as e:
                print(f"[!] 直接挂载 input 失败: {e}")

        # 策略 2：通过按钮文字定位（兼容多个飞书版本：上传音视频 / 上传 / 新建）
        if not uploaded:
            btn_selectors = [
                'button:has-text("上传音视频")',
                'div:has-text("上传音视频")',
                'span:has-text("上传音视频")',
                'button:has-text("上传")',
                'div[role="button"]:has-text("上传")',
                'button:has-text("新建")',
            ]
            for selector in btn_selectors:
                candidates = page.locator(selector)
                if candidates.count() > 0 and candidates.first.is_visible():
                    try:
                        print(f"[*] 尝试点击上传入口: {selector} ...")
                        with page.expect_file_chooser(timeout=3000) as fc_info:
                            candidates.first.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(audio_full_path)
                        uploaded = True
                        print("[*] 已成功触发文件上传！")
                        break
                    except Exception:
                        continue

        if not uploaded:
            # 保存当前页面截图供调试
            debug_shot = str(Path(__file__).resolve().parent / "debug_feishu.png")
            page.screenshot(path=debug_shot)
            print(f"\n" + "!" * 62)
            print("[!] 未能自动识别到上传按钮（已截取当前屏幕保存至 debug_feishu.png）。")
            print("👉 浏览器窗口已为你保持开启状态！")
            print("👉 请直接在弹出的网页上手动点击上传，或将音频文件拖进网页：")
            print(f"   音频路径: {audio_full_path}")
            print("!" * 62)
            input("\n👉 在网页中完成上传后，在终端按 [回车键 Enter] 退出并关闭浏览器...")
            browser_ctx.close()
            return

        print("[*] 文件已提交给飞书妙记，正在等待上传传输...")
        # 等待上传进度（一般几秒到十几秒）
        for _ in range(30):
            time.sleep(2)
            # 判断是否有正在上传进度框
            progress = page.locator('.upload-progress, [class*="progress"]').first
            if not progress.is_visible():
                break

        print("\n" + "=" * 62)
        print("🎉 音频已成功上传到飞书妙记！")
        print("💡 飞书云端正在进行 AI 智能转写与摘要生成。")
        print("📱 转写完成后，飞书 App / 桌面端会自动推送通知。")
        print("=" * 62 + "\n")

        page.wait_for_timeout(3000)
        browser_ctx.close()


def main():
    parser = argparse.ArgumentParser(
        description="浙江大学智云课堂音轨提取并自动上传飞书妙记转写工具"
    )
    parser.add_argument(
        "-u", "--url",
        help="智云课堂视频直链（支持 .mp4 或 .m3u8）"
    )
    parser.add_argument(
        "-f", "--file",
        help="本地已有的音频文件路径（跳过下载，直接上传飞书）"
    )
    parser.add_argument(
        "-o", "--out",
        default="course_audio.m4a",
        help="提取出的音频保存文件名（默认: course_audio.m4a）"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头模式（已登录后使用，不再弹出浏览器界面）"
    )

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.print_help()
        print("\n[使用示例]")
        print("  1. 传入 m3u8 自动抽取并上传：")
        print('     python3 zhiyun_to_feishu.py -u "https://.../index.m3u8"')
        print("  2. 直接上传已有音频：")
        print('     python3 zhiyun_to_feishu.py -f "lesson1.m4a"')
        sys.exit(0)

    audio_target = args.file
    if args.url:
        extract_audio(args.url, args.out)
        audio_target = args.out

    if audio_target:
        upload_to_feishu(audio_target, headless=args.headless)


if __name__ == "__main__":
    main()
