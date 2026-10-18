"""Tools the SkillForge agent can call. Each returns a JSON-serialisable dict."""
import ast
import builtins
import json
import os
import re
from pathlib import Path

OUTPUT_DIR = Path("output")
SKILLS_DIR = Path(__file__).parent / "skills"
MAX_CHARS = 4000
README_CHARS = 2000
MAX_FILE_BYTES = 300_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", "target",
             "vendor", "site-packages", ".next", ".tox", ".mypy_cache", ".pytest_cache", "coverage"}
SRC_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".rs", ".java", ".md", ".rst", ".rb", ".c", ".cpp", ".h"}
API_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".rs"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Names that are normal in skill text but never defined in the repo itself.
KNOWN_EXTERNAL = set(dir(builtins)) | {"console", "JSON", "Math", "Object", "Array", "Promise", "Date", "String",
                                       "Number", "Map", "Set", "os", "sys", "re", "json", "fs", "path", "np", "pd", "plt"}

JS_PATTERNS = [
    re.compile(r"export\s+(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\(([^)]*)\)"),
    re.compile(r"export\s+(?:default\s+)?class\s+(\w+)"),
    re.compile(r"export\s+const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
    re.compile(r"(?:module\.)?exports\.(\w+)\s*="),
]
GO_PATTERN = re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)\s*\(([^)]*)\)", re.M)
RS_PATTERN = re.compile(r"pub\s+(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)")


# ---------- skill files ----------
def _frontmatter(text):
    """Tiny frontmatter parser: returns (dict, body) or (None, text)."""
    m = re.match(r"^---[ \t]*\n?(.*?)\n---[ \t]*\n?(.*)$", text, re.S)
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
        meta, _ = _frontmatter(p.read_text(encoding="utf-8"))
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
    return {"status": "ok", "content": p.read_text(encoding="utf-8")}


# ---------- repository reading ----------
def _repo_files(repo):
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for f in sorted(files):
            yield Path(root) / f


def _priority(rel):
    """Lower = more important to show the model first."""
    parts = [x.lower() for x in rel.parts]
    name = parts[-1]
    is_test = (any(x in {"test", "tests", "spec", "specs", "__tests__", "testing"} for x in parts)
               or name.startswith("test_") or Path(name).stem in {"test", "tests"} or name.endswith("_test.go") or ".test." in name or ".spec." in name)
    if is_test:
        return 6
    if len(parts) == 1 and name.startswith("readme"):
        return 0
    if len(parts) == 1 and name in {"pyproject.toml", "package.json", "setup.py", "setup.cfg", "cargo.toml", "go.mod"}:
        return 1
    if any(x.startswith(".") for x in parts) or Path(name).suffix not in SRC_EXT | {".toml", ".json", ".cfg", ".yaml", ".yml"}:
        return 7
    if parts[0] in {"docs", "doc", "examples", "example"}:
        return 2
    if parts[0] in {"src", "lib"} or len(parts) <= 2:
        return 3
    return 4


def _rel(root, p):
    try:
        return p.resolve().relative_to(root)
    except ValueError:
        return Path(p.name)


def repo_meta(repo):
    """Name/description/entry points from package.json or pyproject.toml, if present."""
    root, meta = Path(repo), {}
    try:
        pj = root / "package.json"
        if pj.exists():
            d = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
            for k in ("name", "description", "bin", "main"):
                if k in d:
                    meta[k] = d[k]
            if "scripts" in d:
                meta["npm_scripts"] = list(d["scripts"])[:10]
    except Exception:
        pass
    try:
        gm = root / "go.mod"
        if gm.exists():
            m = re.search(r"^module\s+(\S+)", gm.read_text(encoding="utf-8", errors="replace"), re.M)
            if m:
                meta["go_module"] = m.group(1)
    except Exception:
        pass
    try:
        pp = root / "pyproject.toml"
        if pp.exists():
            import tomllib
            d = tomllib.loads(pp.read_text(encoding="utf-8", errors="replace")).get("project", {})
            for k in ("name", "description", "requires-python", "scripts"):
                if k in d:
                    meta[k] = d[k]
    except Exception:
        pass
    return meta


