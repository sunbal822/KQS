---
name: skillforge
description: Guidelines for writing a valid, grounded Agent Skill (SKILL.md) for a code repository. Use when asked to generate a skill from a library or project.
---

# Writing a skill for a repository

## File format
- The skill lives in a folder; the folder name equals the `name` field.
- SKILL.md starts with YAML frontmatter between `---` lines, containing `name` and `description`.
- `name`: lowercase letters, digits, single hyphens, max 64 characters.
- `description`: say what the skill does AND when to use it. Max 1024 characters.

## Content rules
1. Inspect the README and source files first. Never invent functions.
2. Mention only functions, classes and commands that exist in the repo, written in backticks, e.g. `word_count(text)`.
3. Include: when to use it, a minimal usage example, the main functions with their parameters, and common pitfalls.
4. Keep it short and concrete. Prefer one working example over long prose.

## Repair loop
If validation fails, read each error, fix exactly that problem, and regenerate. Do not restate the same file unchanged.
