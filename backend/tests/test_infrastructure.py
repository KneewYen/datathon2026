from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "infra" / "template.yaml"
CALLER_POLICY_PATH = (
    ROOT / "infra" / "policies" / "workshop-backend-caller-policy.json"
)
POLICY_DIR = ROOT / "infra" / "policies"


class CloudFormationLoader(yaml.SafeLoader):
    pass


def _construct_intrinsic(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    return {tag_suffix: loader.construct_mapping(node)}


CloudFormationLoader.add_multi_constructor("!", _construct_intrinsic)


def load_template() -> dict:
    return yaml.load(TEMPLATE_PATH.read_text(), Loader=CloudFormationLoader)


def test_workshop_defaults_are_fixed_to_approved_region_and_model() -> None:
    template = load_template()

    assert template["Metadata"]["Workshop"] == {
        "Region": "us-east-1",
        "Role": "WSParticipantRole/Participant",
        "DurationHours": 72,
        "BedrockInferenceProfileId": "us.amazon.nova-lite-v1:0",
    }
    assert (
        template["Parameters"]["BedrockModelId"]["Default"]
        == "us.amazon.nova-lite-v1:0"
    )


def test_workshop_stack_creates_one_unnamed_least_privilege_execution_role() -> None:
    template = load_template()
    resources = template["Resources"]
    iam_resources = [
        item for item in resources.values() if item["Type"].startswith("AWS::IAM::")
    ]
    role = resources["FinancialToolsExecutionRole"]

    assert iam_resources == [role]
    assert role["Type"] == "AWS::IAM::Role"
    assert "RoleName" not in role["Properties"]
    assert role["Properties"]["Policies"][0]["PolicyDocument"]["Statement"][0][
        "Action"
    ] == ["s3:GetObject", "s3:GetObjectVersion"]
    assert resources["FinancialToolsFunction"]["Properties"]["Role"] == {
        "GetAtt": "FinancialToolsExecutionRole.Arn"
    }


def test_bedrock_policy_lists_every_us_nova_lite_destination() -> None:
    policy = json.loads(CALLER_POLICY_PATH.read_text())
    text = json.dumps(policy)

    for region in ("us-east-1", "us-east-2", "us-west-2"):
        assert (
            f"bedrock:{region}::foundation-model/amazon.nova-lite-v1:0" in text
        )
    assert "bedrock:InferenceProfileArn" in text


def test_workshop_policy_review_documents_are_valid_json_without_wildcard_actions() -> None:
    policy_paths = sorted(POLICY_DIR.glob("*.json"))

    assert {path.name for path in policy_paths} == {
        "workshop-backend-caller-policy.json",
        "workshop-lambda-execution-policy.json",
        "workshop-lambda-trust-policy.json",
    }
    for path in policy_paths:
        document = json.loads(path.read_text())
        assert document["Version"] == "2012-10-17"
        for statement in document["Statement"]:
            actions = statement["Action"]
            if isinstance(actions, str):
                actions = [actions]
            assert "*" not in actions
