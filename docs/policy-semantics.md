# AuthRes Policy Semantics — Version 1

**Status:** normative definition for the Phase 1 reference engine.  
**Scope:** condition-free authorization policies and single access requests.  
**Serialization, hashing, and identifier equality:** normative rules are in
[`canonical-encoding.md`](canonical-encoding.md) (JSON Schemas in `schemas/`).  
**Implementation:** `authres/core/models.py`, `authres/core/policy.py`, and
`authres/core/reference_engine.py`.

This document defines the reference model. It does **not** claim that the
model matches any external authorization product, specification, or standard.
No external engine has been integrated or compared yet.

## 1. Purpose and domain

An authorization decision is made for one request against one policy set.
Requests and policies use the same three attributes:

| Attribute | Type | Meaning |
|---|---|---|
| `subject` | string | The principal requesting access |
| `resource` | string | The object being accessed |
| `action` | string | The operation being attempted |

The attribute names and meanings are fixed by this model. The values are
opaque identifiers: this version assigns no hierarchy, wildcard, or semantic
meaning to them.

## 2. Policy model

A policy rule contains:

| Field | Required | Type | Meaning |
|---|---|---|---|
| `subject` | yes | non-empty string | Subject value that must match exactly |
| `resource` | yes | non-empty string | Resource value that must match exactly |
| `action` | yes | non-empty string | Action value that must match exactly |
| `effect` | yes | `ALLOW` or `DENY` | Outcome to apply when the rule matches |
| `id` | no | non-empty string | Reporting identifier; no effect on the decision |

### 2.1 Effects

Only two effects exist:

- `ALLOW`: grants access when the rule matches, unless a matching `DENY`
  overrides it.
- `DENY`: denies access when the rule matches.

The JSON representation accepts only the exact uppercase strings `"ALLOW"`
and `"DENY"`. Lowercase or mixed-case values are validation errors; they are
not normalized.

### 2.2 Policy IDs

`id` is optional. When present it must be a non-empty string and must be unique
within a policy set. IDs are metadata for traces and future analysis; they do
not participate in matching or conflict resolution, and are not required to
construct a valid policy.

## 3. JSON policy representation

A policy document is a JSON object with exactly two fields:

- `version`: integer `1`.
- `policies`: JSON array of policy objects.

Example:

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

An empty `policies` array is valid.

### 3.1 Parsing strictness

The reference policy format intentionally rejects:

- malformed JSON;
- a root value that is not an object;
- missing required top-level or policy fields;
- unknown top-level or policy fields;
- a `version` other than the integer `1`;
- `policies` that is not an array;
- duplicate JSON object keys;
- `NaN` and `Infinity`, which are not valid JSON;
- non-string or empty/whitespace-only identifiers;
- invalid effect values;
- duplicate non-null policy IDs.

Unknown fields are rejected so unsupported features cannot be silently
ignored. For example, adding a `condition` field without updating the format
version produces a validation error rather than a policy that is evaluated
with the condition missing.

Validation failures raise `PolicyValidationError`. They are not transformed
into an authorization decision.

## 4. Access request model

A request has exactly three required attributes:

- `subject`
- `resource`
- `action`

All are non-empty strings. Request data is validated through
`AccessRequest.from_dict` (or by constructing `AccessRequest`) before the
engine is called. Missing, unknown, or invalid attributes raise
`RequestValidationError`. The reference engine accepts only a validated
`AccessRequest`; it does not silently fill missing values.

## 5. Matching

A policy matches a request if and only if all three conditions hold:

```
policy.subject  == request.subject
policy.resource == request.resource
policy.action   == request.action
```

Matching has these properties:

- **Exact:** there is no prefix, substring, wildcard, glob, or regular
  expression matching.
- **Case-sensitive:** `alice`, `Alice`, and `ALICE` are distinct values.
- **No normalization:** values are not trimmed, Unicode-normalized, or
  case-folded. Leading and trailing whitespace is significant. A value made
  only of whitespace is rejected as invalid.
- **No hierarchy:** resources are opaque labels; there is no notion of a
  parent resource or inherited permission.
- **Effect-free:** `ALLOW` and `DENY` policies match on the same three
  attributes. Effect affects the result, not whether the rule matches.

