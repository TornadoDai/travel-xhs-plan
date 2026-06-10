"""
偏好管理模块测试
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from preference_manager import PreferenceManager


def test_create_preference():
    """测试创建偏好配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)

        # 创建偏好
        data = pm.create_preference("test")
        assert data["name"] == "test"
        assert data["travel_style"] == "relaxed"
        assert "food" in data["interests"]

        # 检查文件是否存在
        filepath = Path(tmpdir) / "test.json"
        assert filepath.exists()


def test_list_preferences():
    """测试列出偏好配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)

        # 创建多个偏好
        pm.create_preference("travel1")
        pm.create_preference("travel2")
        pm.create_preference("travel3")

        # 列出偏好
        preferences = pm.list_preferences()
        assert len(preferences) == 3

        names = [p["name"] for p in preferences]
        assert "travel1" in names
        assert "travel2" in names
        assert "travel3" in names


def test_switch_preference():
    """测试切换偏好配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)
        pm.active_preference_file = Path(tmpdir) / "active"

        # 创建偏好
        pm.create_preference("travel1")
        pm.create_preference("travel2")

        # 切换偏好
        data = pm.switch_preference("travel1")
        assert data["name"] == "travel1"
        assert pm.get_active_preference_name() == "travel1"

        # 切换到另一个
        data = pm.switch_preference("travel2")
        assert data["name"] == "travel2"
        assert pm.get_active_preference_name() == "travel2"


def test_edit_preference():
    """测试编辑偏好配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)

        # 创建偏好
        pm.create_preference("test")

        # 编辑偏好
        updates = {
            "travel_style": "adventurous",
            "budget_level": "luxury",
            "interests": ["food", "photography", "shopping"]
        }
        data = pm.edit_preference("test", updates)

        assert data["travel_style"] == "adventurous"
        assert data["budget_level"] == "luxury"
        assert "photography" in data["interests"]


def test_delete_preference():
    """测试删除偏好配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)

        # 创建偏好
        pm.create_preference("test")
        assert Path(tmpdir, "test.json").exists()

        # 删除偏好
        pm.delete_preference("test")
        assert not Path(tmpdir, "test.json").exists()


def test_default_preference():
    """测试默认偏好配置"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)

        # 获取不存在的偏好，应返回默认值
        data = pm.get_preference("nonexistent")
        assert data["travel_style"] == "relaxed"
        assert data["budget_level"] == "mid-range"
        assert "food" in data["interests"]


def test_format_preference_display():
    """测试格式化偏好显示"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = PreferenceManager()
        pm.preferences_dir = Path(tmpdir)

        data = pm.create_preference("test")
        display = pm.format_preference_display(data)

        assert "test" in display
        assert "休闲" in display
        assert "中档" in display
        assert "美食" in display


if __name__ == "__main__":
    test_create_preference()
    test_list_preferences()
    test_switch_preference()
    test_edit_preference()
    test_delete_preference()
    test_default_preference()
    test_format_preference_display()
    print("所有测试通过！")
