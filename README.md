# SkillForge

An open-weight agent harness that **writes, validates and repairs Agent Skills** for code repositories.
Built for the Hacktoberfest Hack Day Lahore x Fluxxion "Best Open-Source AI Project" challenge
(model harness + agent skill angles).

## How it works

```
build context -> call open-weight model -> model picks a tool -> run tool -> append result -> loop
```

- **Model:** any open-weight model served by [Ollama](https://ollama.com) (default `qwen3:8b`, set with `FORGE_MODEL`).
- **Context builder:** system prompt + tool list + skill catalog (name and description only) + every tool result.
- **Progressive disclosure:** the model sees only skill names/descriptions at first and calls `load_skill` to read a full `SKILL.md`.
- **Tools:** `load_skill`, `inspect_repository`, `generate_skill`, `validate_skill`, `finish`.
- **Validation (deterministic):** frontmatter, `name` rules, `name` == directory, description length, body length, and a **grounding check** that every `` `function()` `` the skill mentions exists in the repo.
- **Loop control:** the model chooses the next action; arguments and tool names are checked; JSON parse failures are retried; step budget is bounded (`FORGE_MAX_STEPS`, default 8). Success is decided by the harness re-running validation on `finish`, never by the model's claim.

## Run

```bash
ollama pull qwen3:8b
python harness.py demo_repo --task "Teach an agent to use textstats"
# or a GitHub repo:
python harness.py https://github.com/user/repo
```

The generated skill is written to `output/<name>/SKILL.md` and the full action trace to `output/trace.json`.

No third-party Python packages are required (standard library only).

## Test (no model needed)

```bash
PYTHONPATH=. python tests/test_loop.py
```

Uses a scripted fake model that makes malformed JSON, a hallucinated function and a name mismatch, then repairs them.

## What is original

All code is written for this project: the loop, context builder, tool registry, argument validation, JSON retry,
skill loader, validator and grounding check. `skills/skillforge/SKILL.md` is the bundled skill following the Agent Skill format.

## License

MIT
