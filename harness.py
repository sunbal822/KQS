"""SkillForge: an open-weight agent loop that writes, validates and repairs Agent Skills.

build context -> call model -> run tool -> append result -> loop (bounded).
Success is decided by the harness (validate_skill), never by the model's claim.
"""
import argparse, json, os, re, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import tools

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("FORGE_MODEL", "qwen3:8b")
MAX_STEPS = int(os.environ.get("FORGE_MAX_STEPS", "8"))
PARSE_RETRIES = 2


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
Keep SKILL.md SHORT (under 150 words). The skill_md argument must be the raw file text and start EXACTLY like this (no code fences):
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
                       "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": 800}}).encode()
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


def run(repo, task, log=print):
    messages = [{"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": f"Repository: {repo}\nTask: {task}\nBegin."}]
    trace = []
    last_name = None
    for step in range(1, MAX_STEPS + 1):
        action, raw = decide(messages)
        if action is None:
            log(f"[{step}] model never produced valid JSON; stopping")
            break
        if not isinstance(action.get("arguments"), dict):
            action["arguments"] = {}
        args = action["arguments"]
        if action["action"] in ("generate_skill", "validate_skill") and args.get("name"):
            last_name = args["name"]
        if action["action"] == "finish" and not args.get("name") and last_name:
            args["name"] = last_name  # model forgot the argument; use the last skill it worked on
        result = execute(action, repo)
        log(f"[{step}] {action['action']} -> {result.get('status')}"
            + (f" {result.get('errors')}" if result.get("errors") else "")
            + (f" {result.get('error')}" if result.get("error") else ""))
        trace.append({"step": step, "action": action, "result": result})
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": "TOOL RESULT: " + json.dumps(result)[:6000]})
        if action["action"] == "finish" and result.get("status") == "passed":
            tools.OUTPUT_DIR.mkdir(exist_ok=True)
            (tools.OUTPUT_DIR / "trace.json").write_text(json.dumps(trace, indent=2))
            log(f"SUCCESS: skill verified in output/{action['arguments']['name']}")
            return True
    tools.OUTPUT_DIR.mkdir(exist_ok=True)
    (tools.OUTPUT_DIR / "trace.json").write_text(json.dumps(trace, indent=2))
    log("FAILED: step budget exhausted or no verified skill")
    return False


def resolve_repo(src):
    if src.startswith(("http://", "https://", "git@")):
        dest = tempfile.mkdtemp(prefix="forge-")
        subprocess.run(["git", "clone", "--depth", "1", src, dest], check=True)
        return dest
    return src


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SkillForge: generate and verify an Agent Skill for a repo")
    ap.add_argument("repo", help="local path or git URL")
    ap.add_argument("--task", default="Write a skill that teaches an agent to use this library")
    a = ap.parse_args()
    sys.exit(0 if run(resolve_repo(a.repo), a.task) else 1)