# AuthRes Architecture — Phase 1 + Minimal Phase 2

**Status:** reference model plus a minimal synthetic engine-comparison harness.  
**Policy format:** version 1, as defined in
[`policy-semantics.md`](policy-semantics.md).

## 1. Scope

Phase 1 implements:

- project structure;
- immutable authorization data models;
- strict JSON policy and request loading (shared strict parser) and
  serialization;
- a deterministic reference authorization engine;
- enforced invariants on `EvaluationResult`;
- a hand-authored semantics conformance fixture and test;
- automated tests for the documented semantics, including CLI integration;
- a keyboard-first Textual TUI (`authres/tui/`) as a separate presentation
  layer over the same core APIs;
- canonical serialization and identity hashing (`authres/core/canonical.py`)
  with machine-readable JSON Schemas (`schemas/`);
- run-manifest construction for experiment provenance
  (`authres/core/provenance.py`);
- property/metamorphic tests (Hypothesis) transcribed from the documented
  semantics;
- a neutral engine-contract scaffold (`authres/engines/contract.py`) as a
  design target for future adapters;
- documentation: semantics, architecture, semantic-validation strategy, and
  engine-contract design.

The minimal Phase 2 increment adds:

- a seeded, deterministic synthetic generator
  (`authres/compare/generator.py`);
- Engine B (`authres/engines/index_engine.py`), an exact-match dictionary
  index written from `docs/policy-semantics.md` with a different algorithm
  from the reference engine;
- a neutral comparator (`authres/compare/comparator.py`) and corpus runner
  (`authres/compare/runner.py`);
- a comparison CLI (`python -m authres.compare`) that writes disagreement
  JSONL and a corpus-level manifest;
- a test-only known-fault mutant (`tests/mutants/`) used solely to prove the
  comparator detects a wrong decision.

It does not implement external authorization engines or adapters, external
compatibility, inconsistency classification, dashboards, or statistical
analysis. No external authorization engine has been executed. Engine B is an
in-project implementation authored by an AI coding agent from the same
specification; it is **not fully independent** and its agreement with the
reference engine is not semantic validation. No real-world measurements
exist.

## 2. Component overview

The Phase 1 reference path is unchanged:

```text
                     JSON policy document
                              |
                              v
                    PolicySet.from_json/from_file
                              |
                              v
  request JSON ---> AccessRequest.from_json ---> ReferenceEngine.evaluate
                                                         |
                                                         v
                                                  EvaluationResult
                                             (decision, reason, matches)
                                                         |
                                                         v
                                           CLI JSON trace (main.py)
```

The comparison path runs the same validated inputs through two engines and
normalizes both results into `EngineOutcome`:

```text
  GeneratorConfig(seed, policies, vocabulary, conflict_rate)
                      |
                      v
              generated PolicySet + AccessRequest (validated)
                      |
          +-----------+------------+
          |                        |
          v                        v
  ReferenceEngineUnderTest    IndexEngine (Engine B)
          |                        |
          +-----------+------------+
                      v
              EngineOutcome (neutral)
                      |
                      v
          run_comparison -> agreement | disagreement |
                            error | timeout | non-decision
                      |
                      v
       CLI counts + disagreement JSONL + corpus manifest
```

The comparator never sees engine-native results. It treats `ERROR`,
`TIMEOUT`, `INDETERMINATE`, and `NOT_APPLICABLE` as separate execution
statuses and never coerces them to ALLOW or DENY.

`authres/engines/contract.py` still contains the neutral types a future
external adapter must satisfy. Engine B is in-project and does not establish
that any external engine can satisfy the contract.

## 3. Modules and responsibilities

