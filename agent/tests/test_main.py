"""Tests for agent/main.py."""

import sys
from unittest.mock import MagicMock, patch

# Module is pre-registered in sys.modules by conftest.py
agent_main = sys.modules["agent.main"]
google_maps = sys.modules["tools.google_maps"]


def test_create_agent():
    """create_agent() が Agent インスタンスを返すこと."""
    mock_model_instance = MagicMock()
    mock_agent_instance = MagicMock()

    with (
        patch.object(agent_main, "BedrockModel", return_value=mock_model_instance) as mock_bm,
        patch.object(agent_main, "Agent", return_value=mock_agent_instance) as mock_agent_cls,
    ):
        result = agent_main.create_agent()

    mock_bm.assert_called_once()
    mock_agent_cls.assert_called_once()
    call_kwargs = mock_agent_cls.call_args[1]
    assert call_kwargs["model"] is mock_model_instance
    assert "現在の日時:" in call_kwargs["system_prompt"]
    assert agent_main.SYSTEM_PROMPT in call_kwargs["system_prompt"]
    assert result is mock_agent_instance


def test_invoke_success():
    """mock Agent が応答を返し、success ステータスが返ること."""
    mock_agent = MagicMock()
    mock_agent.return_value = "テスト応答です"

    with patch.object(agent_main, "create_agent", return_value=mock_agent):
        result = agent_main.invoke({"prompt": "こんにちは"})

    assert result["status"] == "success"
    assert result["result"] == "テスト応答です"
    mock_agent.assert_called_once_with("こんにちは")


def test_invoke_empty_prompt():
    """prompt が空のとき error ステータスが返ること."""
    result = agent_main.invoke({"prompt": ""})
    assert result["status"] == "error"
    assert "空" in result["result"]

    result_no_key = agent_main.invoke({})
    assert result_no_key["status"] == "error"


def test_request_location_tool():
    """request_location ツールが正しい JSON を返し _maps_agent_result に設定されること."""
    import json

    # Reset global
    google_maps.clear_maps_result()

    result = google_maps.request_location(message="近くのカフェをお探しするので、位置情報を送ってもらえますか？")
    parsed = json.loads(result)

    assert parsed["type"] == "location_request"
    assert parsed["message"] == "近くのカフェをお探しするので、位置情報を送ってもらえますか？"
    assert google_maps.get_maps_result() == result

    # cleanup
    google_maps.clear_maps_result()


def test_invoke_agent_exception():
    """Agent が例外を投げた場合のエラーハンドリング."""
    mock_agent = MagicMock()
    mock_agent.side_effect = RuntimeError("model error")

    with patch.object(agent_main, "create_agent", return_value=mock_agent):
        try:
            agent_main.invoke({"prompt": "テスト"})
            assert False, "Expected exception to propagate"
        except RuntimeError as e:
            assert "model error" in str(e)
