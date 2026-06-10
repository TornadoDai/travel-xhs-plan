"""
行程生成模块
生成和优化旅行行程安排。
"""

from typing import Optional

from loguru import logger


def generate_itinerary(data: dict, days: int = 5) -> list[dict]:
    """
    生成行程安排。

    Args:
        data: 分析后的数据
        days: 旅行天数

    Returns:
        list[dict]: 行程列表
    """
    itinerary = data.get("itinerary", [])

    # 如果已有行程，直接返回
    if itinerary:
        return itinerary

    # 否则根据景点和美食生成基础行程
    spots = data.get("spots", [])
    foods = data.get("food_recommendations", [])

    if not spots:
        logger.warning("没有景点数据，无法生成行程")
        return []

    # 简单分配：每天安排 2-3 个景点
    spots_per_day = max(1, len(spots) // days)
    itinerary = []

    for day in range(1, days + 1):
        start_idx = (day - 1) * spots_per_day
        end_idx = start_idx + spots_per_day
        day_spots = spots[start_idx:end_idx]

        if not day_spots:
            break

        activities = []
        time_slots = ["上午", "下午", "晚上"]

        for i, spot in enumerate(day_spots):
            time = time_slots[i] if i < len(time_slots) else f"时段{i + 1}"
            activities.append({
                "time": time,
                "spot": spot.get("name", ""),
                "description": spot.get("description", ""),
                "duration": spot.get("duration", "2小时"),
                "tips": spot.get("tips", ""),
                "image": spot.get("image", ""),
            })

        # 添加午餐和晚餐建议
        if foods:
            lunch_idx = (day - 1) * 2 % len(foods)
            dinner_idx = (day * 2 - 1) % len(foods)

            if lunch_idx < len(foods):
                lunch = foods[lunch_idx]
                activities.insert(1, {
                    "time": "午餐",
                    "spot": lunch.get("name", ""),
                    "description": f"{lunch.get('type', '')} | 推荐：{lunch.get('must_try', '')}",
                    "duration": "1小时",
                    "tips": f"人均：{lunch.get('price_range', '')}",
                    "image": lunch.get("image", ""),
                })

            if dinner_idx < len(foods):
                dinner = foods[dinner_idx]
                activities.append({
                    "time": "晚餐",
                    "spot": dinner.get("name", ""),
                    "description": f"{dinner.get('type', '')} | 推荐：{dinner.get('must_try', '')}",
                    "duration": "1.5小时",
                    "tips": f"人均：{dinner.get('price_range', '')}",
                    "image": dinner.get("image", ""),
                })

        theme = _generate_day_theme(day, day_spots)
        itinerary.append({
            "day": day,
            "theme": theme,
            "activities": activities,
        })

    return itinerary


def _generate_day_theme(day: int, spots: list[dict]) -> str:
    """
    生成当日主题。

    Args:
        day: 天数
        spots: 当日景点列表

    Returns:
        str: 主题
    """
    if not spots:
        return f"第{day}天"

    # 根据景点类别生成主题
    categories = set()
    for spot in spots:
        cat = spot.get("category", "")
        if cat:
            categories.add(cat)

    category_themes = {
        "文化古迹": "文化探索",
        "自然风光": "自然之旅",
        "美食探店": "美食之旅",
        "购物天堂": "购物体验",
        "网红打卡": "打卡之旅",
        "历史遗迹": "历史探秘",
        "现代建筑": "都市探索",
        "公园绿地": "休闲漫步",
    }

    for cat in categories:
        if cat in category_themes:
            return f"Day {day} · {category_themes[cat]}"

    return f"Day {day} · 精彩探索"


def optimize_route(spots: list[dict]) -> list[dict]:
    """
    优化路线顺序（简单优化，按位置聚类）。

    Args:
        spots: 景点列表

    Returns:
        list[dict]: 优化后的景点列表
    """
    if len(spots) <= 2:
        return spots

    # 简单实现：保持原顺序
    # 更复杂的实现可以使用地理位置进行聚类优化
    return spots


def distribute_spots_to_days(spots: list[dict], days: int) -> list[list[dict]]:
    """
    将景点分配到各天。

    Args:
        spots: 景点列表
        days: 天数

    Returns:
        list[list[dict]]: 每天的景点列表
    """
    if not spots:
        return [[] for _ in range(days)]

    # 计算每天的景点数
    spots_per_day = len(spots) // days
    extra = len(spots) % days

    result = []
    idx = 0

    for day in range(days):
        count = spots_per_day + (1 if day < extra else 0)
        result.append(spots[idx:idx + count])
        idx += count

    return result
