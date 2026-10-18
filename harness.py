"""SkillForge: an open-weight agent loop that writes, validates and repairs Agent Skills.

build context -> call model -> run tool -> append result -> loop (bounded).
Success is decided by the harness (validate_skill), never by the model's claim.
"""
import argparse, json, os, re, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import tools
import memory

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("FORGE_MODEL", "qwen3:8b")
MAX_STEPS = int(os.environ.get("FORGE_MAX_STEPS", "8"))
PARSE_RETRIES = 2
ALIASES = {"name": ["skill_name", "skill", "directory", "dir", "folder", "skill_dir"],
           "skill_md": ["content", "skill_content", "markdown", "text", "skill_text", "file_content"]}
CTX = int(os.environ.get("FORGE_CTX", "8192"))
MAX_TOKENS = int(os.environ.get("FORGE_MAX_TOKENS", "1000"))


def build_system_prompt():
    tool_lines = "\n".join(f"- {n}: {d}" for n, (_, _, d) in tools.REGISTRY.items())
    catalog = "\n".join(f"- {s['name']}: {s['description']}" for s in tools.skill_catalog())
    return f"""You are SkillForge, an agent that writes an Agent Skill (a SKILL.md folder) for a code repository.
Work in steps. Each reply must be ONE JSON object and nothing else:
{{"action": "<tool name>", "reason": "<short>", "arguments": {{...}}}}

Tools:
{tool_lines}

Bundled skills (load one with load_skill when relevant):
{catalog}

Rules: inspect the repo before writing. After generate_skill, call validate_skill. If it fails, fix the
errors and generate_skill again. Call finish only after validate_skill passed.
The skill must teach another agent how to USE this project: what it is for, how to install or run it, the main functions or commands (real names from the api list or README), one short example, and pitfalls. Keep it under 250 words. The skill_md argument must be the raw file text and start EXACTLY like this (no code fences):
---
name: my-skill-name
description: One sentence saying what it does and when to use it.
---
# Title
Usage example and main functions.
The name must be lowercase with hyphens only, and the generate_skill name argument must equal it."""


