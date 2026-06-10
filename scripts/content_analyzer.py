"""
AI 内容分析模块
将抓取的小红书内容格式化为提示词，供 Claude AI 分析生成结构化旅行攻略。
"""

import json
from typing import Optional

from loguru import logger

from .utils import truncate_text, AnalysisError


def format_scraped_data_for_analysis(scraped_data: dict, preferences: dict, days: int = 5) -> str:
    """
    将抓取的数据格式化为提示词，供 Claude 分析。

    Args:
        scraped_data: 从小红书抓取的原始数据
        preferences: 用户偏好配置
        days: 旅行天数

    Returns:
        str: 格式化后的提示词
    """
    destination = scraped_data.get("destination", "未知目的地")
    feeds = scraped_data.get("feeds", [])
    feed_details = scraped_data.get("feed_details", [])
    feed_images = scraped_data.get("feed_images", {})

    # 偏好标签映射
    style_map = {"adventurous": "冒险", "relaxed": "休闲", "cultural": "文化", "shopping": "购物"}
    budget_map = {"budget": "经济", "mid-range": "中档", "luxury": "高端"}
    companion_map = {"solo": "独自", "couple": "情侣", "family": "家庭", "friends": "朋友"}
    pace_map = {"relaxed": "轻松", "moderate": "适中", "intensive": "紧凑"}
    interest_map = {
        "food": "美食", "photography": "摄影", "culture": "文化",
        "shopping": "购物", "nature": "自然", "nightlife": "夜生活"
    }
    gender_map = {"male": "男", "female": "女", "other": "其他"}
    occupation_map = {
        "student": "学生", "engineer": "工程师", "teacher": "教师",
        "doctor": "医生", "business": "商务人士", "freelance": "自由职业", "other": "其他"
    }

    # 提取出发地和个人信息
    departure = preferences.get("departure", "")
    personal = preferences.get("personal_info", {})
    age = personal.get("age", "")
    gender = gender_map.get(personal.get("gender", ""), "")
    occupation = occupation_map.get(personal.get("occupation", ""), "")

    # 构建提示词
    prompt = f"""请分析以下小红书旅行内容，为用户生成一份个性化的旅行攻略。

## 重要规则
1. **只使用以下小红书笔记中的真实内容**，不要捏造任何信息
2. 如果某些信息在笔记中没有提到，请标注"笔记中未提及"
3. 行程安排必须基于笔记中提到的实际地点和活动
4. 美食推荐必须来自笔记中提到的真实餐厅或菜品
5. 价格信息必须来自笔记中的真实数据
6. 如有冲突信息，以点赞数更高的笔记为准

## 目的地
{destination}

## 出发地
{departure if departure else '未指定'}

## 旅行天数
{days} 天

## 用户信息
"""
    if age or gender or occupation:
        if age:
            prompt += f"- 年龄段：{age}\n"
        if gender:
            prompt += f"- 性别：{gender}\n"
        if occupation:
            prompt += f"- 职业：{occupation}\n"

    prompt += f"""
## 用户偏好
- 旅行风格：{style_map.get(preferences.get('travel_style', ''), '休闲')}
- 预算档次：{budget_map.get(preferences.get('budget_level', ''), '中档')}
- 兴趣爱好：{', '.join([interest_map.get(i, i) for i in preferences.get('interests', [])])}
- 饮食限制：{', '.join(preferences.get('dietary_restrictions', ['无']))}
- 旅行同伴：{companion_map.get(preferences.get('travel_companions', ''), '独自')}
- 旅行节奏：{pace_map.get(preferences.get('pace_preference', ''), '适中')}

## 小红书搜索结果摘要（共 {len(feeds)} 篇，按点赞数排序）
"""

    for i, feed in enumerate(feeds[:20], 1):
        prompt += f"\n{i}. {feed.get('title', '无标题')}"
        prompt += f"\n   作者: {feed.get('author', '未知')} | 点赞: {feed.get('likes', '0')} | 收藏: {feed.get('collected', '0')}"

    prompt += "\n\n## 小红书笔记详细内容（共 " + str(len(feed_details)) + " 篇）\n"

    for i, detail in enumerate(feed_details, 1):
        note = detail.get("note", detail)  # 兼容两种格式
        title = note.get("title", "无标题")
        desc = note.get("desc", "")
        body = note.get("body", "")
        tags = note.get("tags", [])
        user = note.get("user", {})
        nickname = user.get("nickname", "未知")
        interact = note.get("interactInfo", {})
        likes = interact.get("likedCount", "0")
        collected = interact.get("collectedCount", "0")
        images = note.get("imageList", [])
        feed_id = note.get("noteId", "")

        content = body if body else desc
        content = truncate_text(content, 3000)  # 增加内容长度限制

        prompt += f"\n### 笔记 {i}: {title}\n"
        prompt += f"- 作者: {nickname}\n"
        prompt += f"- 点赞: {likes} | 收藏: {collected}\n"
        prompt += f"- 标签: {', '.join(tags) if tags else '无'}\n"
        prompt += f"- 图片数: {len(images)}\n"

        # 添加图片路径信息
        if feed_id in feed_images:
            prompt += f"- 本地图片: {', '.join(feed_images[feed_id])}\n"

        prompt += f"\n{content}\n"

    prompt += """
## 输出要求

请根据以上小红书笔记的真实内容，生成一份结构化的旅行攻略。输出格式为 JSON：

```json
{
    "overview": {
        "best_season": "最佳旅行季节（必须来自笔记内容）",
        "recommended_days": 5,
        "budget_estimate": "预算估计（必须来自笔记中的真实价格）",
        "highlights": ["亮点1", "亮点2", "亮点3"]
    },
    "itinerary": [
        {
            "day": 1,
            "theme": "当日主题",
            "activities": [
                {
                    "time": "上午/下午/晚上",
                    "spot": "地点名称（必须是笔记中提到的真实地点）",
                    "description": "详细描述（基于笔记内容）",
                    "duration": "建议时长",
                    "tips": "小贴士（来自笔记）",
                    "image": "对应的本地图片路径（如有）"
                }
            ]
        }
    ],
    "food_recommendations": [
        {
            "name": "餐厅/美食名称（必须来自笔记）",
            "type": "菜系类型",
            "location": "位置（如有）",
            "price_range": "价格范围（来自笔记）",
            "must_try": "必点菜品（来自笔记）",
            "source": "来源笔记作者",
            "image": "对应的本地图片路径（如有）"
        }
    ],
    "spots": [
        {
            "name": "景点名称（必须来自笔记）",
            "category": "类别",
            "description": "描述（基于笔记内容）",
            "duration": "建议游玩时长",
            "tips": "小贴士（来自笔记）",
            "image": "对应的本地图片路径（如有）"
        }
    ],
    "transportation": {
        "from_airport": "出发地到目的地的交通（来自笔记）",
        "local": ["市内交通方式1", "市内交通方式2"],
        "tips": "交通小贴士（来自笔记）"
    },
    "tips": [
        "实用贴士1（必须来自笔记内容）",
        "实用贴士2"
    ],
    "sources": [
        {
            "feed_id": "笔记ID",
            "title": "笔记标题",
            "author": "作者",
            "likes": "点赞数",
            "url": "小红书链接"
        }
    ]
}
```

注意事项：
1. **严格基于笔记内容**：不要添加笔记中没有的信息
2. 行程安排要合理，考虑地理位置和交通
3. 美食推荐要包含价格范围和必点菜品
4. 景点推荐要包含游玩时长和实用小贴士
5. 如果有对应的本地图片，请在 image 字段中填入路径
6. 请确保输出为有效的 JSON 格式
7. 如有冲突信息，以点赞数更高的笔记为准
"""

    return prompt


