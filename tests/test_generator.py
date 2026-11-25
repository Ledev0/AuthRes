"""Generator tests: determinism, validity, vocabulary, and conflict forcing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from authres.compare.generator import (
    GeneratedCase,
    GeneratorConfig,
    generate_cases,
)
from authres.core.models import AccessRequest, Effect
from authres.core.policy import PolicySet

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = PROJECT_ROOT / "schemas"

POLICY_VALIDATOR = Draft202012Validator(
    json.loads(
        (SCHEMAS_DIR / "policy-v1.schema.json").read_text(encoding="utf-8")
    )
)
REQUEST_VALIDATOR = Draft202012Validator(
    json.loads(
        (SCHEMAS_DIR / "request-v1.schema.json").read_text(encoding="utf-8")
    )
)


def assert_case_is_valid(case: GeneratedCase) -> None:
    policy_document = case.policy_set.to_dict()
    request_document = case.request.to_dict()

    POLICY_VALIDATOR.validate(policy_document)
    REQUEST_VALIDATOR.validate(request_document)

    reparsed_policy = PolicySet.from_json(json.dumps(policy_document))
    reparsed_request = AccessRequest.from_json(json.dumps(request_document))
    assert reparsed_policy == case.policy_set
    assert reparsed_request == case.request


class TestDeterminism:
    def test_same_seed_and_config_produce_identical_corpus(self) -> None:
        config_a = GeneratorConfig(
            seed=1234,
            policies=5,
            vocabulary_size=4,
            conflict_rate=0.4,
        )
        config_b = GeneratorConfig(
            seed=1234,
            policies=5,
            vocabulary_size=4,
            conflict_rate=0.4,
        )

        first = [case.to_dict() for case in generate_cases(config_a, 40)]
        second = [case.to_dict() for case in generate_cases(config_b, 40)]

        assert first == second
        assert json.dumps(first) == json.dumps(second)

    def test_different_seeds_produce_different_corpora(self) -> None:
        first = [
            case.to_dict()
            for case in generate_cases(
                GeneratorConfig(seed=1, policies=4), 20
            )
        ]
        second = [
            case.to_dict()
            for case in generate_cases(
                GeneratorConfig(seed=2, policies=4), 20
            )
        ]

        assert first != second

    def test_prefix_is_stable_when_case_count_grows(self) -> None:
        config = GeneratorConfig(seed=99, policies=3)
        short = [
            case.to_dict() for case in generate_cases(config, 5)
        ]
        long = [
            case.to_dict() for case in generate_cases(config, 10)
        ]

        assert long[:5] == short


class TestValidity:
    def test_all_generated_cases_validate(self) -> None:
        cases = generate_cases(
            GeneratorConfig(
                seed=5,
                policies=7,
                vocabulary_size=5,
                conflict_rate=0.5,
            ),
            count=100,
        )

        for case in cases:
            assert_case_is_valid(case)

    def test_policy_count_is_exact_and_ids_unique(self) -> None:
        cases = generate_cases(
            GeneratorConfig(seed=8, policies=6), count=25
        )

        for case in cases:
            assert len(case.policy_set.policies) == 6
            ids = [
                policy.policy_id for policy in case.policy_set.policies
            ]
            assert len(ids) == len(set(ids))
            assert all(policy_id is not None for policy_id in ids)

    def test_values_come_from_small_vocabulary(self) -> None:
        cases = generate_cases(
            GeneratorConfig(seed=11, policies=10, vocabulary_size=3),
            count=20,
        )
        subjects = {f"s{index}" for index in range(3)}
        resources = {f"r{index}" for index in range(3)}
        actions = {f"a{index}" for index in range(3)}

        for case in cases:
            assert case.request.subject in subjects
            assert case.request.resource in resources
            assert case.request.action in actions
            for policy in case.policy_set.policies:
                assert policy.subject in subjects
                assert policy.resource in resources
                assert policy.action in actions

    def test_zero_policies_produces_valid_empty_sets(self) -> None:
        cases = generate_cases(
            GeneratorConfig(seed=3, policies=0), count=5
        )

        assert len(cases) == 5
        for case in cases:
            assert case.policy_set.policies == ()
            assert_case_is_valid(case)

    def test_zero_cases(self) -> None:
        assert generate_cases(GeneratorConfig(seed=1), 0) == []


class TestConflictRate:
    def test_rate_one_forces_conflict_in_every_eligible_case(self) -> None:
        cases = generate_cases(
            GeneratorConfig(
                seed=12,
                policies=2,
                vocabulary_size=4,
                conflict_rate=1.0,
            ),
            count=50,
        )

        for case in cases:
            effects = {
                policy.effect
                for policy in case.policy_set.policies
                if (
                    policy.subject == case.request.subject
                    and policy.resource == case.request.resource
                    and policy.action == case.request.action
                )
            }
            assert effects == {Effect.ALLOW, Effect.DENY}

    def test_single_policy_cannot_be_forced_into_conflict(self) -> None:
        cases = generate_cases(
            GeneratorConfig(
                seed=13,
                policies=1,
                vocabulary_size=2,
                conflict_rate=1.0,
            ),
            count=20,
        )

        for case in cases:
            effects = {
                policy.effect
                for policy in case.policy_set.policies
                if (
                    policy.subject == case.request.subject
                    and policy.resource == case.request.resource
                    and policy.action == case.request.action
                )
            }
            assert len(effects) <= 1


class TestConfigValidation:
    @pytest.mark.parametrize(
        "kwargs, error",
        [
            ({"seed": True}, TypeError),
            ({"seed": 1, "policies": -1}, ValueError),
            ({"seed": 1, "policies": 1.5}, ValueError),
            ({"seed": 1, "vocabulary_size": 0}, ValueError),
            ({"seed": 1, "conflict_rate": -0.1}, ValueError),
            ({"seed": 1, "conflict_rate": 1.1}, ValueError),
            ({"seed": 1, "conflict_rate": "half"}, TypeError),
        ],
    )
    def test_invalid_config_rejected(self, kwargs, error) -> None:
        with pytest.raises(error):
            GeneratorConfig(**kwargs)

    def test_negative_case_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="count"):
            generate_cases(GeneratorConfig(seed=1), -1)

    def test_config_round_trip(self) -> None:
        config = GeneratorConfig(
            seed=42,
            policies=3,
            vocabulary_size=2,
            conflict_rate=0.5,
        )

        assert config.to_dict() == {
            "seed": 42,
            "policies": 3,
            "vocabulary_size": 2,
            "conflict_rate": 0.5,
        }
