#!/usr/bin/env python3
"""Validate repository-local documentation links and diagram presence offline."""
import pathlib
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
errors = []
diagram_count = 0
for source in files:
    content = source.read_text()
    if content.count("```") % 2:
        errors.append(f"{source.relative_to(ROOT)}: unbalanced code fences")
    diagrams = re.findall(r"```mermaid\n(.*?)```", content, re.S)
    diagram_count += len(diagrams)
    for diagram in diagrams:
        if not diagram.lstrip().startswith(("flowchart ", "sequenceDiagram")):
            errors.append(f"{source.relative_to(ROOT)}: unexpected diagram type")
    prose = re.sub(r"```.*?```", "", content, flags=re.S)
    for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", prose):
        target = urlsplit(link)
        if target.scheme or target.netloc:
            continue
        path = (source.parent / unquote(target.path)).resolve() if target.path else source
        if not path.is_relative_to(ROOT) or not path.exists():
            errors.append(f"{source.relative_to(ROOT)}: missing local link {link}")
            continue
        if target.fragment and path.suffix == ".md":
            anchors = set()
            for heading in re.findall(r"^#{1,6}\s+(.+)$", path.read_text(), re.M):
                heading = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                anchors.add(heading)
            if unquote(target.fragment) not in anchors:
                errors.append(f"{source.relative_to(ROOT)}: missing heading {link}")
if diagram_count < 4:
    errors.append("Expected pipeline, retry, GitOps and trust-boundary diagrams")
for error in errors:
    print(error, file=sys.stderr)
if errors:
    sys.exit(1)
print(f"Documentation checks passed: {len(files)} pages, {diagram_count} Mermaid diagrams.")
