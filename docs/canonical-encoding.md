# AuthRes Canonical Encoding and JSON Rules — Version 1

**Status:** normative for serialization, hashing, and identifier equality of
policy format version 1 and access requests. It changes no authorization
semantics defined in [`policy-semantics.md`](policy-semantics.md).
**Schemas:** [`schemas/policy-v1.schema.json`](../schemas/policy-v1.schema.json),
[`schemas/request-v1.schema.json`](../schemas/request-v1.schema.json).
**Implementation:** `authres/core/canonical.py`, `authres/core/jsonio.py`,
`authres/core/models.py`, `authres/core/policy.py`.

## 1. Canonical JSON form

The canonical form of a JSON-compatible value is defined by
`authres.core.canonical.canonical_json`:

1. Object keys are sorted ascending by Unicode code point.
2. No insignificant whitespace: separators are `,` and `:` only; no
   indentation; no trailing newline in the canonical text itself.
3. The output is pure ASCII. Any character outside U+0020–U+007E is emitted
   as a `\uXXXX` escape in lowercase hexadecimal. Control characters are
   escaped, never emitted as raw bytes: NUL is `\u0000`, and the five
   characters with JSON short escapes (`\b`, `\t`, `\n`, `\f`, `\r`) use
   those standard two-character escapes; all other control characters use
   `\uXXXX`. Non-ASCII letters are always `\uXXXX` (so `é` NFC is `\u00e9`,
   `é` NFD is `e\u0301`).
4. Numbers appear only in their parsed JSON form. The only number in format
   version 1 is the integer `version: 1`; arrays of policies contain no
   numeric values. `allow_nan=False` makes `NaN`/`Infinity` an error here
   even though the input boundary already rejects them.
5. The canonical byte string is the canonical text encoded as UTF-8. Because
   the text is pure ASCII, the UTF-8 encoding is identical to the ASCII
   bytes and cannot fail.

**Hash recipe:** identity hash = lowercase hex SHA-256 over the canonical
byte string (`canonical_sha256`). Two documents have equal hashes iff their
parsed representations are equal — formatting (whitespace, key order,
escaping choices of the source document) never changes the hash.

Every rule above is tested in `tests/test_canonical.py`.

## 2. Unicode handling

| Rule | Statement | Test |
|---|---|---|
| U1 | Identifiers are sequences of Unicode code points. Equality is **code-point equality** (Python `str ==`). | `test_nfc_and_nfd_identifiers_are_distinct` |
| U2 | No normalization of any kind is performed at parse, match, serialization, or hash time. NFC and NFD forms of the same visible text are **different identifiers** and never match. | `test_nfc_and_nfd_identifiers_are_distinct` |
| U3 | No case folding. Case differences are mismatches. | `test_case_differences_never_match` |
| U4 | Whitespace inside identifiers is significant; only strings that are entirely whitespace are rejected (`_require_identifier`). | existing model tests; schema `pattern: "\\S"` |
| U5 | The canonical form is ASCII-only (rule 3), so the hash of an identifier depends only on its code points, not on any environment's normalization settings. | `test_canonical_form_is_ascii_only` |

Rationale: a research instrument must not silently repair data. Normalizing
"look-alike" identifiers would make equality environment-dependent and could
hide real inconsistencies between engines in Phase 2.

## 3. NUL characters

- NUL (`U+0000`) is a legal character inside identifiers. It is **permitted
  and significant**: an identifier containing NUL differs from the same
  identifier without it, and matching treats them as unequal.
- The canonical form emits NUL as `\u0000` (rule 3); it is never emitted as
  a raw zero byte and never stripped.
- Tests: `test_nul_is_significant_in_matching`,
  `test_nul_survives_canonical_round_trip`.

## 4. Lone surrogates

Python's `json` parser accepts `"\ud800"` (a lone surrogate). The canonical
form remains total over such values because it emits ASCII `\ud800`
escapes; the identity hash is therefore still defined and stable **within
Python tooling**. Caveats, stated rather than hidden:

- Lone surrogates are not valid Unicode scalar values; other languages'
  JSON libraries may reject or re-encode them. Fixtures intended for
  cross-implementation comparison must not contain them.
- The JSON Schema `pattern` facets do not test for them.

Tests: `test_lone_surrogate_is_canonical_and_stable`,
`test_lone_surrogate_identifiers_match_exactly`.

## 5. Duplicate keys and non-finite numbers

- Duplicate JSON keys are **rejected** at both the policy and request input
  boundaries (`authres.core.jsonio`), with last-value-wins forbidden. The
  canonical form is defined over already-parsed values, so a duplicate key
  cannot reach it. Tested by the existing strict-JSON suite and referenced
  here as normative.
- `NaN` and `Infinity` are **not valid JSON** and are rejected at the input
  boundary; `allow_nan=False` re-enforces this at the canonical boundary.
  Tested in the existing strict-JSON suite and
  `test_canonical_rejects_non_finite_numbers`.

## 6. Schema scope and limits

The JSON Schemas express: required/optional fields, exact field sets
(`additionalProperties: false`), types, the `version` constant, the effect
enum, and the identifier rule (`minLength: 1`, `pattern: \S`).

They deliberately do **not** express (the Python parser remains normative):

- duplicate-key rejection (JSON Schema sees post-parse objects);
- uniqueness of `id` across `policies` items;
- rejection of `NaN`/`Infinity` constants;
- Unicode subtleties such as lone surrogates.

`tests/test_schema.py` validates both schema files, checks that parser-
accepted examples validate and parser-rejected examples fail, and pins the
agreement between the schema and the parser.

## 7. Versioning

Any change to the rules in this document requires a new document version and
a compatibility statement for existing hashes: hashes are version-bound by
`semantics_version`/`manifest_version` fields in run manifests
(`authres.core.provenance`). Hash equality is only meaningful between
manifests with the same versions.