def _extract(p, text):
    """Public functions/classes found in one source file."""
    out = []
    if p.suffix == ".py":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return out
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
                args = ", ".join(a.arg for a in n.args.args if a.arg not in ("self", "cls"))
                out.append(f"{n.name}({args})")
            elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
                out.append(f"{n.name} (class)")
        return out
    pats = JS_PATTERNS if p.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs"} else \
        [GO_PATTERN] if p.suffix == ".go" else [RS_PATTERN] if p.suffix == ".rs" else []
    for pat in pats:
        for m in pat.finditer(text):
            args = " ".join(m.group(2).split())[:60] if m.lastindex and m.lastindex >= 2 else ""
            out.append(f"{m.group(1)}({args})" if args or "class" not in m.group(0) else f"{m.group(1)} (class)")
    return out


def api_summary(repo, limit=40, boost=None, per_file=None):
    """Public API entries as 'name(args)  [path]'. Functions the README mentions come first,
    then the most central files; per_file caps entries from one file so the list stays varied."""
    root = Path(repo).resolve()
    boost = boost or set()
    items, seen = [], set()
    for p in _repo_files(repo):
        if p.suffix not in API_EXT:
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
            rel = _rel(root, p)
            pr = _priority(rel)
            if pr in (2, 6, 7):  # docs/examples, tests, junk: not the project's API
                continue
            for entry in _extract(p, p.read_text(encoding="utf-8", errors="replace")):
                key = re.match(r"\w+", entry)
                key = key.group(0) if key else entry
                if key in seen:
                    continue
                seen.add(key)
                items.append((key not in boost, pr, len(rel.parts), rel.as_posix(), f"{entry}  [{rel.as_posix()}]"))
        except OSError:
            continue
        if len(items) > 4000:
            break
    items.sort(key=lambda t: t[:4])
    out, count = [], {}
    for _, _, _, rel, text in items:
        if per_file and count.get(rel, 0) >= per_file:
            continue
        count[rel] = count.get(rel, 0) + 1
        out.append(text)
        if len(out) >= limit:
            break
    return out


def inspect_repository(repo, path=None):
    """No path: overview (metadata, key files, public API, README). With path: one file."""
    root = Path(repo).resolve()
    if path:
        target = (root / path).resolve()
        if root not in target.parents and target != root:
            return {"status": "error", "error": "path escapes repository"}
        if not target.is_file():
            return {"status": "error", "error": f"no such file: {path}. Pick a path from key_files or api."}
        return {"status": "ok", "path": path,
                "content": target.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS]}
    files = [_rel(root, p) for p in _repo_files(repo)]
    key = [r for r in sorted(files, key=lambda r: (_priority(r), len(r.parts), r.as_posix())) if _priority(r) < 6][:30]
    readme = next((p for p in _repo_files(repo) if p.name.lower().startswith("readme")), None)
    readme_text = readme.read_text(encoding="utf-8", errors="replace") if readme else ""
    return {"status": "ok", "meta": repo_meta(repo),
            "top_level": sorted({r.parts[0] for r in files if not r.parts[0].startswith(".")})[:25],
            "key_files": [r.as_posix() for r in key],
            "api": api_summary(repo, 40, boost=set(re.findall(r"\w+", readme_text)), per_file=6),
            "readme": readme_text[:README_CHARS] if readme else None}


# ---------- generating and checking ----------
def _clean_md(text):
    """Undo common small-model formatting slips: code fences, literal \\n, stray whitespace."""
    text = str(text)
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\n", "\n")
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    text = text.strip()
    text = re.sub(r"^---[ \t]*(?=\S)", "---\n", text)          # '---name: x' -> '---' newline 'name: x'
    text = re.sub(r"^(---\n.*?)[ \t]*---[ \t]*(?=#)", r"\1\n---\n", text, count=1, flags=re.S)  # 'text.---# Title'
    return text.strip() + "\n"


def generate_skill(repo, name, skill_md):
    """Write output/<name>/SKILL.md."""
    if not re.match(r"^[A-Za-z0-9_-]+$", name or ""):
        return {"status": "error", "error": "directory name may only use letters, digits, - and _"}
    skill_md = _clean_md(skill_md)
    d = OUTPUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill_md, encoding="utf-8")
    return {"status": "ok", "written": str(d / "SKILL.md")}


