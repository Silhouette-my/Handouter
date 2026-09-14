#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PPT asset helper.

The production ZIP importer lives in ``handouter.importers``. The historical
JSON network downloader is retained only for compatibility and is not used by
Handouter's new CLI/TUI pipeline.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
try:
    from handouter.importers import import_slides_zip
except ModuleNotFoundError:
    sys.path.insert(0, str(ROOT / "src"))
    from handouter.importers import import_slides_zip

SLIDES_DIR = Path("slides")


def time_str_to_seconds(t_str: str) -> int:
    """Legacy HH:MM:SS/MM:SS integer conversion used only by old tests/JSON path."""
    parts = list(map(int, t_str.strip().split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def download_from_json(json_path: str):
    """Legacy copied-JSON downloader; prefer the browser ZIP exporter."""
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[!] legacy JSON 下载分支：准备处理 {len(data)} 页；新流程请优先使用浏览器 ZIP。")
    mapping = []

    def fetch_one(item, idx):
        url = item.get("url") or item.get("imgSrc")
        time_str = item.get("timestamp") or item.get("time") or item.get("switchTime")
        if not url:
            return {
                "index": idx, "filename": None, "path": None, "timestamp": time_str,
                "seconds": item.get("seconds"), "status": "missing_url",
            }
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("http://"):
            url = "https://" + url[7:]
        ext = url.split("?")[0].split(".")[-1].lower()
        if ext not in {"jpg", "jpeg", "png", "webp"}:
            ext = "jpg"
        filename = f"slide_{idx:03d}.{ext}"
        filepath = SLIDES_DIR / filename
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://interactivemeta.cmc.zju.edu.cn/",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response, open(filepath, "xb") as output:
                output.write(response.read())
            status = "ok"
        except Exception as exc:
            try:
                filepath.unlink()
            except FileNotFoundError:
                pass
            print(f"[x] 第 {idx:02d} 页下载失败: {type(exc).__name__}")
            status = "download_failed"
        return {
            "index": idx,
            "filename": filename if status == "ok" else None,
            "path": str(filepath) if status == "ok" else None,
            "timestamp": time_str,
            "seconds": item.get("seconds"),
            "status": status,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        for result in executor.map(lambda pair: fetch_one(pair[1], pair[0] + 1), enumerate(data)):
            mapping.append(result)
    mapping.sort(key=lambda item: item["index"])
    mapping_path = SLIDES_DIR / "slides_meta.json"
    with open(mapping_path, "x", encoding="utf-8") as output:
        json.dump(mapping, output, ensure_ascii=False, indent=2, allow_nan=False)
    failed = sum(item["status"] != "ok" for item in mapping)
    print(f"[{'✓' if not failed else '!'}] JSON 下载结束：成功 {len(mapping)-failed}/{len(mapping)}，失败 {failed}；元数据 {mapping_path}")
    return mapping


def extract_from_zip(zip_path: str | Path, output_dir: str | Path | None = None) -> list[dict]:
    """Compatibility wrapper around the package-level production importer."""
    destination = Path(output_dir) if output_dir is not None else SLIDES_DIR
    mapping = import_slides_zip(zip_path, destination)
    missing = sum(item["status"] == "missing_image" for item in mapping)
    unknown = sum(item["start_ms"] is None for item in mapping)
    print(f"[✓] ZIP 导入：{len({item.get('filename') for item in mapping if item.get('filename')})} 张图片，{len(mapping)} 条记录；缺图 {missing}，未知时间 {unknown}。")
    return mapping


def main():
    parser = argparse.ArgumentParser(description="PPT ZIP 导入 / legacy JSON 下载")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("-j", "--json", help="legacy：浏览器复制的 PPT JSON")
    inputs.add_argument("-z", "--zip", help="浏览器资产 ZIP；推荐")
    parser.add_argument("-o", "--output-dir", help="ZIP 输出目录，必须尚不存在（默认 slides）")
    args = parser.parse_args()
    if args.zip is not None:
        if not Path(args.zip).is_file():
            parser.error("指定的 ZIP 文件不存在；不会回退到其他课程输入")
        try:
            extract_from_zip(args.zip, args.output_dir)
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
            parser.error(str(exc))
        return
    if args.output_dir:
        parser.error("--output-dir 只适用于 ZIP 导入")
    json_path = args.json or "ppt_list.json"
    if not Path(json_path).is_file():
        parser.error("请用 -z 指定 ZIP，或用 -j 指定 legacy PPT JSON")
    download_from_json(json_path)


if __name__ == "__main__":
    main()
