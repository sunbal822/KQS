# 🛠️ SkillForge

**An open-weight agent harness that writes, validates, repairs, and remembers Agent Skills for code repositories.**

🏆 *Built for the Hacktoberfest Hack Day Lahore x Fluxxion "Best Open-Source AI Project" challenge.*

## 📖 What is SkillForge?

SkillForge is a self-healing agent harness that enables local open-weight AI models to autonomously generate, validate, and refine Agent Skills for any codebase.

By utilizing intelligent context building, progressive disclosure, and an experience-based memory system, SkillForge allows smaller models to execute complex, repository-grounded tasks with high precision. It builds a compact overview of unfamiliar projects, interacts through a robust tool registry, and validates outputs deterministically.

## 🧠 Model Support & Requirements

* **Primary Engine:** Any open-weight model served by [Ollama](https://ollama.com/).

* **Tested Model:** Extensively tested and optimized for `gemma3:4b`.

* **Default Model:** `qwen3:8b` (can be overridden via environment variables).

## 🚀 How to Run the Harness

**Prerequisites:** Python 3.x (Standard library only—no external packages required) and Ollama running locally.

1. **Pull the Model:**

   ```bash
   ollama pull gemma3:4b
   ```

2. **Set the Environment Variable:**

   * **Windows (cmd):** `set FORGE_MODEL=gemma3:4b`
   * **Linux/macOS:** `export FORGE_MODEL=gemma3:4b`

3. **Run the Harness:**
   Point SkillForge at any GitHub repository (URL or owner/repo) or a local folder. 
   *(Note: When provided with a remote GitHub link or `owner/repo` format, SkillForge automatically clones the repository locally before proceeding with the inspection and analysis loop.)*

   ```bash
   # GitHub repository (owner/repo) - clones locally first
   python harness.py psf/requests
   
   # Full GitHub URL - clones locally first
   python harness.py https://github.com/spf13/cobra
   
   # Local directory - processes directly
   python harness.py C:\path\to\project
   
   # Run without memory injection
   python harness.py demo_repo --no-memory
   ```

   *Generated skills are written to `output/<name>/SKILL.md` and the action trace to `output/trace.json`.*

## 📂 Agent Skill Specifications

SkillForge natively generates and strictly validates skills against the required standard. Judges reviewing the `output/` or `examples/` folders will find that every skill adheres to the following:

1. **Naming Convention:** The skill name is strictly `lowercase-with-hyphens` and identically matches its parent folder name.

2. **Contextual Description:** The description explicitly defines exactly **what the skill does** and **when to use it**.

3. **Validation:** The harness checks for unclosed code blocks, description lengths, and cross-references every mentioned `function()` to guarantee it actually exists in the target repository (Grounding Check).

## 🛠️ Harness: Original Contributions & Modifications

As per the Hacktoberfest submission requirements, here is the breakdown of what was built and modified for this specific project:

* **100% Original Implementation:** All core components were written specifically for this project from scratch. This includes:

  * The autonomous loop and step-budget controller.
  * The context builder and progressive disclosure system.
  * The tool registry (`load_skill`, `inspect_repository`, `generate_skill`, `validate_skill`, `finish`).
  * Argument validation and JSON auto-retry mechanics.

* **Custom API Extractor:** Built an extractor using AST/Regex that understands Python, JavaScript/TypeScript, Go, and Rust.

* **Deterministic Validator:** Engineered a grounding check that validates frontmatter, naming rules, and ensures model-hallucinated functions are rejected.

* **Experience Memory:** Added a unique `memory.json` loop that saves "lessons" when the model fixes its own validation errors, injecting them into future runs without weight training.

* **Bundled Skill:** `skills/skillforge/SKILL.md` is our bundled, native skill formatted to the strict Agent Skill standards.

## 🧪 Testing (No Model Needed)

Verify the core logic, error-repair loop, and memory injection locally:
*(Windows users: Run `set PYTHONPATH=.` before executing)*

```bash
# Tests the repair loop: malformed JSON, hallucinated functions, bad names
PYTHONPATH=. python tests/test_loop.py      

# Tests memory: ensures lessons are saved and injected into future runs
PYTHONPATH=. python tests/test_memory.py    
```

## 📜 License

This project is open-source and licensed under the **[MIT License / Apache-2.0]** *(Note: Please ensure the actual LICENSE file is present in the repository root).*

*Developed for Hacktoberfest.*
