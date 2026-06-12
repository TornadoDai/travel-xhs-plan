"""Post-scrape guide generation.

The scraper can stay as-is. This module consumes the scraped JSON shape and
builds a complete HTML page with stable sections, note images, and extracted
comment insights.
"""

from __future__ import annotations

import html
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import get_guides_dir


DESTINATION_SPOTS = {
    "呼伦贝尔": [
        "草原", "海拉尔", "呼伦湖", "恩和", "莫日格勒河", "额尔古纳湿地",
        "白桦林", "黑山头", "室韦", "莫尔道嘎", "满洲里", "套娃广场",
        "边防线", "驯鹿部落",
    ],
}

DESTINATION_FOODS = {
    "呼伦贝尔": ["列巴", "手把肉", "烤羊排", "锅茶", "酸奶", "冰淇淋", "火锅", "羊肉", "牛肉"],
}

TIP_KEYWORDS = ["注意", "建议", "必备", "推荐", "记得", "提前", "不要", "一定要", "需要", "避雷"]
INVALID_TIP_KEYWORDS = ["求推荐", "求攻略", "有没有", "怎么样", "好不好", "点赞", "收藏", "关注", "评论", "回复"]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _esc(value: Any) -> str:
    return html.escape(_text(value), quote=True)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or default).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        value = _text(item)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _relative_image(path: str, html_dir: Path | None = None) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    html_dir = html_dir or get_guides_dir()
    image_path = Path(path)
    if not image_path.is_absolute():
        image_path = (Path(__file__).parent.parent / image_path).resolve()
    try:
        return image_path.relative_to(html_dir).as_posix()
    except ValueError:
        return os.path.relpath(str(image_path), str(html_dir)).replace("\\", "/")


def _note_content(note: dict) -> str:
    return "\n".join(_text(note.get(key)) for key in ("title", "content", "desc", "body"))


def extract_spots_from_notes(notes: list[dict], destination: str) -> list[str]:
    counts: Counter[str] = Counter()
    for note in notes:
        content = _note_content(note)
        for spot in DESTINATION_SPOTS.get(destination, []):
            if spot in content:
                counts[spot] += 1
    return [name for name, _ in counts.most_common(12)]


def extract_foods_from_notes(notes: list[dict], destination: str) -> list[str]:
    counts: Counter[str] = Counter()
    for note in notes:
        content = _note_content(note)
        for food in DESTINATION_FOODS.get(destination, []):
            if food in content:
                counts[food] += 1
    return [name for name, _ in counts.most_common(10)]


def extract_tips_from_notes(notes: list[dict]) -> list[str]:
    tips = []
    for note in notes:
        for line in _note_content(note).replace("。", "。\n").splitlines():
            line = line.strip(" -·\t")
            if len(line) < 8 or len(line) > 120:
                continue
            if not any(keyword in line for keyword in TIP_KEYWORDS):
                continue
            if any(keyword in line for keyword in INVALID_TIP_KEYWORDS):
                continue
            tips.append(line)
    return _unique(tips)[:12]


def _comment_likes(comment: dict) -> int:
    return _int(comment.get("likes", comment.get("likeCount", comment.get("likedCount", 0))))


def flatten_comments(notes: list[dict]) -> list[dict]:
    comments = []
    for note in notes:
        source = _text(note.get("title"))
        for comment in note.get("comments", []) or []:
            content = _text(comment.get("content"))
            if content:
                comments.append({
                    "content": content,
                    "likes": _comment_likes(comment),
                    "user": _text((comment.get("user") or {}).get("nickname")),
                    "ip": _text(comment.get("ipLocation")),
                    "source": source,
                    "kind": "comment",
                })
            for sub in comment.get("subComments", []) or []:
                sub_content = _text(sub.get("content"))
                if sub_content:
                    comments.append({
                        "content": sub_content,
                        "likes": _comment_likes(sub),
                        "user": _text((sub.get("user") or {}).get("nickname")),
                        "ip": _text(sub.get("ipLocation", comment.get("ipLocation", ""))),
                        "source": source,
                        "kind": "reply",
                    })
    comments.sort(key=lambda item: (item["likes"], len(item["content"])), reverse=True)
    return comments


def extract_comments(notes: list[dict], min_likes: int = 0) -> list[dict]:
    useful = []
    for comment in flatten_comments(notes):
        if len(comment["content"]) >= 5 and (comment["likes"] >= min_likes or len(comment["content"]) >= 12):
            useful.append(comment)
    return useful[:40]


