from dataclasses import FrozenInstanceError

import pytest

from llm.types import Message, TextBlock, ToolUseBlock


def test_text_block_is_frozen() -> None:
    block = TextBlock(text="hello")

    with pytest.raises(FrozenInstanceError):
        block.text = "world"  # type: ignore[misc]


def test_tool_use_block_is_frozen() -> None:
    block = ToolUseBlock(id="x", name="tool", arguments={})

    with pytest.raises(FrozenInstanceError):
        block.id = "y"  # type: ignore[misc]


def test_message_can_contain_mixed_content() -> None:
    msg = Message(
        role="assistant",
        content=[
            TextBlock(text="checking the file"),
            ToolUseBlock(id="1", name="read_file", arguments={"path": "main.py"}),
        ],
    )

    assert len(msg.content) == 2
    assert isinstance(msg.content[0], TextBlock)
    assert isinstance(msg.content[1], ToolUseBlock)
