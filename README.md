# AuthRes

AuthRes is a research prototype for studying whether independent
implementations of the same authorization policy specification return
consistent ALLOW/DENY decisions for the same policy and request.

This repository contains the Phase 1 reference model plus a **minimal Phase 2
comparison harness**: a seeded synthetic case generator, a second in-project
engine (Engine B), a neutral decision comparator, and a CLI. It does **not**
contain external engine integrations or adapters. All comparison data is
synthetic; no real-world authorization measurement has been made.

## Status

**Implemented**

- Immutable, validated `Policy`, `AccessRequest`, `PolicySet`, and
  `EvaluationResult` models (results enforce their documented invariants).
- Strict, versioned JSON policy representation with clear validation errors.
- Strict JSON request parsing (`AccessRequest.from_json`) rejecting
  duplicate keys and non-standard constants, shared with policy loading.
- Deterministic reference engine implementing exact matching,
  DENY-overrides-ALLOW, and default DENY.
- Explicit decision reason codes and matched-policy traces.
- A small CLI for evaluating one request against one policy document.
- A keyboard-first Textual TUI (`python -m authres.tui`) for browsing
  policies, building requests, running evaluations, and exporting session
  results. The TUI is a separate presentation layer over the same core APIs.
- Three example policy documents.
- Automated pytest suite covering the documented semantics, the CLI, a
  hand-authored conformance fixture, the TUI, and property/metamorphic
  tests (Hypothesis).
- A machine-readable JSON Schema for policies and requests, canonical
  serialization, and identity hashing (`authres/core/canonical.py`).
- Run-manifest construction for experiment provenance
  (`authres/core/provenance.py`); manifests record identity only, never
  decisions. Comparison runs use a corpus-level manifest.
- Pinned dependencies and a CI workflow running the full suite on Python
  3.11–3.15.
- A seeded, deterministic synthetic generator
  (`authres/compare/generator.py`).
- Engine B (`authres/engines/index_engine.py`): an exact-match dictionary
  index implementation written from `docs/policy-semantics.md`, with a
  different evaluation algorithm from the reference engine.
- A neutral comparator (`authres/compare/comparator.py`) that keeps engine
  errors, timeouts, and non-decisions separate from ALLOW/DENY agreement.
- A comparison CLI (`python -m authres.compare`) that writes disagreement
  JSONL and a run manifest.
- A test-only mutant under `tests/mutants/` proving that the comparator
  detects a known injected fault. It is not production code.
- Documentation: normative semantics, canonical encoding, architecture,
  semantic-validation strategy, and a neutral engine-contract design.

**Not implemented**

- External authorization engines or adapters (the engine contract is a
  design target; no external adapter exists).
- Any real-world measurement or compatibility claim.
- Dashboards, statistical analysis, or inconsistency classification beyond
  raw counts.
- TUI integration with the comparison harness.

No claim is made that the reference model matches an external product or
specification. Engine B was written by an AI coding agent from the same
specification as the reference engine, so it is **not fully independent**.
Agreement between them is not proof of semantic correctness. A decision
difference is an observation to investigate, not automatically a
vulnerability.

## Requirements

- Python 3.10 or newer for the core and CLI; **3.11+ for the full test
  toolchain** (`hypothesis` requires 3.11). The CI matrix covers 3.11–3.15.
- Dependencies are pinned exact in `requirements.txt` for reproducibility:
  `pytest`, `hypothesis`, and `jsonschema` for development/verification,
  and `textual` (required only for the optional TUI). The AuthRes core has
  no third-party runtime dependencies.

The suite has been exercised locally with Python 3.14.10/pytest 9.2.0 and
Python 3.15.2/pytest 9.2.0; the TUI with Textual 8.2.8 on Python 3.15.2.
CI runs the full suite on Python 3.11–3.15 (`.github/workflows/ci.yml`).

## Setup

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` pins exact versions, so this produces a reproducible
local environment identical to CI.

## Quick start

Evaluate a request that matches both an `ALLOW` and a `DENY` policy:

```bash
python main.py \
  --policies policies/examples/conflict.json \
  --request '{"subject":"alice","resource":"report","action":"read"}'