def call_model(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False,
                       "format": "json", "keep_alive": "30m",
                       "options": {"temperature": 0.2, "num_ctx": CTX, "num_predict": MAX_TOKENS}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", body, {"Content-Type": "application/json"})
    t0 = time.time()
    print("  ...asking model", end="", flush=True)
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.load(r)["message"]["content"]
    print(f" ({time.time() - t0:.0f}s)")
    return out


def parse_action(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    obj = json.loads(text)
    if not isinstance(obj, dict) or "action" not in obj:
        raise ValueError("JSON must contain an 'action' key")
    obj.setdefault("arguments", {})
    return obj


def decide(messages):
    """Call the model; on malformed output, tell it what was wrong and retry."""
    for attempt in range(PARSE_RETRIES + 1):
        raw = call_model(messages)
        try:
            return parse_action(raw), raw
        except Exception as e:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Invalid reply ({e}). Reply with ONE valid JSON object."})
    return None, ""


def execute(action, repo):
    name, args = action["action"], action.get("arguments") or {}
    if name not in tools.REGISTRY:
        return {"status": "error", "error": f"unknown tool '{name}'. Allowed: {list(tools.REGISTRY)}"}
    fn, required, _ = tools.REGISTRY[name]
    missing = [a for a in required if a not in args]
    if missing:
        return {"status": "error", "error": f"missing arguments: {missing}"}
    if name == "finish":
        return tools.validate_skill(repo, args["name"])  # harness verifies, not the model
    allowed = set(required) | {"path"}
    try:
        return fn(repo, **{k: v for k, v in args.items() if k in allowed})
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def run(repo, task, log=print, use_memory=True):
    lessons = memory.retrieve() if use_memory else []
    note = ("\nLessons from previous runs (avoid these mistakes):\n- " + "\n- ".join(lessons)) if lessons else ""
    if lessons:
        log(f"memory: {len(lessons)} lesson(s) loaded into context")
    messages = [{"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": f"Repository: {repo}\nTask: {task}\nUse the skill name: {slug(repo)}{note}\nBegin."}]
    trace = []
    last_name = slug(repo)  # default until the model names its own skill
    pending = []  # errors seen since the last pass; become lessons once fixed
    for step in range(1, MAX_STEPS + 1):
        action, raw = decide(messages)
        if action is None:
            log(f"[{step}] model never produced valid JSON; stopping")
            break
        if not isinstance(action.get("arguments"), dict):
            action["arguments"] = {}
        args = action["arguments"]
        for want, aliases in ALIASES.items():  # small models often rename arguments
            if not args.get(want):
                for a in aliases:
                    if args.get(a):
                        args[want] = args[a]
                        break
        if action["action"] in ("generate_skill", "validate_skill", "finish"):
            if args.get("name"):
                last_name = args["name"]
            elif last_name:
                args["name"] = last_name  # model forgot it; use the suggested/last skill name
        result = execute(action, repo)
        log(f"[{step}] {action['action']} -> {result.get('status')}"
            + (f" {result.get('errors')}" if result.get("errors") else "")
            + (f" {result.get('error')}" if result.get("error") else ""))
        if result.get("coverage"):
            log(f"    coverage: {result['coverage']}")
        if action["action"] in ("validate_skill", "finish"):
            if result.get("status") == "failed":
                pending.extend(e for e in result.get("errors", []) if e not in pending)
            elif result.get("status") == "passed" and pending and use_memory:
                memory.record(pending)
                log(f"memory: saved {len(pending)} lesson(s) from fixed errors")
                pending = []
        trace.append({"step": step, "action": action, "result": result})
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": "TOOL RESULT: " + json.dumps(result)[:8000]})
        if action["action"] == "finish" and result.get("status") == "passed":
            tools.OUTPUT_DIR.mkdir(exist_ok=True)
            (tools.OUTPUT_DIR / "trace.json").write_text(json.dumps(trace, indent=2))
            log(f"SUCCESS: skill verified in output/{action['arguments']['name']}")
            return True
    tools.OUTPUT_DIR.mkdir(exist_ok=True)
    (tools.OUTPUT_DIR / "trace.json").write_text(json.dumps(trace, indent=2))
    log("FAILED: step budget exhausted or no verified skill")
    return False


def slug(repo):
    base = Path(str(repo).rstrip("/\\")).name
    base = re.sub(r"\.git$", "", base)
    s = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return (s[:50] or "project") + "-usage"


def resolve_repo(src):
    """Local path, full git URL, or owner/repo shorthand -> local directory."""
    if not Path(src).exists() and re.match(r"^[\w.-]+/[\w.-]+$", src):
        src = f"https://github.com/{src}"
    if src.startswith(("http://", "https://", "git@")):
        name = re.sub(r"\.git$", "", src.rstrip("/").split("/")[-1])
        dest = str(Path(tempfile.mkdtemp(prefix="forge-")) / name)
        print(f"cloning {src} ...")
        r = subprocess.run(["git", "clone", "--depth", "1", "-q", src, dest])
        if r.returncode != 0:
            sys.exit("git clone failed. Check the URL and that git is installed (git --version).")
        return dest
    if not Path(src).is_dir():
        sys.exit(f"'{src}' is not a folder, a git URL or an owner/repo name.")
    return src


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SkillForge: generate and verify an Agent Skill for a repo")
    ap.add_argument("repo", help="local folder, git URL, or owner/repo")
    ap.add_argument("--task", default="Write a skill that teaches an agent to use this project")
    ap.add_argument("--no-memory", action="store_true", help="do not load or save lessons")
    a = ap.parse_args()
    sys.exit(0 if run(resolve_repo(a.repo), a.task, use_memory=not a.no_memory) else 1)
