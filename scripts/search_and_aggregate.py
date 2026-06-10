#!/usr/bin/env python3
"""
搜索并聚合小红书笔记数据
- 多关键词搜索
- 拉取15篇笔记详情（含评论）
- 下载图片
- 输出聚合后的数据
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from utils import load_config, get_images_dir, save_json


def run_xhs_command(command: str, args: dict) -> dict:
    """运行 xiaohongshu-skills CLI 命令"""
    config = load_config()
    xhs_path = config.get("xhs_skills_path", "")
    if not xhs_path:
        raise Exception("未配置 xhs_skills_path")

    cli_path = os.path.join(xhs_path, "scripts", "cli.py")

    # 优先使用 uv run
    import shutil
    uv_path = shutil.which("uv")
    if uv_path:
        cmd = [uv_path, "run", "python", cli_path, command]
    else:
        cmd = [sys.executable, cli_path, command]

    for key, value in args.items():
        if value is not None:
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

    logger.info(f"执行: {' '.join(cmd[:6])}...")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=os.path.join(xhs_path, "scripts"),
        timeout=180
    )

    if result.returncode != 0:
        logger.error(f"命令失败: {result.stderr[:200]}")
        return {}

    output = result.stdout.strip()
    if not output:
        return {}

    return json.loads(output)


def search_feeds(keyword: str, limit: int = 10) -> list:
    """搜索小红书内容"""
    result = run_xhs_command("search-feeds", {"keyword": keyword})
    feeds = result.get("feeds", [])
    return feeds[:limit]


def get_feed_detail(feed_id: str, xsec_token: str) -> dict:
    """获取笔记详情（含评论）"""
    result = run_xhs_command("get-feed-detail", {
        "feed-id": feed_id,
        "xsec-token": xsec_token,
        "load-all-comments": True,
        "max-comment-items": 20
    })
    return result


def download_images(image_urls: list, save_dir: str) -> list:
    """下载图片（使用正确的请求头）"""
    import hashlib
    import time
    import requests

    os.makedirs(save_dir, exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.xiaohongshu.com/',
        'Origin': 'https://www.xiaohongshu.com',
    }

    downloaded = []
    for url in image_urls[:3]:  # 每篇笔记最多3张
        try:
            # 生成文件名
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
            filename = f"img_{url_hash}.webp"
            filepath = os.path.join(save_dir, filename)

            # 检查是否已存在
            if os.path.exists(filepath):
                downloaded.append(filepath)
                continue

            # 下载
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                downloaded.append(filepath)
                logger.info(f"下载图片成功: {filename}")
            else:
                logger.warning(f"下载图片失败: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"下载图片失败: {e}")

    return downloaded


def search_and_aggregate(destination: str, preferences: dict, max_notes: int = 15) -> dict:
    """
    搜索并聚合小红书笔记数据

    Args:
        destination: 目的地
        preferences: 用户偏好
        max_notes: 最大笔记数量

    Returns:
        dict: 聚合后的数据
    """
    # 1. 生成搜索关键词
    keywords = [
        f"{destination}旅行攻略",
        f"{destination}美食推荐",
        f"{destination}景点打卡",
        f"{destination}交通攻略",
    ]

    # 基于偏好添加关键词
    interests = preferences.get("interests", [])
    if "food" in interests:
        keywords.append(f"{destination}必吃餐厅")
    if "nature" in interests:
        keywords.append(f"{destination}自然风光")
    if "culture" in interests:
        keywords.append(f"{destination}文化体验")

    logger.info(f"搜索关键词: {keywords}")

    # 2. 搜索并去重
    all_feeds = []
    seen_ids = set()

    for keyword in keywords[:5]:  # 限制关键词数量
        try:
            feeds = search_feeds(keyword, limit=10)
            for feed in feeds:
                feed_id = feed.get("id", "")
                if feed_id and feed_id not in seen_ids:
                    seen_ids.add(feed_id)
                    all_feeds.append(feed)
            logger.info(f"关键词 '{keyword}' 找到 {len(feeds)} 篇")
        except Exception as e:
            logger.warning(f"搜索 '{keyword}' 失败: {e}")

    # 按点赞数排序
    all_feeds.sort(key=lambda x: int(x.get("interactInfo", {}).get("likedCount", "0") or "0"), reverse=True)

    logger.info(f"共找到 {len(all_feeds)} 篇不重复笔记")

    # 3. 获取笔记详情
    notes_with_details = []
    images_dir = str(get_images_dir() / destination.replace(" ", "_"))

    for i, feed in enumerate(all_feeds[:max_notes]):
        feed_id = feed.get("id", "")
        xsec_token = feed.get("xsecToken", "")
        if not feed_id or not xsec_token:
            continue

        try:
            detail = get_feed_detail(feed_id, xsec_token)
            if detail and detail.get("note", {}).get("title"):
                note = detail.get("note", {})
                comments = detail.get("comments", [])

                # 下载图片
                image_urls = [img.get("urlDefault", "") for img in note.get("imageList", [])[:3]]
                downloaded_images = download_images(image_urls, images_dir)

                # 构建笔记摘要
                note_summary = {
                    "id": feed_id,
                    "title": note.get("title", ""),
                    "author": note.get("user", {}).get("nickname", ""),
                    "likes": note.get("interactInfo", {}).get("likedCount", "0"),
                    "collected": note.get("interactInfo", {}).get("collectedCount", "0"),
                    "ip_location": note.get("ipLocation", ""),
                    "content": note.get("body", note.get("desc", "")),
                    "tags": note.get("tags", []),
                    "images": downloaded_images,
                    "image_urls": image_urls,
                    "url": f"https://www.xiaohongshu.com/explore/{feed_id}",
                    "comments": []
                }

                # 提取有价值的评论
                for comment in comments:
                    comment_content = comment.get("content", "")
                    if len(comment_content) > 10:  # 只保留有价值的评论
                        note_summary["comments"].append({
                            "content": comment_content,
                            "likes": comment.get("likeCount", "0"),
                            "ip_location": comment.get("ipLocation", ""),
                            "user": comment.get("user", {}).get("nickname", "")
                        })

                notes_with_details.append(note_summary)
                logger.info(f"获取详情 ({len(notes_with_details)}/{max_notes}): {note.get('title', '')[:30]}")
        except Exception as e:
            logger.warning(f"获取详情失败 {feed_id}: {e}")

    logger.info(f"成功获取 {len(notes_with_details)} 篇笔记详情")

    # 4. 聚合数据
    aggregated = aggregate_notes(notes_with_details, destination)

    return aggregated


def aggregate_notes(notes: list, destination: str) -> dict:
    """
    聚合笔记数据，删除重复内容，保留重点

    Args:
        notes: 笔记列表
        destination: 目的地

    Returns:
        dict: 聚合后的数据
    """
    # 提取所有景点
    all_spots = []
    # 提取所有美食
    all_foods = []
    # 提取所有贴士
    all_tips = []
    # 提取所有评论
    all_comments = []

    for note in notes:
        content = note.get("content", "")

        # 提取景点（简单关键词匹配）
        spot_keywords = ["景区", "景点", "公园", "湿地", "河", "湖", "山", "草原", "广场", "博物馆"]
        for keyword in spot_keywords:
            if keyword in content:
                # 提取包含关键词的句子
                sentences = content.split("。")
                for sentence in sentences:
                    if keyword in sentence and len(sentence) < 50:
                        all_spots.append(sentence.strip())

        # 提取美食
        food_keywords = ["美食", "餐厅", "火锅", "烤肉", "奶茶", "冰淇淋", "列巴", "手把肉", "羊排"]
        for keyword in food_keywords:
            if keyword in content:
                sentences = content.split("。")
                for sentence in sentences:
                    if keyword in sentence and len(sentence) < 50:
                        all_foods.append(sentence.strip())

        # 提取贴士
        tip_keywords = ["注意", "建议", "必备", "推荐", "记得", "提前"]
        for keyword in tip_keywords:
            if keyword in content:
                sentences = content.split("。")
                for sentence in sentences:
                    if keyword in sentence and len(sentence) < 80:
                        all_tips.append(sentence.strip())

        # 收集评论
        for comment in note.get("comments", []):
            if int(comment.get("likes", "0") or "0") >= 2:  # 只保留高赞评论
                all_comments.append(comment)

    # 去重
    unique_spots = list(set(all_spots))[:20]
    unique_foods = list(set(all_foods))[:15]
    unique_tips = list(set(all_tips))[:15]

    # 按点赞数排序评论
    all_comments.sort(key=lambda x: int(x.get("likes", "0") or "0"), reverse=True)
    unique_comments = all_comments[:20]

    return {
        "destination": destination,
        "notes_count": len(notes),
        "notes": notes,
        "aggregated": {
            "spots": unique_spots,
            "foods": unique_foods,
            "tips": unique_tips,
            "top_comments": unique_comments
        }
    }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="搜索并聚合小红书笔记数据")
    parser.add_argument("--destination", required=True, help="目的地")
    parser.add_argument("--max-notes", type=int, default=15, help="最大笔记数量")
    parser.add_argument("--output", default=None, help="输出文件路径")

    args = parser.parse_args()

    # 加载偏好
    config = load_config()
    preferences_dir = Path(__file__).parent.parent / "config" / "preferences"
    active_preference_file = Path(__file__).parent.parent / "config" / "active_preference"

    preferences = {}
    if active_preference_file.exists():
        preference_name = active_preference_file.read_text(encoding="utf-8").strip()
        preference_file = preferences_dir / f"{preference_name}.json"
        if preference_file.exists():
            with open(preference_file, "r", encoding="utf-8") as f:
                preferences = json.load(f)

    # 搜索并聚合
    result = search_and_aggregate(args.destination, preferences, args.max_notes)

    # 保存结果
    if args.output:
        output_path = args.output
    else:
        output_path = str(Path(__file__).parent.parent / "output" / f"{args.destination}_data.json")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    save_json(result, Path(output_path))

    print(f"\n✅ 数据已保存到: {output_path}")
    print(f"📊 共获取 {result['notes_count']} 篇笔记")
    print(f"📍 提取 {len(result['aggregated']['spots'])} 个景点")
    print(f"🍜 提取 {len(result['aggregated']['foods'])} 个美食")
    print(f"💡 提取 {len(result['aggregated']['tips'])} 条贴士")
    print(f"💬 提取 {len(result['aggregated']['top_comments'])} 条高赞评论")


if __name__ == "__main__":
    main()
