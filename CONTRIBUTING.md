# Contributing

Thanks for looking. This is a research apparatus maintained by one person, so
the most useful contribution is usually not a patch — it is telling me whether
the reproducibility claim holds on *your* machine.

## The fastest useful thing you can do (about a minute)

The central claim of this repository is that a simulation with a real language
model inside its loop replays **byte-for-byte across operating systems**. You can
check that yourself without a language model, without a GPU, and without
installing a test framework:

```bash
git clone https://github.com/mikotomiura/ERRE-Sandbox.git
cd ERRE-Sandbox
uv run --frozen --no-dev python scripts/verify_committed_artifacts.py
```

Exit code `0` means every committed artifact re-rendered to identical bytes on
your machine. [`REPRODUCING.md`](REPRODUCING.md) explains exactly what that does
and — just as importantly — what it deliberately does *not* do.

**Please report the result either way**, using the
[Reproduction report](https://github.com/mikotomiura/ERRE-Sandbox/issues/new?template=reproduction-report.yml)
issue template. A failure is more valuable than a success: it means the claim is
narrower than stated, and I would rather find that out from you than from a
reviewer. A success is also worth filing — an independent run on hardware I do
not own is evidence I cannot generate myself.

Please paste your OS and the command's output. Nothing else is needed.

## Reporting a bug

Use the [Bug report](https://github.com/mikotomiura/ERRE-Sandbox/issues/new?template=bug-report.yml)
template. Include the command you ran and its full output.

## Asking something / suggesting something

Open a regular issue. Questions about *why* something is designed the way it is
are welcome — the design rationale lives in `docs/architecture.md` and
`docs/research-positioning.md`, and if the answer is not there, that is a
documentation bug worth filing.

## Pull requests

Before opening one, please open an issue first so we can agree on the shape.
This codebase has an unusual constraint: **the measurement apparatus under
`src/erre_sandbox/evidence/` is frozen**, because committed experimental results
were produced by it, and changing it retroactively invalidates them. Changes
there need a reason that survives that argument.

If you do send a patch:

```powershell
pwsh scripts/dev/pre-push-check.ps1   # Windows
```

```bash
bash scripts/dev/pre-push-check.sh    # Linux / macOS
```

This runs the same four stages as CI (`ruff format --check`, `ruff check`,
`mypy src`, `pytest`) with the same selection, so a green local run means a green
CI run. All four must pass.

Conventions: Python 3.11, type hints required, `ruff` for formatting and linting,
Conventional Commits for commit messages, and no direct pushes to `main`.
`docs/development-guidelines.md` has the details.

## Scope

This is a research apparatus for studying deliberate inefficiency and embodied
return in LLM-agent simulations, not a general-purpose framework. Contributions
that make the reproducibility guarantees stronger, clearer, or easier to check
independently are the ones most likely to land.

## Licence

By contributing you agree that your contribution is licensed under the same
terms as the project: **Apache-2.0 OR MIT**, at the user's choice.
