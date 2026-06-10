"""
工具函数模块
提供通用的工具函数，包括配置加载、JSON 处理、错误处理等。
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 配置文件路径
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"


def setup_logger(level: str = "INFO"):
    """配置日志"""
    logger.remove()
    logger.add(sys.stderr, level=level)
    logger.add(PROJECT_ROOT / "output" / "travel_xhs.log", rotation="10 MB", retention="7 days")


def load_config() -> dict:
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"配置文件不存在: {CONFIG_PATH}，使用默认配置")
        return get_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"配置文件格式错误: {e}")
        return get_default_config()


def get_default_config() -> dict:
    """获取默认配置"""
    return {
        "xhs_skills_path": "",
        "github_repo": "",
        "github_branch": "gh-pages",
        "output_dir": "output",
        "max_feeds_per_keyword": 10,
        "max_images_per_feed": 5,
        "preferences_dir": "~/.claude/travel_xhs/preferences",
        "active_preference_file": "~/.claude/travel_xhs/active_preference"
    }


def save_config(config: dict):
    """保存配置文件"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info(f"配置已保存: {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        raise


def get_output_dir() -> Path:
    """获取输出目录"""
    config = load_config()
    output_dir = PROJECT_ROOT / config.get("output_dir", "output")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_guides_dir() -> Path:
    """获取攻略输出目录"""
    guides_dir = get_output_dir() / "guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    return guides_dir


def get_images_dir() -> Path:
    """获取图片输出目录"""
    images_dir = get_output_dir() / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def save_json(data: Any, filepath: Path, ensure_ascii: bool = False):
    """保存 JSON 文件"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=2)
        logger.debug(f"JSON 已保存: {filepath}")
    except Exception as e:
        logger.error(f"保存 JSON 失败: {e}")
        raise


def load_json(filepath: Path) -> Optional[Any]:
    """加载 JSON 文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"文件不存在: {filepath}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON 格式错误: {e}")
        return None


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename.strip()


def truncate_text(text: str, max_length: int = 2000) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_likes(likes: int) -> str:
    """格式化点赞数"""
    if likes >= 10000:
        return f"{likes / 10000:.1f}万"
    elif likes >= 1000:
        return f"{likes / 1000:.1f}k"
    return str(likes)


class TravelXhsError(Exception):
    """旅行攻略生成器基础异常"""
    pass


class ConfigError(TravelXhsError):
    """配置错误"""
    pass


class ScrapingError(TravelXhsError):
    """抓取错误"""
    pass


class AnalysisError(TravelXhsError):
    """分析错误"""
    pass


class DeploymentError(TravelXhsError):
    """部署错误"""
    pass
