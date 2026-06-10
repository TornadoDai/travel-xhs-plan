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
1. **基于小红书笔记内容**：行程、美食、景点等信息必须来自笔记
2. **补充网上资料**：如果笔记中信息不足，请使用你的知识补充：
   - 各景点之间的距离和交通时间
   - 景点的开放时间、门票价格
   - 当地特色美食的推荐餐厅
   - 实用的交通、住宿建议
3. **逻辑一致性**：
   - 上午安排适合上午的活动（如晨景、早餐）
   - 下午安排适合下午的活动（如日落、夜景）
   - 考虑景点之间的距离和交通时间
   - 路线要合理，不走回头路
4. **真实可落地**：
   - 行程安排要考虑实际交通时间
   - 每个景点的游玩时间要合理
   - 美食推荐要有具体餐厅或位置
   - 价格信息要真实可靠
5. **重点关注评论中的信息**：
   - 当地用户（IP地址与目的地相关）的建议更可靠
   - 高赞评论代表大众认可的建议
   - 评论中可能包含补充景点、美食、避坑建议等

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

    # 收集所有评论用于后续分析
    all_comments = []

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

        # 获取笔记链接
        note_url = ""
        for feed in feeds:
            if feed.get("id") == feed_id:
                note_url = feed.get("url", "")
                break

        content = body if body else desc
        content = truncate_text(content, 3000)  # 增加内容长度限制

        prompt += f"\n### 笔记 {i}: {title}\n"
        prompt += f"- 作者: {nickname}\n"
        prompt += f"- 点赞: {likes} | 收藏: {collected}\n"
        prompt += f"- 标签: {', '.join(tags) if tags else '无'}\n"
        prompt += f"- 图片数: {len(images)}\n"
        if note_url:
            prompt += f"- 链接: {note_url}\n"

        # 添加图片路径信息
        if feed_id in feed_images:
            prompt += f"- 本地图片: {', '.join(feed_images[feed_id])}\n"

        prompt += f"\n{content}\n"

        # 收集评论
        comments = detail.get("comments", [])
        if comments:
            all_comments.extend([
                {**c, "note_title": title, "note_author": nickname}
                for c in comments
            ])

    # 添加评论分析部分
    if all_comments:
        prompt += "\n## 评论分析\n"
        prompt += "以下是从各篇笔记中提取的评论，重点关注：\n"
        prompt += "1. **当地用户评论**（IP地址与目的地相关的用户，他们的建议更可靠）\n"
        prompt += "2. **高赞评论**（获得较多点赞的评论，代表大众认可的建议）\n"
        prompt += "3. **补充信息**（评论中提到的额外景点、美食、避坑建议等）\n\n"

        # 分类评论
        local_comments = []  # 当地用户评论
        high_like_comments = []  # 高赞评论
        other_comments = []  # 其他评论

        for comment in all_comments:
            ip_location = comment.get("ipLocation", "")
            like_count = int(comment.get("likeCount", "0") or "0")
            content = comment.get("content", "")

            if not content or len(content) < 5:
                continue

            # 判断是否为当地用户（IP包含目的地关键词）
            is_local = False
            if ip_location:
                # 提取目的地的主要地名（如"呼伦贝尔" -> "呼伦"、"海拉尔"）
                dest_keywords = [destination[:2], destination[:3], destination[:4]]
                for keyword in dest_keywords:
                    if keyword in ip_location:
                        is_local = True
                        break

            if is_local:
                local_comments.append(comment)
            elif like_count >= 5:  # 高赞阈值
                high_like_comments.append(comment)
            elif len(content) > 15:  # 有价值的长评论
                other_comments.append(comment)

        # 输出当地用户评论
        if local_comments:
            prompt += "### 当地用户评论（IP地址与目的地相关）\n"
            for j, comment in enumerate(local_comments[:10], 1):  # 最多10条
                user = comment.get("user", {})
                nickname = user.get("nickname", "未知")
                ip = comment.get("ipLocation", "")
                like_count = comment.get("likeCount", "0")
                content = comment.get("content", "")
                note_title = comment.get("note_title", "")

                prompt += f"\n{j}. [{ip}] {nickname} (赞: {like_count})\n"
                prompt += f"   来源笔记: {note_title}\n"
                prompt += f"   内容: {truncate_text(content, 200)}\n"

                # 添加子评论
                sub_comments = comment.get("subComments", [])
                if sub_comments:
                    for sub in sub_comments[:3]:  # 最多3条子评论
                        sub_user = sub.get("user", {})
                        sub_nickname = sub_user.get("nickname", "")
                        sub_content = sub.get("content", "")
                        if sub_content and len(sub_content) > 3:
                            prompt += f"   └─ {sub_nickname}: {truncate_text(sub_content, 100)}\n"

        # 输出高赞评论
        if high_like_comments:
            prompt += "\n### 高赞评论（点赞数 ≥ 5）\n"
            high_like_comments.sort(key=lambda x: int(x.get("likeCount", "0") or "0"), reverse=True)
            for j, comment in enumerate(high_like_comments[:10], 1):
                user = comment.get("user", {})
                nickname = user.get("nickname", "未知")
                ip = comment.get("ipLocation", "")
                like_count = comment.get("likeCount", "0")
                content = comment.get("content", "")
                note_title = comment.get("note_title", "")

                prompt += f"\n{j}. [{ip}] {nickname} (赞: {like_count})\n"
                prompt += f"   来源笔记: {note_title}\n"
                prompt += f"   内容: {truncate_text(content, 200)}\n"

                # 添加子评论
                sub_comments = comment.get("subComments", [])
                if sub_comments:
                    for sub in sub_comments[:3]:
                        sub_user = sub.get("user", {})
                        sub_nickname = sub_user.get("nickname", "")
                        sub_content = sub.get("content", "")
                        if sub_content and len(sub_content) > 3:
                            prompt += f"   └─ {sub_nickname}: {truncate_text(sub_content, 100)}\n"

        # 输出其他有价值的评论
        if other_comments:
            prompt += "\n### 其他有价值的评论\n"
            for j, comment in enumerate(other_comments[:8], 1):
                user = comment.get("user", {})
                nickname = user.get("nickname", "未知")
                ip = comment.get("ipLocation", "")
                content = comment.get("content", "")
                note_title = comment.get("note_title", "")

                prompt += f"\n{j}. [{ip}] {nickname}\n"
                prompt += f"   来源笔记: {note_title}\n"
                prompt += f"   内容: {truncate_text(content, 150)}\n"

    prompt += """
## 输出要求

请根据以上小红书笔记的真实内容，结合你的知识补充，生成一份**真实可落地**的旅行攻略。

### 行程规划原则
1. **路线合理**：不走回头路，按地理位置顺序安排景点
2. **时间合理**：
   - 上午：适合观景、徒步、参观
   - 下午：适合休闲、购物、体验活动
   - 傍晚：适合日落、夜景
   - 晚上：适合美食、篝火、星空
3. **交通时间**：考虑景点之间的距离和交通时间
4. **游玩时长**：每个景点的游玩时间要合理

### 输出格式

```json
{
    "overview": {
        "best_season": "最佳旅行季节",
        "recommended_days": 5,
        "budget_estimate": "预算估计（包含交通、住宿、餐饮、门票）",
        "highlights": ["亮点1", "亮点2", "亮点3"],
        "route_summary": "路线概述（如：海拉尔→额尔古纳→恩和→黑山头→满洲里）"
    },
    "itinerary": [
        {
            "day": 1,
            "theme": "当日主题",
            "route": "当日路线（如：海拉尔→额尔古纳，约130km，2小时）",
            "activities": [
                {
                    "time": "09:00-11:00",
                    "spot": "地点名称",
                    "description": "详细描述",
                    "duration": "2小时",
                    "distance_from_prev": "距上一站距离（如：30km，40分钟）",
                    "tips": "实用小贴士",
                    "image": "对应的本地图片路径（如有）"
                }
            ],
            "meals": {
                "lunch": {"name": "午餐推荐", "location": "位置", "price": "价格"},
                "dinner": {"name": "晚餐推荐", "location": "位置", "price": "价格"}
            },
            "accommodation": {"name": "住宿推荐", "type": "类型", "price": "价格范围"}
        }
    ],
    "food_recommendations": [
        {
            "name": "餐厅/美食名称",
            "type": "菜系类型",
            "location": "位置",
            "price_range": "价格范围",
            "must_try": "必点菜品",
            "source": "来源笔记作者",
            "image": "对应的本地图片路径（如有）"
        }
    ],
    "spots": [
        {
            "name": "景点名称",
            "category": "类别",
            "description": "描述",
            "duration": "建议游玩时长",
            "opening_hours": "开放时间",
            "ticket_price": "门票价格",
            "best_time": "最佳游玩时间",
            "tips": "小贴士",
            "image": "对应的本地图片路径（如有）"
        }
    ],
    "transportation": {
        "from_departure": "从出发地到目的地的交通方式",
        "local": ["当地交通方式1", "当地交通方式2"],
        "route_driving": "自驾路线建议",
        "tips": "交通小贴士"
    },
    "tips": [
        "实用贴士1",
        "实用贴士2"
    ],
    "sources": [
        {
            "feed_id": "笔记ID",
            "title": "笔记标题",
            "author": "作者",
            "likes": "点赞数",
            "collected": "收藏数",
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
