#!/usr/bin/env python3
"""Validate converted Kiro Powers against the AWS migration guide checklist."""
import re, sys
from pathlib import Path

POWERS = Path(sys.argv[1] if len(sys.argv) > 1 else "powers")

def frontmatter(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    return text[3:end], text[end+4:]

total = 0
fails = []
stats = {"mcp": 0, "steering_listed_ok": 0, "has_attribution": 0,
         "ref_links_clean": 0, "no_backlinks": 0, "no_claude_plugin": 0}

for pd in sorted(p for p in POWERS.iterdir() if p.is_dir()):
    total += 1
    power_md = pd / "POWER.md"
    issues = []
    if not power_md.exists():
        fails.append((pd.name, ["missing POWER.md"])); continue
    text = power_md.read_text(encoding="utf-8", errors="ignore")
    fm, body = frontmatter(text)

    # [ ] valid frontmatter: name, displayName, description
    if fm is None:
        issues.append("no frontmatter")
    else:
        for key in ("name:", "displayName:", "description:"):
            if not re.search(rf"^{key}", fm, re.M):
                issues.append(f"missing {key}")
        # keywords present and specific (not generic)
        kw = re.search(r"^keywords:\s*\[(.*)\]", fm, re.M)
        if not kw:
            issues.append("missing keywords")
        else:
            toks = [t.strip().strip('"\'').lower() for t in kw.group(1).split(",") if t.strip()]
            if any(t in {"help", "tool", "tools"} for t in toks):
                issues.append("generic keyword present")
            if len(toks) < 3:
                issues.append("too few keywords")

    # [ ] all steering files listed in "Available Steering Files"
    steering_dir = pd / "steering"
    steering_files = sorted(f.stem for f in steering_dir.glob("*.md")) if steering_dir.exists() else []
    if steering_files:
        sec = re.search(r"## Available Steering Files(.+?)(\n## |\Z)", body, re.S)
        listed = set(re.findall(r"\*\*([^*]+)\*\*", sec.group(1))) if sec else set()
        missing = [f for f in steering_files if f not in listed]
        if missing:
            issues.append(f"steering not listed: {missing}")
        else:
            stats["steering_listed_ok"] += 1

    # [ ] internal links updated references/ -> steering/
    if re.search(r"\breferences/", body):
        issues.append("stale references/ link")
    else:
        stats["ref_links_clean"] += 1

    # [ ] back-links to SKILL.md removed/updated
    if "../SKILL.md" in body or re.search(r"\]\(SKILL\.md\)", body):
        issues.append("stale SKILL.md backlink")
    else:
        stats["no_backlinks"] += 1

    # [ ] attribution present
    if "## License & Attribution" in body and "Original Work:" in body:
        stats["has_attribution"] += 1
    else:
        issues.append("missing attribution")

    # [ ] no .claude-plugin remains
    if (pd / ".claude-plugin").exists():
        issues.append(".claude-plugin present")
    else:
        stats["no_claude_plugin"] += 1

    # mcp.json validity if present
    if (pd / "mcp.json").exists():
        import json
        try:
            json.loads((pd / "mcp.json").read_text())
            stats["mcp"] += 1
        except Exception as e:
            issues.append(f"invalid mcp.json: {e}")

    if issues:
        fails.append((pd.name, issues))

print(f"Validated {total} powers")
print(f"  attribution OK:        {stats['has_attribution']}/{total}")
print(f"  references/ clean:     {stats['ref_links_clean']}/{total}")
print(f"  no SKILL.md backlinks: {stats['no_backlinks']}/{total}")
print(f"  no .claude-plugin:     {stats['no_claude_plugin']}/{total}")
print(f"  valid mcp.json:        {stats['mcp']}")
print(f"  steering lists OK:     {stats['steering_listed_ok']} (of powers with steering)")
print(f"FAILURES: {len(fails)}")
for name, iss in fails[:40]:
    print(f"  - {name}: {iss}")
sys.exit(1 if fails else 0)
