# 小红书旅行攻略生成器

基于小红书真实用户内容，结合 AI 分析能力，为用户生成个性化的 HTML 旅行攻略文档。

## 功能特点

- 🎯 **个性化推荐**：根据用户偏好定制搜索和推荐
- 📱 **真实数据源**：基于小红书用户的真实旅行分享
- 🎨 **精美输出**：生成可在线查看的 HTML 攻略文档
- 🖼️ **图片抓取**：自动下载小红书笔记中的图片
- 🚀 **一键部署**：支持 GitHub Pages 在线查看

## 安装

### 前置要求

- Python 3.9+
- [xiaohongshu-skills](https://github.com/autoclaw-cc/xiaohongshu-skills)

### 安装步骤

```bash
# 克隆项目
git clone https://github.com/TornadoDai/travel-xhs-plan.git
cd travel-xhs-plan

# 安装依赖
pip install -r requirements.txt

# 配置 xiaohongshu-skills 路径
# 编辑 config/settings.json，设置 xhs_skills_path
```

## 使用方法

### 1. 管理偏好配置

```bash
# 查看所有偏好配置
python scripts/cli.py list-preferences

# 创建新偏好配置
python scripts/cli.py create-preference --name my_travel

# 切换偏好配置
python scripts/cli.py switch-preference --name my_travel

# 显示当前偏好
python scripts/cli.py show-preference

# 编辑当前偏好
python scripts/cli.py edit-preference
```

### 2. 生成旅行攻略

```bash
# 生成攻略（完整流程）
python scripts/cli.py generate-guide --destination "东京" --days 5

# 仅搜索小红书内容
python scripts/cli.py search-xhs --keyword "东京旅行" --limit 10

# 本地预览攻略
python scripts/cli.py preview-guide --file output/guides/tokyo_guide.html

# 部署到 GitHub Pages
python scripts/cli.py deploy-guide --file output/guides/tokyo_guide.html
```

## 项目结构

```
travel-xhs-skill/
├── SKILL.md                    # Claude Skill 定义文件
├── README.md                   # 项目说明
├── requirements.txt            # Python 依赖
├── scripts/
│   ├── cli.py                  # 统一 CLI 入口
│   ├── xhs_scraper.py          # 小红书内容抓取模块
│   ├── content_analyzer.py     # AI 内容分析模块
│   ├── itinerary_gen.py        # 行程生成模块
│   ├── guide_writer.py         # 攻略文档生成模块
│   ├── preference_manager.py   # 偏好管理模块
│   ├── deployer.py             # 部署模块
│   └── utils.py                # 工具函数
├── templates/
│   └── guide_template.html     # 攻略文档 HTML 模板
├── config/
│   └── settings.json           # 配置文件
├── output/
│   ├── guides/                 # 生成的 HTML 攻略
│   └── images/                 # 下载的图片
└── tests/
    └── ...                     # 测试文件
```

## 配置说明

### settings.json

```json
{
  "xhs_skills_path": "E:\\Projects\\xiaohongshu-skills",
  "github_repo": "",
  "github_branch": "gh-pages",
  "output_dir": "output",
  "max_feeds_per_keyword": 10,
  "max_images_per_feed": 5
}
```

## 数据来源

- 小红书用户真实旅行分享
- 通过 [xiaohongshu-skills](https://github.com/autoclaw-cc/xiaohongshu-skills) 抓取

## License

MIT
