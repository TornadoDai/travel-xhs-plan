"""
攻略文档生成模块
使用 Jinja2 模板生成精美的 HTML 旅行攻略文档。
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from .utils import get_guides_dir, sanitize_filename, TravelXhsError


# 模板目录
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def get_template_env() -> Environment:
    """获取 Jinja2 模板环境"""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True
    )


def generate_html_guide(analyzed_data: dict, destination: str, output_path: Optional[str] = None) -> str:
    """
    生成 HTML 攻略文档。

    Args:
        analyzed_data: AI 分析后的结构化数据
        destination: 目的地名称
        output_path: 输出文件路径（可选）

    Returns:
        str: 生成的 HTML 文件路径
    """
    # 准备模板数据
    template_data = prepare_template_data(analyzed_data, destination)

    # 渲染 HTML
    env = get_template_env()
    template = env.get_template("guide_template.html")
    html_content = template.render(**template_data)

    # 确定输出路径
    if output_path is None:
        filename = sanitize_filename(f"{destination}_guide") + ".html"
        output_path = str(get_guides_dir() / filename)

    # 保存文件
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"攻略已生成: {output_path}")
        return output_path
    except Exception as e:
        raise TravelXhsError(f"保存攻略文件失败: {e}")


def prepare_template_data(analyzed_data: dict, destination: str) -> dict:
    """
    准备模板渲染数据。

    Args:
        analyzed_data: 分析后的数据
        destination: 目的地

    Returns:
        dict: 模板数据
    """
    overview = analyzed_data.get("overview", {})
    itinerary = analyzed_data.get("itinerary", [])
    food_recommendations = analyzed_data.get("food_recommendations", [])
    spots = analyzed_data.get("spots", [])
    transportation = analyzed_data.get("transportation", {})
    tips = analyzed_data.get("tips", [])
    sources = analyzed_data.get("sources", [])

    # 处理图片路径（转为相对路径或 URL）
    for day in itinerary:
        for activity in day.get("activities", []):
            if activity.get("image"):
                activity["image"] = _process_image_path(activity["image"])

    for food in food_recommendations:
        if food.get("image"):
            food["image"] = _process_image_path(food["image"])

    for spot in spots:
        if spot.get("image"):
            spot["image"] = _process_image_path(spot["image"])

    return {
        "destination": destination,
        "days": overview.get("recommended_days", 5),
        "budget_estimate": overview.get("budget_estimate", "待定"),
        "feed_count": len(sources),
        "generate_date": datetime.now().strftime("%Y年%m月%d日"),
        "overview": overview,
        "itinerary": itinerary,
        "food_recommendations": food_recommendations,
        "spots": spots,
        "transportation": transportation,
        "tips": tips,
        "sources": sources,
    }


def _process_image_path(image_path: str) -> str:
    """
    处理图片路径，转换为相对路径或 URL。

    Args:
        image_path: 原始图片路径

    Returns:
        str: 处理后的路径
    """
    if not image_path:
        return ""

    # 如果是 URL，直接返回
    if image_path.startswith(("http://", "https://")):
        return image_path

    # 如果是绝对路径，转换为相对路径
    if os.path.isabs(image_path):
        try:
            guides_dir = get_guides_dir()
            rel_path = os.path.relpath(image_path, guides_dir)
            return rel_path
        except ValueError:
            # Windows 跨盘符情况
            return image_path

    return image_path


def generate_overview_section(data: dict) -> str:
    """生成行程概览 HTML"""
    overview = data.get("overview", {})
    highlights = overview.get("highlights", [])

    html = '<section id="overview" class="card">\n'
    html += '  <h2 class="section-title">📋 行程概览</h2>\n'
    html += '  <div class="overview-grid">\n'
    html += f'    <div class="overview-item"><div class="label">最佳季节</div><div class="value">{overview.get("best_season", "全年")}</div></div>\n'
    html += f'    <div class="overview-item"><div class="label">推荐天数</div><div class="value">{overview.get("recommended_days", 5)}天</div></div>\n'
    html += f'    <div class="overview-item"><div class="label">预算估计</div><div class="value">{overview.get("budget_estimate", "待定")}</div></div>\n'
    html += '  </div>\n'

    if highlights:
        html += '  <div class="highlights">\n'
        for h in highlights:
            html += f'    <span class="highlight-tag">{h}</span>\n'
        html += '  </div>\n'

    html += '</section>\n'
    return html


def generate_itinerary_section(data: dict) -> str:
    """生成每日行程 HTML"""
    itinerary = data.get("itinerary", [])

    html = '<section id="itinerary">\n'
    html += '  <h2 class="section-title">🗓️ 每日行程</h2>\n'

    for day in itinerary:
        html += '  <div class="day-card">\n'
        html += '    <div class="day-header">\n'
        html += f'      <div class="day-number">D{day.get("day", 1)}</div>\n'
        html += f'      <div class="day-theme">{day.get("theme", "")}</div>\n'
        html += '    </div>\n'

        for activity in day.get("activities", []):
            html += '    <div class="activity">\n'
            html += f'      <span class="activity-time">{activity.get("time", "")}</span>\n'
            html += f'      <div class="activity-spot">{activity.get("spot", "")}</div>\n'
            html += f'      <div class="activity-desc">{activity.get("description", "")}</div>\n'
            html += '      <div class="activity-meta">\n'
            if activity.get("duration"):
                html += f'        <span>⏱️ {activity["duration"]}</span>\n'
            if activity.get("tips"):
                html += f'        <span>💡 {activity["tips"]}</span>\n'
            html += '      </div>\n'
            if activity.get("image"):
                html += f'      <img src="{activity["image"]}" alt="{activity.get("spot", "")}" class="activity-image" loading="lazy">\n'
            html += '    </div>\n'

        html += '  </div>\n'

    html += '</section>\n'
    return html


def generate_food_section(data: dict) -> str:
    """生成美食推荐 HTML"""
    foods = data.get("food_recommendations", [])

    html = '<section id="food">\n'
    html += '  <h2 class="section-title">🍜 美食推荐</h2>\n'
    html += '  <div class="grid">\n'

    for food in foods:
        html += '    <div class="food-card">\n'
        if food.get("image"):
            html += f'      <img src="{food["image"]}" alt="{food.get("name", "")}" class="card-image" loading="lazy">\n'
        html += '      <div class="card-body">\n'
        html += f'        <div class="card-name">{food.get("name", "")}</div>\n'
        html += f'        <div class="card-info">🍽️ {food.get("type", "")}</div>\n'
        html += f'        <div class="card-info">📍 {food.get("location", "")}</div>\n'
        html += f'        <div class="card-info">💰 {food.get("price_range", "")}</div>\n'
        html += f'        <div class="card-info">⭐ 必点：{food.get("must_try", "")}</div>\n'
        if food.get("source"):
            html += f'        <div class="card-source">来源：{food["source"]}</div>\n'
        html += '      </div>\n'
        html += '    </div>\n'

    html += '  </div>\n'
    html += '</section>\n'
    return html


def generate_spots_section(data: dict) -> str:
    """生成景点打卡 HTML"""
    spots = data.get("spots", [])

    html = '<section id="spots">\n'
    html += '  <h2 class="section-title">📸 景点打卡</h2>\n'
    html += '  <div class="grid">\n'

    for spot in spots:
        html += '    <div class="spot-card">\n'
        if spot.get("image"):
            html += f'      <img src="{spot["image"]}" alt="{spot.get("name", "")}" class="card-image" loading="lazy">\n'
        html += '      <div class="card-body">\n'
        html += f'        <div class="card-name">{spot.get("name", "")}</div>\n'
        html += f'        <span class="card-tag">{spot.get("category", "")}</span>\n'
        html += f'        <div class="card-info" style="margin-top: 10px;">{spot.get("description", "")}</div>\n'
        html += f'        <div class="card-info">⏱️ 建议游玩：{spot.get("duration", "")}</div>\n'
        if spot.get("tips"):
            html += f'        <div class="card-info">💡 {spot["tips"]}</div>\n'
        html += '      </div>\n'
        html += '    </div>\n'

    html += '  </div>\n'
    html += '</section>\n'
    return html


def generate_transport_section(data: dict) -> str:
    """生成交通指南 HTML"""
    transport = data.get("transportation", {})

    html = '<section id="transport" class="card">\n'
    html += '  <h2 class="section-title">🚇 交通指南</h2>\n'

    html += '  <div class="transport-item">\n'
    html += '    <div class="transport-label">✈️ 机场到市区</div>\n'
    html += f'    <div>{transport.get("from_airport", "待补充")}</div>\n'
    html += '  </div>\n'

    local = transport.get("local", [])
    if local:
        html += '  <div class="transport-item">\n'
        html += '    <div class="transport-label">🚌 市内交通</div>\n'
        html += f'    <div>{"、".join(local)}</div>\n'
        html += '  </div>\n'

    if transport.get("tips"):
        html += '  <div class="transport-item">\n'
        html += '    <div class="transport-label">💡 交通小贴士</div>\n'
        html += f'    <div>{transport["tips"]}</div>\n'
        html += '  </div>\n'

    html += '</section>\n'
    return html


def generate_tips_section(data: dict) -> str:
    """生成实用贴士 HTML"""
    tips = data.get("tips", [])

    html = '<section id="tips" class="card">\n'
    html += '  <h2 class="section-title">💡 实用贴士</h2>\n'
    html += '  <ul class="tips-list">\n'

    for i, tip in enumerate(tips, 1):
        html += '    <li>\n'
        html += f'      <span class="tip-icon">{i}</span>\n'
        html += f'      <span>{tip}</span>\n'
        html += '    </li>\n'

    html += '  </ul>\n'
    html += '</section>\n'
    return html


def generate_sources_section(data: dict) -> str:
    """生成数据来源 HTML"""
    sources = data.get("sources", [])

    html = '<section id="sources" class="card">\n'
    html += '  <h2 class="section-title">📚 数据来源</h2>\n'
    html += '  <p style="color: var(--text-light); margin-bottom: 15px;">本攻略基于以下小红书笔记生成</p>\n'
    html += '  <ul class="source-list">\n'

    for source in sources:
        html += '    <li class="source-item">\n'
        html += '      <div>\n'
        html += f'        <div class="source-title">{source.get("title", "")}</div>\n'
        html += f'        <div class="source-meta">作者：{source.get("author", "")} | 👍 {source.get("likes", "0")}</div>\n'
        html += '      </div>\n'
        if source.get("url"):
            html += f'      <a href="{source["url"]}" target="_blank" class="source-link">查看原文 →</a>\n'
        html += '    </li>\n'

    html += '  </ul>\n'
    html += '</section>\n'
    return html
