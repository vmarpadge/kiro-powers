#!/usr/bin/env python3
"""
Convert Claude Code Skills into Kiro Powers.

Implements the AWS migration guide:
https://builder.aws.com/content/39DLiJ3W2dTp53IqbWNxsJYgcHB/a-guide-for-migrating-claude-code-skills-to-kiro-powers

Mapping applied per source skill directory:
  SKILL.md                      -> POWER.md (+ Kiro frontmatter, Steering list, Attribution)
  references/*.md OR any other   -> steering/<name>.md   (deep-dive content, loaded on demand)
    *.md that isn't SKILL.md
  scripts/ examples/ assets ...  -> copied as-is (Powers can bundle tools/resources)
  .claude-plugin/, README.md,    -> removed
    CHANGELOG.md
  requires: mcp: [rube]          -> mcp.json (Rube MCP server config)

Usage:
  convert_skill_to_power.py --src <skills_root> --out <powers_root> [--only composio|top|all]
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
from pathlib import Path

GUIDE_URL = "https://builder.aws.com/content/39DLiJ3W2dTp53IqbWNxsJYgcHB/a-guide-for-migrating-claude-code-skills-to-kiro-powers"
SOURCE_REPO = "https://github.com/ComposioHQ/awesome-claude-skills"
AUTHOR = "Converted by kiro-powers (automated migration)"
ORIGINAL_AUTHOR = "ComposioHQ and awesome-claude-skills contributors"

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "your", "you", "from", "into",
    "help", "tool", "tools", "using", "use", "via", "skill", "a", "an", "to",
    "of", "in", "on", "it", "is", "are", "or", "by", "as", "automate", "automation",
}

# ---------- frontmatter parsing ----------

def split_frontmatter(text: str):
    """Return (frontmatter_dict, body). Minimal YAML (flat keys + simple lists)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    fm = {}
    current_key = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val == "":
                fm[key] = {}
                current_key = key
            else:
                fm[key] = _scalar(val)
                current_key = None
        else:
            sub = re.match(r"^\s+(\w[\w-]*):\s*(.*)$", line)
            if sub and current_key and isinstance(fm.get(current_key), dict):
                fm[current_key][sub.group(1)] = _scalar(sub.group(2).strip())
    return fm, body


def _scalar(val: str):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip('"\'') for v in inner.split(",")]
    if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
        return val[1:-1]
    return val


# ---------- helpers ----------

def kebab(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-+", "-", name)


def title_case(name: str) -> str:
    return " ".join(w.capitalize() for w in kebab(name).split("-"))


def clamp_sentences(text: str, max_sentences: int = 3) -> str:
    text = " ".join(text.split())
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:max_sentences]).strip()


def derive_keywords(name: str, description: str, existing, k=6):
    if isinstance(existing, list) and existing:
        kws = [str(x).strip() for x in existing if str(x).strip()]
        if kws:
            return kws[:7]
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]+", f"{name} {description}".lower())
    seen, out = set(), []
    for w in words:
        if w in STOPWORDS or len(w) < 3 or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= k:
            break
    while len(out) < 5:
        out.append(kebab(name).split("-")[0] if "-" in name else name.lower())
        break
    return out[:7]


def rewrite_links(body: str) -> str:
    # Step 5: references/ -> steering/, and back-links to SKILL.md -> POWER.md
    body = body.replace("references/", "steering/")
    body = re.sub(r"\.\./SKILL\.md", "POWER.md", body)
    body = re.sub(r"\(SKILL\.md\)", "(POWER.md)", body)
    body = re.sub(r"\[([^\]]*)\]\(\.\./SKILL\.md\)", r"[\1](POWER.md)", body)
    return body


def steering_list_section(steering_files):
    if not steering_files:
        return ""
    lines = ["## Available Steering Files", ""]
    for fn, desc in steering_files:
        lines.append(f"- **{fn}** - {desc}")
    return "\n".join(lines) + "\n"


