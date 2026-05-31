"""Build immutable manifest.json + sha256 for a PEFT LoRA adapter directory.

Designed for M9-C-adopt Phase B (rank sweep on kant) + Phase C
(3 persona expansion). Produces the DA-10 manifest schema verbatim so
``_validate_adapter_manifest()`` (Phase F, DA-6 HIGH-4) can consume it
without ad-hoc parsing.

Schema (DA-10):

    {
      "adapter_name": "kant_r8_real",
      "persona_id": "kant",
      "base_model": "Qwen/Qwen3-8B",
      "rank": 8,
      "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
      "sha256_adapter_model": "abc123...",
      "training_git_sha": "c1e118c",
      "is_mock": false,
      "created_at": "2026-05-14T09:30:00Z"
    }

Usage:

    python scripts/build_adapter_manifest.py \\
        --adapter-dir /root/erre-sandbox/checkpoints/kant_r4_real \\
        --persona-id kant \\
        --rank 4 \\
        --output /path/to/manifest.json

The script reads ``adapter_config.json`` from the adapter directory to
cross-check ``base_model`` and ``target_modules`` against the operator
flags, refusing to emit a manifest when the adapter on disk disagrees
with the declared metadata (an early signal that the wrong directory
was passed). ``training_git_sha`` falls back to ``unknown`` when the
script is run outside a git workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BASE_MODEL = "Qwen/Qwen3-8B"
DEFAULT_TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")
ALLOWED_RANKS_DEFAULT = (4, 8, 16)
ALLOWED_RANKS_WITH_TAIL = (4, 8, 16, 32)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_git_sha(cwd: Path) -> str:
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _load_adapter_config(adapter_dir: Path) -> dict:
    cfg_path = adapter_dir / "adapter_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"adapter_config.json not found in {adapter_dir!s}; "
            f"PEFT save_pretrained() did not run or wrong directory passed",
        )
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def build_manifest(
    *,
    adapter_dir: Path,
    persona_id: str,
    rank: int,
    base_model: str = DEFAULT_BASE_MODEL,
    target_modules: tuple[str, ...] = DEFAULT_TARGET_MODULES,
    is_mock: bool = False,
    allow_tail_sweep: bool = False,
    git_workdir: Path | None = None,
) -> dict:
    """Compute manifest dict (without writing). Caller persists.

    Raises ValueError / FileNotFoundError for hard-block conditions so
    ``_validate_adapter_manifest()`` in Phase F can rely on the schema.
    """
    allowed_ranks = (
        ALLOWED_RANKS_WITH_TAIL if allow_tail_sweep else ALLOWED_RANKS_DEFAULT
    )
    if rank not in allowed_ranks:
        raise ValueError(
            f"rank={rank!r} not in allowed set {allowed_ranks!r}"
            f" (DA-1 + tail-sweep gate); pass --allow-tail-sweep to accept 32",
        )

    safetensors_path = adapter_dir / "adapter_model.safetensors"
    if not safetensors_path.exists():
        # CS-9 / DA-6 hard block #2: refuse .bin pickle fallback
        bin_path = adapter_dir / "adapter_model.bin"
        if bin_path.exists():
            raise FileNotFoundError(
                f"adapter_model.safetensors missing in {adapter_dir!s} but"
                f" adapter_model.bin present; .bin pickle fallback refused"
                f" (DA-6 HIGH-4 hard block, safetensors security baseline)",
            )
        raise FileNotFoundError(
            f"adapter_model.safetensors missing in {adapter_dir!s};"
            f" cannot produce manifest without PEFT artefact",
        )

    cfg = _load_adapter_config(adapter_dir)
    cfg_base = cfg.get("base_model_name_or_path") or cfg.get("base_model")
    if cfg_base and cfg_base != base_model:
        raise ValueError(
            f"adapter_config.json base_model_name_or_path={cfg_base!r}"
            f" disagrees with operator --base-model={base_model!r};"
            f" wrong adapter directory or operator-flag mismatch",
        )
    cfg_targets = tuple(sorted(cfg.get("target_modules", [])))
    expected_targets = tuple(sorted(target_modules))
    if cfg_targets and cfg_targets != expected_targets:
        raise ValueError(
            f"adapter_config.json target_modules={cfg_targets!r}"
            f" disagrees with operator --target-modules={expected_targets!r}"
            f" (CS-1 LoRA target modules contract); refusing to emit manifest",
        )
    cfg_rank = cfg.get("r")
    if cfg_rank is not None and cfg_rank != rank:
        raise ValueError(
            f"adapter_config.json r={cfg_rank!r} disagrees with operator"
            f" --rank={rank!r}; wrong adapter directory passed",
        )

    sha256 = _sha256_of(safetensors_path)
    adapter_name = f"{persona_id}_r{rank}_{'mock' if is_mock else 'real'}"

    created_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    # Replace ``+00:00`` with ``Z`` to match the DA-6 schema example.
    if created_at.endswith("+00:00"):
        created_at = created_at[:-6] + "Z"

    return {
        "adapter_name": adapter_name,
        "persona_id": persona_id,
        "base_model": base_model,
        "rank": rank,
        "target_modules": list(target_modules),
        "sha256_adapter_model": sha256,
        "training_git_sha": _resolve_git_sha(git_workdir or Path.cwd()),
        "is_mock": is_mock,
        "created_at": created_at,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/build_adapter_manifest.py",
        description=(
            "Build immutable manifest.json + sha256 for a PEFT LoRA adapter"
            " directory (M9-C-adopt DA-10 schema, Codex HIGH-4 reflected)"
        ),
    )
    parser.add_argument(
        "--adapter-dir",
        type=Path,
        required=True,
        help="PEFT adapter directory (contains adapter_config.json + adapter_model.safetensors)",
    )
    parser.add_argument(
        "--persona-id",
        required=True,
        choices=["kant", "nietzsche", "rikyu"],
        help="persona id (kant/nietzsche/rikyu, DA-3)",
    )
    parser.add_argument(
        "--rank",
        type=int,
        required=True,
        help="LoRA rank (must be in DA-1 allowed set {4,8,16} or {4,8,16,32} with --allow-tail-sweep)",
    )
    parser.add_argument(
        "--base-model",
        default=DEFAULT_BASE_MODEL,
        help=f"HF base model id (default: {DEFAULT_BASE_MODEL})",
    )
    parser.add_argument(
        "--target-modules",
        nargs="+",
        default=list(DEFAULT_TARGET_MODULES),
        help="LoRA target modules (default: %(default)s)",
    )
    parser.add_argument(
        "--is-mock",
        action="store_true",
        help="set is_mock=True (mock adapters under tools/spike/; production loader will reject)",
    )
    parser.add_argument(
        "--allow-tail-sweep",
        action="store_true",
        help="allow rank=32 (DA-1 conditional tail-sweep fire)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="manifest.json output path (default: <adapter-dir>/manifest.json)",
    )
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(
            adapter_dir=args.adapter_dir,
            persona_id=args.persona_id,
            rank=args.rank,
            base_model=args.base_model,
            target_modules=tuple(args.target_modules),
            is_mock=args.is_mock,
            allow_tail_sweep=args.allow_tail_sweep,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"build_adapter_manifest: {exc}", file=sys.stderr)  # noqa: T201
        return 2

    output_path = args.output or (args.adapter_dir / "manifest.json")
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, sort_keys=True))  # noqa: T201  # stdout single-line for shell capture
    print(f"manifest written: {output_path!s}", file=sys.stderr)  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
