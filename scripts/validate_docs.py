#!/usr/bin/env python3
"""
Documentation validation script.

Checks for:
1. Broken relative links in markdown files
2. Undocumented API endpoints (routes registered but not in API.md)
3. Documented but non-existent API endpoints

Usage:
    python scripts/validate_docs.py
"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
WEB_API_DIR = PROJECT_ROOT / "web" / "api" / "v1"
API_DOC = DOCS_DIR / "API.md"

issues = []


def check_broken_links():
    """Scan all .md files for relative links and verify targets exist."""
    link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')

    for md_file in PROJECT_ROOT.rglob("*.md"):
        # Skip archive and node_modules
        rel = md_file.relative_to(PROJECT_ROOT)
        if any(part in rel.parts for part in ("archive", "node_modules", ".git", "build", "dist")):
            continue

        content = md_file.read_text(errors="ignore")

        # Remove code blocks to avoid false positives from example markdown
        cleaned = re.sub(r'```[\s\S]*?```', '', content)

        for match in link_pattern.finditer(cleaned):
            link_text, link_target = match.group(1), match.group(2)

            # Skip external URLs, anchors, and mailto
            if link_target.startswith(("http://", "https://", "#", "mailto:")):
                continue

            # Strip anchor from relative links
            target_path = link_target.split("#")[0]
            if not target_path:
                continue

            # Resolve relative to the file's directory
            resolved = (md_file.parent / target_path).resolve()
            if not resolved.exists():
                # Approximate line number from cleaned content
                line_num = cleaned[:match.start()].count("\n") + 1
                issues.append(
                    f"BROKEN LINK: {rel}:{line_num} — [{link_text}]({link_target}) → target not found"
                )


def check_api_endpoints():
    """Cross-reference documented endpoints against actual FastAPI routes."""
    if not API_DOC.exists():
        issues.append(f"MISSING FILE: {API_DOC.relative_to(PROJECT_ROOT)} not found")
        return

    # Extract documented endpoints from API.md
    api_content = API_DOC.read_text(errors="ignore")

    documented = set()

    # Pattern 1: backtick-wrapped like `POST /api/v1/...`
    backtick_pattern = re.compile(r'`(GET|POST|PUT|DELETE|PATCH)\s+(/api/v1/[^`\s]+)`')
    for match in backtick_pattern.finditer(api_content):
        method, path = match.group(1), match.group(2)
        normalized = re.sub(r'\{[^}]+\}', '{param}', path)
        documented.add(f"{method} {normalized}")

    # Pattern 2: table rows like | `POST` | `/api/v1/configs` |
    table_pattern = re.compile(r'\|\s*`(GET|POST|PUT|DELETE|PATCH)`\s*\|\s*`(/api/v1/[^`]+)`')
    for match in table_pattern.finditer(api_content):
        method, path = match.group(1), match.group(2)
        normalized = re.sub(r'\{[^}]+\}', '{param}', path)
        documented.add(f"{method} {normalized}")

    # Pattern 3: markdown headers like ### POST /api/v1/...
    header_pattern = re.compile(r'#{1,4}\s+(GET|POST|PUT|DELETE|PATCH)\s+(/api/v1/\S+)')
    for match in header_pattern.finditer(api_content):
        method, path = match.group(1), match.group(2)
        normalized = re.sub(r'\{[^}]+\}', '{param}', path)
        documented.add(f"{method} {normalized}")

    # Extract actual routes from web/api/v1/ source files
    route_pattern = re.compile(
        r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']*)["\']'
    )
    registered = set()

    if not WEB_API_DIR.exists():
        return

    # Read router prefixes
    prefixes = {}
    prefix_pattern = re.compile(r'APIRouter\(prefix=["\']([^"\']*)["\']')
    for py_file in WEB_API_DIR.glob("*.py"):
        content = py_file.read_text(errors="ignore")
        prefix_match = prefix_pattern.search(content)
        prefix = prefix_match.group(1) if prefix_match else ""
        prefixes[py_file.stem] = prefix

        for match in route_pattern.finditer(content):
            method = match.group(1).upper()
            route_path = match.group(2)
            full_path = f"/api/v1{prefix}{route_path}"
            normalized = re.sub(r'\{[^}]+\}', '{param}', full_path)
            registered.add(f"{method} {normalized}")

    # Find mismatches
    for endpoint in registered - documented:
        issues.append(f"UNDOCUMENTED ENDPOINT: {endpoint} exists in code but not in API.md")

    for endpoint in documented - registered:
        issues.append(f"PHANTOM ENDPOINT: {endpoint} documented in API.md but not found in code")


def main():
    print("Validating documentation...\n")

    check_broken_links()
    check_api_endpoints()

    if issues:
        print(f"Found {len(issues)} issue(s):\n")
        for issue in sorted(issues):
            print(f"  ⚠  {issue}")
        print()
        sys.exit(1)
    else:
        print("✅ All documentation checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
