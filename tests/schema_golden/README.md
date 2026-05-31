# JSON Schema golden files

These three files pin the Pydantic-generated JSON Schema for the public
wire types in `src/erre_sandbox/schemas.py`:

| File | Target type | Purpose |
| --- | --- | --- |
| `agent_state.schema.json` | `AgentState` | Per-tick snapshot used by Gateway / Godot |
| `persona_spec.schema.json` | `PersonaSpec` | YAML shape loaded from `personas/*.yaml` |
| `control_envelope.schema.json` | `ControlEnvelope` | Discriminated WebSocket envelope |

`tests/test_schema_contract.py::test_json_schema_matches_golden` compares
the current Pydantic output against these files. Any drift (field added /
renamed / re-typed / constraint changed) fails CI.

## When to regenerate

Regenerate **only** as part of a PR that explicitly bumps
`SCHEMA_VERSION` in `schemas.py` §1. Never hand-edit these files.

## Regeneration command

```bash
uv run python - <<'EOF'
import json
from pathlib import Path
from pydantic import TypeAdapter
from erre_sandbox.schemas import AgentState, PersonaSpec, ControlEnvelope

targets = {
    "agent_state": AgentState,
    "persona_spec": PersonaSpec,
    "control_envelope": ControlEnvelope,
}
out_dir = Path("tests/schema_golden")
for name, target in targets.items():
    adapter = TypeAdapter(target)
    text = json.dumps(adapter.json_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    (out_dir / f"{name}.schema.json").write_text(text, encoding="utf-8")
    print(f"wrote {name}")
EOF
```

Then stage the regenerated files alongside your `schemas.py` change and
the bump in `SCHEMA_VERSION`.

## Notes

- Output is pretty-printed and sort-keyed so diffs stay readable.
- Trailing newline is intentional (POSIX + git friendliness).
- Pydantic pin in `pyproject.toml` (`pydantic>=2.7,<3`) keeps output
  stable across minor versions; a Pydantic upgrade PR may require golden
  regeneration even if `schemas.py` is unchanged.
