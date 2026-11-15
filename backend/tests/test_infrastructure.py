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


def test_workshop_stack_creates_only_unnamed_scoped_execution_roles() -> None:
    template = load_template()
    resources = template["Resources"]
    iam_resources = [
        item for item in resources.values() if item["Type"].startswith("AWS::IAM::")
    ]
    role = resources["FinancialToolsExecutionRole"]

    assert len(iam_resources) == 5
    assert all(item["Type"] == "AWS::IAM::Role" for item in iam_resources)
    assert all("RoleName" not in item["Properties"] for item in iam_resources)
    assert role["Type"] == "AWS::IAM::Role"
    assert "RoleName" not in role["Properties"]
    assert role["Properties"]["Policies"][0]["PolicyDocument"]["Statement"][0][
        "Action"
    ] == ["s3:GetObject", "s3:GetObjectVersion"]
    assert resources["FinancialToolsFunction"]["Properties"]["Role"] == {
        "GetAtt": "FinancialToolsExecutionRole.Arn"
    }
    assert resources["InvestmentAnalysisStateMachine"]["Properties"]["Type"] == "STANDARD"
    assert resources["WorkflowAgentFunction"]["Properties"]["Role"] == {
        "GetAtt": "WorkflowAgentExecutionRole.Arn"
    }
    state_actions = resources["InvestmentWorkflowExecutionRole"]["Properties"][
        "Policies"
    ][0]["PolicyDocument"]["Statement"][0]["Action"]
    assert state_actions == "lambda:InvokeFunction"


def test_financial_lambda_preserves_deployed_market_contract() -> None:
    template = load_template()
    resources = template["Resources"]
    function = resources["FinancialToolsFunction"]["Properties"]
    role = resources["FinancialToolsExecutionRole"]["Properties"]
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    variables = {
        **template["Globals"]["Function"]["Environment"]["Variables"],
        **function["Environment"]["Variables"],
    }

    assert function["Timeout"] == 120
    assert function["ReservedConcurrentExecutions"] == 5
    assert set(variables) == {
        "DATA_BUCKET",
        "DATA_PREFIX",
        "DATASET_ID",
        "MARKET_PREFIX",
        "MARKET_DATASET_ID",
        "BEDROCK_MODEL_ID",
    }
    assert {item["Sid"] for item in statements} == {
        "ReadPortfolioGuardDataset",
        "WritePortfolioGuardLambdaLogs",
        "ReadSimulatedMarketData",
        "WriteScoredHeadlinesOnly",
        "InvokeNovaLiteInferenceProfile",
        "InvokeNovaLiteDestinationModels",
    }
    write = next(item for item in statements if item["Sid"] == "WriteScoredHeadlinesOnly")
    assert write["Action"] == "s3:PutObject"
    assert len(write["Resource"]) == 2


def test_bedrock_destination_permissions_require_the_approved_profile() -> None:
    resources = load_template()["Resources"]
    for role_name in (
        "FinancialToolsExecutionRole",
        "WorkflowAgentExecutionRole",
        "BackendApiExecutionRole",
    ):
        statements = resources[role_name]["Properties"]["Policies"][0][
            "PolicyDocument"
        ]["Statement"]
        destination = next(
            item for item in statements if "Destination" in item.get("Sid", "")
        )
        assert destination["Action"] == "bedrock:InvokeModel"
        assert destination["Condition"]["StringEquals"] == {
            "bedrock:InferenceProfileArn": {
                "Sub": "arn:${AWS::Partition}:bedrock:${AWS::Region}:${AWS::AccountId}:inference-profile/${BedrockModelId}"
            }
        }


def test_http_api_requires_cognito_jwt_and_has_demo_throttling() -> None:
    resources = load_template()["Resources"]
    api = resources["BackendHttpApi"]["Properties"]
    client = resources["DemoUserPoolClient"]["Properties"]
    events = resources["BackendApiFunction"]["Properties"]["Events"]

    assert api["Auth"]["DefaultAuthorizer"] == "CognitoJwtAuthorizer"
    assert api["DefaultRouteSettings"] == {
        "DetailedMetricsEnabled": False,
        "ThrottlingBurstLimit": 2,
        "ThrottlingRateLimit": 1,
    }
    assert api["CorsConfiguration"]["AllowOrigins"] == [{"Ref": "FrontendOrigin"}]
    assert api["CorsConfiguration"]["AllowHeaders"] == [
        "authorization",
        "content-type",
    ]
    assert events["ApiProxy"]["Properties"]["Method"] == "ANY"
    assert events["ApiCorsPreflight"]["Properties"] == {
        "ApiId": {"Ref": "BackendHttpApi"},
        "Path": "/{proxy+}",
        "Method": "OPTIONS",
        "Auth": {"Authorizer": "NONE"},
    }
    assert client["GenerateSecret"] is False
    assert client["AllowedOAuthFlows"] == ["code"]
    assert client["AllowedOAuthScopes"] == ["openid", "email"]
    assert resources["DemoUserPool"]["Properties"]["AdminCreateUserConfig"] == {
        "AllowAdminCreateUserOnly": True
    }


def test_backend_lambda_builds_exclude_the_test_tree() -> None:
    resources = load_template()["Resources"]

    for logical_id in (
        "BackendApiFunction",
        "WorkflowAgentFunction",
        "WorkflowCoordinatorFunction",
    ):
        assert resources[logical_id]["Metadata"]["BuildMethod"] == "makefile"

    makefile = (ROOT / "backend" / "Makefile").read_text()
    assert "cp -R app" in makefile
    assert "tests" not in makefile
    assert "--platform manylinux2014_aarch64" in makefile
    assert "--only-binary=:all:" in makefile
    assert "-name __pycache__" in makefile
    assert "-name '*.pyc'" in makefile


def test_standard_workflow_has_a_bounded_execution_timeout() -> None:
    definition = json.loads(
        (ROOT / "infra" / "workflows" / "investment_analysis.asl.json").read_text()
    )
    assert definition["TimeoutSeconds"] == 180


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