| Path | Responsibility |
|---|---|
| `authres/core/models.py` | `Effect`, `Decision`, `DecisionReason`, `Policy`, `AccessRequest`, `EvaluationResult`; construction-time validation; `AccessRequest.from_json`; `EvaluationResult` invariant enforcement |
| `authres/core/policy.py` | `PolicySet`, strict JSON parsing, policy-file loading, deterministic serialization, duplicate-ID checks |
| `authres/core/jsonio.py` | Shared strict JSON decoder (duplicate-key and non-standard-constant rejection) used by both policy and request boundaries |
| `authres/core/canonical.py` | Canonical JSON text/bytes and SHA-256 identity hashing per `docs/canonical-encoding.md` |
| `authres/core/provenance.py` | `RunManifest` for one policy-set/request pair and `ComparisonRunManifest` for a multi-case corpus: identity hashes, semantics/engine/tool versions, Python/platform info, dependency versions, seed and generator config. Identity only — contains no decisions |
| `authres/core/reference_engine.py` | Exact matching, DENY-overrides-ALLOW combination, default DENY, reason codes |
| `authres/core/errors.py` | `AuthResError`, `PolicyValidationError`, `RequestValidationError` |
| `authres/engines/contract.py` | Neutral future-adapter design types: `EngineStatus`, `EngineOutcome`, `EngineAdapter` protocol |
| `authres/engines/index_engine.py` | Engine B: exact-match dictionary index keyed by `(subject, resource, action)` to effect sets; lookup-based DENY-overrides-ALLOW and default DENY; no reference-engine import |
| `authres/compare/generator.py` | Seeded deterministic synthetic policy/request generator with small vocabulary and conflict forcing |
| `authres/compare/comparator.py` | Runs neutral engines on one case, separates agreement/disagreement/errors/timeouts/non-decisions |
| `authres/compare/conflicts.py` | Descriptive request-specific ALLOW/DENY conflict classification (not a decision) |
| `authres/compare/reference_adapter.py` | The only comparison module that imports the reference engine; normalizes `EvaluationResult` to `EngineOutcome` |
| `authres/compare/runner.py` | Corpus-level counts, disagreement records, and conflict statistics |
| `authres/compare/__main__.py` | CLI entry point; writes disagreement JSONL and a corpus manifest |
| `authres/tui/` | Interactive Textual presentation layer. `services/` adapt the core APIs (policy listing/validation, evaluation recording, settings persistence); `screens/` and `widgets/` display data only and import no authorization logic; `app.py` wires screens and keybindings. Run with `python -m authres.tui` |
| `main.py` | Thin CLI adapter; loads one policy file, validates one request, prints the reference result |
| `policies/examples/` | Small hand-written policy documents used in documentation and tests |
| `schemas/` | JSON Schema (draft 2020-12) for policy documents and requests; parser remains normative for rules schemas cannot express |
| `tests/` | Unit, conformance-fixture, property/metamorphic, comparison, CLI-integration, schema-agreement, and contract-boundary tests |
| `tests/mutants/` | Test-adequacy-only known-fault engine; never production code |
| `docs/` | Normative semantics, canonical encoding, architecture, semantic-validation strategy, engine-contract design |

### 3.1 Dependency direction

```text
main.py
  |-- authres.core.policy  -------> authres.core.models ---> authres.core.errors
  |-- authres.core.reference_engine ---> authres.core.models
  |                                  \-> authres.core.policy
  \-- authres.core.models

authres.engines.contract ---> authres.core.models
                         \--> authres.core.policy

authres.engines.index_engine ---> authres.core.models
                             \--> authres.core.policy
                             \--> authres.engines.contract

authres.compare.comparator ---> authres.core.{models,policy}
                           \--> authres.engines.contract
authres.compare.reference_adapter ---> authres.core.reference_engine
authres.compare.runner ---> authres.compare.{comparator,conflicts,generator}
authres.compare.__main__ ---> authres.compare + authres.core.provenance
```

`models.py` does not import the policy loader or the engine.
`authres/engines` may depend only on `authres.core.models`,
`authres.core.policy`, and itself — never on the reference engine — and the
reference engine never imports `authres.engines`. Both directions are
enforced by AST boundary tests in `tests/test_engine_contract.py`.
`authres.compare.reference_adapter` is the deliberate boundary where the
comparison layer imports the reference engine; the comparator itself and
Engine B do not. There are no cyclic imports and no runtime third-party
dependencies.

### 3.2 TUI dependency direction

```text
authres.tui.screens / widgets  (presentation; no authorization logic)
        \-> authres.tui.services  (adapters: listing, recording, settings)
              \-> authres.core.{models, policy, reference_engine, errors}
```

Only `authres/tui/services` may import `authres.core.reference_engine`;
screens, widgets, and `app.py` must not. This is enforced by an AST test in
`tests/test_tui_import.py`. The TUI runs no external engine and changes no
semantics; `main.py` and the CLI path are untouched.

## 4. Key design decisions

### 4.1 Immutable validated models

`Policy`, `AccessRequest`, `PolicySet`, and `EvaluationResult` are frozen
dataclasses. Values are validated when constructed. This prevents the engine
from receiving partially initialized or mutated state and makes repeated
evaluation deterministic.

### 4.2 Validation at the boundary

All parsing and structural validation happens before evaluation:

- JSON policy documents are parsed by `PolicySet.from_json` / `from_file`.
- Request JSON is parsed by `AccessRequest.from_json` (or `from_dict` for
  already-decoded mappings).
- The engine accepts only `PolicySet` and `AccessRequest` instances.

