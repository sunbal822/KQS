# SkillForge

An open-weight agent harness that **writes, validates, repairs and remembers** Agent Skills for code repositories.
Built for the Hacktoberfest Hack Day Lahore x Fluxxion "Best Open-Source AI Project" challenge
(model harness + agent skill angles).

## How it works

```
build context -> call open-weight model -> model picks a tool -> run tool -> append result -> loop
```

- **Model:** any open-weight model served by [Ollama](https://ollama.com). Tested with `gemma3:4b`
  (set with `FORGE_MODEL`, default `qwen3:8b`).
- **Context builder:** system prompt + tool list + skill catalog (name and description only) + lessons from past runs + every tool result.
- **Progressive disclosure:** the model sees only skill names/descriptions first and calls `load_skill` to read a full `SKILL.md`.
- **Works on any repo:** `inspect_repository` builds a compact overview of an unfamiliar project: package metadata (`package.json`, `pyproject.toml`, `go.mod`), key files ranked by importance (tests, docs and dotfiles pushed down), a README excerpt, and a public API list (Python via `ast`; JavaScript/TypeScript, Go and Rust via patterns). Functions that the README mentions are ranked first, with a per-file cap so one file cannot fill the list.
- **Tools:** `load_skill`, `inspect_repository`, `generate_skill`, `validate_skill`, `finish`.
- **Validation (deterministic):** frontmatter, `name` rules, `name` equals directory, description length, body length,
  unclosed code blocks, at least one real function mentioned, and a **grounding check** that every `` `function()` `` the skill mentions exists in the repo. Coverage (how many public functions are mentioned) is reported.
- **Error feedback:** errors are returned to the model with the exact fix (for example the corrected name), so small models can repair themselves.
- **Memory:** when a validation error is later fixed in the same run, a short lesson is saved to `memory.json`
  and loaded into the context of future runs. This is experience memory, not weight training. Use `--no-memory` to turn it off.
- **Loop control:** the model chooses the next action; tool names and arguments are checked; malformed JSON is retried; the step budget is bounded (`FORGE_MAX_STEPS`, default 8). Success is decided by the harness, which re-runs validation on `finish`; the model's claim is never trusted.
- **Model-output cleanup:** code fences, literal `\n` and stray whitespace in the model's file are normalised.

## Run

```bash
ollama pull gemma3:4b
set FORGE_MODEL=gemma3:4b        # Windows cmd. On Linux/macOS: export FORGE_MODEL=gemma3:4b
python harness.py demo_repo
# any GitHub repo, as a URL or owner/repo:
python harness.py psf/requests
python harness.py https://github.com/spf13/cobra
# any local folder:
python harness.py C:\path\to\project
# without memory:
python harness.py demo_repo --no-memory
```

The generated skill is written to `output/<name>/SKILL.md` and the action trace to `output/trace.json`.
A real run is saved in `examples/`. No third-party Python packages are required (standard library only).

## Tests (no model needed)

```bash
PYTHONPATH=. python tests/test_loop.py      # malformed JSON, hallucinated function, bad name -> repair
PYTHONPATH=. python tests/test_memory.py    # lessons are saved, then injected into the next run
```

On Windows cmd: `set PYTHONPATH=.` first.

## What is original

All code is written for this project: the loop, context builder, tool registry, argument validation, JSON retry,
skill loader, validator, grounding check, API extractor and memory. `skills/skillforge/SKILL.md` is the bundled skill in the Agent Skill format.

## Limitations

Small models (a 4B model was used) are slow on CPU, and big repos make the first model call slower because the overview is larger (context is set with `FORGE_CTX`, default 8192; skill length with `FORGE_MAX_TOKENS`, default 1000). The API extractor understands Python, JavaScript/TypeScript, Go and Rust; for other languages the model relies on the README and `inspect_repository(path=...)`. Grounding checks that named functions exist but does not run the skill; there is no second-agent task evaluation yet.

## License

MIT
