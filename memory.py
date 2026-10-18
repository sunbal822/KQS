"""Experience memory: lessons from validation failures that a later repair fixed.

Stored as JSON, retrieved into the model's context at the start of a new run.
This is memory, not weight training: the model itself never changes.
"""
import json
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "memory.json"

RULES = [  # (error prefix, reusable lesson)
    ("'name' is", "The 'name' must be lowercase letters, digits and hyphens only, and equal the directory name."),
    ("'name' (", "The frontmatter 'name' must equal the generate_skill name argument."),
    ("SKILL.md has no frontmatter", "SKILL.md must start with a line '---', then name and description, then '---'. No code fences."),
    ("Grounding:", "Mention only functions that exist in the repo; copy names from the api list of inspect_repository."),
    ("Code block is not closed", "Close every code fence with ``` before finishing the file."),
    ("The skill mentions none", "Name at least one real function from the repo's api list in backticks."),
    ("Body is too short", "Write at least a few sentences with a concrete usage example."),
]


def lesson_for(error):
    for prefix, lesson in RULES:
        if error.startswith(prefix):
            return lesson
    return error[:160]


def load(path=None):
    p = Path(path or MEMORY_FILE)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def record(errors, path=None):
    """Store lessons for errors that were fixed in this run."""
    p = Path(path or MEMORY_FILE)
    items = load(p)
    for e in errors:
        text = lesson_for(e)
        for it in items:
            if it["lesson"] == text:
                it["count"] += 1
                break
        else:
            items.append({"lesson": text, "count": 1})
    p.write_text(json.dumps(items, indent=2), encoding="utf-8")


def retrieve(limit=5, path=None):
    items = sorted(load(path), key=lambda i: -i["count"])
    return [i["lesson"] for i in items[:limit]]