def extract_comment_insights(notes: list[dict], destination: str) -> dict[str, list[dict]]:
    categories = {
        "避坑提醒": ["避雷", "别去", "不要", "坑", "贵", "排队", "踩雷", "后悔", "注意", "小心"],
        "推荐玩法": ["推荐", "一定要", "必须", "值得", "好看", "好玩", "绝", "拍照", "日落", "星空"],
        "交通住宿": ["包车", "自驾", "租车", "司机", "路", "车", "住", "酒店", "民宿", "机场", "火车"],
        "吃喝补充": ["吃", "餐", "肉", "火锅", "奶茶", "冰淇淋", "列巴", "羊", "牛", "锅茶"],
    }
    dest_keys = [destination[:2], destination[:3], destination[:4]]
    insights = {name: [] for name in categories}

    for comment in extract_comments(notes):
        content = comment["content"]
        priority = comment["likes"]
        if comment.get("ip") and any(key and key in comment["ip"] for key in dest_keys):
            priority += 8
        for name, keywords in categories.items():
            if any(keyword in content for keyword in keywords):
                insights[name].append({**comment, "priority": priority})
                break

    for name, values in insights.items():
        values.sort(key=lambda item: (item["priority"], len(item["content"])), reverse=True)
        insights[name] = values[:5]
    return insights


def collect_note_gallery(notes: list[dict], html_dir: Path | None = None) -> list[dict]:
    gallery = []
    seen = set()
    for note in notes:
        for image in note.get("images", []) or []:
            src = _relative_image(image, html_dir)
            if not src or src in seen:
                continue
            seen.add(src)
            gallery.append({
                "src": src,
                "title": _text(note.get("title")) or "小红书实拍",
                "author": _text(note.get("author")),
            })
    return gallery


def aggregate_data(notes: list[dict], destination: str) -> dict:
    return {
        "spots": extract_spots_from_notes(notes, destination),
        "foods": extract_foods_from_notes(notes, destination),
        "tips": extract_tips_from_notes(notes),
        "comments": extract_comments(notes),
        "comment_insights": extract_comment_insights(notes, destination),
    }


def normalize_generation_data(notes: list[dict], aggregated: dict, spot_images: dict, destination: str, days: int) -> dict:
    notes = notes or []
    aggregated = aggregated or {}
    spots = _unique(aggregated.get("spots", [])) or extract_spots_from_notes(notes, destination)
    foods = _unique(aggregated.get("foods", [])) or extract_foods_from_notes(notes, destination)
    tips = _unique(aggregated.get("tips", [])) or extract_tips_from_notes(notes)
    comments = extract_comments(notes)
    gallery = collect_note_gallery(notes)
    normalized_spot_images = {spot: _relative_image(path) for spot, path in (spot_images or {}).items() if path}
    sources = [{
        "title": _text(note.get("title")),
        "author": _text(note.get("author")),
        "likes": _text(note.get("likes")),
        "collected": _text(note.get("collected")),
        "url": _text(note.get("url")),
        "image_count": len(note.get("images", []) or []),
        "comment_count": len(note.get("comments", []) or []),
    } for note in notes]
    return {
        "destination": destination,
        "days": days,
        "spots": spots,
        "foods": foods,
        "tips": tips,
        "comments": comments,
        "comment_insights": extract_comment_insights(notes, destination),
        "spot_images": normalized_spot_images,
        "gallery": gallery,
        "sources": sources,
        "stats": {
            "notes": len(notes),
            "spots": len(spots),
            "foods": len(foods),
            "tips": len(tips),
            "comments": len(comments),
            "images": len(gallery) + len(normalized_spot_images),
        },
    }


def _split_evenly(items: list[str], days: int) -> list[list[str]]:
    buckets = [[] for _ in range(max(1, days))]
    for idx, item in enumerate(items):
        buckets[idx % len(buckets)].append(item)
    return buckets


