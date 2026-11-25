# AuthRes Engine Contract — Design for External Adapters

**Status:** design for external adapters. No external adapter is implemented,
no external engine has been executed, and **no compatibility with any engine
is established or claimed**. The in-project comparison harness (Engine B plus
`authres/compare`) implements this neutral outcome model for two in-project
engines; that is not external validation.

**Scope:** the neutral outcome model, the adapter protocol, the policy and
request mapping contract, and the independence guardrails for Phase 2.

## 1. Design goals

1. Every external engine result is recorded in a neutral form that the
   comparison layer can consume without knowing the engine.
2. Authorization decisions are separated from execution statuses, so an
   engine failure or non-decision can never be silently coerced into an
   ALLOW/DENY data point.
3. Policy translation is owned by each adapter; no decision logic is shared
   between engines, and the reference engine is never reused for translation
   or evaluation.
4. Mismatches can later be attributed: to the engine, to the translation, or
   to the specification — never silently to whichever the tooling prefers.

## 2. Neutral outcome model

Implemented in `authres/engines/contract.py`; tested by
`tests/test_engine_contract.py`.

### 2.1 Execution statuses

| Status | Meaning | Carries a decision? |
|---|---|---|
| `DECIDED` | The engine evaluated the request and returned a definitive result | Yes, exactly one of ALLOW/DENY |
| `NOT_APPLICABLE` | The engine reports that no policy applied to the request | No |
| `INDETERMINATE` | The engine could not reach a definitive result from the loaded policy | No |
| `ERROR` | The engine failed (crash, invalid translated artifact, unexpected output) | No |
| `TIMEOUT` | The engine did not return within the configured budget | No |

These statuses deliberately mirror the outcome taxonomy of XACML-style
authorization architectures. The names are a design reference; no XACML
conformance is claimed.

### 2.2 `EngineOutcome`

Fields: `engine_id`, `engine_version`, `status`, `decision` (optional),
`detail` (optional diagnostic).

Invariants, all enforced at construction:

- `engine_id` and `engine_version` are non-empty, non-whitespace strings.
- `DECIDED` requires a `Decision` (ALLOW or DENY); it cannot be omitted.
- Only `DECIDED` may carry a decision; every other status requires
  `decision=None`.
- `ERROR` and `TIMEOUT` require a non-empty `detail`.
- No reference-specific reason codes or matched-policy traces. Those belong
  to `EvaluationResult` and are never fabricated for external engines.

### 2.3 Decisions versus statuses

The reference `Decision` (ALLOW/DENY) is a policy outcome. `EngineStatus` is
an execution outcome. They are different axes:

```text
EngineStatus.DECIDED        -> has Decision.ALLOW or Decision.DENY
EngineStatus.NOT_APPLICABLE -> no decision; comparable to reference DEFAULT_DENY only by explicit analysis
EngineStatus.INDETERMINATE  -> no decision; flagged for analysis
EngineStatus.ERROR/TIMEOUT  -> no decision; excluded from agreement statistics, reported separately
```

**Mapping rule for `NOT_APPLICABLE`:** the reference semantics have no
not-applicable state — a request that matches nothing is `DEFAULT_DENY`
(DENY). An adapter must not map `NOT_APPLICABLE` to DENY automatically.
Whether "no applicable policy" means the same thing as "no matching policy"
in a given engine is a semantic question that must be resolved in that
adapter's documented mapping and recorded per outcome. Until resolved, the
outcome is treated as non-decision evidence.

**Mapping rule for unknown states:** if an engine returns a state the adapter
does not recognize, the adapter must emit `ERROR` with a `detail` describing
the raw result. Guessing a decision is prohibited.

## 3. Adapter protocol

`EngineAdapter` is a structural `Protocol` with three separated stages:

```text
compile(policy_set: PolicySet) -> TCompiled     # translation, adapter-owned
execute(compiled, request: AccessRequest) -> TRaw  # engine execution
normalize(raw: TRaw) -> EngineOutcome           # no invention of decisions
```

Plus read-only `engine_id` and `engine_version` recorded in every outcome.

Stage separation exists so that:

- translation defects can be reproduced and fixed without rerunning the
  engine (compile once, execute many);
- raw engine output is retained for diagnosis, not discarded during
  normalization;
- the comparison layer never sees engine-native structures.