def attribution_section(name, license_name):
    return "\n".join([
        "## License & Attribution",
        "",
        f"**License:** {license_name}",
        "",
        f"**Power Author:** {AUTHOR}",
        "",
        f"**Original Work:** This power is converted from the `{name}` skill in "
        f"[awesome-claude-skills]({SOURCE_REPO}) by {ORIGINAL_AUTHOR}.",
        "",
        "**Source Version:** Based on the `master` branch of awesome-claude-skills.",
        "",
        f"**Migration Guide:** Converted per the AWS guide: {GUIDE_URL}",
        "",
        "**Update Frequency:** This power will be updated periodically.",
        "",
    ])


def first_heading_or_name(body: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, re.M)
    return m.group(1).strip() if m else title_case(fallback)


def describe_steering(path: Path) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "Deep-dive reference content."
    _, body = split_frontmatter(txt)
    m = re.search(r"^#\s+(.+)$", body, re.M)
    if m:
        return m.group(1).strip()
    for line in body.splitlines():
        if line.strip():
            return clamp_sentences(line.strip(), 1)[:120]
    return "Deep-dive reference content."


MCP_JSON = {
    "mcpServers": {
        "rube": {
            "command": "npx",
            "args": ["-y", "@composio/mcp@latest", "start", "--client", "kiro"],
            "env": {"RUBE_API_KEY": "${RUBE_API_KEY}"},
            "disabled": False,
            "autoApprove": [],
        }
    }
}

MARKDOWN_SKIP = {"readme.md", "changelog.md"}

# Registry of allocated power names -> source dir, to resolve kebab collisions.
_USED_NAMES: dict[str, str] = {}


def convert_skill(skill_dir: Path, out_root: Path, meta: dict):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    raw = skill_md.read_text(encoding="utf-8", errors="ignore")
    fm, body = split_frontmatter(raw)

    src_name = fm.get("name") or skill_dir.name
    power_name = kebab(src_name)
    # Resolve kebab-name collisions (e.g. foo_bar vs foo-bar both -> foo-bar)
    # by disambiguating with the original directory name, then a counter.
    if power_name in _USED_NAMES and _USED_NAMES[power_name] != str(skill_dir):
        alt = kebab(skill_dir.name)
        candidate = alt if alt not in _USED_NAMES else f"{power_name}-v2"
        n = 2
        while candidate in _USED_NAMES:
            n += 1
            candidate = f"{power_name}-v{n}"
        power_name = candidate
    _USED_NAMES[power_name] = str(skill_dir)
    display = title_case(power_name)

    mkt = meta.get(skill_dir.name) or meta.get(src_name) or {}
    description = mkt.get("description") or fm.get("description") or first_heading_or_name(body, power_name)
    description = clamp_sentences(str(description), 3)

    keywords = derive_keywords(power_name, description, fm.get("keywords"))
    if mkt.get("category"):
        cat = kebab(mkt["category"]).replace("-", " ")
        for w in cat.split():
            if w not in keywords and w not in STOPWORDS:
                keywords.append(w)
    keywords = keywords[:7]

    power_dir = out_root / power_name
    steering_dir = power_dir / "steering"
    power_dir.mkdir(parents=True, exist_ok=True)

    # Step 4/5: move non-SKILL markdown into steering/, copy assets as-is.
    steering_entries = []
    for item in sorted(skill_dir.iterdir()):
        if item.name == "SKILL.md":
            continue
        if item.name == ".claude-plugin":
            continue
        if item.is_file() and item.name.lower() in MARKDOWN_SKIP:
            continue
        if item.is_file() and item.suffix.lower() == ".md":
            steering_dir.mkdir(parents=True, exist_ok=True)
            dest = steering_dir / item.name
            content = rewrite_links(item.read_text(encoding="utf-8", errors="ignore"))
            dest.write_text(content, encoding="utf-8")
            steering_entries.append((item.stem, describe_steering(item)))
        else:
            # copy directories (scripts/, examples/, themes/, fonts, assets) and non-md files as-is
            dest = power_dir / item.name
            if item.is_dir():
                # also pull any nested .md into steering while keeping the dir for scripts/assets
                shutil.copytree(item, dest, dirs_exist_ok=True)
                for md in item.rglob("*.md"):
                    rel = md.relative_to(item)
                    steering_dir.mkdir(parents=True, exist_ok=True)
                    s_dest = steering_dir / (f"{item.name}-" + "-".join(rel.parts)).replace(".md", ".md")
                    s_dest.write_text(rewrite_links(md.read_text(encoding="utf-8", errors="ignore")), encoding="utf-8")
                    steering_entries.append((s_dest.stem, describe_steering(md)))
            else:
                shutil.copy2(item, dest)

    # License detection
    license_name = "See original repository (awesome-claude-skills)"
    for lic in list(skill_dir.glob("LICENSE*")) + list(skill_dir.glob("license*")):
        license_name = f"See bundled {lic.name} (from original skill)"
        break

    # Step 2/3/7: assemble POWER.md
    body = rewrite_links(body)
    fm_block = (
        "---\n"
        f'name: "{power_name}"\n'
        f'displayName: "{display}"\n'
        f'description: "{description.replace(chr(34), chr(39))}"\n'
        f'keywords: [{", ".join(json.dumps(k) for k in keywords)}]\n'
        f'author: "{AUTHOR}"\n'
        "---\n\n"
    )

    parts = [fm_block, body.rstrip(), ""]
    if steering_entries:
        parts.append("")
        parts.append(steering_list_section(sorted(set(steering_entries))))
    parts.append("")
    parts.append(attribution_section(src_name, license_name))
    (power_dir / "POWER.md").write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")

    # MCP integration: composio skills require the Rube MCP server.
    requires = fm.get("requires")
    needs_mcp = isinstance(requires, dict) and "mcp" in requires
    if needs_mcp:
        (power_dir / "mcp.json").write_text(json.dumps(MCP_JSON, indent=2) + "\n", encoding="utf-8")

    return {
        "name": power_name,
        "display": display,
        "description": description,
        "keywords": keywords,
        "steering": len(steering_entries),
        "mcp": needs_mcp,
    }