def _repo_text(repo):
    chunks, total = [], 0
    for p in _repo_files(repo):
        if p.suffix in SRC_EXT:
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            chunks.append(t)
            total += len(t)
            if total > 15_000_000:
                break
    return "\n".join(chunks)


def _api_names(repo):
    return {re.match(r"\w+", s).group(0) for s in api_summary(repo, 4000) if re.match(r"\w+", s)}


def check_skill(repo, name):
    """Return a list of error strings (empty list = pass)."""
    f = OUTPUT_DIR / name / "SKILL.md"
    if not f.exists():
        return [f"{f} does not exist. Call generate_skill first."]
    errors = []
    meta, body = _frontmatter(f.read_text(encoding="utf-8"))
    if meta is None:
        start = f.read_text(encoding="utf-8")[:60].replace("\n", "\\n")
        return [f"SKILL.md has no frontmatter. Your file starts with: '{start}'. "
                f"The very first line must be exactly ---, then 'name: {name}', then 'description: <one sentence>', "
                "then ---, then the body. No code fences, no text before the first ---."]
    n, desc = meta.get("name", ""), meta.get("description", "")
    if not n:
        errors.append("Frontmatter is missing 'name'.")
    else:
        if not NAME_RE.match(n) or len(n) > 64:
            fixed = re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:64]
            errors.append(f"'name' is '{n}', which is invalid: use only lowercase letters, digits and single hyphens "
                          f"(no spaces, underscores or capitals). Set the frontmatter line to exactly 'name: {fixed}' "
                          f"and use '{fixed}' as the generate_skill name argument too.")
        if n != name:
            errors.append(f"'name' ({n}) must match the directory name ({name}).")
    if not desc:
        errors.append("Frontmatter is missing 'description'.")
    elif len(desc) > 1024:
        errors.append("'description' must be at most 1024 characters.")
    if len(body.strip()) < 100:
        errors.append("Body is too short: add concrete usage instructions.")
    if body.count("```") % 2 == 1:
        errors.append("Code block is not closed: end it with ``` on its own line.")
    words = set(re.findall(r"\w+", body))
    api = _api_names(repo)
    if api and not (api & words):
        errors.append("The skill mentions none of the repo's functions. Use names from the api list of inspect_repository.")
    # Grounding: every `call()` or `dotted.name` must exist in the repo.
    text = _repo_text(repo)
    root = Path(repo).resolve()
    names = {root.name, Path(str(repo)).name}
    for p in _repo_files(repo):
        names.update(_rel(root, p).parts)
        names.add(p.stem)
    bad = []
    for span in sorted(set(re.findall(r"`([^`\n]+)`", body))):
        m = re.match(r"^([A-Za-z_$][\w\.$]*)(\(.*\))?$", span.strip())
        if not m:
            continue
        ident, call = m.group(1), m.group(2)
        first = ident.split(".")[0]
        if ident in names or first in KNOWN_EXTERNAL:
            continue  # a file/folder name, or a builtin/common library: not a repo function
        if call is None and "." not in ident:
            continue
        if ident.split(".")[-1] not in text:
            bad.append(span)
    for span in bad[:6]:
        errors.append(f"Grounding: `{span}` is not found in the repository. "
                      "Either remove it, or if it is not a function write it without backticks.")
    return errors


def validate_skill(repo, name):
    errs = check_skill(repo, name)
    res = {"status": "passed" if not errs else "failed", "errors": errs}
    f = OUTPUT_DIR / name / "SKILL.md"
    api = _api_names(repo)
    if f.exists() and api:
        words = set(re.findall(r"\w+", f.read_text(encoding="utf-8")))
        res["coverage"] = f"{len(api & words)}/{len(api)} public functions mentioned"
    return res


# name -> (function, required args, description shown to the model)
REGISTRY = {
    "load_skill": (load_skill, ["name"], "Load the full text of a bundled skill. args: name"),
    "inspect_repository": (inspect_repository, [], "Without args: overview (metadata, key_files, public api list, README). args: path (optional) to read one file"),
    "generate_skill": (generate_skill, ["name", "skill_md"], "Write output/<name>/SKILL.md. args: name, skill_md (the full file text incl. frontmatter)"),
    "validate_skill": (validate_skill, ["name"], "Check format and grounding of output/<name>. args: name"),
    "finish": (None, ["name"], "Ask to stop. The harness re-validates; you only stop if it passes. args: name"),
}
