"""
偏好管理模块
支持多个偏好配置文件的创建、切换、编辑和删除。
"""

import json
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from .utils import load_json, save_json, TravelXhsError


class PreferenceManager:
    """偏好管理器"""

    # 偏好字段定义
    PREFERENCE_FIELDS = {
        "travel_style": {
            "label": "旅行风格",
            "options": ["adventurous", "relaxed", "cultural", "shopping"],
            "option_labels": ["冒险", "休闲", "文化", "购物"]
        },
        "budget_level": {
            "label": "预算档次",
            "options": ["budget", "mid-range", "luxury"],
            "option_labels": ["经济", "中档", "高端"]
        },
        "interests": {
            "label": "兴趣爱好（多选，逗号分隔）",
            "options": ["food", "photography", "culture", "shopping", "nature", "nightlife"],
            "option_labels": ["美食", "摄影", "文化", "购物", "自然", "夜生活"],
            "multiple": True
        },
        "dietary_restrictions": {
            "label": "饮食限制（多选，逗号分隔）",
            "options": ["none", "vegetarian", "halal", "gluten-free"],
            "option_labels": ["无", "素食", "清真", "无麸质"],
            "multiple": True
        },
        "travel_companions": {
            "label": "旅行同伴",
            "options": ["solo", "couple", "family", "friends"],
            "option_labels": ["独自", "情侣", "家庭", "朋友"]
        },
        "pace_preference": {
            "label": "旅行节奏",
            "options": ["relaxed", "moderate", "intensive"],
            "option_labels": ["轻松", "适中", "紧凑"]
        }
    }

    def __init__(self):
        self.preferences_dir = Path.home() / ".claude" / "travel_xhs" / "preferences"
        self.active_preference_file = Path.home() / ".claude" / "travel_xhs" / "active_preference"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录存在"""
        self.preferences_dir.mkdir(parents=True, exist_ok=True)

    def list_preferences(self) -> list[dict]:
        """列出所有偏好配置"""
        preferences = []
        for file in self.preferences_dir.glob("*.json"):
            try:
                data = load_json(file)
                if data:
                    preferences.append({
                        "name": file.stem,
                        "label": data.get("name", file.stem),
                        "is_active": file.stem == self.get_active_preference_name()
                    })
            except Exception as e:
                logger.warning(f"读取偏好文件失败 {file}: {e}")
        return preferences

    def get_active_preference_name(self) -> str:
        """获取当前激活的偏好名称"""
        try:
            if self.active_preference_file.exists():
                return self.active_preference_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"读取激活偏好失败: {e}")
        return "default"

    def get_active_preference(self) -> dict:
        """获取当前激活的偏好配置"""
        name = self.get_active_preference_name()
        return self.get_preference(name)

    def get_preference(self, name: str) -> dict:
        """获取指定名称的偏好配置"""
        filepath = self.preferences_dir / f"{name}.json"
        data = load_json(filepath)
        if data is None:
            logger.info(f"偏好 '{name}' 不存在，返回默认偏好")
            return self._get_default_preference(name)
        return data

    def create_preference(self, name: str, data: Optional[dict] = None) -> dict:
        """创建新的偏好配置"""
        filepath = self.preferences_dir / f"{name}.json"
        if filepath.exists():
            raise TravelXhsError(f"偏好 '{name}' 已存在")

        if data is None:
            data = self._get_default_preference(name)

        save_json(data, filepath)
        logger.info(f"偏好 '{name}' 已创建")
        return data

    def switch_preference(self, name: str) -> dict:
        """切换到指定的偏好配置"""
        filepath = self.preferences_dir / f"{name}.json"
        if not filepath.exists():
            raise TravelXhsError(f"偏好 '{name}' 不存在")

        self.active_preference_file.write_text(name, encoding="utf-8")
        logger.info(f"已切换到偏好 '{name}'")
        return load_json(filepath)

    def save_preference(self, name: str, data: dict):
        """保存偏好配置"""
        filepath = self.preferences_dir / f"{name}.json"
        save_json(data, filepath)
        logger.info(f"偏好 '{name}' 已保存")

    def edit_preference(self, name: str, updates: dict) -> dict:
        """编辑偏好配置"""
        current = self.get_preference(name)
        current.update(updates)
        self.save_preference(name, current)
        logger.info(f"偏好 '{name}' 已更新")
        return current

    def delete_preference(self, name: str):
        """删除偏好配置"""
        if name == "default":
            raise TravelXhsError("不能删除默认偏好")

        filepath = self.preferences_dir / f"{name}.json"
        if not filepath.exists():
            raise TravelXhsError(f"偏好 '{name}' 不存在")

        filepath.unlink()
        logger.info(f"偏好 '{name}' 已删除")

        # 如果删除的是当前激活的偏好，切换到 default
        if self.get_active_preference_name() == name:
            self.switch_preference("default")

    def _get_default_preference(self, name: str = "default") -> dict:
        """获取默认偏好配置"""
        return {
            "name": name,
            "travel_style": "relaxed",
            "budget_level": "mid-range",
            "interests": ["food", "culture"],
            "dietary_restrictions": ["none"],
            "travel_companions": "solo",
            "pace_preference": "moderate",
            "language_skills": ["Chinese"],
            "previous_destinations": [],
            "bucket_list": []
        }

    def format_preference_display(self, data: dict) -> str:
        """格式化偏好配置为显示文本"""
        lines = []
        lines.append(f"偏好名称: {data.get('name', '未命名')}")
        lines.append(f"旅行风格: {self._get_label('travel_style', data.get('travel_style', ''))}")
        lines.append(f"预算档次: {self._get_label('budget_level', data.get('budget_level', ''))}")

        interests = data.get("interests", [])
        interest_labels = [self._get_label("interests", i) for i in interests]
        lines.append(f"兴趣爱好: {', '.join(interest_labels)}")

        dietary = data.get("dietary_restrictions", [])
        dietary_labels = [self._get_label("dietary_restrictions", d) for d in dietary]
        lines.append(f"饮食限制: {', '.join(dietary_labels)}")

        lines.append(f"旅行同伴: {self._get_label('travel_companions', data.get('travel_companions', ''))}")
        lines.append(f"旅行节奏: {self._get_label('pace_preference', data.get('pace_preference', ''))}")

        return "\n".join(lines)

    def _get_label(self, field: str, value: str) -> str:
        """获取字段值的显示标签"""
        field_info = self.PREFERENCE_FIELDS.get(field, {})
        options = field_info.get("options", [])
        labels = field_info.get("option_labels", [])
        try:
            idx = options.index(value)
            return labels[idx] if idx < len(labels) else value
        except ValueError:
            return value

    def interactive_create(self) -> dict:
        """交互式创建偏好配置"""
        print("\n=== 创建旅行偏好配置 ===\n")

        name = input("配置名称: ").strip()
        if not name:
            name = "my_travel"

        data = {"name": name}

        for field, info in self.PREFERENCE_FIELDS.items():
            label = info["label"]
            options = info["options"]
            option_labels = info["option_labels"]
            is_multiple = info.get("multiple", False)

            print(f"\n{label}:")
            for i, (opt, opt_label) in enumerate(zip(options, option_labels), 1):
                print(f"  {i}. {opt_label}")

            while True:
                choice = input(f"请选择 (1-{len(options)}): ").strip()
                if is_multiple:
                    choices = [c.strip() for c in choice.split(",")]
                    selected = []
                    for c in choices:
                        try:
                            idx = int(c) - 1
                            if 0 <= idx < len(options):
                                selected.append(options[idx])
                        except ValueError:
                            pass
                    if selected:
                        data[field] = selected
                        break
                else:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(options):
                            data[field] = options[idx]
                            break
                    except ValueError:
                        pass
                print("无效选择，请重试")

        return self.create_preference(name, data)


def get_preference_manager() -> PreferenceManager:
    """获取偏好管理器实例"""
    return PreferenceManager()
