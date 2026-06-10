# 小红书旅行攻略生成器 - 实现计划

## 概述

基于设计文档 `2026-06-10-travel-xhs-skill-design.md`，分阶段实现小红书驱动的旅行攻略生成器。

---

## 用户需要提供的信息

在开始实现前，请准备以下信息：

### 必需信息

| 信息 | 说明 | 获取方式 |
|------|------|----------|
| **xiaohongshu-skills 路径** | 小红书抓取工具的本地路径 | 已提供：`E:\Projects\xiaohongshu-skills` |

### 可选信息（部署时需要）

| 信息 | 说明 | 获取方式 |
|------|------|----------|
| **GitHub 仓库地址** | 用于部署攻略的 GitHub Pages 仓库 | 在 GitHub 创建新仓库 |
| **GitHub 用户名** | 用于生成访问链接 | GitHub 账号设置 |

> **注意**：AI 分析功能直接使用当前 Claude Code 环境的能力，无需额外的 API Key。

---

## 实现阶段

### 阶段 1：项目初始化

**目标**：创建项目基础结构

**步骤**：

1. 创建项目目录结构
2. 创建 `requirements.txt`
3. 创建 `README.md`
4. 创建 `SKILL.md`
5. 初始化 Git 仓库

**输出文件**：

```
travel-xhs-skill/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/
├── templates/
├── config/
└── tests/
```

---

### 阶段 2：偏好管理模块

**目标**：实现用户偏好收集、保存、切换功能

**步骤**：

1. 创建 `scripts/preference_manager.py`
   - 实现 `list_preferences()`：列出所有偏好配置
   - 实现 `create_preference(name)`：创建新偏好配置
   - 实现 `switch_preference(name)`：切换偏好配置
   - 实现 `get_current_preference()`：获取当前偏好
   - 实现 `save_preference(data)`：保存偏好数据
   - 实现 `edit_preference(updates)`：编辑当前偏好

2. 创建 `scripts/cli.py`
   - 实现 CLI 入口
   - 添加偏好管理相关命令

3. 创建偏好收集交互流程
   - 旅行风格
   - 预算档次
   - 兴趣爱好
   - 饮食限制
   - 旅行同伴

**输出文件**：

```
scripts/
├── cli.py
└── preference_manager.py
```

**测试**：

```bash
# 测试偏好管理
python scripts/cli.py list-preferences
python scripts/cli.py create-preference --name test
python scripts/cli.py switch-preference --name test
python scripts/cli.py show-preference
```

---

### 阶段 3：小红书内容抓取模块

**目标**：实现基于用户偏好的个性化搜索、内容抓取和图片下载

**步骤**：

1. 创建 `scripts/xhs_scraper.py`
   - 实现 `generate_search_keywords(destination, preferences)`：生成个性化搜索关键词
   - 实现 `search_xhs(keywords, limit)`：调用小红书搜索
   - 实现 `get_feed_details(feed_ids)`：获取笔记详情
   - 实现 `extract_info(feeds)`：提取关键信息
   - 实现 `download_images(feed_details, save_dir)`：下载笔记图片

2. 集成 xiaohongshu-skills CLI
   - 确定 CLI 调用方式
   - 处理 JSON 输出
   - 调用 `image_downloader.py` 下载图片

3. 创建数据缓存机制
   - 避免重复抓取
   - 本地存储抓取结果
   - 图片 SHA256 缓存（避免重复下载）

**图片抓取逻辑**：

```python
from xiaohongshu_skills.scripts.image_downloader import ImageDownloader

def download_feed_images(feed_details: list, save_dir: str) -> dict:
    """
    下载笔记中的图片

    Args:
        feed_details: 笔记详情列表
        save_dir: 图片保存目录

    Returns:
        dict: {feed_id: [local_image_paths]}
    """
    downloader = ImageDownloader(save_dir)
    result = {}

    for feed in feed_details:
        feed_id = feed.note_id
        image_paths = []

        # 下载笔记详情图片
        for img in feed.image_list:
            if img.url_default:
                try:
                    local_path = downloader.download_image(img.url_default)
                    image_paths.append(local_path)
                except Exception as e:
                    logger.warning(f"下载图片失败: {e}")

        result[feed_id] = image_paths

    return result
```

**输出文件**：

```
scripts/
└── xhs_scraper.py
output/
└── images/  # 下载的图片
```

**测试**：

```bash
# 测试搜索关键词生成
python scripts/cli.py search-xhs --keyword "东京" --limit 5

# 测试图片下载
python scripts/cli.py download-images --feed-id FEED_ID
```

**依赖**：

- 用户需要提供 xiaohongshu-skills 的本地路径：`E:\Projects\xiaohongshu-skills`
- 需要先安装 xiaohongshu-skills

---

### 阶段 4：AI 内容分析模块

**目标**：使用 Claude AI 分析抓取内容，提取结构化信息

**步骤**：

1. 创建 `scripts/content_analyzer.py`
   - 实现 `format_scraped_data_for_analysis(scraped_data, preferences)`：格式化数据为提示词
   - 实现 `parse_analysis_result(ai_response)`：解析 AI 返回的 JSON
   - 实现 `validate_analysis_result(result)`：验证分析结果格式

2. 创建 `scripts/utils.py`
   - 实现通用工具函数
   - JSON 处理
   - 错误处理

3. 创建提示词模板
   - 内容分析提示词（包含用户偏好）
   - 信息提取提示词

**输出文件**：

```
scripts/
├── content_analyzer.py
└── utils.py
```

**测试**：

```bash
# 测试内容分析（Claude 会自动处理）
python scripts/cli.py analyze --destination "东京"
```

**依赖**：

- 无外部 API 依赖，使用当前 Claude 环境

