"""
小红书内容抓取模块
基于用户偏好生成个性化搜索关键词，调用 xiaohongshu-skills CLI 抓取内容和图片。
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from .utils import load_config, get_images_dir, ScrapingError, save_json, load_json


# 兴趣 -> 搜索关键词映射
INTEREST_KEYWORD_MAP = {
    "food": ["美食推荐", "必吃餐厅", "小吃攻略"],
    "photography": ["拍照打卡", "出片地点", "机位推荐"],
    "culture": ["文化体验", "历史古迹", "博物馆"],
    "shopping": ["购物攻略", "买什么", "免税店"],
    "nature": ["自然风光", "户外徒步", "公园"],
    "nightlife": ["夜生活", "酒吧推荐", "夜景"],
}

# 预算 -> 搜索关键词映射
BUDGET_KEYWORD_MAP = {
    "budget": ["穷游攻略", "省钱技巧", "平价推荐"],
    "mid-range": ["性价比", "推荐"],
    "luxury": ["高端体验", "奢华酒店", "米其林"],
}

# 同伴 -> 搜索关键词映射
COMPANION_KEYWORD_MAP = {
    "solo": ["独自旅行", "一个人"],
    "couple": ["情侣攻略", "约会"],
    "family": ["亲子游", "家庭出行"],
    "friends": ["朋友出行", "闺蜜游"],
}


def generate_search_keywords(destination: str, preferences: dict) -> list[str]:
    """
    基于用户偏好生成个性化搜索关键词。

    Args:
        destination: 目的地
        preferences: 用户偏好配置

    Returns:
        list[str]: 搜索关键词列表
    """
    keywords = [f"{destination}旅行攻略"]

    # 基于兴趣
    interests = preferences.get("interests", [])
    for interest in interests:
        if interest in INTEREST_KEYWORD_MAP:
            for kw in INTEREST_KEYWORD_MAP[interest]:
                keywords.append(f"{destination}{kw}")

    # 基于预算
    budget = preferences.get("budget_level", "mid-range")
    if budget in BUDGET_KEYWORD_MAP:
        for kw in BUDGET_KEYWORD_MAP[budget]:
            keywords.append(f"{destination}{kw}")

    # 基于同伴
    companion = preferences.get("travel_companions", "")
    if companion in COMPANION_KEYWORD_MAP:
        for kw in COMPANION_KEYWORD_MAP[companion]:
            keywords.append(f"{destination}{kw}")

    # 基于饮食限制
    dietary = preferences.get("dietary_restrictions", [])
    if "vegetarian" in dietary:
        keywords.append(f"{destination}素食餐厅")
    if "halal" in dietary:
        keywords.append(f"{destination}清真餐厅")

    # 去重
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return unique_keywords


def _get_xhs_cli_path() -> str:
    """获取 xiaohongshu-skills CLI 路径"""
    config = load_config()
    xhs_path = config.get("xhs_skills_path", "")
    if not xhs_path:
        raise ScrapingError("未配置 xiaohongshu-skills 路径，请在 config/settings.json 中设置 xhs_skills_path")
    cli_path = os.path.join(xhs_path, "scripts", "cli.py")
    if not os.path.exists(cli_path):
        raise ScrapingError(f"xiaohongshu-skills CLI 不存在: {cli_path}")
    return cli_path


def _run_xhs_command(command: str, args: dict) -> dict:
    """
    运行 xiaohongshu-skills CLI 命令。

    Args:
        command: 子命令名称
        args: 命令参数

    Returns:
        dict: JSON 输出

    Raises:
        ScrapingError: 命令执行失败
    """
    cli_path = _get_xhs_cli_path()
    xhs_path = os.path.dirname(os.path.dirname(cli_path))

    cmd = [sys.executable, cli_path, command]
    for key, value in args.items():
        if value is not None:
            cmd.extend([f"--{key}", str(value)])

    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=xhs_path,
            timeout=120
        )

        if result.returncode != 0:
            logger.error(f"命令失败: {result.stderr}")
            raise ScrapingError(f"xiaohongshu-skills 命令失败: {result.stderr}")

        output = result.stdout.strip()
        if not output:
            return {}

        return json.loads(output)

    except subprocess.TimeoutExpired:
        raise ScrapingError("命令执行超时")
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        raise ScrapingError(f"输出格式错误: {e}")
    except Exception as e:
        raise ScrapingError(f"执行命令失败: {e}")


def search_xhs_content(keyword: str, limit: int = 10) -> list[dict]:
    """
    搜索小红书内容。

    Args:
        keyword: 搜索关键词
        limit: 结果数量限制

    Returns:
        list[dict]: 搜索结果列表
    """
    result = _run_xhs_command("search-feeds", {
        "keyword": keyword,
    })

    feeds = result.get("feeds", [])
    return feeds[:limit]


def get_feed_detail(feed_id: str, xsec_token: str) -> dict:
    """
    获取笔记详情。

    Args:
        feed_id: 笔记 ID
        xsec_token: 安全令牌

    Returns:
        dict: 笔记详情
    """
    result = _run_xhs_command("get-feed-detail", {
        "feed-id": feed_id,
        "xsec-token": xsec_token,
    })
    return result


def download_feed_images(feed_details: list[dict], save_dir: Optional[str] = None) -> dict:
    """
    下载笔记中的图片。

    Args:
        feed_details: 笔记详情列表
        save_dir: 图片保存目录

    Returns:
        dict: {feed_id: [local_image_paths]}
    """
    if save_dir is None:
        save_dir = str(get_images_dir())

    config = load_config()
    max_images = config.get("max_images_per_feed", 5)

    # 导入 image_downloader
    xhs_path = config.get("xhs_skills_path", "")
    if xhs_path:
        sys.path.insert(0, xhs_path)

    try:
        from image_downloader import ImageDownloader
    except ImportError:
        logger.warning("无法导入 image_downloader，跳过图片下载")
        return {}

    downloader = ImageDownloader(save_dir)
    result = {}

    for feed in feed_details:
        feed_id = feed.get("noteId", "")
        if not feed_id:
            continue

        image_paths = []
        image_list = feed.get("imageList", [])

        for img in image_list[:max_images]:
            url = img.get("urlDefault", "")
            if url:
                try:
                    local_path = downloader.download_image(url)
                    image_paths.append(local_path)
                    logger.debug(f"图片已下载: {local_path}")
                except Exception as e:
                    logger.warning(f"下载图片失败: {e}")

        if image_paths:
            result[feed_id] = image_paths

    return result


def scrape_destination(destination: str, preferences: dict, max_feeds: int = 20) -> dict:
    """
    抓取目的地相关内容。

    Args:
        destination: 目的地
        preferences: 用户偏好
        max_feeds: 最大抓取数量

    Returns:
        dict: 抓取结果，包含 feeds 和 images
    """
    # 1. 生成个性化搜索关键词
    keywords = generate_search_keywords(destination, preferences)
    logger.info(f"生成 {len(keywords)} 个搜索关键词: {keywords}")

    # 2. 搜索小红书内容
    all_feeds = []
    seen_ids = set()

    for keyword in keywords:
        try:
            feeds = search_xhs_content(keyword, limit=5)
            for feed in feeds:
                feed_id = feed.get("id", "")
                if feed_id and feed_id not in seen_ids:
                    seen_ids.add(feed_id)
                    all_feeds.append(feed)
        except Exception as e:
            logger.warning(f"搜索 '{keyword}' 失败: {e}")

    logger.info(f"共找到 {len(all_feeds)} 篇不重复内容")

    # 3. 获取笔记详情
    feed_details = []
    for feed in all_feeds[:max_feeds]:
        feed_id = feed.get("id", "")
        xsec_token = feed.get("xsecToken", "")
        if not feed_id or not xsec_token:
            continue

        try:
            detail = get_feed_detail(feed_id, xsec_token)
            if detail:
                feed_details.append(detail)
                logger.debug(f"获取详情: {feed.get('displayTitle', feed_id)}")
        except Exception as e:
            logger.warning(f"获取详情失败 {feed_id}: {e}")

    logger.info(f"成功获取 {len(feed_details)} 篇笔记详情")

    # 4. 下载图片
    images_dir = str(get_images_dir() / destination.replace(" ", "_"))
    feed_images = download_feed_images(feed_details, images_dir)
    logger.info(f"下载了 {sum(len(v) for v in feed_images.values())} 张图片")

    # 5. 整理结果
    return {
        "destination": destination,
        "keywords": keywords,
        "feeds": [_format_feed_summary(f) for f in all_feeds[:max_feeds]],
        "feed_details": feed_details,
        "feed_images": feed_images,
    }


def _format_feed_summary(feed: dict) -> dict:
    """格式化搜索结果摘要"""
    return {
        "id": feed.get("id", ""),
        "title": feed.get("displayTitle", ""),
        "author": feed.get("user", {}).get("nickname", ""),
        "likes": feed.get("interactInfo", {}).get("likedCount", "0"),
        "cover": feed.get("cover", ""),
        "xsec_token": feed.get("xsecToken", ""),
    }