def load_meta(src_root: Path) -> dict:
    meta = {}
    mkt = src_root / "composio-skills" / ".claude-plugin" / "marketplace.json"
    if mkt.exists():
        try:
            data = json.loads(mkt.read_text(encoding="utf-8"))
            for p in data.get("plugins", []):
                src = (p.get("source") or "").lstrip("./").rstrip("/")
                key = src.split("/")[-1] if src else p.get("name")
                if key:
                    meta[key] = {"description": p.get("description"), "category": p.get("category")}
                if p.get("name"):
                    meta.setdefault(p["name"], {"description": p.get("description"), "category": p.get("category")})
        except Exception as e:
            print(f"warn: could not parse marketplace.json: {e}")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", choices=["composio", "top", "all"], default="all")
    args = ap.parse_args()

    src_root = Path(args.src).resolve()
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    meta = load_meta(src_root)

    skill_dirs = []
    for skill_md in src_root.rglob("SKILL.md"):
        if ".git" in skill_md.parts:
            continue
        d = skill_md.parent
        is_composio = "composio-skills" in d.parts
        if args.only == "composio" and not is_composio:
            continue
        if args.only == "top" and is_composio:
            continue
        skill_dirs.append(d)

    results, errors = [], []
    for d in sorted(skill_dirs):
        try:
            r = convert_skill(d, out_root, meta)
            if r:
                results.append(r)
        except Exception as e:
            errors.append((str(d), repr(e)))

    print(f"Converted {len(results)} powers into {out_root}")
    print(f"  with MCP (mcp.json): {sum(1 for r in results if r['mcp'])}")
    print(f"  with steering files: {sum(1 for r in results if r['steering'] > 0)}")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for p, e in errors[:20]:
            print("  ", p, e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
