#!/usr/bin/env python3
"""
完整工作流程：搜索 → 聚合 → 生成HTML → 部署

使用模板中的所有模块：
1. overview - 行程概览
2. itinerary - 每日行程
3. food - 美食推荐
4. spots - 景点打卡
5. transport - 交通指南
6. tips - 实用贴士
7. sources - 数据来源
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from loguru import logger
from utils import load_config, get_images_dir
from generation_pipeline import (
    aggregate_data as generate_aggregate_data,
    generate_html as generate_complete_html,
)


# ============================================================
# 1. 搜索模块
# ============================================================

def run_xhs_command(command: str, args: dict) -> dict:
    """运行 xiaohongshu-skills CLI 命令"""
    config = load_config()
    xhs_path = config.get("xhs_skills_path", "")
    if not xhs_path:
        raise Exception("未配置 xhs_skills_path")

    cli_path = os.path.join(xhs_path, "scripts", "cli.py")
    import shutil
    uv_path = shutil.which("uv")
    cmd = [uv_path, "run", "python", cli_path, command] if uv_path else [sys.executable, cli_path, command]

    for key, value in args.items():
        if value is not None:
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          cwd=os.path.join(xhs_path, "scripts"), timeout=300)
    if result.returncode != 0:
        return {}
    output = result.stdout.strip()
    return json.loads(output) if output else {}


def search_feeds(keyword: str, limit: int = 10) -> list:
    """搜索小红书内容"""
    result = run_xhs_command("search-feeds", {"keyword": keyword})
    return result.get("feeds", [])[:limit]


def get_feed_detail(feed_id: str, xsec_token: str) -> dict:
    """获取笔记详情"""
    return run_xhs_command("get-feed-detail", {
        "feed-id": feed_id, "xsec-token": xsec_token,
        "load-all-comments": True, "max-comment-items": 10
    })


# ============================================================
# 2. 图片下载模块
# ============================================================

def download_image(url: str, save_dir: str, filename: str) -> str:
    """下载单张图片"""
    import requests
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, filename)
    if os.path.exists(filepath):
        return filepath
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Referer': 'https://www.xiaohongshu.com/',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            return filepath
    except Exception as e:
        logger.warning(f"下载图片失败: {e}")
    return ""


def download_note_images(note: dict, save_dir: str, max_images: int = 3) -> list:
    """下载笔记中的图片"""
    image_urls = [img.get("urlDefault", "") for img in note.get("imageList", [])[:max_images]]
    downloaded = []
    for i, url in enumerate(image_urls):
        if url:
            filename = f"note_{note.get('noteId', '')}_{i}.webp"
            path = download_image(url, save_dir, filename)
            if path:
                downloaded.append(path)
    return downloaded


def search_spot_image(spot_name: str) -> str:
    """搜索景点代表性图片"""
    import requests
    search_url = "https://image.baidu.com/search/acjson"
    params = {
        "tn": "resultjson_com", "logid": "1234567890", "ipn": "rj",
        "ct": "201326592", "word": spot_name, "queryWord": spot_name,
        "cl": "2", "lm": "-1", "ie": "utf-8", "oe": "utf-8",
        "pn": 0, "rn": 5, "gsm": "1e",
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*', 'Referer': 'https://image.baidu.com/',
    }
    try:
        resp = requests.get(search_url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", []):
                thumb_url = item.get("thumbURL", "")
                if thumb_url:
                    return thumb_url
    except Exception as e:
        logger.warning(f"搜索图片失败 {spot_name}: {e}")
    return ""


def download_spot_image(spot_name: str, save_dir: str) -> str:
    """下载景点代表性图片"""
    import hashlib
    image_url = search_spot_image(spot_name)
    if not image_url:
        return ""
    url_hash = hashlib.sha256(image_url.encode()).hexdigest()[:16]
    filename = f"spot_{url_hash}.jpg"
    return download_image(image_url, save_dir, filename)


# ============================================================
# 3. 数据聚合模块
# ============================================================

DESTINATION_SPOTS = {
    "呼伦贝尔": [
        "莫日格勒河", "额尔古纳湿地", "呼伦湖", "满洲里国门", "套娃广场",
        "白桦林", "黑山头", "恩和", "室韦", "临江", "莫尔道嘎",
        "海拉尔", "草原", "边防线", "驯鹿部落"
    ],
}

DESTINATION_FOODS = {
    "呼伦贝尔": [
        "手把肉", "烤羊排", "火锅", "锅茶", "列巴", "酸奶",
        "羊肉", "牛肉", "饺子", "西餐", "冰淇淋"
    ],
}

INVALID_TIP_KEYWORDS = [
    "求推荐", "求攻略", "有没有", "怎么样", "好不好",
    "多少钱", "几天合适", "什么时候去", "需要准备",
    "点赞", "收藏", "关注", "评论", "回复"
]


def extract_spots_from_notes(notes: list, destination: str) -> list:
    """从笔记中提取景点"""
    predefined_spots = DESTINATION_SPOTS.get(destination, [])
    spot_counts = Counter()
    for note in notes:
        content = note.get("content", "")
        for spot in predefined_spots:
            if spot in content:
                spot_counts[spot] += 1
    return [spot for spot, count in spot_counts.most_common(10)]


def extract_foods_from_notes(notes: list, destination: str) -> list:
    """从笔记中提取美食"""
    predefined_foods = DESTINATION_FOODS.get(destination, [])
    food_counts = Counter()
    for note in notes:
        content = note.get("content", "")
        for food in predefined_foods:
            if food in content:
                food_counts[food] += 1
    return [food for food, count in food_counts.most_common(8)]


def extract_tips_from_notes(notes: list) -> list:
    """从笔记中提取实用贴士（过滤无效内容）"""
    tips = []
    tip_keywords = ["注意", "建议", "必备", "推荐", "记得", "提前", "不要", "一定要", "需要"]
    for note in notes:
        content = note.get("content", "")
        for line in content.split("\n"):
            line = line.strip()
            if not line or len(line) < 10 or len(line) > 100:
                continue
            has_keyword = any(kw in line for kw in tip_keywords)
            if not has_keyword:
                continue
            has_invalid = any(kw in line for kw in INVALID_TIP_KEYWORDS)
            if has_invalid:
                continue
            tips.append(line)
    return list(set(tips))[:10]


def extract_comments(notes: list, min_likes: int = 3) -> list:
    """提取高赞评论"""
    all_comments = []
    for note in notes:
        for comment in note.get("comments", []):
            likes = int(comment.get("likes", "0") or "0")
            content = comment.get("content", "")
            if likes >= min_likes and len(content) > 10:
                all_comments.append({
                    "content": content, "likes": likes,
                    "user": comment.get("user", {}).get("nickname", ""),
                })
    all_comments.sort(key=lambda x: x["likes"], reverse=True)
    return all_comments[:15]


def aggregate_data(notes: list, destination: str) -> dict:
    """聚合数据"""
    return {
        "spots": extract_spots_from_notes(notes, destination),
        "foods": extract_foods_from_notes(notes, destination),
        "tips": extract_tips_from_notes(notes),
        "comments": extract_comments(notes),
    }


# ============================================================
# 4. HTML生成模块（使用模板中的所有模块）
# ============================================================

def generate_html(notes: list, aggregated: dict, spot_images: dict, destination: str, days: int = 6) -> str:
    """生成完整的HTML攻略（包含模板中的所有模块）"""

    spots = aggregated["spots"]
    foods = aggregated["foods"]
    tips = aggregated["tips"]
    comments = aggregated["comments"]

    # ===== 1. 每日行程 =====
    itinerary_html = ""
    for day in range(1, days + 1):
        spots_per_day = max(1, len(spots) // days)
        start_idx = (day - 1) * spots_per_day
        end_idx = start_idx + spots_per_day
        day_spots = spots[start_idx:end_idx]
        if not day_spots:
            day_spots = [spots[-1]] if spots else ["自由活动"]

        activities_html = ""
        time_slots = ["上午", "下午", "晚上"]
        for i, spot in enumerate(day_spots[:3]):
            time = time_slots[i] if i < len(time_slots) else f"时段{i+1}"
            img_path = spot_images.get(spot, "")
            img_html = f'<img src="images/{os.path.basename(img_path)}" alt="{spot}" class="activity-image" loading="lazy">' if img_path else ""
            activities_html += f'''
      <div class="activity">
        <span class="time-badge">{time}</span>
        <h4>{spot}</h4>
        <p>游览{spot}，感受{destination}的独特魅力</p>
        <div class="meta-row">
          <span>⏱ 2小时</span>
          <span>💡 建议提前规划路线</span>
        </div>
        {img_html}
      </div>'''

        itinerary_html += f'''
    <div class="day">
      <div class="day-head">
        <div class="day-num">D{day}</div>
        <div class="day-title">第{day}天行程</div>
      </div>
      {activities_html}
    </div>'''

    # ===== 2. 景点打卡 =====
    spots_html = ""
    for spot in spots:
        img_path = spot_images.get(spot, "")
        img_html = f'<img src="images/{os.path.basename(img_path)}" alt="{spot}" class="card-image" loading="lazy">' if img_path else ""
        spots_html += f'''
    <div class="grid-card">
        {img_html}
        <div class="body">
            <h4>{spot}</h4>
            <span class="badge">景点</span>
            <div class="info" style="margin-top:10px">{spot}是{destination}的著名景点</div>
            <div class="info">⏱ 建议游玩：2小时</div>
        </div>
    </div>'''

    # ===== 3. 美食推荐 =====
    foods_html = ""
    for food in foods:
        foods_html += f'''
    <div class="grid-card">
        <div class="body">
            <h4>{food}</h4>
            <div class="info">🍖 当地特色</div>
            <div class="info">📍 {destination}各地</div>
            <div class="info">💰 人均50-100元</div>
            <div class="info">⭐ 必点：{food}</div>
        </div>
    </div>'''

    # ===== 4. 交通指南 =====
    transport_html = '''
    <div class="transport-card">
      <div class="transport-item">
        <div class="transport-label">✈️ 从哈尔滨出发</div>
        <div>飞机：哈尔滨太平机场 → 海拉尔东山机场（约2小时）</div>
        <div>火车：哈尔滨站 → 海拉尔站（约10小时，夕发朝至）</div>
      </div>
      <div class="transport-item">
        <div class="transport-label">🚌 当地交通</div>
        <div>包车：最推荐的方式，500-800元/天，司机兼导游</div>
        <div>自驾：路况较好，但需注意草原路段</div>
      </div>
      <div class="transport-item">
        <div class="transport-label">💡 交通小贴士</div>
        <div>• 草原信号不好，建议提前下载离线地图</div>
        <div>• 包车师傅可以帮忙安排住宿和餐饮</div>
        <div>• 自由行能力一般的建议包车找领队</div>
      </div>
    </div>'''

    # ===== 5. 实用贴士 =====
    tips_html = ""
    for i, tip in enumerate(tips, 1):
        tips_html += f'<li>{tip}</li>\n'

    # ===== 6. 热门评论 =====
    comments_html = ""
    for comment in comments[:5]:
        comments_html += f'''
    <div class="comment-item">
        <div class="comment-content">{comment["content"]}</div>
        <div class="comment-meta">👍 {comment["likes"]} · {comment["user"]}</div>
    </div>'''

    # ===== 7. 数据来源 =====
    sources_html = ""
    for note in notes[:8]:
        sources_html += f'''
    <li class="source-item">
        <div>
            <div class="title">{note["title"][:40]}</div>
            <div class="meta">作者：{note["author"]} · 👍 {note["likes"]}</div>
        </div>
        <a href="{note.get("url", "#")}" target="_blank" rel="noopener">查看原文</a>
    </li>'''

    # ===== 生成完整HTML =====
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{destination} · 旅行攻略</title>
<style>
:root {{
  --ink: #1a1a2e; --paper: #fafaf9; --accent: #e63946; --accent-light: #ff6b6b;
  --secondary: #457b9d; --secondary-light: #a8dadc; --sand: #f1faee;
  --stone: #6b7280; --stone-light: #9ca3af; --radius: 16px; --radius-sm: 10px;
  --radius-lg: 24px; --space: clamp(16px, 3vw, 32px); --max-w: 1000px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-lg: 0 12px 40px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.06);
  --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; color: var(--ink); background: var(--paper); line-height: 1.75; font-size: 15px; }}
.wrap {{ max-width: var(--max-w); margin: 0 auto; padding: 0 var(--space); }}
.hero {{ padding: clamp(60px, 12vh, 120px) var(--space); text-align: center; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; }}
.hero h1 {{ font-size: clamp(2rem, 6vw, 3.5rem); font-weight: 700; margin-bottom: 12px; }}
.hero .subtitle {{ font-size: 1.1rem; opacity: 0.75; }}
.hero .meta {{ display: flex; justify-content: center; gap: 24px; margin-top: 28px; flex-wrap: wrap; }}
.hero .meta span {{ font-size: 0.85rem; opacity: 0.65; }}
.toc {{ background: white; border-radius: var(--radius); padding: 20px 24px; margin: -24px auto 40px; max-width: var(--max-w); position: relative; z-index: 1; box-shadow: var(--shadow-lg); }}
.toc ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }}
.toc a {{ display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 0.85rem; color: var(--ink); text-decoration: none; border: 1px solid rgba(0,0,0,0.08); transition: all var(--transition); }}
.toc a:hover {{ background: var(--accent); color: white; transform: translateY(-2px); }}
section {{ margin-bottom: 72px; }}
.section-head {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 32px; padding-bottom: 16px; border-bottom: 3px solid var(--ink); }}
.overview-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }}
.stat {{ background: white; border-radius: var(--radius); padding: 28px 24px; text-align: center; border: 1px solid rgba(0,0,0,0.06); transition: all var(--transition); }}
.stat:hover {{ transform: translateY(-4px); box-shadow: var(--shadow-md); }}
.stat .label {{ font-size: 0.72rem; color: var(--stone); text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 8px; font-weight: 600; }}
.stat .value {{ font-family: 'Georgia', serif; font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
.tags {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.tag {{ display: inline-flex; align-items: center; padding: 8px 18px; border-radius: 24px; font-size: 0.85rem; background: var(--ink); color: var(--paper); font-weight: 500; transition: all var(--transition); }}
.tag:hover {{ background: var(--accent); transform: translateY(-2px); }}
.day {{ background: white; border-radius: var(--radius-lg); padding: 32px; margin-bottom: 24px; border: 1px solid rgba(0,0,0,0.06); box-shadow: var(--shadow-sm); position: relative; overflow: hidden; }}
.day::before {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 6px; background: linear-gradient(180deg, var(--accent), var(--accent-light)); }}
.day-head {{ display: flex; align-items: center; gap: 20px; margin-bottom: 28px; }}
.day-num {{ width: 56px; height: 56px; border-radius: 50%; background: linear-gradient(135deg, var(--accent), var(--accent-light)); color: white; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; flex-shrink: 0; }}
.day-title {{ font-size: 1.3rem; font-weight: 700; }}
.activity {{ padding: 20px 0; border-top: 1px solid rgba(0,0,0,0.06); }}
.activity:first-of-type {{ border-top: none; padding-top: 0; }}
.time-badge {{ display: inline-flex; padding: 6px 16px; border-radius: 20px; font-size: 0.78rem; font-weight: 600; background: var(--sand); color: var(--secondary); margin-bottom: 12px; }}
.activity h4 {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; }}
.activity p {{ color: var(--stone); font-size: 0.92rem; margin-bottom: 12px; }}
.activity .meta-row {{ display: flex; gap: 20px; flex-wrap: wrap; font-size: 0.82rem; color: var(--stone); }}
.activity-image {{ width: 100%; max-height: 320px; object-fit: cover; border-radius: var(--radius); margin-top: 16px; box-shadow: var(--shadow-sm); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
.grid-card {{ background: white; border-radius: var(--radius); overflow: hidden; border: 1px solid rgba(0,0,0,0.06); box-shadow: var(--shadow-sm); transition: all var(--transition); }}
.grid-card:hover {{ box-shadow: var(--shadow-lg); transform: translateY(-4px); }}
.grid-card .card-image {{ width: 100%; height: 200px; object-fit: cover; }}
.grid-card .body {{ padding: 20px 22px; }}
.grid-card h4 {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 12px; }}
.grid-card .info {{ font-size: 0.88rem; color: var(--stone); margin: 6px 0; }}
.grid-card .badge {{ display: inline-flex; padding: 5px 14px; border-radius: 16px; font-size: 0.78rem; background: var(--sand); color: var(--secondary); margin-top: 10px; font-weight: 600; }}
.transport-card {{ background: white; border-radius: var(--radius-lg); padding: 32px; box-shadow: var(--shadow-sm); border: 1px solid rgba(0,0,0,0.06); }}
.transport-item {{ padding: 20px 0; border-bottom: 1px solid rgba(0,0,0,0.06); }}
.transport-item:last-child {{ border-bottom: none; padding-bottom: 0; }}
.transport-item:first-child {{ padding-top: 0; }}
.transport-label {{ font-weight: 700; color: var(--accent); font-size: 0.95rem; margin-bottom: 8px; }}
.transport-item div:not(.transport-label) {{ color: var(--stone); font-size: 0.92rem; }}
.tips-list {{ list-style: none; counter-reset: tip; }}
.tips-list li {{ counter-increment: tip; padding: 16px 0; border-bottom: 1px solid rgba(0,0,0,0.04); display: flex; align-items: flex-start; gap: 16px; }}
.tips-list li:last-child {{ border-bottom: none; }}
.tips-list li::before {{ content: counter(tip); display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, var(--accent), var(--accent-light)); color: white; font-size: 0.82rem; font-weight: 700; flex-shrink: 0; }}
.comment-item {{ padding: 16px; background: var(--sand); border-radius: 12px; margin-bottom: 16px; }}
.comment-content {{ font-size: 0.92rem; color: var(--ink); margin-bottom: 10px; line-height: 1.6; }}
.comment-meta {{ font-size: 0.82rem; color: var(--stone); }}
.source-list {{ list-style: none; }}
.source-item {{ padding: 16px 0; border-bottom: 1px solid rgba(0,0,0,0.06); display: flex; justify-content: space-between; align-items: center; gap: 20px; transition: all var(--transition); }}
.source-item:hover {{ background: var(--sand); margin: 0 -16px; padding: 16px; border-radius: var(--radius-sm); }}
.source-item:last-child {{ border-bottom: none; }}
.source-title {{ font-weight: 600; font-size: 0.95rem; color: var(--ink); margin-bottom: 4px; }}
.source-meta {{ font-size: 0.82rem; color: var(--stone); }}
.source-link {{ color: var(--accent); text-decoration: none; font-size: 0.88rem; font-weight: 500; white-space: nowrap; padding: 6px 14px; border-radius: 16px; border: 1px solid var(--accent); transition: all var(--transition); }}
.source-link:hover {{ background: var(--accent); color: white; }}
footer {{ text-align: center; padding: 48px var(--space); color: var(--stone); font-size: 0.85rem; border-top: 1px solid rgba(0,0,0,0.08); margin-top: 40px; background: white; }}
footer strong {{ color: var(--ink); font-weight: 600; }}
footer .footer-meta {{ margin-top: 12px; display: flex; justify-content: center; gap: 24px; flex-wrap: wrap; font-size: 0.78rem; color: var(--stone-light); }}
@media (max-width: 768px) {{
  .hero {{ min-height: 50vh; padding: 60px 16px; }}
  .hero .meta {{ flex-direction: column; gap: 16px; }}
  .toc {{ margin: -24px 16px 32px; padding: 20px; }}
  .toc ul {{ flex-direction: column; }}
  .overview-grid {{ grid-template-columns: 1fr 1fr; }}
  .grid {{ grid-template-columns: 1fr; }}
  .day {{ padding: 24px 20px; }}
  .source-item {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .grid-card, .stat, .day, .toc a, .tag {{ transition: none; }}
  .grid-card:hover, .stat:hover, .day:hover, .toc a:hover, .tag:hover {{ transform: none; }}
}}
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <h1>{destination}</h1>
    <p class="subtitle">基于小红书 {len(notes)} 篇真实攻略生成</p>
    <div class="meta">
      <span>{days} 天行程</span>
      <span>中档预算</span>
      <span>2026年6月11日</span>
    </div>
  </div>
</header>
<nav class="toc wrap">
  <ul>
    <li><a href="#overview">📋 行程概览</a></li>
    <li><a href="#itinerary">🗓️ 每日行程</a></li>
    <li><a href="#spots">📸 景点打卡</a></li>
    <li><a href="#food">🍜 美食推荐</a></li>
    <li><a href="#transport">🚇 交通指南</a></li>
    <li><a href="#tips">💡 实用贴士</a></li>
    <li><a href="#comments">💬 热门评论</a></li>
    <li><a href="#sources">📚 数据来源</a></li>
  </ul>
</nav>
<div class="wrap">
  <section id="overview">
    <h2 class="section-head">📋 行程概览</h2>
    <div class="overview-grid">
      <div class="stat"><div class="label">最佳季节</div><div class="value">6-9月</div></div>
      <div class="stat"><div class="label">推荐天数</div><div class="value">{days} 天</div></div>
      <div class="stat"><div class="label">预算估计</div><div class="value">3000-5000元</div></div>
      <div class="stat"><div class="label">笔记数量</div><div class="value">{len(notes)} 篇</div></div>
    </div>
    <div class="tags">
      <span class="tag">呼伦贝尔大草原</span>
      <span class="tag">莫日格勒河</span>
      <span class="tag">额尔古纳湿地</span>
      <span class="tag">呼伦湖</span>
      <span class="tag">满洲里国门</span>
      <span class="tag">星空篝火</span>
    </div>
  </section>
  <section id="itinerary">
    <h2 class="section-head">🗓️ 每日行程</h2>
    {itinerary_html}
  </section>
  <section id="spots">
    <h2 class="section-head">📸 景点打卡</h2>
    <div class="grid">{spots_html}</div>
  </section>
  <section id="food">
    <h2 class="section-head">🍜 美食推荐</h2>
    <div class="grid">{foods_html}</div>
  </section>
  <section id="transport">
    <h2 class="section-head">🚇 交通指南</h2>
    {transport_html}
  </section>
  <section id="tips">
    <h2 class="section-head">💡 实用贴士</h2>
    <div class="card">
      <ol class="tips-list">{tips_html}</ol>
    </div>
  </section>
  <section id="comments">
    <h2 class="section-head">💬 热门评论</h2>
    <p style="color:var(--stone);margin-bottom:16px;font-size:0.92rem">来自小红书用户的高赞评论</p>
    {comments_html}
  </section>
  <section id="sources">
    <h2 class="section-head">📚 数据来源</h2>
    <p style="color:var(--stone);margin-bottom:20px;font-size:0.92rem">本攻略基于以下小红书笔记生成</p>
    <ul class="source-list">{sources_html}</ul>
  </section>
</div>
<footer>
  <p>由 <strong>小红书旅行攻略生成器</strong> 自动生成</p>
  <div class="footer-meta">
    <span>2026年6月11日</span>
    <span>数据来源：小红书</span>
    <span>{len(notes)} 篇笔记</span>
  </div>
</footer>
</body>
</html>'''

    return html


# ============================================================
# 5. 主流程
# ============================================================

def full_workflow(destination: str, preferences: dict, days: int = 6, max_notes: int = 15):
    """完整工作流程"""
    print(f"\n{'='*50}")
    print(f"开始为 {destination} 生成旅行攻略")
    print(f"{'='*50}\n")

    # 1. 搜索笔记
    print("[1/5] 搜索小红书笔记...")
    keywords = [
        f"{destination}旅行攻略", f"{destination}美食推荐",
        f"{destination}景点打卡", f"{destination}交通攻略",
    ]
    all_feeds = []
    seen_ids = set()
    for keyword in keywords[:4]:
        feeds = search_feeds(keyword, limit=10)
        for feed in feeds:
            feed_id = feed.get("id", "")
            if feed_id and feed_id not in seen_ids:
                seen_ids.add(feed_id)
                all_feeds.append(feed)
    all_feeds.sort(key=lambda x: int(x.get("interactInfo", {}).get("likedCount", "0") or "0"), reverse=True)
    print(f"  找到 {len(all_feeds)} 篇不重复笔记")

    # 2. 获取笔记详情
    print("\n[2/5] 获取笔记详情...")
    notes = []
    images_dir = str(get_images_dir() / destination.replace(" ", "_") / "notes")
    for i, feed in enumerate(all_feeds[:max_notes]):
        feed_id = feed.get("id", "")
        xsec_token = feed.get("xsecToken", "")
        if not feed_id or not xsec_token:
            continue
        detail = get_feed_detail(feed_id, xsec_token)
        if detail and detail.get("note", {}).get("title"):
            note = detail.get("note", {})
            comments = detail.get("comments", [])
            downloaded_images = download_note_images(note, images_dir)
            notes.append({
                "id": feed_id, "title": note.get("title", ""),
                "author": note.get("user", {}).get("nickname", ""),
                "likes": note.get("interactInfo", {}).get("likedCount", "0"),
                "collected": note.get("interactInfo", {}).get("collectedCount", "0"),
                "content": note.get("body", note.get("desc", "")),
                "images": downloaded_images,
                "url": f"https://www.xiaohongshu.com/explore/{feed_id}",
                "comments": comments
            })
            print(f"  [{len(notes)}/{max_notes}] {note.get('title', '')[:30]}")
    print(f"\n  成功获取 {len(notes)} 篇笔记详情")

    # 3. 聚合数据
    print("\n[3/5] 聚合数据...")
    aggregated = generate_aggregate_data(notes, destination)
    print(f"  景点: {len(aggregated['spots'])}")
    print(f"  美食: {len(aggregated['foods'])}")
    print(f"  贴士: {len(aggregated['tips'])}")
    print(f"  评论: {len(aggregated['comments'])}")

    # 4. 下载景点图片
    print("\n[4/5] 下载景点图片...")
    spot_images_dir = str(get_images_dir() / destination.replace(" ", "_") / "spots")
    spot_images = {}
    for spot in aggregated["spots"]:
        img_path = download_spot_image(spot, spot_images_dir)
        if img_path:
            spot_images[spot] = img_path
            print(f"  ✓ {spot}")
        else:
            print(f"  ✗ {spot} (未找到图片)")
    print(f"\n  成功下载 {len(spot_images)}/{len(aggregated['spots'])} 张景点图片")

    # 5. 生成HTML
    print("\n[5/5] 生成HTML攻略...")
    html = generate_complete_html(notes, aggregated, spot_images, destination, days)
    output_dir = Path(__file__).parent.parent / "output" / "guides"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{destination}_guide.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  HTML已生成: {output_path}")

    # 保存数据
    data_path = Path(__file__).parent.parent / "output" / f"{destination}_data.json"
    data_path.parent.mkdir(exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({"destination": destination, "notes_count": len(notes), "notes": notes,
                   "aggregated": aggregated, "spot_images": spot_images}, f, ensure_ascii=False, indent=2)
    print(f"  数据已保存: {data_path}")

    print(f"\n{'='*50}")
    print(f"攻略生成完成！")
    print(f"{'='*50}")
    return str(output_path)


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="完整工作流程")
    parser.add_argument("--destination", required=True, help="目的地")
    parser.add_argument("--days", type=int, default=6, help="旅行天数")
    parser.add_argument("--max-notes", type=int, default=15, help="最大笔记数量")
    args = parser.parse_args()

    preferences_dir = Path(__file__).parent.parent / "config" / "preferences"
    active_preference_file = Path(__file__).parent.parent / "config" / "active_preference"
    preferences = {}
    if active_preference_file.exists():
        preference_name = active_preference_file.read_text(encoding="utf-8").strip()
        preference_file = preferences_dir / f"{preference_name}.json"
        if preference_file.exists():
            with open(preference_file, "r", encoding="utf-8") as f:
                preferences = json.load(f)

    full_workflow(args.destination, preferences, args.days, args.max_notes)


if __name__ == "__main__":
    main()
