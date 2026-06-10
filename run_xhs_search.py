#!/usr/bin/env python3
"""Wrapper script to run xiaohongshu-skills CLI with correct path"""
import sys
import os

# Add xiaohongshu-skills scripts to path
xhs_scripts_path = os.path.join(os.path.dirname(__file__), '..', '..', 'xiaohongshu-skills', 'scripts')
sys.path.insert(0, os.path.abspath(xhs_scripts_path))

# Now import and run the CLI
from cli import main

if __name__ == "__main__":
    sys.argv = ["cli.py", "search-feeds", "--keyword", "呼伦贝尔旅行攻略"]
    main()
