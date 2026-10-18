"""Run: PYTHONPATH=. python tests/test_memory.py   (no model needed)"""
import json, tempfile, pathlib
import harness, memory, tools

tmp = pathlib.Path(tempfile.mkdtemp()) / "mem.json"
memory.MEMORY_FILE = tmp

good = "---\nname: textstats\ndescription: Word stats with the textstats library. Use for text statistics.\n---\n# textstats\nCall `word_count(text)` and `top_words(text, n)`.\n```python\nword_count('a b')\n```\nThis is enough body text to pass the length rule.\n"
unclosed = good.rstrip().rsplit("```", 1)[0]  # drops closing fence
nofn = "---\nname: textstats\ndescription: Word stats.\n---\n# textstats\nThis skill mentions nothing from the library at all, only general words here and there okay.\n"

def run_with(script, use_memory=True):
    it = iter(script)
    harness.call_model = lambda m: (seen.append(m), next(it))[1]
    return harness.run("demo_repo", "t", use_memory=use_memory)

A = lambda a, **k: json.dumps({"action": a, "arguments": k})
seen = []
# Run 1: unclosed fence, then no functions, then good -> lessons saved
ok = run_with([A("inspect_repository"), A("generate_skill", name="textstats", skill_md=unclosed),
               A("validate_skill", name="textstats"), A("generate_skill", name="textstats", skill_md=nofn),
               A("validate_skill", name="textstats"), A("generate_skill", name="textstats", skill_md=good),
               A("validate_skill", name="textstats"), A("finish", name="textstats")])
assert ok, "run 1 should succeed"
lessons = memory.retrieve()
assert any("code fence" in l for l in lessons) and any("real function" in l for l in lessons), lessons
print("saved lessons:", lessons)

# Run 2: lessons must be injected into the first user message
seen.clear()
ok = run_with([A("generate_skill", name="textstats", skill_md=good), A("validate_skill", name="textstats"), A("finish", name="textstats")])
first_user = [m for m in seen[0] if m["role"] == "user"][0]["content"]
assert "Lessons from previous runs" in first_user and "Close every code fence" in first_user
print("lessons injected into context: OK")

# Run 3: --no-memory must not inject
seen.clear()
run_with([A("generate_skill", name="textstats", skill_md=good), A("validate_skill", name="textstats"), A("finish", name="textstats")], use_memory=False)
assert "Lessons" not in [m for m in seen[0] if m["role"] == "user"][0]["content"]
print("no-memory mode: OK")
print("ALL PASSED")