def generate_html(notes: list[dict], aggregated: dict, spot_images: dict, destination: str, days: int = 6) -> str:
    model = normalize_generation_data(notes, aggregated, spot_images, destination, days)
    spots = model["spots"]
    foods = model["foods"]
    tips = model["tips"]
    gallery = model["gallery"]
    sources = model["sources"]
    comments = model["comments"]
    insights = model["comment_insights"]
    spot_images = model["spot_images"]
    stats = model["stats"]

    def empty(text: str) -> str:
        return f'<div class="empty">{_esc(text)}</div>'

    day_buckets = _split_evenly(spots, days)
    time_slots = ["上午", "下午", "傍晚"]
    itinerary_html = ""
    for day in range(1, days + 1):
        activities = ""
        for idx, spot in enumerate(day_buckets[day - 1][:3] if day - 1 < len(day_buckets) else []):
            image = spot_images.get(spot, "")
            image_html = f'<img src="{_esc(image)}" alt="{_esc(spot)}" class="activity-image" loading="lazy">' if image else ""
            activities += f'''
      <div class="activity">
        <span class="time-badge">{time_slots[idx] if idx < len(time_slots) else "机动"}</span>
        <h4>{_esc(spot)}</h4>
        <p>围绕 {_esc(spot)} 安排游览，结合笔记热度和路线节奏预留拍照、休息和转场时间。</p>
        <div class="meta-row"><span>建议游玩 2-3 小时</span><span>提前确认天气、路况和开放状态</span></div>
        {image_html}
      </div>'''
        itinerary_html += f'''
    <div class="day">
      <div class="day-head"><div class="day-num">D{day}</div><div class="day-title">第 {day} 天行程</div></div>
      {activities or empty("这一天暂无明确景点，可作为机动日、返程日或根据天气调整。")}
    </div>'''

    spots_html = "".join(
        f'''<div class="grid-card">{f'<img src="{_esc(spot_images.get(spot, ""))}" alt="{_esc(spot)}" class="card-image" loading="lazy">' if spot_images.get(spot) else ""}<div class="body"><h4>{_esc(spot)}</h4><span class="badge">景点</span><div class="info">{_esc(spot)} 是本次抓取内容中反复出现的目的地线索。</div><div class="info">建议游玩：2-3 小时</div></div></div>'''
        for spot in spots
    ) or empty("暂未从抓取内容中提取到稳定景点。")
    foods_html = "".join(
        f'''<div class="grid-card"><div class="body"><h4>{_esc(food)}</h4><div class="info">类型：当地特色</div><div class="info">位置：{_esc(destination)} 沿线</div><div class="info">建议：结合当天路线就近安排</div></div></div>'''
        for food in foods
    ) or empty("暂未从抓取内容中提取到明确美食。")
    gallery_html = "".join(
        f'''<figure class="photo"><img src="{_esc(item["src"])}" alt="{_esc(item["title"])}" loading="lazy"><figcaption>{_esc(item["title"][:36])}{(" · " + _esc(item["author"])) if item["author"] else ""}</figcaption></figure>'''
        for item in gallery
    ) or empty("本次数据没有可插入的本地实拍图。")
    tips_html = "".join(f"<li>{_esc(tip)}</li>" for tip in tips) or "<li>暂无明确贴士，建议结合天气、交通和个人体力保留机动时间。</li>"

    insight_html = ""
    for category, items in insights.items():
        if not items:
            continue
        evidence = "".join(
            f'''<li><span>{_esc(item["content"])}</span><small>{_esc(item.get("user")) or "用户"} · 赞 {item["likes"]} · {_esc(item.get("source"))}</small></li>'''
            for item in items[:3]
        )
        insight_html += f'''<div class="insight-card"><h4>{_esc(category)}</h4><ul>{evidence}</ul></div>'''
    insight_html = insight_html or empty("评论里暂时没有足够清晰的高价值信息；已保留原始热门评论供人工判断。")
    comments_html = "".join(
        f'''<div class="comment-item"><div class="comment-content">{_esc(comment["content"])}</div><div class="comment-meta">赞 {comment["likes"]} · {_esc(comment.get("user")) or "用户"} · {_esc(comment.get("source"))}</div></div>'''
        for comment in comments[:8]
    ) or empty("暂无可展示评论。")
    sources_html = "".join(
        f'''<li class="source-item"><div><div class="source-title">{_esc(source["title"][:48])}</div><div class="source-meta">作者：{_esc(source["author"])} · 赞 {_esc(source["likes"])} · 图 {source["image_count"]} · 评论 {source["comment_count"]}</div></div>{f'<a href="{_esc(source["url"])}" target="_blank" rel="noopener">查看原文</a>' if source["url"] else ""}</li>'''
        for source in sources
    ) or empty("暂无数据来源。")

    date_text = datetime.now().strftime("%Y年%m月%d日")
    hero_image = gallery[0]["src"] if gallery else ""
    tags_html = "".join(f'<span class="tag">{_esc(spot)}</span>' for spot in spots[:10]) or '<span class="tag">暂无景点标签</span>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{_esc(destination)} · 旅行攻略</title>