## 6. Combining rule and default

Let `M` be the set of all policies in the policy set that match the request.

1. If `M` is empty, the decision is **DENY** (default deny).
2. If any policy in `M` has effect `DENY`, the decision is **DENY**, even if
   other matching policies have effect `ALLOW`.
3. Otherwise all policies in `M` have effect `ALLOW`, and the decision is
   **ALLOW**.

Equivalently:

```
if M is empty:          DENY
elif any DENY in M:     DENY
else:                   ALLOW
```

Policy order, policy count, and policy IDs do not affect the decision. An
empty policy set therefore denies every request.

### 6.1 Why conflict is request-specific

In this document, a conflict exists when a request matches at least one
`ALLOW` policy and at least one `DENY` policy. It is not a claim that two
policy rules are globally contradictory for all possible requests. A
disagreement or conflict observed by AuthRes is an observation to investigate,
not automatically a vulnerability.

## 7. Decision reasons

The reference engine returns both a decision and a reason code. The reason
distinguishes an explicit deny from the default:

| Reason | Decision | Condition |
|---|---|---|
| `DEFAULT_DENY` | `DENY` | No policy matched, including the empty policy set |
| `MATCHED_ALLOW` | `ALLOW` | At least one policy matched; all matches are `ALLOW` |
| `MATCHED_DENY` | `DENY` | At least one policy matched; all matches are `DENY` |
| `DENY_OVERRIDE` | `DENY` | Matches include at least one `ALLOW` and at least one `DENY` |

The result also records every matched policy for auditability. Matched
policies are listed in policy-set order. This order is descriptive only and
does not influence the decision.

## 8. Evaluation algorithm

```text
evaluate(policy_set, request):
    matched = [
        policy for policy in policy_set.policies
        if policy.subject == request.subject
        and policy.resource == request.resource
        and policy.action == request.action
    ]

    if matched is empty:
        return DENY with reason DEFAULT_DENY

    if any(match.effect == DENY for match in matched):
        if any(match.effect == ALLOW for match in matched):
            return DENY with reason DENY_OVERRIDE
        return DENY with reason MATCHED_DENY

    return ALLOW with reason MATCHED_ALLOW
```

The implementation is a pure function of the validated policy set and request.
It uses no randomness, clock, network, filesystem access during evaluation, or
mutable global state.

## 9. Invalid input versus denied access

These are different outcomes:

- **Invalid policy or request data:** raise a validation error. No decision is
  produced.
- **Valid request with no match:** produce `DENY` with reason `DEFAULT_DENY`.

This distinction matters for experiments. A malformed policy must not be
counted as a legitimate DENY decision, because doing so would make an
implementation error look like authorization behavior.

## 10. Explicit assumptions and limitations

The following assumptions are part of version 1 and must be reconsidered
before extending the model:

1. Identifiers are arbitrary non-empty strings with no external meaning.
2. String equality is exact and case-sensitive; Unicode normalization is not
   performed.
3. Every policy is unconditional and applies to all contexts.
4. There are no wildcard, hierarchy, ownership, delegation, temporal,
   environmental, or attribute-based conditions.
5. A policy set is a flat collection; there is no nesting or inheritance.
6. Policy order is irrelevant to the decision.
7. Duplicate matching rules are permitted; duplicate explicit policy IDs are
   not.
8. All policies use the same format version.
9. DENY overrides ALLOW. There is no "first match" or "last match" rule.
10. The default decision is DENY.
11. The reference engine is the reference model only by project convention. Its
    correspondence to an external specification or product is not established,
    and its semantics have no independent validation beyond implementation
    self-consistency and a hand-authored conformance fixture. See
    [`semantic-validation.md`](semantic-validation.md) for the evidence ladder
    and the list of assumptions that cannot yet be independently validated.
12. Results produced with this model are synthetic reference results, not
    evidence about real deployments or vulnerabilities.

## 11. Extension policy

Adding conditions, wildcards, delegation, or other matching features requires
an explicit format-version change and corresponding updates to:

- this semantics document;
- validation logic;
- the reference engine;
- tests;
- example policies.

Because unknown fields are rejected, older parsers will not silently ignore
new fields. New format versions must not change the meaning of version 1
documents.