Malformed input raises a validation error. It never becomes a synthetic
authorization decision.

### 4.3 Strict JSON

Policy and request parsing share one strict decoder
(`authres/core/jsonio.py`) that rejects duplicate keys, the non-standard
`NaN`/`Infinity` constants, and malformed JSON. The policy parser additionally
rejects unknown fields, invalid versions, and malformed values. This is a
research-integrity decision: an unsupported feature or ambiguous input must
fail loudly rather than be silently reinterpreted (for example, last-value-
wins duplicate keys), so the executed input always equals the apparent input.
JSON keys and effects are case-sensitive.

### 4.4 Explicit reason codes and result invariants

`Decision` alone cannot distinguish "no policy matched" from "a matching DENY
policy applied"; both are DENY. `DecisionReason` records the cause, and
`EvaluationResult` retains every matched rule. This trace supports later
inspection without changing the decision.

`EvaluationResult` enforces the documented invariants at construction:
`DEFAULT_DENY` requires DENY with no matches; `MATCHED_ALLOW` requires ALLOW
with at least one ALLOW-only match; `MATCHED_DENY` requires DENY with at
least one DENY-only match; `DENY_OVERRIDE` requires DENY with matches
containing both effects. Impossible decision/reason/trace combinations are
rejected with `ValueError`, so a corrupted result cannot silently enter
audit trails or future comparators.

### 4.5 No normalization

The engine compares identifiers with Python string equality. It performs no
case folding, trimming, Unicode normalization, wildcard expansion, or
hierarchy lookup. The rules and their assumptions are documented in
[`policy-semantics.md`](policy-semantics.md).

### 4.6 Deterministic behavior

The reference path has no random seeds, clock reads, network access, or
filesystem access during evaluation. Given the same validated policy set and
request, it returns the same result. Policy order does not affect the decision,
although it is preserved in the matched-policy trace for audit output.

## 5. Error behavior

| Error | Raised when | Example |
|---|---|---|
| `PolicyValidationError` | Policy JSON or model data is invalid | Unknown policy field, bad effect, missing version, duplicate policy ID |
| `RequestValidationError` | Request data is invalid | Missing `action`, empty subject, unknown attribute |
| `TypeError` | Engine receives an object of the wrong type | Passing a dict instead of `AccessRequest` |

The CLI converts validation errors into a clear message on standard error and
exit code `2`. A valid evaluation exits `0`, including when the decision is
DENY.

## 6. Test strategy

Tests are deterministic and use no network or external services. They cover:

- model construction and validation;
- strict JSON parsing and serialization (policy and request boundaries);
- matching ALLOW and DENY policies;
- unmatched requests and default DENY;
- conflicting ALLOW and DENY rules in both orders;
- multiple matching policies, including duplicate identical rules;
- empty policy collections;
- exact and case-sensitive matching, with whitespace preserved as data;
- missing request attributes;
- invalid policies and invalid request documents (duplicate keys,
  non-standard constants, malformed JSON);
- example policy documents;
- CLI exit codes, output, and error messages;
- hand-authored semantics conformance cases (`tests/fixtures/semantics_v1.json`,
  written from the document, not generated by the engine);
- `EvaluationResult` invariant acceptance and rejection;
- engine-contract invariants (`EngineStatus`/`EngineOutcome`);
- AST-based independence boundaries between `authres/engines`, the reference
  engine, and the shared core;
- TUI services (settings persistence, policy listing/validation, evaluation
  recording and export);
- TUI app navigation, help modal, and per-screen behavior (headless pilot
  sessions), including invalid policy/request handling and import safety;
- an AST boundary test keeping authorization logic out of TUI screens and
  widgets;
- canonical encoding rules (key sorting, ASCII form, escapes, hashing,
  Unicode/NUL/lone-surrogate behavior) with expected byte outputs;
- schema/parser agreement in both directions (accepted examples validate,
  rejected examples fail both schema and parser);
- run-manifest construction, repetition, hash coverage, and the
  no-decisions guarantee;
- Hypothesis property tests transcribed from the documented formula:
  order independence, non-matching insertion, duplicate-ID rejection,
  JSON formatting equivalence, re-serialization stability, empty-set
  denial, and trace ordering;
- Engine B against the hand-authored fixture and metamorphic properties
  (order independence, non-matching insertion, documented decision formula);
- comparator agreement, disagreement, error, timeout, and non-decision
  separation using test-local stub engines;
- comparator detection of a deliberately wrong test-only mutant
  (`tests/mutants/allow_overrides_deny.py`);
- generator determinism, exact policy counts, vocabulary bounds, schema and
  parser validity, and conflict forcing;