```

Observed output from the current implementation:

```json
{
  "decision": "DENY",
  "reason": "DENY_OVERRIDE",
  "matched_policy_ids": [
    "allow-alice-read-report",
    "deny-alice-read-report"
  ],
  "matched_policies": [
    {
      "id": "allow-alice-read-report",
      "subject": "alice",
      "resource": "report",
      "action": "read",
      "effect": "ALLOW"
    },
    {
      "id": "deny-alice-read-report",
      "subject": "alice",
      "resource": "report",
      "action": "read",
      "effect": "DENY"
    }
  ]
}
```

A valid evaluation exits with status `0`, even when the decision is DENY.
Validation errors are printed to standard error and exit with status `2`.

## TUI

An interactive terminal interface is included:

```bash
python -m authres.tui
```

It is a separate presentation layer over the same core APIs; it contains no
authorization logic of its own. Screens:

| Key | Screen |
|---|---|
| `d` | Dashboard — project/engine status and latest evaluation |
| `p` | Policy Explorer — browse, preview, and validate policy files |
| `b` | Request Builder — construct and validate an access request |
| `e` | Evaluation — run the reference engine on the pending request |
| `v` | Results — session log, details, and JSON export |
| `s` | Settings — policy/export paths, display preference |
| `?` | Help — keyboard shortcuts |
| `q` | Quit |

Notes:

- While a text field is focused, letters are typed into the field; press
  `escape` to leave the field first.
- Session results are in-memory; exports use the existing serialization
  contracts (`EvaluationResult.to_dict`, `AccessRequest.to_dict`,
  `PolicySet.to_dict`).
- The TUI never modifies policy semantics and never runs any external
  authorization engine.

## Engine comparison (synthetic)

Engine B is an in-project exact-match index implementation
(`authres/engines/index_engine.py`). The comparator runs the reference engine
and Engine B on the same validated policy set and request, and reports
agreement, disagreement, engine errors, timeouts, and non-decisions
separately. No external engine is involved.

Run the seeded synthetic corpus:

```bash
python -m authres.compare --seed 1 --cases 1000 --policies 5
```

Observed output from the implementation in this repository:

```text
AuthRes synthetic engine comparison
seed=1 cases=1000 policies=5 vocabulary=4 conflict_rate=0.25
engine: authres-reference-engine 0.1.0
engine: authres-index-engine 1.0.0
total cases: 1000
agreements: 1000
disagreements: 0
engine errors: 0
timeouts: 0
non-decided cases: 0
conflicting ALLOW/DENY cases: 263
disagreement file: runs/comparison-seed-1-cases-1000.disagreements.jsonl
manifest: runs/comparison-seed-1-cases-1000.manifest.json
```

The disagreement JSONL file is written even when empty. The manifest is a
corpus-level record (seed, generator configuration, corpus hash, engine
versions, Python/dependency versions, semantics version) built with
`authres/core/provenance.py`; it contains no decisions.

Other options:

```bash
python -m authres.compare --seed 2 --cases 5000 --policies 10 \
  --vocabulary 2 --conflict-rate 0.5 --output runs
