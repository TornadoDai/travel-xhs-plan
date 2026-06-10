#!/usr/bin/env python3
"""
完整工作流程：搜索 → 聚合 → 生成HTML → 部署

解决的问题：
1. 所有景点都要有代表性图片
2. HTML模板保留所有模块
3. 实用贴士过滤无效评论
4. 确保数据质量
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

from loguru import logger
from utils import load_config, get_images_dir, save_json


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

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=os.path.join(xhs_path, "scripts"),
        timeout=300  # 增加超时时间到5分钟
    )

    if result.returncode != 0:
        return {}

    output = result.stdout.strip()
    if not output:
        return {}

    return json.loads(output)


def search_feeds(keyword: str, limit: int = 10) -> list:
    """搜索小红书内容"""
    result = run_xhs_command("search-feeds", {"keyword": keyword})
    return result.get("feeds", [])[:limit]


def get_feed_detail(feed_id: str, xsec_token: str) -> dict:
    """获取笔记详情（含评论）"""
    return run_xhs_command("get-feed-detail", {
        "feed-id": feed_id,
        "xsec-token": xsec_token,
        "load-all-comments": True,
        "max-comment-items": 10  # 减少评论数量以提高速度
    })


# ============================================================
# 2. 图片下载模块
# ============================================================

def download_image(url: str, save_dir: str, filename: str) -> str:
    """下载单张图片"""
    import hashlib
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
        "tn": "resultjson_com",
        "logid": "1234567890",
        "ipn": "rj",
        "ct": "201326592",
        "is": "",
        "fp": "result",
        "fr": "",
        "word": spot_name,
        "queryWord": spot_name,
        "cl": "2",
        "lm": "-1",
        "ie": "utf-8",
        "oe": "utf-8",
        "adpicid": "",
        "st": "-1",
        "z": "",
        "ic": "",
        "hd": "",
        "latest": "",
        "copyright": "",
        "s": "",
        "se": "",
        "tab": "",
        "width": "",
        "height": "",
        "face": "0",
        "istype": "2",
        "qc": "",
        "nc": "1",
        "expermode": "",
        "nojc": "",
        "isAsync": "",
        "pn": 0,
        "rn": 5,
        "gsm": "1e",
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://image.baidu.com/',
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

    # 搜索图片
    image_url = search_spot_image(spot_name)
    if not image_url:
        return ""

    # 生成文件名
    url_hash = hashlib.sha256(image_url.encode()).hexdigest()[:16]
    filename = f"spot_{url_hash}.jpg"

    return download_image(image_url, save_dir, filename)


# ============================================================
# 3. 数据聚合模块
# ============================================================

# 预定义的景点列表（按目的地）
DESTINATION_SPOTS = {
    "呼伦贝尔": [
        "莫日格勒河", "额尔古纳湿地", "呼伦湖", "满洲里国门", "套娃广场",
        "白桦林", "黑山头", "恩和", "室韦", "临江", "莫尔道嘎",
        "海拉尔", "草原", "边防线", "驯鹿部落"
    ],
    "东京": [
        "浅草寺", "涩谷十字路口", "新宿", "东京塔", "秋叶原",
        "银座", "皇居", "台场", "上野公园", "明治神宫"
    ],
    "京都": [
        "伏见稻荷大社", "金阁寺", "清水寺", "岚山", "祇园",
        "二条城", "银阁寺", "哲学之道", "嵯峨野", "宇治"
    ]
}

# 预定义的美食列表
DESTINATION_FOODS = {
    "呼伦贝尔": [
        "手把肉", "烤羊排", "火锅", "锅茶", "列巴", "酸奶",
        "羊肉", "牛肉", "饺子", "西餐", "冰淇淋"
    ],
    "东京": [
        "寿司", "拉面", "天妇罗", "烤肉", "甜点", "居酒屋"
    ],
    "京都": [
        "抹茶", "怀石料理", "汤豆腐", "荞麦面", "和果子"
    ]
}

# 无效贴士关键词（用于过滤）
INVALID_TIP_KEYWORDS = [
    "求推荐", "求攻略", "有没有", "怎么样", "好不好",
    "多少钱", "几天合适", "什么时候去", "需要准备",
    "点赞", "收藏", "关注", "评论", "回复"
]


def extract_spots_from_notes(notes: list, destination: str) -> list:
    """从笔记中提取景点"""
    # 获取预定义的景点列表
    predefined_spots = DESTINATION_SPOTS.get(destination, [])

    # 统计景点出现次数
    spot_counts = Counter()

    for note in notes:
        content = note.get("content", "")
        for spot in predefined_spots:
            if spot in content:
                spot_counts[spot] += 1

    # 按出现次数排序，返回前10个
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

            # 检查是否包含贴士关键词
            has_keyword = any(kw in line for kw in tip_keywords)
            if not has_keyword:
                continue

            # 过滤无效内容
            has_invalid = any(kw in line for kw in INVALID_TIP_KEYWORDS)
            if has_invalid:
                continue

            # 过滤评论相关内容
            if any(kw in line for kw in ["点赞", "收藏", "关注", "评论"]):
                continue

            tips.append(line)

    # 去重并返回前10条
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
                    "content": content,
                    "likes": likes,
                    "user": comment.get("user", {}).get("nickname", ""),
                    "ip_location": comment.get("ipLocation", "")
                })

    # 按点赞数排序
    all_comments.sort(key=lambda x: x["likes"], reverse=True)
    return all_comments[:15]


def aggregate_data(notes: list, destination: str) -> dict:
    """聚合数据"""
    # 提取景点
    spots = extract_spots_from_notes(notes, destination)

    # 提取美食
    foods = extract_foods_from_notes(notes, destination)

    # 提取贴士（过滤无效内容）
    tips = extract_tips_from_notes(notes)

    # 提取高赞评论
    comments = extract_comments(notes)

    return {
        "spots": spots,
        "foods": foods,
        "tips": tips,
        "comments": comments
    }


# ============================================================
# 4. HTML生成模块
# ============================================================

def generate_html(notes: list, aggregated: dict, spot_images: dict, destination: str, days: int = 6) -> str:
    """生成完整的HTML攻略"""

    spots = aggregated["spots"]
    foods = aggregated["foods"]
    tips = aggregated["tips"]
    comments = aggregated["comments"]

    # 构建景点HTML
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
    </div>
    '''

    # 构建美食HTML
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
    </div>
    '''

    # 构建贴士HTML
    tips_html = ""
    for i, tip in enumerate(tips, 1):
        tips_html += f'<li>{tip}</li>\n'

    # 构建评论HTML（作为补充信息）
    comments_html = ""
    for comment in comments[:5]:
        comments_html += f'''
    <div class="comment-item">
        <div class="comment-content">{comment["content"]}</div>
        <div class="comment-meta">👍 {comment["likes"]} · {comment["user"]}</div>
    </div>
    '''

    # 构建数据来源HTML
    sources_html = ""
    for note in notes[:8]:
        sources_html += f'''
    <li class="source-item">
        <div>
            <div class="title">{note["title"][:40]}</div>
            <div class="meta">作者：{note["author"]} · 👍 {note["likes"]}</div>
        </div>
        <a href="{note.get("url", "#")}" target="_blank" rel="noopener">查看原文</a>
    </li>
    '''

    # 生成完整HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{destination} · 旅行攻略</title>
<style>
:root {{
  --ink: #1a1a2e;
  --paper: #fafaf9;
  --accent: #e63946;
  --secondary: #457b9d;
  --sand: #f1faee;
  --stone: #6b7280;
  --radius: 12px;
  --space: clamp(16px, 3vw, 32px);
  --max-w: 960px;
}}
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; color: var(--ink); background: var(--paper); line-height: 1.75; font-size: 15px; }}
.wrap {{ max-width: var(--max-w); margin: 0 auto; padding: 0 var(--space); }}
.hero {{ padding: clamp(60px, 12vh, 120px) var(--space); text-align: center; background: var(--ink); color: var(--paper); }}
.hero h1 {{ font-size: clamp(2rem, 6vw, 3.5rem); font-weight: 700; margin-bottom: 12px; }}
.hero .subtitle {{ font-size: 1.1rem; opacity: 0.75; }}
.hero .meta {{ display: flex; justify-content: center; gap: 24px; margin-top: 28px; flex-wrap: wrap; }}
.hero .meta span {{ font-size: 0.85rem; opacity: 0.65; }}
.toc {{ background: white; border-radius: var(--radius); padding: 20px 24px; margin: -24px auto 40px; max-width: var(--max-w); position: relative; z-index: 1; box-shadow: 0 4px 24px rgba(0,0,0,0.06); }}
.toc ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }}
.toc a {{ display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 0.85rem; color: var(--ink); text-decoration: none; border: 1px solid rgba(0,0,0,0.08); }}
.toc a:hover {{ background: var(--accent); color: white; }}
section {{ margin-bottom: 56px; }}
.section-head {{ font-size: 1.35rem; font-weight: 700; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 2px solid var(--ink); }}
.overview-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }}
.stat {{ background: var(--sand); border-radius: var(--radius); padding: 20px; text-align: center; }}
.stat .label {{ font-size: 0.78rem; color: var(--stone); margin-bottom: 6px; }}
.stat .value {{ font-size: 1.25rem; font-weight: 700; color: var(--accent); }}
.tags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
.tag {{ display: inline-block; padding: 5px 14px; border-radius: 20px; font-size: 0.8rem; background: var(--ink); color: var(--paper); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
.grid-card {{ background: white; border-radius: var(--radius); overflow: hidden; border: 1px solid rgba(0,0,0,0.05); }}
.grid-card .card-image {{ width: 100%; height: 200px; object-fit: cover; }}
.grid-card .body {{ padding: 16px 18px; }}
.grid-card h4 {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; }}
.grid-card .info {{ font-size: 0.85rem; color: var(--stone); margin: 4px 0; }}
.grid-card .badge {{ display: inline-block; padding: 3px 10px; border-radius: 10px; font-size: 0.75rem; background: var(--sand); color: var(--secondary); margin-top: 8px; }}
.source-list {{ list-style: none; }}
.source-item {{ padding: 12px 0; border-bottom: 1px solid rgba(0,0,0,0.04); display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
.source-item .title {{ font-weight: 600; font-size: 0.95rem; }}
.source-item .meta {{ font-size: 0.8rem; color: var(--stone); margin-top: 2px; }}
.source-item a {{ color: var(--accent); text-decoration: none; font-size: 0.85rem; }}
.tips-list {{ list-style: none; counter-reset: tip; }}
.tips-list li {{ counter-increment: tip; padding: 14px 0; border-bottom: 1px solid rgba(0,0,0,0.04); display: flex; align-items: flex-start; gap: 14px; }}
.tips-list li::before {{ content: counter(tip); display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: white; font-size: 0.78rem; font-weight: 700; flex-shrink: 0; }}
.comment-item {{ padding: 12px; background: var(--sand); border-radius: 8px; margin-bottom: 12px; }}
.comment-content {{ font-size: 0.9rem; color: var(--ink); margin-bottom: 8px; }}
.comment-meta {{ font-size: 0.8rem; color: var(--stone); }}
footer {{ text-align: center; padding: 40px var(--space); color: var(--stone); font-size: 0.82rem; border-top: 1px solid rgba(0,0,0,0.06); margin-top: 20px; }}
@media (max-width: 640px) {{
  .hero {{ padding: 48px 16px; }}
  .hero .meta {{ flex-direction: column; gap: 8px; }}
  .toc ul {{ flex-direction: column; }}
  .grid {{ grid-template-columns: 1fr; }}
  .source-item {{ flex-direction: column; align-items: flex-start; gap: 6px; }}
}}
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <h1>{destination}</h1>
    <p class="subtitle">基于小红书 {len(notes)} 篇真实攻略生成 · 从哈尔滨出发</p>
    <div class="meta">
      <span>{days} 天行程</span>
      <span>中档预算</span>
      <span>2026年6月11日</span>
    </div>
  </div>
</header>
<nav class="toc wrap">
  <ul>
    <li><a href="#overview">行程概览</a></li>
    <li><a href="#spots">景点打卡</a></li>
    <li><a href="#food">美食推荐</a></li>
    <li><a href="#tips">实用贴士</a></li>
    <li><a href="#comments">热门评论</a></li>
    <li><a href="#sources">数据来源</a></li>
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
  <section id="spots">
    <h2 class="section-head">📸 景点打卡</h2>
    <div class="grid">
      {spots_html}
    </div>
  </section>
  <section id="food">
    <h2 class="section-head">🍜 美食推荐</h2>
    <div class="grid">
      {foods_html}
    </div>
  </section>
  <section id="tips">
    <h2 class="section-head">💡 实用贴士</h2>
    <div class="card">
      <ol class="tips-list">
        {tips_html}
      </ol>
    </div>
  </section>
  <section id="comments">
    <h2 class="section-head">💬 热门评论</h2>
    <p style="color:var(--stone);margin-bottom:16px;font-size:0.9rem">来自小红书用户的高赞评论</p>
    {comments_html}
  </section>
  <section id="sources">
    <h2 class="section-head">📚 数据来源</h2>
    <p style="color:var(--stone);margin-bottom:16px;font-size:0.9rem">本攻略基于以下小红书笔记生成</p>
    <ul class="source-list">
      {sources_html}
    </ul>
  </section>
</div>
<footer>
  <p>由 <strong>小红书旅行攻略生成器</strong> 自动生成 · 2026年6月11日</p>
  <p style="margin-top:8px">出发地：哈尔滨 · 旅行风格：休闲 · 预算：中档 · 兴趣：美食、文化、自然</p>
</footer>
</body>
</html>'''

    return html


# ============================================================
# 5. 主流程
# ============================================================

def full_workflow(destination: str, preferences: dict, days: int = 6, max_notes: int = 15):
    """
    完整工作流程

    Args:
        destination: 目的地
        preferences: 用户偏好
        days: 旅行天数
        max_notes: 最大笔记数量
    """
    print(f"\n{'='*50}")
    print(f"开始为 {destination} 生成旅行攻略")
    print(f"{'='*50}\n")

    # 1. 搜索笔记
    print("[1/5] 搜索小红书笔记...")
    keywords = [
        f"{destination}旅行攻略",
        f"{destination}美食推荐",
        f"{destination}景点打卡",
        f"{destination}交通攻略",
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

    # 按点赞数排序
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

            # 下载笔记图片
            downloaded_images = download_note_images(note, images_dir)

            note_summary = {
                "id": feed_id,
                "title": note.get("title", ""),
                "author": note.get("user", {}).get("nickname", ""),
                "likes": note.get("interactInfo", {}).get("likedCount", "0"),
                "collected": note.get("interactInfo", {}).get("collectedCount", "0"),
                "content": note.get("body", note.get("desc", "")),
                "images": downloaded_images,
                "url": f"https://www.xiaohongshu.com/explore/{feed_id}",
                "comments": comments
            }

            notes.append(note_summary)
            print(f"  [{len(notes)}/{max_notes}] {note.get('title', '')[:30]}")

    print(f"\n  成功获取 {len(notes)} 篇笔记详情")

    # 3. 聚合数据
    print("\n[3/5] 聚合数据...")
    aggregated = aggregate_data(notes, destination)
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
    html = generate_html(notes, aggregated, spot_images, destination, days)

    # 保存HTML
    output_dir = Path(__file__).parent.parent / "guides"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{destination.lower()}.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  HTML已生成: {output_path}")

    # 保存数据
    data_path = Path(__file__).parent.parent / "output" / f"{destination}_data.json"
    data_path.parent.mkdir(exist_ok=True)

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({
            "destination": destination,
            "notes_count": len(notes),
            "notes": notes,
            "aggregated": aggregated,
            "spot_images": spot_images
        }, f, ensure_ascii=False, indent=2)

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

    # 加载偏好
    preferences_dir = Path(__file__).parent.parent / "config" / "preferences"
    active_preference_file = Path(__file__).parent.parent / "config" / "active_preference"

    preferences = {}
    if active_preference_file.exists():
        preference_name = active_preference_file.read_text(encoding="utf-8").strip()
        preference_file = preferences_dir / f"{preference_name}.json"
        if preference_file.exists():
            with open(preference_file, "r", encoding="utf-8") as f:
                preferences = json.load(f)

    # 执行完整流程
    full_workflow(args.destination, preferences, args.days, args.max_notes)


if __name__ == "__main__":
    main()