def parse_analysis_result(ai_response: str) -> dict:
    """
    解析 AI 返回的 JSON 结果。

    Args:
        ai_response: AI 返回的文本

    Returns:
        dict: 解析后的结构化数据

    Raises:
        AnalysisError: 解析失败
    """
    # 尝试提取 JSON 块
    json_str = ai_response

    # 尝试从 markdown 代码块中提取
    if "```json" in ai_response:
        start = ai_response.index("```json") + 7
        end = ai_response.index("```", start)
        json_str = ai_response[start:end].strip()
    elif "```" in ai_response:
        start = ai_response.index("```") + 3
        end = ai_response.index("```", start)
        json_str = ai_response[start:end].strip()

    try:
        result = json.loads(json_str)
        return validate_analysis_result(result)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        logger.debug(f"原始响应: {ai_response[:500]}")
        raise AnalysisError(f"无法解析 AI 返回的 JSON: {e}")


def validate_analysis_result(result: dict) -> dict:
    """
    验证分析结果格式。

    Args:
        result: 解析后的数据

    Returns:
        dict: 验证后的数据（补充缺失字段）
    """
    # 确保必要字段存在
    if "overview" not in result:
        result["overview"] = {
            "best_season": "全年",
            "recommended_days": 5,
            "budget_estimate": "待定",
            "highlights": []
        }

    if "itinerary" not in result:
        result["itinerary"] = []

    if "food_recommendations" not in result:
        result["food_recommendations"] = []

    if "spots" not in result:
        result["spots"] = []

    if "transportation" not in result:
        result["transportation"] = {
            "from_airport": "待补充",
            "local": [],
            "tips": ""
        }

    if "tips" not in result:
        result["tips"] = []

    if "sources" not in result:
        result["sources"] = []

    return result


def analyze_content(scraped_data: dict, preferences: dict, days: int = 5) -> dict:
    """
    分析抓取的内容，生成结构化攻略数据。

    注意：此函数生成提示词，实际 AI 分析在 Claude 对话中完成。
    当直接调用时，返回提示词供外部使用。

    Args:
        scraped_data: 抓取的数据
        preferences: 用户偏好
        days: 旅行天数

    Returns:
        dict: 包含 prompt 和 scraped_data 的字典
    """
    prompt = format_scraped_data_for_analysis(scraped_data, preferences, days)

    return {
        "prompt": prompt,
        "scraped_data": scraped_data,
        "preferences": preferences,
        "days": days,
        "destination": scraped_data.get("destination", ""),
    }