```

`conflict-rate` is the probability that a case with at least two policies is
constructed to contain a request-matching ALLOW and DENY pair. Unforced cases
can still conflict, so the observed count can be higher. The vocabulary is
deliberately small to make exact-match collisions frequent. Every case is
synthetic.

Comparator semantics in one line: agreement is computed only when every
engine returned `DECIDED`; `ERROR`, `TIMEOUT`, `INDETERMINATE`, and
`NOT_APPLICABLE` are never coerced into ALLOW or DENY.

## Policy JSON

A policy document is a versioned JSON object:

```json
{
  "version": 1,
  "policies": [
    {
      "id": "allow-alice-read-report",
      "subject": "alice",
      "resource": "report",
      "action": "read",
      "effect": "ALLOW"
    }
  ]
}
```

Rules for version 1:

- `version` must be the integer `1`.
- `policies` must be an array; it may be empty.
- Each policy requires `subject`, `resource`, `action`, and `effect`.
- `effect` must be exactly `"ALLOW"` or `"DENY"`.
- `id` is optional metadata and must be unique when present.
- Unknown fields, duplicate JSON keys, invalid types, and malformed JSON are
  rejected.

Request JSON obeys the same strictness: duplicate keys and the
non-standard `NaN`/`Infinity` constants are rejected on both boundaries.

Example files:

- `policies/examples/basic_allow.json` — two non-conflicting ALLOW rules.
- `policies/examples/conflict.json` — matching ALLOW and DENY rules.
- `policies/examples/default_deny.json` — empty policy set.

## Semantics summary

A policy matches only when `subject`, `resource`, and `action` all match the
request exactly. Matching is case-sensitive, with no trimming, wildcard,
hierarchy, or Unicode normalization. In particular, the policy identifier is
metadata and never affects matching.

When multiple policies match:

1. Any matching `DENY` produces DENY, even if matching ALLOW rules exist.
2. Otherwise, a matching ALLOW produces ALLOW.
3. If nothing matches, the decision is DENY, including for an empty policy set.

Matched policies are retained in the result for auditing, in policy-set order.
Order does not influence the decision.

The full normative definition, assumptions, and limitations are in
[`docs/policy-semantics.md`](docs/policy-semantics.md).

## Tests

Run the complete suite from the project root:

```bash
python -m pytest
```

The tests cover matching ALLOW and DENY rules, unmatched requests, conflicting
rules in both orders, multiple matches, empty policy sets, invalid policies,
missing request attributes, strict JSON behavior on both the policy and
request boundaries, exact matching, example documents, repeatability, CLI
exit codes and output, hand-authored conformance cases
(`tests/fixtures/semantics_v1.json`), result-model invariants, and the
engine-contract invariants and independence boundaries. They also cover
Engine B against the conformance fixture and metamorphic properties, comparator
agreement/error/timeout/non-decision separation, deterministic generation and
schema validity, corpus-level counts, CLI artifacts, and a test-only mutant
that the comparator must detect.

At the time of writing the full suite result was:

```text
430 passed in 66.60s (0:01:06)
```

Tests verify conformance to the project's documented semantics and the
comparison machinery. They do not prove agreement with any external
implementation, and they do not make the reference semantics independently
validated.

## Project structure

```text
authres/
├── .github/
│   └── workflows/
│       └── ci.yml
├── authres/
│   ├── __init__.py
│   ├── compare/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── comparator.py
│   │   ├── conflicts.py
│   │   ├── generator.py
│   │   ├── reference_adapter.py
│   │   └── runner.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── canonical.py
│   │   ├── errors.py
│   │   ├── jsonio.py
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── provenance.py
│   │   └── reference_engine.py
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── contract.py
│   │   └── index_engine.py
│   └── tui/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── screens/
│       ├── services/
│       └── widgets/
├── docs/
│   ├── architecture.md
│   ├── canonical-encoding.md
│   ├── engine-contract.md
│   ├── policy-semantics.md
│   └── semantic-validation.md
├── policies/
│   └── examples/
│       ├── basic_allow.json
│       ├── conflict.json
│       └── default_deny.json
├── schemas/
│   ├── policy-v1.schema.json
│   └── request-v1.schema.json
├── tests/
│   ├── fixtures/
│   │   └── semantics_v1.json
│   ├── mutants/
│   │   └── allow_overrides_deny.py
│   ├── test_canonical.py
│   ├── test_cli.py
│   ├── test_compare_cli.py
│   ├── test_comparator.py
│   ├── test_conflicts.py
│   ├── test_engine_contract.py
│   ├── test_generator.py
│   ├── test_index_engine.py
│   ├── test_metamorphic.py
│   ├── test_models.py
│   ├── test_policy.py
│   ├── test_provenance.py
│   ├── test_reference_engine.py
│   ├── test_runner.py
│   ├── test_schema.py
│   ├── test_semantics_conformance.py
│   ├── test_tui_app.py
│   ├── test_tui_import.py
│   ├── test_tui_screens.py
│   ├── test_tui_services.py
│   └── tui_support.py
├── main.py
├── pytest.ini
├── requirements.txt
└── README.md
```

## Documentation

- [`docs/policy-semantics.md`](docs/policy-semantics.md) — normative version 1
  semantics, validation rules, assumptions, and limitations.
- [`docs/canonical-encoding.md`](docs/canonical-encoding.md) — canonical
  serialization, identity hashing, Unicode/NUL/equality rules, and the
  JSON Schemas' scope (`schemas/`).
- [`docs/semantic-validation.md`](docs/semantic-validation.md) — evidence
  ladder separating specification, reference, and adapter claims; the
  independent review/reimplementation process; and assumptions not yet
  independently validated.
- [`docs/engine-contract.md`](docs/engine-contract.md) — design for the
  neutral `EngineOutcome`/`EngineStatus` model and the `EngineAdapter`
  protocol. No external adapter is implemented and no external-engine
  compatibility is established. Engine B is an in-project implementation,
  not an external adapter.

## Research integrity notes

- The reference engine is deterministic; it does not use randomness or external
  state during evaluation.
- The tests are implementation tests plus a hand-authored conformance fixture
  and a property suite transcribed from the same documented semantics; they
  do not prove the reference model is correct. See
  [`docs/semantic-validation.md`](docs/semantic-validation.md).
- Engine B was written by an AI coding agent from the same specification and
  in the same project as the reference engine. It uses a different algorithm,
  but it is **not fully independent**: shared misreadings are possible, and no
  independent human wrote or reviewed it. Its agreement with the reference
  engine is not semantic validation.
- The included examples and all generated comparison cases are synthetic
  illustrations, not experimental measurements. No result describes a real
  deployment, product, or vulnerability.
- AuthRes has not compared any external or independently developed engine.
  The `--seed 1 --cases 1000` run above produced 1000 agreements and 0
  disagreements on synthetic data; that is a same-specification,
  same-project observation, not a real-world agreement rate.
- The comparator's fault detection is demonstrated with a deliberately wrong
  test-only mutant (`tests/mutants/`). This is test-adequacy evidence only;
  the mutant is not used to make authorization decisions.
- Run manifests record identity metadata only. Same-seed artifact
  reproduction has been checked on this machine; cross-machine reproducibility
  has not been verified and is not claimed.
- Planned functionality is not described as implemented.
- No release has been tagged; the in-tree `0.1.0` version string is not a
  completed freeze decision.
