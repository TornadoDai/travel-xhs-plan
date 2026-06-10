"""
CLI 入口模块
提供统一的命令行接口，用于管理偏好配置、搜索小红书内容、生成攻略等。
"""

import sys
from pathlib import Path

import click
from loguru import logger

from .utils import setup_logger, load_config, TravelXhsError
from .preference_manager import get_preference_manager


@click.group()
@click.option("--debug", is_flag=True, help="启用调试模式")
def cli(debug):
    """小红书旅行攻略生成器"""
    setup_logger("DEBUG" if debug else "INFO")


# ============================================================
# 偏好管理命令
# ============================================================

@cli.command("list-preferences")
def list_preferences():
    """列出所有偏好配置"""
    pm = get_preference_manager()
    preferences = pm.list_preferences()

    if not preferences:
        click.echo("暂无偏好配置，使用 'create-preference' 创建")
        return

    click.echo("\n=== 偏好配置列表 ===\n")
    for pref in preferences:
        active_mark = "✓" if pref["is_active"] else " "
        click.echo(f"  [{active_mark}] {pref['name']}")
    click.echo(f"\n当前激活: {pm.get_active_preference_name()}")


@cli.command("create-preference")
@click.option("--name", prompt="配置名称", help="偏好配置名称")
@click.option("--interactive", "-i", is_flag=True, help="交互式创建")
def create_preference(name, interactive):
    """创建新的偏好配置"""
    pm = get_preference_manager()

    if interactive:
        data = pm.interactive_create()
        click.echo(f"\n✓ 偏好 '{data['name']}' 已创建")
    else:
        try:
            data = pm.create_preference(name)
            click.echo(f"\n✓ 偏好 '{name}' 已创建（使用默认值）")
            click.echo("使用 'edit-preference' 编辑偏好内容")
        except TravelXhsError as e:
            click.echo(f"✗ 错误: {e}")
            sys.exit(1)


@cli.command("switch-preference")
@click.option("--name", prompt="偏好名称", help="要切换的偏好名称")
def switch_preference(name):
    """切换偏好配置"""
    pm = get_preference_manager()
    try:
        data = pm.switch_preference(name)
        click.echo(f"\n✓ 已切换到偏好 '{name}'")
        click.echo(pm.format_preference_display(data))
    except TravelXhsError as e:
        click.echo(f"✗ 错误: {e}")
        sys.exit(1)


@cli.command("show-preference")
@click.option("--name", default=None, help="偏好名称（默认显示当前激活的）")
def show_preference(name):
    """显示偏好配置详情"""
    pm = get_preference_manager()
    if name is None:
        name = pm.get_active_preference_name()

    data = pm.get_preference(name)
    click.echo(f"\n=== 偏好配置: {name} ===\n")
    click.echo(pm.format_preference_display(data))


@cli.command("edit-preference")
@click.option("--name", default=None, help="偏好名称（默认编辑当前激活的）")
@click.option("--field", default=None, help="要编辑的字段")
@click.option("--value", default=None, help="新的值")
def edit_preference(name, field, value):
    """编辑偏好配置"""
    pm = get_preference_manager()
    if name is None:
        name = pm.get_active_preference_name()

    if field and value:
        # 直接编辑指定字段
        updates = {field: value}
        data = pm.edit_preference(name, updates)
        click.echo(f"\n✓ 偏好 '{name}' 已更新")
        click.echo(pm.format_preference_display(data))
    else:
        # 交互式编辑
        current = pm.get_preference(name)
        click.echo(f"\n=== 编辑偏好: {name} ===\n")
        click.echo(pm.format_preference_display(current))

        click.echo("\n可编辑字段:")
        for i, (field_name, info) in enumerate(pm.PREFERENCE_FIELDS.items(), 1):
            click.echo(f"  {i}. {info['label']} ({field_name})")

        choice = input("\n请选择字段编号 (直接回车取消): ").strip()
        if not choice:
            return

        try:
            idx = int(choice) - 1
            field_name = list(pm.PREFERENCE_FIELDS.keys())[idx]
            field_info = pm.PREFERENCE_FIELDS[field_name]

            click.echo(f"\n{field_info['label']}:")
            for i, (opt, label) in enumerate(zip(field_info["options"], field_info["option_labels"]), 1):
                click.echo(f"  {i}. {label}")

            value_choice = input("请选择: ").strip()
            value_idx = int(value_choice) - 1
            new_value = field_info["options"][value_idx]

            if field_info.get("multiple"):
                values = [v.strip() for v in value_choice.split(",")]
                new_value = [field_info["options"][int(v) - 1] for v in values if v.isdigit()]

            data = pm.edit_preference(name, {field_name: new_value})
            click.echo(f"\n✓ 偏好 '{name}' 已更新")
            click.echo(pm.format_preference_display(data))
        except (ValueError, IndexError) as e:
            click.echo(f"✗ 无效输入: {e}")