- corpus runner counts, conflict counts, and JSON-compatible disagreement
  records;
- comparison CLI output, artifact writing, same-seed artifact reproduction,
  manifest hash coverage, and clean rejection of invalid arguments.

Tests verify conformance to the documented semantics and the comparison
machinery. They are not differential tests against an external implementation,
and passing them does not establish that the reference semantics are
universally correct. The validation strategy and its limits are in
[`semantic-validation.md`](semantic-validation.md).

Run from the project root:

```bash
python -m pytest
```

## 7. Reproducibility

The prototype supports reproducibility through:

- explicit policy format versioning and a separate semantics version
  (`authres-policy-v1`);
- immutable validated inputs;
- deterministic evaluation;
- canonical serialization with a defined SHA-256 identity recipe
  (`authres.core.canonical`), so hashes do not depend on formatting;
- run manifests (`authres.core.provenance`) recording policy-set/request
  identity hashes, engine and semantics versions, Python/platform
  information, dependency versions, seed, and generator configuration;
- corpus-level manifests for comparison runs, recording a canonical corpus
  hash, case count, engine versions, seed, and generator configuration;
- a seeded generator with a private `random.Random` instance and no global
  state;
- pinned dependencies (`requirements.txt`) and a CI matrix (Python
  3.11–3.15) running the full suite;
- a CLI and TUI that print complete traces for manual inspection.

Reproducibility status: manifest construction, generation, and evaluation are
deterministic and covered by repetition tests within one interpreter.
Re-running `python -m authres.compare --seed 1 --cases 1000 --policies 5`
twice on the development machine produced byte-identical disagreement JSONL
and manifest files (the disagreement file was empty both times).
**Cross-machine reproducibility has not been verified through actual
repeated runs and is not claimed.** The manifests exist so that runs *can* be
compared.

The comparison harness is minimal: it records raw counts and disagreement
cases, not a full experiment package, statistical analysis, or external
adapter provenance.

## 8. Project tree

```text
authres/
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
│   ├── test_compare_cli.py
│   ├── test_comparator.py
│   ├── test_conflicts.py
│   ├── test_engine_contract.py
│   ├── test_generator.py
│   ├── test_index_engine.py
│   ├── test_metamorphic.py
│   ├── test_runner.py
│   └── ... existing Phase 1/TUI tests ...
├── main.py
├── pytest.ini
├── requirements.txt
└── README.md
```

## 9. Extension points for later phases

Future work must preserve the version 1 reference semantics. The minimal
comparison increment provides a base; remaining extensions require separate
designs:

1. **External engines** — external adapters implementing the
   `EngineAdapter` protocol from [`engine-contract.md`](engine-contract.md),
   each owning its own policy translation, with engine versions and
   configuration recorded and no shared decision logic. Engine B is not an
   external adapter.
2. **Independent semantic validation** — an independent human review and/or a
   document-first reimplementation by an author who did not write the current
   engines, per [`semantic-validation.md`](semantic-validation.md).
3. **Inconsistency analysis** — classify disagreements and distinguish
   reference errors, Engine B errors, adapter errors, and genuine semantic
   differences. The current harness records raw disagreements but does not
   adjudicate them.
4. **Experiment package** — versioned corpora, full per-case outcomes,
   statistical analysis, and cross-machine reproduction checks.
5. **Richer policy semantics** — conditions, wildcards, and delegation require
   a new format version, updated reference model, and new validation rules.

## 10. Current limitations

- The reference model is implemented and tested only against its own documented
  semantics, a hand-authored conformance fixture, property tests, and Engine B.
  No independent human review or external conformance run exists
  ([`semantic-validation.md`](semantic-validation.md)).
- Engine B was written by an AI coding agent from the same specification and in
  the same project. It uses a different algorithm but is not fully
  independent; shared misreadings are possible. Its agreement with the
  reference engine is not proof of correctness.
- No external authorization engine has been executed or compared, and the
  engine contract remains unproven against an external system.
- Generated data is synthetic. The observed 1000/1000 agreement for seed 1 is
  not a real-world agreement rate and must not be described as one.
- The comparator's timeout implementation runs engines in daemon threads;
  Python cannot forcibly stop a hung worker, so a timed-out engine is marked
  unavailable for that case while the worker may finish in the background.
- The harness writes disagreement JSONL and a manifest, but it does not
  classify disagreements or prove that a disagreement is an engine fault.
- A decision difference is a signal for investigation, not proof of a
  vulnerability.
- TUI session results are in-memory only; the TUI is not connected to the
  comparison harness, and its exports use the existing serialization
  contracts.
