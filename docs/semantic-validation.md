# AuthRes Semantic Validation Strategy

**Status:** process document for the reference baseline plus the minimal
synthetic comparison harness.  
**Scope:** what evidence exists for the version 1 semantics, what does not
exist yet, what evidence each claim requires, and the process for obtaining
independent validation before external-engine comparisons are run.

This document does **not** claim that the version 1 semantics are correct.

## 1. Three distinct claims, three distinct evidence types

These are frequently conflated. They are kept separate here and in every
status statement:

| Layer | Claim | Evidence that supports it |
|---|---|---|
| L-spec | The **normative specification** (`docs/policy-semantics.md`, `docs/canonical-encoding.md`) is complete, unambiguous, and internally consistent | Human review against an external checklist, reviewer sign-off, schema cross-checks; **never** implementation behavior |
| L-ref | The **reference implementation** is a faithful transcription of the normative specification | Independent reimplementation or independent review of `reference_engine.py` against the document; the property suite narrows the space but does not close it |
| L-ext | An **external adapter** is a faithful transcription of the same specification | Adapter conformance fixtures authored from the document, executed against that adapter; never against the reference engine's output |

Consequences stated explicitly:

- Two engines agreeing proves, at most, that they implement the same shared
  reading of the document. If both authors share a misreading (a common-mode
  error), agreement is fully consistent with an incorrect specification.
  Agreement is **never** automatic proof of semantic correctness.
- The reference engine passing tests is evidence only for L-ref, and only
  for the cases tested.
- Nothing in this repository currently establishes L-spec beyond the
  document's own internal consistency checks (schema/parser agreement and
  property tests, which are implementation-derived in part).

## 2. Evidence ladder

| Level | Evidence | Status |
|---|---|---|
| L0 | Engine satisfies its own unit tests | Present |
| L0 | Truth-table verification of matched-effect combinations (review-time script, 123 configurations) | Performed once, not retained |
| L1 | Hand-authored conformance fixture `tests/fixtures/semantics_v1.json` (15 cases) | Present |
| L1.5 | Metamorphic/property suite `tests/test_metamorphic.py` (Hypothesis): order independence, non-matching insertion, duplicate-ID rejection, JSON formatting equivalence, empty-set denial, trace ordering, documented-formula transcription | Present; expectations transcribed from the document, but by the same project — shared-misreading risk remains |
| L1.6 | In-project second implementation, Engine B (`authres/engines/index_engine.py`), different dictionary-index algorithm; fixture conformance, metamorphic tests, and a 1000-case synthetic comparison | Present; **not independent**. Engine B was written by the same AI coding agent from the same specification in the same project. Agreement closes no L-spec question and does not count as L2 |
| L2 | Independently authored implementation of the same specification, compared case by case | Absent |
| L2 | Independent human specification review with sign-off | Absent |
| L3 | Conformance runs against external, independently developed authorization engines | Absent; out of scope for this increment and blocked on the mapping contract |

L1.5 strengthens the *transcription* check: the expected outcomes in
`test_metamorphic.py` come from a locally transcribed copy of the
documented formula, not from the engine. It does not validate the document.

L1.6 is intentionally labelled below L2. Engine B exercises a different
algorithm (index lookup rather than a matching scan), but authorship and
specification reading are shared with the reference engine. A 1000/1000
agreement result on synthetic inputs is therefore evidence about
implementation consistency within this project, not independent validation.

The comparator is tested for fault detection with a deliberately wrong
test-only mutant (`tests/mutants/allow_overrides_deny.py`). That demonstrates
test adequacy for one injected fault; it does not validate either engine.

## 3. Normative versus implementation-derived expectations

Rules for hand-authored expectations (currently realized by
`tests/fixtures/semantics_v1.json` and the transcription function in
`tests/test_metamorphic.py`):

- Expected `decision`, `reason`, and `matched_policy_ids` are written from
  `docs/policy-semantics.md`, never computed by `ReferenceEngine`.
- Fixtures use raw JSON documents and requests, exercising the real
  parsing boundary.
- Both artifacts are versioned and change only with a documented reason.

Known limits, stated plainly:

- The fixture author and the engine author share one project context;
  shared misreadings are invisible to both.
- Fifteen cases are a regression floor, not exhaustive.
- Property strategies cover the documented decision core; they do not reach
  undocumented corners (there should be none — that is L-spec's job to
  confirm).