<style>
:root {{ --ink:#1f2933; --paper:#f7f5ef; --card:#fffdf8; --accent:#c2410c; --accent2:#0f766e; --muted:#667085; --line:rgba(31,41,51,.12); --radius:8px; --max:1080px; }}
* {{ box-sizing:border-box; }} body {{ margin:0; font-family:"PingFang SC","Microsoft YaHei",Arial,sans-serif; color:var(--ink); background:var(--paper); line-height:1.75; }} a {{ color:var(--accent); text-decoration:none; }}
.wrap {{ max-width:var(--max); margin:0 auto; padding:0 clamp(16px,3vw,32px); }}
.hero {{ min-height:58vh; display:flex; align-items:center; color:white; background:linear-gradient(rgba(0,0,0,.28),rgba(0,0,0,.44)), url("{_esc(hero_image)}") center/cover no-repeat, #334155; }} .hero-inner {{ width:100%; padding:72px 0; }} .kicker {{ font-size:14px; letter-spacing:.12em; opacity:.85; }} h1 {{ font-size:clamp(42px,8vw,86px); line-height:1.05; margin:12px 0; letter-spacing:0; }} .subtitle {{ max-width:720px; font-size:18px; opacity:.92; }} .hero-stats {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:28px; }} .hero-stats span {{ border:1px solid rgba(255,255,255,.38); background:rgba(255,255,255,.12); padding:8px 14px; border-radius:999px; backdrop-filter:blur(8px); }}
.toc {{ position:sticky; top:0; z-index:2; background:rgba(247,245,239,.92); backdrop-filter:blur(12px); border-bottom:1px solid var(--line); }} .toc ul {{ list-style:none; display:flex; gap:8px; overflow:auto; margin:0; padding:14px 0; }} .toc a {{ display:block; white-space:nowrap; color:var(--ink); padding:7px 12px; border-radius:999px; }}
section {{ padding:56px 0 8px; }} .section-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:16px; border-bottom:2px solid var(--ink); padding-bottom:12px; margin-bottom:24px; }} .section-head h2 {{ margin:0; font-size:26px; }} .section-head span,.comment-meta,.source-meta {{ color:var(--muted); font-size:13px; }}
.overview-grid,.grid,.insight-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }} .stat,.grid-card,.day,.transport-card,.tips-card,.comment-item,.insight-card,.empty {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius); box-shadow:0 4px 18px rgba(31,41,51,.05); }} .stat {{ padding:20px; }} .stat .label {{ color:var(--muted); font-size:13px; }} .stat .value {{ font-size:28px; font-weight:700; color:var(--accent); }} .tags {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }} .tag {{ background:#1f2933; color:white; border-radius:999px; padding:7px 12px; font-size:14px; }}
.day {{ padding:24px; margin-bottom:16px; }} .day-head {{ display:flex; align-items:center; gap:14px; margin-bottom:12px; }} .day-num {{ width:46px; height:46px; border-radius:50%; display:grid; place-items:center; background:var(--accent); color:white; font-weight:800; }} .day-title {{ font-size:20px; font-weight:700; }} .activity {{ border-top:1px solid var(--line); padding:18px 0; }} .activity:first-of-type {{ border-top:0; }} .time-badge,.badge {{ display:inline-block; color:var(--accent2); background:#dff4ef; border-radius:999px; padding:4px 10px; font-size:13px; font-weight:700; }} .activity h4,.grid-card h4,.insight-card h4 {{ margin:10px 0 6px; font-size:18px; }} .activity p,.info {{ color:var(--muted); margin:6px 0; }} .meta-row {{ display:flex; flex-wrap:wrap; gap:12px; color:var(--muted); font-size:13px; }} .activity-image,.card-image {{ width:100%; height:230px; object-fit:cover; border-radius:var(--radius); margin-top:14px; }}
.grid-card {{ overflow:hidden; }} .grid-card .card-image {{ border-radius:0; margin:0; height:210px; }} .grid-card .body {{ padding:18px; }} .photo-grid {{ columns:3 240px; column-gap:14px; }} .photo {{ break-inside:avoid; margin:0 0 14px; background:var(--card); border:1px solid var(--line); border-radius:var(--radius); overflow:hidden; }} .photo img {{ width:100%; display:block; }} .photo figcaption {{ padding:10px 12px; color:var(--muted); font-size:13px; }}
.transport-card,.tips-card,.comment-item,.insight-card,.empty {{ padding:18px; }} .transport-item {{ padding:14px 0; border-top:1px solid var(--line); }} .transport-item:first-child {{ border-top:0; padding-top:0; }} .transport-label {{ color:var(--accent); font-weight:700; }} .tips-list {{ margin:0; padding-left:22px; }} .tips-list li,.insight-card li {{ margin:10px 0; }} .insight-card ul {{ margin:0; padding-left:18px; }} .insight-card small {{ display:block; color:var(--muted); margin-top:3px; }} .comment-item {{ margin-bottom:12px; }} .source-list {{ list-style:none; margin:0; padding:0; }} .source-item {{ display:flex; justify-content:space-between; gap:16px; padding:14px 0; border-bottom:1px solid var(--line); }} .source-title {{ font-weight:700; }} .empty {{ color:var(--muted); }} footer {{ margin-top:48px; padding:32px; text-align:center; color:var(--muted); background:var(--card); border-top:1px solid var(--line); }}
@media (max-width:720px) {{ .hero {{ min-height:50vh; }} .source-item {{ display:block; }} .overview-grid {{ grid-template-columns:1fr 1fr; }} }}
</style></head><body>
<header class="hero"><div class="wrap hero-inner"><div class="kicker">小红书抓取内容生成 · {_esc(date_text)}</div><h1>{_esc(destination)}</h1><p class="subtitle">基于 {stats["notes"]} 篇笔记、{stats["images"]} 张图片和 {stats["comments"]} 条评论线索生成，保留完整模块并展示评论证据。</p><div class="hero-stats"><span>{days} 天行程</span><span>{stats["spots"]} 个景点</span><span>{stats["foods"]} 个美食线索</span><span>{stats["images"]} 张图片</span></div></div></header>
<nav class="toc"><div class="wrap"><ul><li><a href="#overview">概览</a></li><li><a href="#itinerary">每日行程</a></li><li><a href="#spots">景点</a></li><li><a href="#gallery">实拍图集</a></li><li><a href="#food">美食</a></li><li><a href="#transport">交通</a></li><li><a href="#tips">贴士</a></li><li><a href="#comments">评论洞察</a></li><li><a href="#sources">来源</a></li></ul></div></nav>
<main class="wrap">
<section id="overview"><div class="section-head"><h2>行程概览</h2><span>所有模块固定输出</span></div><div class="overview-grid"><div class="stat"><div class="label">推荐天数</div><div class="value">{days} 天</div></div><div class="stat"><div class="label">笔记数量</div><div class="value">{stats["notes"]}</div></div><div class="stat"><div class="label">图片数量</div><div class="value">{stats["images"]}</div></div><div class="stat"><div class="label">评论线索</div><div class="value">{stats["comments"]}</div></div></div><div class="tags">{tags_html}</div></section>
<section id="itinerary"><div class="section-head"><h2>每日行程</h2><span>{days} 天</span></div>{itinerary_html}</section>
<section id="spots"><div class="section-head"><h2>景点打卡</h2><span>{len(spots)} 个</span></div><div class="grid">{spots_html}</div></section>
<section id="gallery"><div class="section-head"><h2>笔记实拍图集</h2><span>{len(gallery)} 张</span></div><div class="photo-grid">{gallery_html}</div></section>
<section id="food"><div class="section-head"><h2>美食推荐</h2><span>{len(foods)} 个</span></div><div class="grid">{foods_html}</div></section>
<section id="transport"><div class="section-head"><h2>交通指南</h2><span>通用建议</span></div><div class="transport-card"><div class="transport-item"><div class="transport-label">大交通</div><div>优先确认抵达海拉尔或满洲里等节点，再按行程方向安排包车、自驾或火车转场。</div></div><div class="transport-item"><div class="transport-label">当地移动</div><div>草原、湿地和边境线景点分散，建议包车或自驾，并提前下载离线地图。</div></div><div class="transport-item"><div class="transport-label">节奏提醒</div><div>旺季路上时间容易拉长，每天保留至少 1 个机动时段。</div></div></div></section>
<section id="tips"><div class="section-head"><h2>实用贴士</h2><span>{len(tips)} 条</span></div><div class="tips-card"><ol class="tips-list">{tips_html}</ol></div></section>
<section id="comments"><div class="section-head"><h2>评论洞察</h2><span>提炼 + 原文证据</span></div><div class="insight-grid">{insight_html}</div><h3>热门原评论</h3>{comments_html}</section>
<section id="sources"><div class="section-head"><h2>数据来源</h2><span>{len(sources)} 篇</span></div><ul class="source-list">{sources_html}</ul></section>
</main><footer>由旅行攻略生成流程自动生成 · 数据来源：小红书抓取结果 · {_esc(date_text)}</footer></body></html>'''
