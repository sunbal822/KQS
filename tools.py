"""Tools the SkillForge agent can call. Each returns a JSON-serialisable dict."""
import re
from pathlib import Path

OUTPUT_DIR = Path("output")
SKILLS_DIR = Path(__file__).parent / "skills"
MAX_CHARS = 4000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
SRC_EXT = {".py", ".js", ".ts", ".go", ".rs", ".java", ".md", ".rb", ".c", ".cpp", ".h"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _frontmatter(text):
    """Tiny frontmatter parser: returns (dict, body) or (None, text)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, m.group(2)


def skill_catalog():
    """Name + description of every bundled skill (progressive disclosure, level 1)."""
    out = []
    for p in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta, _ = _frontmatter(p.read_text())
        if meta:
            out.append({"name": meta.get("name"), "description": meta.get("description")})
    return out


def load_skill(repo, name):
    """Full SKILL.md of a bundled skill (progressive disclosure, level 2)."""
    if not NAME_RE.match(name):
        return {"status": "error", "error": "invalid skill name"}
    p = SKILLS_DIR / name / "SKILL.md"
    if not p.exists():
        return {"status": "error", "error": f"no bundled skill named {name}"}
    return {"status": "ok", "content": p.read_text()}


def _repo_files(repo):
    for p in sorted(Path(repo).rglob("*")):
        if p.is_file() and not (set(p.parts) & SKIP_DIRS):
            yield p


def inspect_repository(repo, path=None):
    """No path: file tree + README. With path: bounded file contents."""
    repo = Path(repo).resolve()
    if path:
        target = (repo / path).resolve()
        if repo not in target.parents and target != repo:
            return {"status": "error", "error": "path escapes repository"}
        if not target.is_file():
            return {"status": "error", "error": f"no such file: {path}"}
        return {"status": "ok", "path": path,
                "content": target.read_text(errors="replace")[:MAX_CHARS]}
    tree = [str(p.relative_to(repo)) for p in _repo_files(repo)][:80]
    readme = next((p for p in _repo_files(repo) if p.name.lower().startswith("readme")), None)
    return {"status": "ok", "files": tree,
            "readme": readme.read_text(errors="replace")[:MAX_CHARS] if readme else None}


def _clean_md(text):
    """Undo common small-model formatting slips: code fences, literal \\n, stray whitespace."""
    text = str(text)
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\n", "\n")
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip() + "\n"


def generate_skill(repo, name, skill_md):
    """Write output/<name>/SKILL.md exactly as the model wrote it."""
    if not re.match(r"^[A-Za-z0-9_-]+$", name or ""):
        return {"status": "error", "error": "directory name may only use letters, digits, - and _"}
    skill_md = _clean_md(skill_md)
    d = OUTPUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill_md, encoding="utf-8")
    return {"status": "ok", "written": str(d / "SKILL.md")}


def _repo_text(repo):
    chunks = []
    for p in _repo_files(repo):
        if p.suffix in SRC_EXT:
            chunks.append(p.read_text(errors="replace"))
    return "\n".join(chunks)


def check_skill(repo, name):
    """Return a list of error strings (empty list = pass)."""
    d = OUTPUT_DIR / name
    f = d / "SKILL.md"
    if not f.exists():
        return [f"{f} does not exist. Call generate_skill first."]
    errors = []
    meta, body = _frontmatter(f.read_text(encoding="utf-8"))
    if meta is None:
        start = f.read_text(encoding="utf-8")[:60].replace("\n", "\\n")
        return [f"SKILL.md has no frontmatter. Your file starts with: '{start}'. "
                f"The very first line must be exactly ---, then 'name: {name}', then 'description: <one sentence>', then ---, then the body. "
                "No code fences, no text before the first ---."]
    n, desc = meta.get("name", ""), meta.get("description", "")
    if not n:
        errors.append("Frontmatter is missing 'name'.")
    else:
        if not NAME_RE.match(n) or len(n) > 64:
            fixed = re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:64]
            errors.append(f"'name' is '{n}', which is invalid: use only lowercase letters, digits and single hyphens (no spaces, underscores or capitals). Set the frontmatter line to exactly 'name: {fixed}' and use '{fixed}' as the generate_skill name argument too.")
        if n != name:
            errors.append(f"'name' ({n}) must match the directory name ({name}).")
    if not desc:
        errors.append("Frontmatter is missing 'description'.")
    elif len(desc) > 1024:
        errors.append("'description' must be at most 1024 characters.")
    if len(body.strip()) < 100:
        errors.append("Body is too short: add concrete usage instructions.")
    # Grounding: every `code()` or `dotted.name` / `snake_case` span must exist in the repo.
    text = _repo_text(repo)
    root = Path(repo).resolve()
    names = {root.name, Path(str(repo)).name}
    for p in _repo_files(repo):
        names.update(p.resolve().relative_to(root).parts)
        names.add(p.stem)
    for span in set(re.findall(r"`([^`\n]+)`", body)):
        m = re.match(r"^([A-Za-z_][\w\.]*)(\(.*\))?$", span.strip())
        if not m:
            continue
        ident, call = m.group(1), m.group(2)
        if ident in names or ident.split(".")[0] in names:
            continue  # a file or folder name, not a function
        if call is None and "." not in ident:
            continue  # only check calls like f(x) and dotted names like mod.f
        last = ident.split(".")[-1]
        if last not in text:
            errors.append(f"Grounding: `{span}` is not found in the repository. "
                          "Either remove it, or if it is not a function write it without backticks.")
    return errors


def validate_skill(repo, name):
    errs = check_skill(repo, name)
    return {"status": "passed" if not errs else "failed", "errors": errs}


# name -> (function, required args, description shown to the model)
REGISTRY = {
    "load_skill": (load_skill, ["name"], "Load the full text of a bundled skill. args: name"),
    "inspect_repository": (inspect_repository, [], "Without args: file tree + README. args: path (optional) to read one file"),
    "generate_skill": (generate_skill, ["name", "skill_md"], "Write output/<name>/SKILL.md. args: name, skill_md (the full file text incl. frontmatter)"),
    "validate_skill": (validate_skill, ["name"], "Check format and grounding of output/<name>. args: name"),
    "finish": (None, ["name"], "Ask to stop. The harness re-validates; you only stop if it passes. args: name"),
}