## 4. Assumptions not yet independently validated

| # | Assumption | Why it is not yet validated |
|---|---|---|
| A1 | DENY-overrides-ALLOW is the intended conflict rule | Specification choice, not derivable. Confirmable only by independent review or external mapping demonstration. |
| A2 | Exact string equality means Unicode code-point comparison (no normalization, no case folding) | Now **documented normatively** and machine-tested (`docs/canonical-encoding.md`, `tests/test_canonical.py`), but the *choice* itself still awaits independent review (L-spec). |
| A3 | The document is complete (no unspecified behavior) | No completeness review against an external checklist performed. |
| A4 | Default DENY, including for an empty policy set, is the intended closed-world behavior | Chosen convention; same status as A1. |
| A5 | Optional policy IDs do not affect decisions; `None` trace entries are acceptable provenance | Run manifests now hash the *whole* policy set (`tests/test_provenance.py`), decoupling experiment identity from IDs; the semantic question itself is unchanged. |
| A6 | Strict rejection (rather than normalization) of case, whitespace, and JSON anomalies is correct for research inputs | Deliberate design choice; effect on later translation fidelity unmeasured. |
| A7 | The three-attribute exact-match model can be expressed faithfully in external engines | Nothing compiled into any engine; untested. |

## 5. Required evidence before oracle status

Before the version 1 semantics may be described as validated, at least one
of the following processes must have been executed with recorded, versioned
evidence:

### 5.1 Independent review process (L-spec + L-ref)

1. A reviewer who did not author the implementation reads
   `docs/policy-semantics.md` and `docs/canonical-encoding.md` and produces
   a written review: ambiguities, incompleteness, undocumented edge cases,
   each mapped to a checklist (outcome taxonomy, conflict resolution,
   defaults, error handling, identifier equality).
2. Every reviewer finding becomes either a document amendment (version
   bump) or a recorded decision to keep current behavior.
3. The reviewer then reviews `reference_engine.py` **against the amended
   document** and lists transcription errors, without reading the test
   suite first. Findings are triaged: document bug, code bug, or both.
4. Sign-off: the reviewer states which of L-spec/L-ref they can attest to
   and which remain unattested. The sign-off is stored in the repository
   with its date and reviewer identity.

### 5.2 Independent reimplementation process (L-ref)

1. A second implementation of the document is written **from the document
   alone**, by an author (or session) that does not read
   `reference_engine.py` first.
2. Both implementations run on a shared, versioned corpus: the L1 fixture,
   the property-generated cases, plus randomized effect-combination and
   identifier cases (NUL, NFC/NFD, whitespace, case).
3. All disagreements are resolved by **document amendment**, never by
   silently changing either implementation. Amendments trigger a version
   bump of the affected document.
4. Agreement is recorded with corpus version, both implementations'
   versions, and the amendment log.

Engine B does **not** satisfy step 1: it was written from the document by the
same AI coding agent that works in this repository, in the same project
context as the reference engine. It is useful as a different-algorithm
cross-check, but it cannot close L-ref or L-spec.

### 5.3 Why agreement alone is not proof

If two implementations agree, the posterior probability that the document
is correct rises only when the implementations' *authors and readings are
independent*. Common-mode failures are the threat: same author, same
tutorial, same standard misread, same test corpus. This is why 5.2
mandates document-first authorship and document-mediated disagreement
resolution, and why L-ext fixtures are authored from the document, never
from reference-engine output.

## 6. Current status statement

As of the minimal Phase 2 comparison increment: L0, L1, L1.5, and L1.6
evidence exists. Schema/canonicalization rules are documented normatively and
machine-tested (partial R8 resolution). Engine B agrees with the reference
engine on the hand-authored fixture and on the executed synthetic corpus
(`--seed 1 --cases 1000 --policies 5`: 1000 agreements, 0 disagreements, 263
request-specific conflict cases). Those are same-project, synthetic
observations, not independent validation. No L2 or L3 evidence exists. The
reference engine's semantics are unvalidated beyond self-consistency,
hand-authored conformance, property testing, and an in-project
different-algorithm cross-check. No conformance result may be reported as
evidence of external compatibility, and no cross-machine reproducibility
claim may be made until repeated runs are actually verified (see
`docs/architecture.md` §7 and the manifest module's own status note).
