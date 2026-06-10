# 小红书驱动的旅行攻略生成器 - 设计文档

## 概述

本项目是一个 Claude Code Skill，基于小红书的真实用户内容，结合 AI 分析能力，为用户生成个性化的 HTML 旅行攻略文档。

### 核心价值

- **数据来源真实**：基于小红书用户的真实旅行分享
- **个性化推荐**：根据用户偏好定制搜索和推荐
- **精美输出**：生成可在线查看的 HTML 攻略文档

### 参考项目

| 项目 | 参考内容 |
|------|----------|
| [travel-planner](https://github.com/ailabs-393/ai-labs-claude-skills/tree/main/dist/skills/travel-planner) | 用户偏好收集流程、行程规划结构 |
| [xiaohongshu-skills](https://github.com/autoclaw-cc/xiaohongshu-skills) | 小红书内容抓取 CLI |
| [fly-ai](https://github.com/geofqiu-hub/fly-ai) | AI 分析能力、Gemini API 集成 |

---

## 架构设计

### 技术选型

**推荐方案：Python 单层架构**

理由：
1. **数据源一致性**：xiaohongshu-skills 是 Python 实现，直接调用 CLI 更自然
2. **参考项目一致性**：travel-planner 也是 Python 实现
3. **简化依赖**：直接调用 Gemini API，无需依赖 fly-ai 的 TypeScript 实现
4. **部署简单**：纯 Python 实现，不需要 Node.js 环境

### 项目结构

```
travel-xhs-skill/
├── SKILL.md                    # Claude Skill 定义文件
├── README.md                   # 项目说明
├── requirements.txt            # Python 依赖
├── scripts/
│   ├── cli.py                  # 统一 CLI 入口
│   ├── xhs_scraper.py          # 小红书内容抓取模块（含图片下载）
│   ├── content_analyzer.py     # AI 内容分析模块
│   ├── itinerary_gen.py        # 行程生成模块
│   ├── guide_writer.py         # 攻略文档生成模块
│   ├── preference_manager.py   # 偏好管理模块
│   └── utils.py                # 工具函数
├── templates/
│   ├── guide_template.html     # 攻略文档 HTML 模板
│   └── itinerary_template.html # 行程 HTML 模板
├── config/
│   └── models.json             # AI 模型配置
├── output/                     # 生成的攻略和图片
│   ├── guides/                 # HTML 攻略文件
│   └── images/                 # 下载的图片
└── tests/
    └── ...                     # 测试文件
```

---

## 核心模块设计

### 1. 偏好管理模块 (preference_manager.py)

#### 多配置文件支持

支持保存多个偏好配置文件，用户可根据不同旅行场景切换。

**文件结构：**

```
~/.claude/travel_xhs/
├── preferences/
│   ├── solo_travel.json      # 独自旅行偏好
│   ├── family_trip.json      # 家庭旅行偏好
│   ├── couple_vacation.json  # 情侣度假偏好
│   └── default.json          # 默认偏好
└── active_preference         # 当前激活的偏好文件名
```

**偏好数据结构：**

```python
preferences = {
    "name": "solo_travel",
    "travel_style": "adventurous",
    "budget_level": "mid-range",
    "accommodation_preference": ["boutique hotels", "Airbnb"],
    "interests": ["culture", "food", "hiking", "photography"],
    "dietary_restrictions": ["vegetarian"],
    "pace_preference": "moderate",
    "travel_companions": "solo",
    "language_skills": ["English", "Chinese"],
    "previous_destinations": ["Tokyo", "Seoul"],
    "bucket_list": [
        {"destination": "Kyoto", "notes": "Cherry blossom season"},
        {"destination": "Bangkok", "notes": "Street food"}
    ]
}
```

**CLI 命令：**

```bash
# 查看所有偏好配置
python scripts/cli.py list-preferences

# 切换偏好配置
python scripts/cli.py switch-preference --name solo_travel

# 创建新偏好配置
python scripts/cli.py create-preference --name business_trip

# 编辑当前偏好
python scripts/cli.py edit-preference

# 显示当前偏好
python scripts/cli.py show-preference
```

### 2. 小红书内容抓取模块 (xhs_scraper.py)

#### 个性化搜索

基于用户偏好生成个性化的搜索关键词。

**搜索关键词生成逻辑：**

```python
def generate_search_keywords(destination: str, preferences: dict) -> list[str]:
    keywords = [f"{destination}旅行攻略"]
    
    # 基于兴趣
    interest_map = {
        "food": [f"{destination}美食推荐", f"{destination}必吃餐厅"],
        "photography": [f"{destination}拍照打卡", f"{destination}出片地点"],
        "culture": [f"{destination}文化体验", f"{destination}历史古迹"],
        "shopping": [f"{destination}购物攻略", f"{destination}买什么"],
        "nature": [f"{destination}自然风光", f"{destination}户外徒步"],
        "nightlife": [f"{destination}夜生活", f"{destination}酒吧推荐"],
    }
    
    for interest in preferences.get("interests", []):
        if interest in interest_map:
            keywords.extend(interest_map[interest])
    
    # 基于预算
    budget = preferences.get("budget_level", "mid-range")
    if budget == "budget":
        keywords.append(f"{destination}穷游攻略")
    elif budget == "luxury":
        keywords.append(f"{destination}高端体验")
    
    # 基于同伴
    companion = preferences.get("travel_companions", "")
    companion_map = {
        "couple": f"{destination}情侣攻略",
        "family": f"{destination}亲子游",
        "solo": f"{destination}独自旅行",
    }
    if companion in companion_map:
        keywords.append(companion_map[companion])
    
    # 基于饮食限制
    if "vegetarian" in preferences.get("dietary_restrictions", []):
        keywords.append(f"{destination}素食餐厅")
    
    return keywords
```

**抓取流程：**

```
用户输入目的地
    ↓
读取当前激活的用户偏好
    ↓
生成个性化搜索关键词
    ↓
调用 xiaohongshu-skills CLI
    ├── search-feeds --keyword "关键词1"
    ├── search-feeds --keyword "关键词2"
    └── ...
    ↓
获取搜索结果列表（含封面图 URL）
    ↓
抓取前 N 篇笔记详情（get-feed-detail）
    ↓
提取关键信息 + 图片列表
    ↓
下载图片到本地（image_downloader）
```

**图片抓取功能：**

xiaohongshu-skills 提供了完整的图片抓取能力：

1. **搜索结果封面图**：`Feed.note_card.cover.url`
2. **笔记详情图片**：`FeedDetail.image_list`（多张图片）
3. **图片下载器**：`scripts/image_downloader.py`（SHA256 缓存）

```python
# 图片数据结构
@dataclass
class DetailImageInfo:
    width: int = 0
    height: int = 0
    url_default: str = ""  # 图片 URL
    url_pre: str = ""      # 预览图 URL
    live_photo: bool = False

# 使用方式
from scripts.image_downloader import ImageDownloader

downloader = ImageDownloader(save_dir="./output/images")
for image in feed_detail.image_list:
    local_path = downloader.download_image(image.url_default)
```

**CLI 命令：**

```bash
# 搜索小红书内容（调试用）
python scripts/cli.py search-xhs \
    --keyword "东京旅行" \
    --limit 10

# 获取笔记详情（含图片）
python scripts/cli.py get-feed-detail \
    --feed-id FEED_ID \
    --xsec-token XSEC_TOKEN
```

### 3. AI 内容分析模块 (content_analyzer.py)

#### Claude AI 分析

直接利用 Claude Code 环境的 AI 能力进行内容分析，无需外部 API。

**分析流程：**

```
抓取的小红书内容
    ↓
Claude AI 分析（当前对话环境）
    ├── 提取景点信息（名称、地址、评分、描述、图片）
    ├── 提取美食推荐（餐厅、菜品、价格、位置）
    ├── 提取交通方式（地铁、公交、打卡点）
    ├── 提取住宿建议（酒店、民宿、区域）
    ├── 提取实用贴士（注意事项、省钱技巧）
    └── 按用户偏好加权排序
    ↓
生成结构化数据
```

**实现方式**：

```python
def format_scraped_data_for_analysis(scraped_data: dict, preferences: dict) -> str:
    """
    将抓取的数据格式化为提示词，供 Claude 分析
    
    Args:
        scraped_data: 从小红书抓取的原始数据
        preferences: 用户偏好配置
    
    Returns:
        str: 格式化后的提示词
    """
    prompt = f"""请分析以下小红书旅行内容，生成结构化的旅行攻略。

目的地：{scraped_data['destination']}
用户偏好：
- 预算：{preferences.get('budget_level', '中档')}
- 兴趣：{', '.join(preferences.get('interests', []))}
- 同伴：{preferences.get('travel_companions', '独自')}
- 节奏：{preferences.get('pace_preference', '适中')}

抓取内容：
"""
    for feed in scraped_data.get('feeds', []):
        prompt += f"\n--- {feed['title']} (作者: {feed['author']}, 点赞: {feed['likes']}) ---\n"
        prompt += feed['content'][:2000] + "\n"  # 限制长度避免超限
    
    prompt += """
请按以下格式输出 JSON：
{
    "overview": {...},
    "itinerary": [...],
    "food_recommendations": [...],
    "spots": [...],
    "transportation": {...},
    "tips": [...]
}
"""
    return prompt
```

**输出数据结构：**

```python
analyzed_data = {
    "destination": "东京",
    "overview": {
        "best_season": "春季（3-5月）",
        "recommended_days": 5,
        "budget_estimate": "8000-15000元",
        "highlights": ["浅草寺", "涩谷十字路口", "新宿"]
    },
    "itinerary": [
        {
            "day": 1,
            "theme": "抵达 & 浅草文化体验",
            "activities": [
                {
                    "time": "上午",
                    "spot": "浅草寺",
                    "description": "...",
                    "duration": "2小时",
                    "tips": "..."
                }
            ]
        }
    ],
    "food_recommendations": [
        {
            "name": "一兰拉面",
            "type": "拉面",
            "location": "涩谷",
            "price_range": "1000-2000日元",
            "must_try": "豚骨拉面",
            "source": "小红书用户@xxx"
        }
    ],
    "spots": [
        {
            "name": "浅草寺",
            "category": "文化古迹",
            "description": "...",
            "duration": "2小时",
            "tips": "..."
        }
    ],
    "transportation": {
        "from_airport": "...",
        "local": ["地铁", "JR", "公交"],
        "tips": "..."
    },
    "tips": [
        "带现金，很多地方不支持刷卡",
        "地铁卡很方便",
        "..."
    ],
    "sources": [
        {
            "feed_id": "xxx",
            "title": "东京5天4晚攻略",
            "author": "旅行达人",
            "likes": 1234,
            "url": "..."
        }
    ]
}
```

### 4. HTML 攻略生成模块 (guide_writer.py)

#### 精美 HTML 模板

生成响应式、美观的 HTML 攻略文档。

**HTML 结构：**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{目的地}旅行攻略</title>
    <style>
        /* 精美样式 */
        :root {
            --primary-color: #FF6B6B;
            --secondary-color: #4ECDC4;
            --background: #f7f7f7;
        }
        
        body {
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            background: var(--background);
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* 渐变背景封面 */
        header {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 60px 20px;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        
        /* 卡片布局 */
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* 响应式网格 */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        
        /* 目录导航 */
        nav {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        
        nav ul {
            list-style: none;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        nav a {
            color: var(--primary-color);
            text-decoration: none;
        }

        /* 图片样式 */
        .card-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 15px;
        }

        .food-card .location,
        .food-card .price,
        .food-card .must-try,
        .spot-card .category,
        .spot-card .duration {
            color: #666;
            font-size: 0.9em;
            margin: 5px 0;
        }

        .source {
            color: #999;
            font-size: 0.8em;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 封面区 -->
        <header>
            <h1>{目的地}旅行攻略</h1>
            <p>基于小红书 {N} 篇热门攻略生成</p>
            <p>生成时间：{date}</p>
        </header>
        
        <!-- 目录导航 -->
        <nav>
            <ul>
                <li><a href="#overview">行程概览</a></li>
                <li><a href="#itinerary">每日行程</a></li>
                <li><a href="#food">美食推荐</a></li>
                <li><a href="#spots">景点打卡</a></li>
                <li><a href="#transport">交通指南</a></li>
                <li><a href="#tips">实用贴士</a></li>
                <li><a href="#sources">数据来源</a></li>
            </ul>
        </nav>
        
        <!-- 行程概览 -->
        <section id="overview" class="card">
            <h2>行程概览</h2>
            <div class="grid">
                <div class="card">
                    <h3>建议天数</h3>
                    <p>{days}天</p>
                </div>
                <div class="card">
                    <h3>预算参考</h3>
                    <p>{budget}</p>
                </div>
                <div class="card">
                    <h3>最佳季节</h3>
                    <p>{season}</p>
                </div>
            </div>
        </section>
        
        <!-- 每日行程 -->
        <section id="itinerary">
            <h2>每日行程</h2>
            <!-- Day 1, Day 2, ... -->
        </section>
        
        <!-- 美食推荐 -->
        <section id="food">
            <h2>美食推荐</h2>
            <div class="grid">
                <!-- 餐厅卡片（含图片） -->
                <div class="card food-card">
                    <img src="{food_image_url}" alt="{food_name}" class="card-image">
                    <h3>{food_name}</h3>
                    <p class="location">📍 {location}</p>
                    <p class="price">💰 {price_range}</p>
                    <p class="must-try">🍽️ 必点：{must_try}</p>
                    <p class="source">来源：小红书 @{author}</p>
                </div>
            </div>
        </section>

        <!-- 景点打卡 -->
        <section id="spots">
            <h2>景点打卡</h2>
            <div class="grid">
                <!-- 景点卡片（含图片） -->
                <div class="card spot-card">
                    <img src="{spot_image_url}" alt="{spot_name}" class="card-image">
                    <h3>{spot_name}</h3>
                    <p class="category">🏷️ {category}</p>
                    <p class="duration">⏱️ 建议时长：{duration}</p>
                    <p class="description">{description}</p>
                    <p class="tips">💡 {tips}</p>
                </div>
            </div>
        </section>
        
        <!-- 交通指南 -->
        <section id="transport" class="card">
            <h2>交通指南</h2>
        </section>
        
        <!-- 实用贴士 -->
        <section id="tips" class="card">
            <h2>实用贴士</h2>
        </section>
        
        <!-- 数据来源 -->
        <footer id="sources" class="card">
            <h2>数据来源</h2>
            <p>本攻略基于以下小红书内容生成：</p>
            <ul>
                <!-- 来源列表 -->
            </ul>
        </footer>
    </div>
</body>
</html>
```

### 5. 在线部署模块

#### GitHub Pages 部署

将生成的 HTML 攻略自动部署到 GitHub Pages。

**部署流程：**

```python
import os
import subprocess
from datetime import datetime

def deploy_to_github_pages(html_content: str, destination: str) -> str:
    """
    将 HTML 攻略部署到 GitHub Pages
    
    Args:
        html_content: HTML 内容
        destination: 目的地名称（用于文件名）
    
    Returns:
        str: 部署后的访问链接
    """
    # 1. 创建部署目录
    deploy_dir = os.path.expanduser("~/.claude/travel_xhs/deploy")
    os.makedirs(deploy_dir, exist_ok=True)
    
    # 2. 生成文件名（目的地+时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{destination}_{timestamp}.html"
    filepath = os.path.join(deploy_dir, filename)
    
    # 3. 保存 HTML 文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # 4. 初始化 Git 仓库（如果不存在）
    if not os.path.exists(os.path.join(deploy_dir, ".git")):
        subprocess.run(["git", "init"], cwd=deploy_dir)
        subprocess.run(["git", "checkout", "-b", "gh-pages"], cwd=deploy_dir)
    
    # 5. 添加并提交
    subprocess.run(["git", "add", "."], cwd=deploy_dir)
    subprocess.run(["git", "commit", "-m", f"Add {destination} guide"], cwd=deploy_dir)
    
    # 6. 推送到 GitHub（需要用户配置远程仓库）
    # 用户需要先执行: git remote add origin <repo-url>
    try:
        subprocess.run(["git", "push", "origin", "gh-pages"], cwd=deploy_dir, check=True)
        # 7. 返回访问链接
        repo_url = subprocess.run(
            ["git", "remote", "get-url", "origin"], 
            cwd=deploy_dir, capture_output=True, text=True
        ).stdout.strip()
        
        # 从 repo URL 提取用户名和仓库名
        # 格式: https://github.com/user/repo.git
        parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
        if len(parts) == 2:
            return f"https://{parts[0]}.github.io/{parts[1]}/{filename}"
    except subprocess.CalledProcessError:
        pass
    
    # 如果推送失败，返回本地文件路径
    return f"file:///{filepath}"
```

**CLI 命令：**

```bash
# 生成攻略（不部署）
python scripts/cli.py generate-guide \
    --destination "东京" \
    --days 5 \
    --budget 10000

# 生成并部署攻略
python scripts/cli.py generate-guide \
    --destination "东京" \
    --days 5 \
    --budget 10000 \
    --deploy

# 仅本地预览
python scripts/cli.py preview-guide \
    --file guide.html
```

---

## 完整工作流

```
用户首次使用
    │
    ▼
┌─────────────────┐
│ 偏好收集流程     │
│ 1. 旅行风格      │
│ 2. 预算档次      │
│ 3. 兴趣爱好      │
│ 4. 饮食限制      │
│ 5. 旅行同伴      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 保存偏好配置     │
│ ~/.claude/...   │
└────────┬────────┘
         │
         ▼
用户输入目的地（如"东京"）
    │
    ▼
┌─────────────────┐
│ 个性化搜索       │
│ 基于偏好生成关键词│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 调用小红书 CLI   │
│ search-feeds    │
│ get-feed-detail │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AI 内容分析      │
│ Claude AI       │
│ 提取结构化信息   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 生成 HTML 攻略   │
│ 精美样式        │
│ 响应式设计      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 部署/分享        │
│ GitHub Pages    │
│ 或本地预览      │
└─────────────────┘
```

---

## SKILL.md 定义

```markdown
---
name: travel-xhs-skill
description: |
  小红书驱动的旅行攻略生成器。基于小红书真实用户内容，结合 AI 分析，
  为用户生成个性化的 HTML 旅行攻略文档。
  当用户需要规划旅行、生成旅行攻略、查找旅行信息时触发。
version: 1.0.0
metadata:
  requires:
    bins:
      - python3
---

# 小红书旅行攻略生成器

你是"旅行攻略助手"。根据用户的目的地和偏好，从小红书抓取相关内容，
生成精美的 HTML 旅行攻略文档。

## 技能边界

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`
- **数据来源**：小红书内容通过 xiaohongshu-skills CLI 获取
- **AI 能力**：使用当前 Claude 环境进行内容分析和生成

## 输入判断

按优先级判断用户意图：

1. **偏好管理**（"设置偏好 / 切换偏好 / 查看偏好"）→ 执行偏好管理流程
2. **生成攻略**（"生成攻略 / 规划旅行 / 去xxx"）→ 执行攻略生成流程
3. **预览攻略**（"预览 / 打开攻略"）→ 打开已生成的 HTML 文件
4. **部署攻略**（"部署 / 发布攻略"）→ 部署到 GitHub Pages

## 工作流

### Step 1: 检查偏好配置
检查是否存在偏好配置，如无则进入偏好收集流程

### Step 2: 选择/切换偏好
显示已有偏好配置，让用户选择或创建新配置

### Step 3: 收集行程信息
- 目的地（必填）
- 天数（可选，默认根据小红书推荐）
- 预算（可选，默认使用偏好中的预算档次）
- 特殊需求（可选）

### Step 4: 个性化搜索
基于偏好和目的地生成搜索关键词

### Step 5: 抓取小红书内容
调用 xiaohongshu-skills CLI 搜索和获取详情

### Step 6: AI 分析内容
使用 Gemini API 分析抓取内容，提取结构化信息

### Step 7: 生成 HTML 攻略
渲染精美 HTML 攻略文档

### Step 8: 部署/预览
推送到 GitHub Pages 或本地预览
```

---

## 依赖项

### Python 依赖

```txt
jinja2>=3.1.0               # HTML 模板渲染
requests>=2.28.0            # HTTP 请求
```

### 外部依赖

- **xiaohongshu-skills**：小红书内容抓取 CLI
  - 本地路径：`E:\Projects\xiaohongshu-skills`
  - 依赖：需要 Python 3.10+、uv 包管理器
  - 使用方式：通过 `python scripts/cli.py` 调用

### 依赖安装

```bash
# 1. 克隆本项目
git clone <repo-url>
cd travel-xhs-skill

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 xiaohongshu-skills（已存在于本地）
cd E:\Projects\xiaohongshu-skills
uv sync
cd ..
```

---

## 测试策略

### 单元测试

- `test_preference_manager.py`：偏好管理功能测试
- `test_xhs_scraper.py`：搜索关键词生成测试
- `test_content_analyzer.py`：内容分析功能测试
- `test_guide_writer.py`：HTML 生成测试

### 集成测试

- `test_workflow.py`：完整工作流测试

---

## 未来扩展

1. **多语言支持**：支持生成英文、日文等多语言攻略
2. **图片生成**：使用 Claude AI 生成攻略配图
3. **社交分享**：支持分享到微信、微博等平台
4. **离线缓存**：缓存已抓取的内容，减少重复请求
5. **攻略模板**：支持自定义攻略模板样式