The comparison layer itself is **outside** this protocol. It is implemented
in `authres/compare/` and consumes only `EngineOutcome` values and normalized
reference results, never engine-native results. It reports non-`DECIDED`
statuses as their own class of outcome rather than as disagreements or
agreements. Engine B (`authres/engines/index_engine.py`) is an in-project
engine, not an external adapter.

## 4. Mapping contract (R3)

An adapter must document all of the following before its outcomes may be
used in any comparison:

### 4.1 Request translation

- The three attributes (`subject`, `resource`, `action`) are transmitted as
  exact strings. The adapter must specify the encoding it sends (for example
  UTF-8) and must not trim, case-fold, normalize, or otherwise transform
  values.
- Exact-match requirement: the effective comparison performed by the engine
  must be equality over the transmitted strings with no normalization. If
  the engine cannot be configured to guarantee this, the adapter must record
  the limitation; its outcomes are then not comparable to the reference
  engine for identifier values that could collide under that engine's
  comparison.

### 4.2 Policy translation

- Each AuthRes policy becomes one engine rule requiring exact equality on
  all three attributes with the policy's effect.
- Optional AuthRes policy IDs: when an engine requires identifiers, the
  adapter generates deterministic IDs (for example `p1..pN` in policy-set
  order) and records the mapping in translation provenance. Original IDs
  remain in the AuthRes `PolicySet` and reference trace; the generated IDs
  exist only inside the engine.
- Duplicate AuthRes rules must be preserved as duplicate engine rules, not
  deduplicated, because duplicate counts are part of matching behavior.

### 4.3 Conflict resolution and defaults

- The engine must be configured so that when both ALLOW and DENY match, the
  result is DENY (DENY-overrides-ALLOW).
- When no policy matches, the engine result must correspond to
  `DECIDED`/DENY — not `NOT_APPLICABLE` — for comparability with the
  reference `DEFAULT_DENY`. If the engine cannot be configured that way, the
  discrepancy must be documented in the adapter's mapping notes.
- An empty policy set is a valid input and must compile to an empty rule
  set, producing `DECIDED`/DENY under the same rule.

### 4.4 Outcome normalization table

Each adapter must provide a table mapping every externally observable engine
result to `EngineOutcome`:

| Engine observation | Required normalized outcome |
|---|---|
| Definitive allow | `DECIDED` / `Decision.ALLOW` |
| Definitive deny | `DECIDED` / `Decision.DENY` |
| No applicable policy / no match | `NOT_APPLICABLE` unless the mapping in 4.3 guarantees DENY, in which case `DECIDED`/DENY with the justification recorded |
| Indeterminate / undecidable | `INDETERMINATE` with detail |
| Crash, invalid output, parse failure | `ERROR` with detail |
| Exceeded time budget | `TIMEOUT` with detail |
| Unrecognized state | `ERROR` with detail containing the raw result |

### 4.5 Provenance

Every `EngineOutcome` records `engine_id` and `engine_version`. Future work
(planned for the comparison layer, not this increment): translation
provenance linking outcomes to a compiled-policy artifact and a policy-set
version, so that a mismatch can be re-run against the exact translation used.

## 5. Independence guardrails (R4)

- **Import boundary (tested).** `authres/engines` may import only
  `authres.core.models`, `authres.core.policy`, and its own package. It must
  never import `authres.core.reference_engine`. Enforced by AST inspection in
  `tests/test_engine_contract.py::TestIndependenceBoundaries`.
- **Reference independence (tested).** `authres.core.reference_engine` must
  not import `authres.engines`; the reference engine is a standalone model.
- **No shared decision helpers.** Adapters implement their own matching,
  combination, and default configuration. There is no shared "decision
  helper" module for adapters to call.
- **Translation ownership.** `compile` is adapter-owned. No project-provided
  translator may be injected into an adapter.
- **Raw retention.** `execute` returns engine-native raw output; `normalize`
  is the only place raw becomes neutral, and it must not be used to fabricate
  decisions for non-decided statuses.

## 6. Explicit non-claims

- No external engine has been integrated, executed, or compared.
- No conformance result exists, and none may be fabricated. Agreement between
  the reference engine and in-project Engine B is not external conformance.
- The status taxonomy is inspired by common authorization architectures; no
  standard conformance is claimed.
- This contract remains a design target for external adapters. It does not
  demonstrate that any external engine can satisfy it.
