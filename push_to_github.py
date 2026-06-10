#!/usr/bin/env python3
"""Push files to GitHub using API"""
import os
import base64
import json
import urllib.request
import urllib.error

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "TornadoDai/travel-xhs-plan"
BASE_URL = f"https://api.github.com/repos/{REPO}/contents"

def push_file(file_path, repo_path):
    """Push a single file to GitHub"""
    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    data = json.dumps({
        "message": f"Add {repo_path}",
        "content": content
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/{repo_path}",
        data=data,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"✓ {repo_path}")
            return True
    except urllib.error.HTTPError as e:
        print(f"✗ {repo_path}: {e.code} {e.reason}")
        return False

def main():
    if not TOKEN:
        print("Error: GITHUB_TOKEN environment variable not set")
        return

    files_to_push = [
        ("README.md", "README.md"),
        ("SKILL.md", "SKILL.md"),
        ("requirements.txt", "requirements.txt"),
        (".gitignore", ".gitignore"),
        ("config/settings.json", "config/settings.json"),
        ("scripts/__init__.py", "scripts/__init__.py"),
        ("scripts/cli.py", "scripts/cli.py"),
        ("scripts/preference_manager.py", "scripts/preference_manager.py"),
        ("scripts/xhs_scraper.py", "scripts/xhs_scraper.py"),
        ("scripts/content_analyzer.py", "scripts/content_analyzer.py"),
        ("scripts/guide_writer.py", "scripts/guide_writer.py"),
        ("scripts/itinerary_gen.py", "scripts/itinerary_gen.py"),
        ("scripts/deployer.py", "scripts/deployer.py"),
        ("scripts/utils.py", "scripts/utils.py"),
        ("templates/guide_template.html", "templates/guide_template.html"),
        ("tests/__init__.py", "tests/__init__.py"),
        ("tests/test_preference_manager.py", "tests/test_preference_manager.py"),
        ("docs/examples/sample_preference.json", "docs/examples/sample_preference.json"),
    ]

    success = 0
    for local_path, repo_path in files_to_push:
        if os.path.exists(local_path):
            if push_file(local_path, repo_path):
                success += 1

    print(f"\n{success}/{len(files_to_push)} files pushed")

if __name__ == "__main__":
    main()
