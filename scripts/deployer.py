"""
部署模块
支持本地预览和 GitHub Pages 部署。
"""

import os
import platform
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

from loguru import logger

from .utils import load_config, DeploymentError


def preview_local(file_path: str) -> str:
    """
    本地预览攻略文件。

    Args:
        file_path: HTML 文件路径

    Returns:
        str: 文件的绝对路径
    """
    abs_path = os.path.abspath(file_path)

    if not os.path.exists(abs_path):
        raise DeploymentError(f"文件不存在: {abs_path}")

    # 尝试用系统默认浏览器打开
    try:
        webbrowser.open(f"file://{abs_path}")
        logger.info(f"已在浏览器中打开: {abs_path}")
    except Exception as e:
        logger.warning(f"无法自动打开浏览器: {e}")
        print(f"请手动打开文件: {abs_path}")

    return abs_path


def deploy_to_github(file_path: str, config: Optional[dict] = None) -> str:
    """
    部署攻略到 GitHub Pages。

    Args:
        file_path: HTML 文件路径
        config: 配置信息（可选）

    Returns:
        str: 访问链接

    Raises:
        DeploymentError: 部署失败
    """
    if config is None:
        config = load_config()

    repo_url = config.get("github_repo", "")
    branch = config.get("github_branch", "gh-pages")

    if not repo_url:
        raise DeploymentError("未配置 GitHub 仓库地址，请在 config/settings.json 中设置 github_repo")

    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise DeploymentError(f"文件不存在: {abs_path}")

    filename = os.path.basename(abs_path)

    # 解析仓库信息
    repo_info = _parse_repo_url(repo_url)
    if not repo_info:
        raise DeploymentError(f"无法解析仓库地址: {repo_url}")

    username, repo_name = repo_info

    # 创建临时部署目录
    deploy_dir = Path(os.path.dirname(abs_path)).parent / "_deploy"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 复制文件到部署目录
        import shutil
        dest_file = deploy_dir / filename
        shutil.copy2(abs_path, dest_file)

        # 复制图片目录（如果有）
        images_dir = Path(os.path.dirname(abs_path)).parent / "images"
        if images_dir.exists():
            dest_images = deploy_dir / "images"
            if dest_images.exists():
                shutil.rmtree(dest_images)
            shutil.copytree(images_dir, dest_images)

        # 初始化 Git 仓库并推送
        _git_deploy(deploy_dir, repo_url, branch, filename)

        # 生成访问链接
        url = f"https://{username}.github.io/{repo_name}/{filename}"
        logger.info(f"部署成功: {url}")
        return url

    except Exception as e:
        raise DeploymentError(f"部署失败: {e}")
    finally:
        # 清理临时目录
        if deploy_dir.exists():
            try:
                shutil.rmtree(deploy_dir)
            except Exception:
                pass


def _parse_repo_url(repo_url: str) -> Optional[tuple[str, str]]:
    """
    解析 GitHub 仓库地址。

    Args:
        repo_url: 仓库地址

    Returns:
        tuple: (username, repo_name) 或 None
    """
    # HTTPS: https://github.com/username/repo.git
    # SSH: git@github.com:username/repo.git
    # 简写: username/repo

    repo_url = repo_url.strip().rstrip("/")

    if repo_url.startswith("https://github.com/"):
        parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
    elif repo_url.startswith("git@github.com:"):
        parts = repo_url.replace("git@github.com:", "").replace(".git", "").split("/")
    elif "/" in repo_url and not repo_url.startswith("http"):
        parts = repo_url.split("/")
    else:
        return None

    if len(parts) >= 2:
        return parts[0], parts[1]

    return None


def _git_deploy(deploy_dir: Path, repo_url: str, branch: str, filename: str):
    """
    使用 Git 部署到 GitHub Pages。

    Args:
        deploy_dir: 部署目录
        repo_url: 仓库地址
        branch: 分支名称
        filename: 文件名
    """
    cwd = str(deploy_dir)

    def run_git(*args):
        cmd = ["git"] + list(args)
        logger.debug(f"执行: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        if result.returncode != 0:
            logger.error(f"Git 命令失败: {result.stderr}")
            raise DeploymentError(f"Git 命令失败: {result.stderr}")
        return result.stdout.strip()

    try:
        # 初始化仓库
        run_git("init")

        # 配置用户信息
        run_git("config", "user.email", "travel-xhs@example.com")
        run_git("config", "user.name", "Travel XHS Generator")

        # 添加文件
        run_git("add", ".")

        # 提交
        run_git("commit", "-m", f"Deploy travel guide: {filename}")

        # 添加远程仓库
        try:
            run_git("remote", "add", "origin", repo_url)
        except DeploymentError:
            # 远程仓库已存在，更新 URL
            run_git("remote", "set-url", "origin", repo_url)

        # 推送
        run_git("push", "-f", "origin", f"HEAD:{branch}")

        logger.info(f"已推送到 {repo_url} ({branch})")

    except DeploymentError:
        raise
    except Exception as e:
        raise DeploymentError(f"Git 操作失败: {e}")


def get_deploy_url(filename: str, config: Optional[dict] = None) -> str:
    """
    获取部署后的访问链接。

    Args:
        filename: 文件名
        config: 配置信息

    Returns:
        str: 访问链接
    """
    if config is None:
        config = load_config()

    repo_url = config.get("github_repo", "")
    if not repo_url:
        return ""

    repo_info = _parse_repo_url(repo_url)
    if not repo_info:
        return ""

    username, repo_name = repo_info
    return f"https://{username}.github.io/{repo_name}/{filename}"
