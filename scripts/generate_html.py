#!/usr/bin/env python3
"""生成HTML攻略"""

import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# 读取聚合数据
with open('output/呼伦贝尔_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

notes = data['notes']
aggregated = data['aggregated']
spot_images = aggregated.get('spot_images', {})

# 构建景点列表
spots_html = ''
for spot in aggregated['spots'][:10]:
    img_path = spot_images.get(spot, '')
    img_html = f'<img src="images/{os.path.basename(img_path)}" alt="{spot}" class="card-image" loading="lazy">' if img_path else ''
    spots_html += f'''
    <div class="grid-card">
        {img_html}
        <div class="body">
            <h4>{spot}</h4>
            <span class="badge">景点</span>
            <div class="info" style="margin-top:10px">{spot}是呼伦贝尔的著名景点</div>
            <div class="info">⏱ 建议游玩：2小时</div>
        </div>
    </div>
    '''

# 构建美食列表
foods_html = ''
for food in aggregated['foods'][:6]:
    foods_html += f'''
    <div class="grid-card">
        <div class="body">
            <h4>{food}</h4>
            <div class="info">🍖 当地特色</div>
            <div class="info">📍 呼伦贝尔各地</div>
            <div class="info">💰 人均50-100元</div>
            <div class="info">⭐ 必点：{food}</div>
        </div>
    </div>
    '''

# 构建数据来源
sources_html = ''
for note in notes[:5]:
    sources_html += f'''
    <li class="source-item">
        <div>
            <div class="title">{note["title"][:40]}</div>
            <div class="meta">作者：{note["author"]} · 👍 {note["likes"]}</div>
        </div>
        <a href="{note.get("url", "#")}" target="_blank" rel="noopener">查看原文</a>
    </li>
    '''

# 构建贴士
tips_html = ''
for i, tip in enumerate(aggregated['tips'][:8], 1):
    tips_html += f'<li>{tip}</li>\n'

# 生成完整HTML
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>呼伦贝尔 · 旅行攻略</title>
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
    <h1>呼伦贝尔</h1>
    <p class="subtitle">基于小红书 {len(notes)} 篇真实攻略生成 · 从哈尔滨出发</p>
    <div class="meta">
      <span>6 天行程</span>
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
    <li><a href="#sources">数据来源</a></li>
  </ul>
</nav>
<div class="wrap">
  <section id="overview">
    <h2 class="section-head">📋 行程概览</h2>
    <div class="overview-grid">
      <div class="stat"><div class="label">最佳季节</div><div class="value">6-9月</div></div>
      <div class="stat"><div class="label">推荐天数</div><div class="value">6 天</div></div>
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

# 保存HTML
with open('guides/hulunbuir.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('HTML已生成')
print(f'景点: {len(aggregated["spots"][:10])}')
print(f'美食: {len(aggregated["foods"][:6])}')
print(f'贴士: {len(aggregated["tips"][:8])}')
print(f'来源: {len(notes[:5])}')
