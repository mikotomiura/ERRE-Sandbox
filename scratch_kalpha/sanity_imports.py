"""Verify sglang and supporting deps import OK in WSL2 venv."""

import sys

print("python:", sys.version.split()[0])

import sglang  # noqa: E402

print("sglang:", sglang.__version__)

import torch  # noqa: E402

print("torch:", torch.__version__, "cuda_avail:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device:", torch.cuda.get_device_name(0))

import flashinfer  # noqa: E402

print("flashinfer:", flashinfer.__version__)
