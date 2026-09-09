# Prompts

Clean, flat directory - no subdirs, no archive.

- **5 files:** `planner.md`, `researcher.md`, `developer.md`, `tester.md`, `reviewer.md` - 1:1 with `TASK_ROUTING` keys `backend/core/llm.py:12` and `graph/workflow.py` nodes.
- **Format:** Markdown + YAML front-matter (`id`, `version`, `tier`, `temperature`, `output_schema`) + body with `{var}` placeholders. Front-matter `tier` maps to `MODEL_MAP` (`pro`->`gemini-pro-latest`, `flash`->`gemini-flash-latest`).
- **Versioning:** `patch` wording, `minor` schema add, `major` breaking var rename. Check `git log -- agents/prompts/planner.md`.
- **Loader:** `loader.py:1` `load_prompt(name)` with `@lru_cache` + fallback to inline `_FALLBACK` if file missing (keeps `tests/test_workflow.py:9` and `backend/core/llm.py:91` mock alive). See `graph/nodes.py:1` for usage.
- **Why clean vs inline:** Non-dev can edit without Python, diff per prompt, no duplicate schemas in code + mock `backend/core/llm.py:95`, separation keeps workflow code `graph/workflow.py:82` stable.

Lint: `python -m agents.prompts.loader --validate` (check no duplicate id, valid JSON schema) - future.
