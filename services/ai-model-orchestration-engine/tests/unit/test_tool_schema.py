import pytest
from nova_ai_model_orchestration_engine.domain import tool_schema
from nova_ai_model_orchestration_engine.domain.models import ToolSchema


def _tool(name: str = "get_weather") -> ToolSchema:
    return ToolSchema(
        name=name,
        description="Get the weather",
        parameters_json_schema={"type": "object", "properties": {"city": {"type": "string"}}},
    )


def test_validate_accepts_well_formed_schemas() -> None:
    tool_schema.validate_tool_schemas([_tool("a"), _tool("b")])


def test_validate_rejects_duplicate_names() -> None:
    with pytest.raises(tool_schema.InvalidToolSchemaError):
        tool_schema.validate_tool_schemas([_tool("a"), _tool("a")])


def test_validate_rejects_non_object_schema() -> None:
    bad = ToolSchema(name="x", description="x", parameters_json_schema={"type": "string"})
    with pytest.raises(tool_schema.InvalidToolSchemaError):
        tool_schema.validate_tool_schemas([bad])


def test_parse_arguments_accepts_dict() -> None:
    assert tool_schema.parse_tool_arguments({"city": "Paris"}) == {"city": "Paris"}


def test_parse_arguments_accepts_json_string() -> None:
    assert tool_schema.parse_tool_arguments('{"city": "Paris"}') == {"city": "Paris"}


def test_parse_arguments_rejects_malformed_json() -> None:
    with pytest.raises(tool_schema.InvalidToolSchemaError):
        tool_schema.parse_tool_arguments("{not json")


def test_parse_arguments_rejects_non_object_json() -> None:
    with pytest.raises(tool_schema.InvalidToolSchemaError):
        tool_schema.parse_tool_arguments("[1, 2, 3]")
