# AGENTS.md

AuthRes is a Python research prototype for checking whether independent
implementations of the same authorization policy return consistent
ALLOW/DENY decisions. It contains a reference engine, an in-project Engine B,
a synthetic corpus generator/comparator, a CLI, and a Textual TUI. No external
authorization engine or adapter exists.

## Setup and commands

Run everything from the repository root. There is no `pyproject.toml` or
install step; `pytest.ini` sets `pythonpath = .`.

- Setup: `python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt`
- Python: core supports 3.10+, but the full test toolchain needs 3.11+.
  CI matrix is 3.11–3.15.
- Full suite: `python -m pytest` (offline and headless).
- Focused test: `python -m pytest tests/test_reference_engine.py::test_deny_overrides_allow_regardless_of_policy_order -q`
- Evaluate one request:
  `python main.py --policies policies/examples/conflict.json --request '{"subject":"alice","resource":"report","action":"read"}'`
- Synthetic comparison:
  `python -m authres.compare --seed 1 --cases 1000 --policies 5`
  Writes gitignored `runs/*.disagreements.jsonl` and `*.manifest.json`.
- TUI: `python -m authres.tui`
- Plain-text demo: `python demo/run_demo.py --seed 1 --cases 1000`

There is no lint, formatter, or typecheck configuration. `pytest` is the only
verification gate; do not invent tooling commands.

## Layout and enforced boundaries

- `authres/core/` — frozen validated models, strict JSON, reference engine,
  canonical serialization/hashing, run manifests.
- `authres/engines/` — `contract.py` (future adapter protocol) and
  `index_engine.py` (Engine B).
- `authres/compare/` — synthetic generator, comparator, corpus runner, CLI.
- `authres/tui/` — presentation layer; `services/` adapts core APIs.
- `demo/run_demo.py` — three-part demonstration, including a deliberately
  wrong test-only mutant.

AST tests enforce dependency direction:

- `authres/engines/*` must not import `authres.core.reference_engine` and may
  depend only on `authres.core.models`, `authres.core.policy`, and itself.
- `authres.core.reference_engine` must not import `authres.engines`.
- TUI `screens/`, `widgets/`, and `app.py` must not import the reference
  engine. Only `authres/compare/reference_adapter.py` and
  `authres/tui/services/` may.

Core has zero third-party runtime dependencies. Keep `textual` confined to the
TUI; `pytest`, `hypothesis`, and `jsonschema` are development-only.

## Invariants

- Policy format v1 semantics (`docs/policy-semantics.md`) are normative.
  Changing matching, decision, canonical encoding, or hash behavior requires a
  new format version plus corresponding doc, schema, and test updates. Never
  silently change version 1.
- All JSON input must go through `authres/core/jsonio.py`: reject duplicate
  keys, `NaN`/`Infinity`, unknown fields, and malformed values. Identifiers are
  opaque — no case folding, trimming, Unicode normalization, wildcards, or
  hierarchy.
- `EvaluationResult` enforces its decision/reason/matched-trace invariants at
  construction. Keep reason codes meaningful and traces complete.
- The comparator must never coerce `ERROR`, `TIMEOUT`, `INDETERMINATE`, or
  `NOT_APPLICABLE` into ALLOW or DENY.
- Manifests record identity metadata only, never decisions.
- JSON Schemas in `schemas/` must stay in sync with the Python parser;
  `tests/test_schema.py` pins agreement in both directions.
- `main.py` exits `0` even when the decision is DENY; exit `2` is only for
  validation errors.

## Research-integrity constraints

These are deliberate claims boundaries; preserve them when editing README or
docs.

- No external authorization engine has been run or compared. Engine B is
  in-project and AI-written from the same specification, so it is not
  independent; agreement with it is not semantic validation.
- All generated cases and observed agreement rates are synthetic. Never
  describe them as real-world measurements, compatibility evidence, or
  vulnerability findings.
- `tests/mutants/allow_overrides_deny.py` is a known-fault test fixture. It is
  not production code and is only evidence of comparator fault detection.
- Cross-machine reproducibility is unverified, and no release is tagged;
  the `0.1.0` version string is not a freeze decision.

## Documentation

- `docs/policy-semantics.md` — normative version 1 semantics and extension
  policy.
- `docs/canonical-encoding.md` — canonical JSON, hashing, Unicode/NUL rules.
- `docs/architecture.md` — module map, dependency direction, test strategy.
- `docs/semantic-validation.md` — evidence ladder and unvalidated assumptions.
- `docs/engine-contract.md` — future external-adapter design.
