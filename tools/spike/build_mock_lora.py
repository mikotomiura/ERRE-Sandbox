"""Build a deterministic no-op PEFT LoRA adapter for SGLang infrastructure proof.

m9-c-spike Phase J (decisions.md CS-9). The output adapter is a PEFT
identity transform (B initialised to 0, A from kaiming uniform — the
HuggingFace PEFT default) so a Kant prompt routed through this adapter
produces the same logits as the bare base model. That property is what
makes the Phase K-α FSM smoke test meaningful: any divergence in the
ERRE FSM 8-mode walk through SGLang must come from the LoRA path itself,
not from the adapter contents.

Three CS-9 invariants this module enforces:

1. **Refusal guard** — the function refuses to write under any directory
   whose path components contain ``src``, or whose final segment lower-
   cases to include ``checkpoint`` or ``production``. The guard runs
   *before* peft / transformers are imported so a misconfigured caller
   on a CI default install (no [training] extras) still trips the
   ValueError.
2. **Sentinel metadata** — the emitted ``adapter_config.json`` carries a
   ``metadata`` field with ``mock=true`` plus build provenance
   (base_model, rank, target_modules, init_lora_weights, git_sha). The
   sentinel lets a production loader detect a mock adapter at policy
   level (the SGLangChatClient warns at load time but does not block;
   blocking belongs to the production loader).
3. **No-op identity** — the adapter uses PEFT's default init
   (``init_lora_weights=True`` → kaiming-A + zero-B; labelled
   ``"default"`` in the sentinel metadata for human readability) so
   the B matrix is zero and the adapter is functionally
   indistinguishable from the bare base model.
   The Phase K-α smoke is thus meaningful only as a wire-protocol /
   format / FSM-route check, not an adapter-contents check (the LoRA
   route through SGLang must preserve the base model's outputs).

Layout boundary (CS-9):

* This module lives under ``tools/spike/`` (production code is under
  ``src/erre_sandbox/``). The mypy ``exclude`` config blocks
  ``tools/**`` from the strict typecheck universe, and the refusal
  guard rejects any caller that tries to write the mock adapter under
  ``src/`` or any path containing ``checkpoint`` / ``production``.
* The ``[training]`` extras stack (peft / transformers / accelerate /
  bitsandbytes) is imported lazily inside :func:`build_mock_lora` —
  the refusal-guard CI tests run on the default install with no GPU
  extras. Real PEFT-side tests carry the ``@pytest.mark.spike`` marker
  and only run when ``uv sync --extra training`` has installed the
  stack.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

DEFAULT_BASE_MODEL: Final[str] = "Qwen/Qwen3-8B"
DEFAULT_RANK: Final[int] = 8
DEFAULT_TARGET_MODULES: Final[tuple[str, ...]] = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
)

_FORBIDDEN_NAME_SUBSTRINGS: Final[tuple[str, ...]] = ("checkpoint", "production")


class MockLoRAGuardError(ValueError):
    """Raised when the refusal guard rejects an output_dir (CS-9 sentinel)."""


def refusal_guard(output_dir: Path) -> None:
    """Reject any path that looks like production / source / checkpoint storage.

    Three checks (CS-9):

    1. No path segment may equal ``src``. This blocks the obvious
       "mock adapter under the source tree" footgun.
    2. The final segment, lower-cased, must not contain ``checkpoint``
       or ``production``. This catches paths like
       ``/var/checkpoints/kant`` or ``./production-lora``.
    3. The check runs in PurePath-segment space, so the same rule fires
       on POSIX and Windows-style paths and on absolute / relative
       inputs uniformly.

    Raises:
        MockLoRAGuardError: When any check fails. The message names the
            failed check so test fixtures can match on substring.
    """
    # Resolve symlinks before segment check — a symlink under
    # ``/tmp/safe_dir`` pointing at ``src/erre_sandbox/...`` would
    # otherwise pass the literal-segment guard. ``strict=False`` allows
    # the path to not yet exist (we mkdir later).
    resolved = Path(output_dir).resolve(strict=False)
    parts = resolved.parts
    if "src" in parts:
        raise MockLoRAGuardError(
            f"refusing to write mock LoRA to {output_dir!s} "
            f"(resolved={resolved!s}): 'src' segment found in path; mock "
            f"adapters must stay outside the source tree (CS-9 isolation)",
        )
    name_lower = resolved.name.lower()
    for bad in _FORBIDDEN_NAME_SUBSTRINGS:
        if bad in name_lower:
            raise MockLoRAGuardError(
                f"refusing to write mock LoRA to {output_dir!s} "
                f"(resolved={resolved!s}): directory name contains {bad!r}; "
                f"mock adapters must not masquerade as production "
                f"checkpoints (CS-9 sentinel)",
            )


def _read_git_sha() -> str:
    """Best-effort current git sha; ``"unknown"`` if git is missing or repo-less."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 — relies on PATH-resolved git
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def build_mock_lora(
    output_dir: Path,
    *,
    base_model: str = DEFAULT_BASE_MODEL,
    rank: int = DEFAULT_RANK,
    target_modules: tuple[str, ...] = DEFAULT_TARGET_MODULES,
) -> Path:
    """Build a no-op PEFT LoRA adapter and embed the CS-9 sentinel metadata.

    The function MUST be called with the [training] extras installed
    (``uv sync --extra training``) — peft / transformers are imported
    lazily inside the body, so a caller without the extras hits an
    ``ImportError`` at the import site rather than at module-load time.
    The refusal guard runs *before* the lazy imports so a CI default
    caller still trips on a forbidden path.

    Args:
        output_dir: Directory to write ``adapter_config.json`` +
            ``adapter_model.safetensors`` into. Subject to the
            :func:`refusal_guard` checks.
        base_model: HuggingFace model id the adapter is anchored to.
            Loaded only to satisfy PEFT's ``get_peft_model`` contract;
            the resulting adapter is identity (B=0).
        rank: LoRA rank. Default 8 (CS-1 / CS-5 continuity hypothesis).
        target_modules: Attention projection module names to attach the
            adapter to. Default matches Qwen3-8B (CS-1).

    Returns:
        The ``output_dir`` Path on success.

    Raises:
        MockLoRAGuardError: From :func:`refusal_guard`.
        ImportError: When peft / transformers are not installed (i.e.
            no ``[training]`` extras).
    """
    refusal_guard(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Lazy import — keep this module importable on the CI default install
    # so the refusal-guard tests can run without peft / transformers.
    from peft import LoraConfig, get_peft_model  # noqa: PLC0415
    from transformers import AutoModelForCausalLM  # noqa: PLC0415

    logger.info(
        "build_mock_lora: loading base model %r for PEFT identity wrapping",
        base_model,
    )
    base = AutoModelForCausalLM.from_pretrained(base_model)
    lora_config = LoraConfig(
        r=rank,
        lora_alpha=rank * 2,
        target_modules=list(target_modules),
        # PEFT default = kaiming-A + zero-B → identity transform (CS-9 / LOW-2).
        # Pass ``True`` (not the string ``"default"``) — peft>=0.19 raises
        # ``ValueError: Unknown initialization init_lora_weights='default'``.
        # The sentinel metadata below labels this scheme as ``"default"`` for
        # human readability; the LoraConfig field accepts ``bool | Literal[...]``.
        init_lora_weights=True,
        task_type="CAUSAL_LM",
    )
    peft_model = get_peft_model(base, lora_config)
    peft_model.save_pretrained(str(output_dir))

    # CS-9 sentinel — overwrite adapter_config.json's metadata field with
    # mock=true plus provenance. Production loaders inspect this to refuse
    # mock adapters at policy level.
    config_path = output_dir / "adapter_config.json"
    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["metadata"] = {
        "mock": "true",
        "base_model": base_model,
        "rank": str(rank),
        "target_modules": ",".join(target_modules),
        "init_lora_weights": "default",
        "git_sha": _read_git_sha(),
    }
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    logger.info(
        "build_mock_lora: wrote no-op identity adapter to %s (mock=true sentinel set)",
        output_dir,
    )
    return output_dir


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tools.spike.build_mock_lora",
        description="Build a deterministic no-op PEFT LoRA adapter for the m9-c-spike.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write adapter_config.json + adapter_model.safetensors.",
    )
    parser.add_argument(
        "--base-model",
        default=DEFAULT_BASE_MODEL,
        help=f"HuggingFace base model id (default: {DEFAULT_BASE_MODEL}).",
    )
    parser.add_argument(
        "--rank",
        type=int,
        default=DEFAULT_RANK,
        help=f"LoRA rank (default: {DEFAULT_RANK}; CS-1/CS-5 continuity).",
    )
    args = parser.parse_args(argv)
    build_mock_lora(
        args.output_dir,
        base_model=args.base_model,
        rank=args.rank,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