---

### 阶段 5：HTML 攻略生成模块

**目标**：生成精美的 HTML 攻略文档

**步骤**：

1. 创建 `templates/guide_template.html`
   - 响应式布局
   - 精美样式
   - 各 section 模板

2. 创建 `scripts/guide_writer.py`
   - 实现 `render_template(data)`：渲染 HTML 模板
   - 实现 `generate_overview(data)`：生成行程概览
   - 实现 `generate_itinerary(data)`：生成每日行程
   - 实现 `generate_food_section(data)`：生成美食推荐
   - 实现 `generate_spots_section(data)`：生成景点打卡
   - 实现 `generate_transport_section(data)`：生成交通指南
   - 实现 `generate_tips_section(data)`：生成实用贴士
   - 实现 `generate_sources_section(data)`：生成数据来源

3. 创建 `scripts/itinerary_gen.py`
   - 实现 `generate_itinerary(data, days)`：生成行程安排
   - 实现 `optimize_route(spots)`：优化路线

**输出文件**：

```
scripts/
├── guide_writer.py
└── itinerary_gen.py
templates/
└── guide_template.html
```

**测试**：

```bash
# 测试 HTML 生成
python scripts/cli.py generate-guide --destination "东京" --preview
```

---

### 阶段 6：部署模块

**目标**：实现 GitHub Pages 部署功能

**步骤**：

1. 创建 `scripts/deployer.py`
   - 实现 `init_deploy_dir()`：初始化部署目录
   - 实现 `deploy_to_github(html_content, filename)`：部署到 GitHub Pages
   - 实现 `get_deploy_url(filename)`：获取访问链接

2. 创建部署配置
   - 支持配置 GitHub 仓库地址
   - 支持配置分支名称

3. 创建本地预览功能
   - 实现 `preview_local(html_content)`：本地预览

**输出文件**：

```
scripts/
└── deployer.py
```

**测试**：

```bash
# 测试本地预览
python scripts/cli.py preview-guide --file guide.html

# 测试部署（需要提供 GitHub 仓库信息）
python scripts/cli.py deploy-guide --file guide.html
```

**依赖**：

- 用户需要提供 GitHub 仓库地址
- 用户需要配置 Git 凭据

---

### 阶段 7：完整工作流集成

**目标**：将所有模块集成为完整工作流

**步骤**：

1. 更新 `scripts/cli.py`
   - 实现 `generate-guide` 命令
   - 集成所有模块

2. 更新 `SKILL.md`
   - 完善工作流定义
   - 添加使用示例

3. 创建完整测试
   - 单元测试
   - 集成测试

**输出文件**：

```
scripts/
└── cli.py（更新）
SKILL.md（更新）
tests/
└── test_workflow.py
```

**测试**：

```bash
# 完整工作流测试
python scripts/cli.py generate-guide \
    --destination "东京" \
    --days 5 \
    --budget 10000
```

---

### 阶段 8：文档与优化

**目标**：完善文档，优化用户体验

**步骤**：

1. 更新 `README.md`
   - 安装说明
   - 使用说明
   - 配置说明

2. 创建使用示例
   - 示例偏好配置
   - 示例攻略输出

3. 性能优化
   - 缓存机制
   - 并发抓取

4. 错误处理完善
   - 网络错误
   - API 错误
   - 依赖错误

**输出文件**：

```
README.md（更新）
docs/
└── examples/
    ├── sample_preference.json
    └── sample_guide.html
```

---

## 实现顺序建议

```
阶段 1 → 阶段 2 → 阶段 3 → 阶段 4 → 阶段 5 → 阶段 6 → 阶段 7 → 阶段 8
   │         │         │         │         │         │         │         │
   └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
                            可以并行实现的阶段
```

**建议实现顺序**：

1. **阶段 1**：项目初始化（必须首先完成）
2. **阶段 2**：偏好管理模块（独立模块）
3. **阶段 3**：小红书内容抓取模块（独立模块）
4. **阶段 4**：AI 内容分析模块（依赖阶段 3）
5. **阶段 5**：HTML 攻略生成模块（依赖阶段 4）
6. **阶段 6**：部署模块（独立模块，可与阶段 5 并行）
7. **阶段 7**：完整工作流集成（依赖所有模块）
8. **阶段 8**：文档与优化（最后完成）

---

## 用户信息收集点

在实现过程中，需要向用户收集以下信息：

### 阶段 2（偏好管理）

- 确认偏好字段是否完整
- 确认偏好收集的交互方式

### 阶段 3（小红书抓取）

- 确认 xiaohongshu-skills 的安装路径
- 确认搜索关键词生成逻辑

### 阶段 4（AI 分析）

- 确认分析输出格式（使用当前 Claude 环境，无需 API Key）

### 阶段 5（HTML 生成）

- 确认 HTML 样式偏好
- 确认攻略内容结构

### 阶段 6（部署）

- 提供 GitHub 仓库地址
- 确认部署配置

### 阶段 7（集成）

- 确认 CLI 命令设计
- 确认工作流步骤

---

## 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| xiaohongshu-skills 接口变更 | 抓取功能失效 | 封装调用层，便于适配 |
| 小红书内容质量参差 | 攻略质量不稳定 | 多源对比，加权排序 |
| GitHub Pages 部署失败 | 无法在线查看 | 提供本地预览备选方案 |

---

## 成功标准

1. ✅ 用户可以创建和管理多个偏好配置
2. ✅ 用户可以输入目的地生成个性化攻略
3. ✅ 攻略内容基于小红书真实用户分享
4. ✅ 生成的 HTML 攻略样式精美、响应式
5. ✅ 攻略可以部署到 GitHub Pages 在线查看
6. ✅ CLI 命令简洁易用