@cli.command("delete-preference")
@click.option("--name", prompt="偏好名称", help="要删除的偏好名称")
def delete_preference(name):
    """删除偏好配置"""
    pm = get_preference_manager()
    try:
        if click.confirm(f"确定要删除偏好 '{name}' 吗？"):
            pm.delete_preference(name)
            click.echo(f"\n✓ 偏好 '{name}' 已删除")
    except TravelXhsError as e:
        click.echo(f"✗ 错误: {e}")
        sys.exit(1)


# ============================================================
# 小红书搜索命令
# ============================================================

@cli.command("search-xhs")
@click.option("--keyword", prompt="搜索关键词", help="搜索关键词")
@click.option("--limit", default=10, help="结果数量限制")
def search_xhs(keyword, limit):
    """搜索小红书内容"""
    try:
        from .xhs_scraper import search_xhs_content
        results = search_xhs_content(keyword, limit)
        click.echo(f"\n=== 搜索结果: {keyword} ===\n")
        for i, feed in enumerate(results, 1):
            click.echo(f"{i}. {feed['title']}")
            click.echo(f"   作者: {feed['author']} | 点赞: {feed['likes']}")
            click.echo()
    except ImportError:
        click.echo("✗ 小红书抓取模块未安装，请检查 xiaohongshu-skills 路径配置")
    except Exception as e:
        click.echo(f"✗ 搜索失败: {e}")


# ============================================================
# 攻略生成命令
# ============================================================

@cli.command("generate-guide")
@click.option("--destination", prompt="目的地", help="旅行目的地")
@click.option("--days", default=5, help="旅行天数")
@click.option("--preview", is_flag=True, help="生成后预览")
def generate_guide(destination, days, preview):
    """生成旅行攻略"""
    try:
        from .xhs_scraper import scrape_destination
        from .content_analyzer import analyze_content
        from .guide_writer import generate_html_guide
        from .deployer import preview_local

        pm = get_preference_manager()
        preferences = pm.get_active_preference()

        click.echo(f"\n正在为 '{destination}' 生成攻略...")
        click.echo(f"当前偏好: {pm.get_active_preference_name()}")

        # 1. 抓取小红书内容
        click.echo("\n[1/4] 正在搜索小红书内容...")
        scraped_data = scrape_destination(destination, preferences)
        click.echo(f"  找到 {len(scraped_data.get('feeds', []))} 篇相关内容")

        # 2. AI 分析
        click.echo("\n[2/4] 正在分析内容...")
        analyzed_data = analyze_content(scraped_data, preferences, days)
        click.echo("  分析完成")

        # 3. 生成 HTML
        click.echo("\n[3/4] 正在生成攻略文档...")
        html_path = generate_html_guide(analyzed_data, destination)
        click.echo(f"  攻略已生成: {html_path}")

        # 4. 预览
        if preview:
            click.echo("\n[4/4] 正在打开预览...")
            preview_local(html_path)
        else:
            click.echo(f"\n✓ 攻略生成完成！")
            click.echo(f"  文件: {html_path}")
            click.echo(f"  使用 'preview-guide --file {html_path}' 预览")

    except ImportError as e:
        click.echo(f"✗ 模块导入失败: {e}")
    except Exception as e:
        logger.exception("生成攻略失败")
        click.echo(f"✗ 生成失败: {e}")


# ============================================================
# 预览和部署命令
# ============================================================

@cli.command("preview-guide")
@click.option("--file", prompt="攻略文件路径", help="HTML 攻略文件路径")
def preview_guide(file):
    """本地预览攻略"""
    try:
        from .deployer import preview_local
        preview_local(file)
        click.echo(f"✓ 已打开预览: {file}")
    except Exception as e:
        click.echo(f"✗ 预览失败: {e}")


@cli.command("deploy-guide")
@click.option("--file", prompt="攻略文件路径", help="HTML 攻略文件路径")
@click.option("--repo", default=None, help="GitHub 仓库地址")
def deploy_guide(file, repo):
    """部署攻略到 GitHub Pages"""
    try:
        from .deployer import deploy_to_github
        config = load_config()
        if repo:
            config["github_repo"] = repo

        if not config.get("github_repo"):
            click.echo("✗ 请先配置 GitHub 仓库地址")
            click.echo("  使用 --repo 参数或编辑 config/settings.json")
            sys.exit(1)

        url = deploy_to_github(file, config)
        click.echo(f"\n✓ 部署成功！")
        click.echo(f"  访问链接: {url}")
    except Exception as e:
        click.echo(f"✗ 部署失败: {e}")


# ============================================================
# 配置命令
# ============================================================

@cli.command("show-config")
def show_config():
    """显示当前配置"""
    config = load_config()
    click.echo("\n=== 当前配置 ===\n")
    for key, value in config.items():
        click.echo(f"  {key}: {value}")


@cli.command("set-config")
@click.option("--key", prompt="配置项", help="配置项名称")
@click.option("--value", prompt="配置值", help="配置值")
def set_config(key, value):
    """设置配置项"""
    from .utils import save_config
    config = load_config()
    config[key] = value
    save_config(config)
    click.echo(f"\n✓ 配置已更新: {key} = {value}")


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()
