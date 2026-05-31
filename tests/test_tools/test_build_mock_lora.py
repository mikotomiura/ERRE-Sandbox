"""Tests for ``tools.spike.build_mock_lora`` (m9-c-spike Phase J, CS-9).

Two test groups:

* Refusal-guard tests (no peft / transformers required) — run on the
  CI default install. Regression of these is a CS-9 enforcement
  failure, so they MUST stay marker-less.
* PEFT-build tests carry ``@pytest.mark.spike`` — they exercise the
  real ``peft.get_peft_model`` + ``save_pretrained`` path and require
  ``uv sync --extra training`` to be installed. CI default deselects
  them; on a developer machine ``uv run pytest -m spike`` runs them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools.spike.build_mock_lora import (
    MockLoRAGuardError,
    build_mock_lora,
    refusal_guard,
)

# ---------------------------------------------------------------------------
# CS-9 refusal-guard tests (CI default — peft NOT required)
# ---------------------------------------------------------------------------


def test_refuses_path_with_src_segment(tmp_path: Path) -> None:
    """Any path component equal to ``src`` is rejected (CS-9)."""
    bad = tmp_path / "src" / "lora_kant"
    with pytest.raises(MockLoRAGuardError, match="'src' segment"):
        refusal_guard(bad)
    # The full build path also raises before any peft import is attempted.
    with pytest.raises(MockLoRAGuardError, match="'src' segment"):
        build_mock_lora(bad)


def test_refuses_directory_name_with_checkpoint_or_production(tmp_path: Path) -> None:
    """Final segment containing ``checkpoint`` / ``production`` is rejected (CS-9)."""
    cp = tmp_path / "Kant_Checkpoint"
    with pytest.raises(MockLoRAGuardError, match="'checkpoint'"):
        refusal_guard(cp)
    prod = tmp_path / "production-lora"
    with pytest.raises(MockLoRAGuardError, match="'production'"):
        refusal_guard(prod)


def test_refuses_symlink_pointing_into_src(tmp_path: Path) -> None:
    """Symlink into a src/ tree is rejected after resolve() (security HIGH-1)."""
    src_target = tmp_path / "src" / "erre_sandbox" / "lora_inside_src"
    src_target.mkdir(parents=True)
    link = tmp_path / "innocuous_link"
    try:
        link.symlink_to(src_target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not supported on this platform / FS")
    with pytest.raises(MockLoRAGuardError, match="'src' segment"):
        refusal_guard(link)


# ---------------------------------------------------------------------------
# PEFT identity-build tests (require [training] extras + GPU stack)
# ---------------------------------------------------------------------------


# tiny-gpt2 uses HuggingFace ``Conv1D`` for ``c_attn``, so PEFT's dispatcher
# auto-corrects ``fan_in_fan_out`` and emits a UserWarning. The
# auto-correction is benign for the spike's purpose (we're verifying the
# build wrapper, not the projection layer's transpose orientation), and
# real Qwen3-8B uses ``torch.nn.Linear`` (no warning). Filter at the test
# level so the project-wide ``filterwarnings = ["error"]`` does not flip
# the auto-correction into a failure on developer machines that run
# ``pytest -m spike`` with ``[training]`` extras installed.
_FAN_IN_FAN_OUT_FILTER = "ignore:fan_in_fan_out is set to:UserWarning"
# The CS-9 sentinel is written into the LoraConfig JSON's ``metadata`` key.
# peft 0.19.1's ``LoraConfig`` does not declare ``metadata`` and warns
# (informationally — the warning text says "these are ignored") whenever a
# loader reads back the config. The sentinel design is intentional: it sits
# inside adapter_config.json so production loaders inspecting that single
# file find the ``mock=true`` flag without a side-channel artefact. Filter
# the read-back warning at the test level for the same reason as the
# fan_in_fan_out filter above.
_UNKNOWN_METADATA_KW_FILTER = (
    "ignore:Unexpected keyword arguments \\['metadata'\\]:UserWarning"
)


@pytest.mark.spike
@pytest.mark.filterwarnings(_FAN_IN_FAN_OUT_FILTER)
def test_build_emits_mock_sentinel_metadata(tmp_path: Path) -> None:
    """Built adapter_config.json carries the CS-9 ``mock=true`` sentinel."""
    pytest.importorskip("peft")
    pytest.importorskip("transformers")
    out = tmp_path / "mock_kant_r8"
    # Use a tiny base for the spike test — Qwen3-8B is too heavy to load
    # on a developer machine just to verify the metadata sentinel.
    build_mock_lora(
        out,
        base_model="sshleifer/tiny-gpt2",
        rank=4,
        target_modules=("c_attn",),
    )
    config = json.loads((out / "adapter_config.json").read_text(encoding="utf-8"))
    assert config["metadata"]["mock"] == "true"
    assert config["metadata"]["init_lora_weights"] == "default"
    assert config["metadata"]["target_modules"] == "c_attn"


@pytest.mark.spike
@pytest.mark.filterwarnings(_FAN_IN_FAN_OUT_FILTER)
@pytest.mark.filterwarnings(_UNKNOWN_METADATA_KW_FILTER)
def test_build_produces_zero_b_identity_adapter(tmp_path: Path) -> None:
    """Built adapter has B=0 → identity transform (CS-9 / LOW-2)."""
    pytest.importorskip("peft")
    torch = pytest.importorskip("torch")
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    out = tmp_path / "mock_identity_r4"
    build_mock_lora(
        out,
        base_model="sshleifer/tiny-gpt2",
        rank=4,
        target_modules=("c_attn",),
    )

    base = AutoModelForCausalLM.from_pretrained("sshleifer/tiny-gpt2")
    peft_model = PeftModel.from_pretrained(base, str(out))
    # Walk the adapter modules; PEFT names the B matrix ``lora_B``.
    found_b = False
    for name, param in peft_model.named_parameters():
        if "lora_B" in name:
            found_b = True
            assert torch.all(param == 0.0), (
                f"PEFT default init must zero the B matrix, but {name} has "
                f"non-zero entries (max abs={param.abs().max().item()})"
            )
    assert found_b, "no lora_B parameter found — PEFT integration is broken"
