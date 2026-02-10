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


# ---------------------------------------------------------------------------
# Memory 統合テスト
# ---------------------------------------------------------------------------


def test_create_agent_without_memory():
    """session_manager=None の場合、Agent に session_manager が渡されないこと."""
    mock_model_instance = MagicMock()
    mock_agent_instance = MagicMock()

    with (
        patch.object(agent_main, "BedrockModel", return_value=mock_model_instance),
        patch.object(agent_main, "Agent", return_value=mock_agent_instance) as mock_agent_cls,
    ):
        result = agent_main.create_agent(session_manager=None)

    call_kwargs = mock_agent_cls.call_args[1]
    assert "session_manager" not in call_kwargs
    assert result is mock_agent_instance


def test_create_agent_with_memory():
    """session_manager が非 None の場合、Agent に渡されること."""
    mock_model_instance = MagicMock()
    mock_agent_instance = MagicMock()
    mock_session_manager = MagicMock()

    with (
        patch.object(agent_main, "BedrockModel", return_value=mock_model_instance),
        patch.object(agent_main, "Agent", return_value=mock_agent_instance) as mock_agent_cls,
    ):
        result = agent_main.create_agent(session_manager=mock_session_manager)

    call_kwargs = mock_agent_cls.call_args[1]
    assert call_kwargs["session_manager"] is mock_session_manager
    assert result is mock_agent_instance


def test_invoke_with_line_user_id():
    """line_user_id があれば _build_session_manager が呼ばれること."""
    mock_agent = MagicMock()
    mock_agent.return_value = "応答"
    mock_sm = MagicMock()

    with (
        patch.object(agent_main, "_build_session_manager", return_value=mock_sm) as mock_build,
        patch.object(agent_main, "create_agent", return_value=mock_agent) as mock_create,
    ):
        result = agent_main.invoke({"prompt": "こんにちは", "line_user_id": "U1234"})

    mock_build.assert_called_once_with("U1234")
    mock_create.assert_called_once_with(session_manager=mock_sm)
    assert result["status"] == "success"


def test_invoke_without_line_user_id():
    """line_user_id がなければ session_manager=None で呼ばれること."""
    mock_agent = MagicMock()
    mock_agent.return_value = "応答"

    with (
        patch.object(agent_main, "create_agent", return_value=mock_agent) as mock_create,
    ):
        result = agent_main.invoke({"prompt": "こんにちは"})

    mock_create.assert_called_once_with(session_manager=None)
    assert result["status"] == "success"


def test_invoke_memory_failure_graceful():
    """_build_session_manager が例外を投げても Agent は動作すること."""
    mock_agent = MagicMock()
    mock_agent.return_value = "応答"

    with (
        patch.object(agent_main, "_build_session_manager", side_effect=RuntimeError("memory error")),
        patch.object(agent_main, "create_agent", return_value=mock_agent) as mock_create,
    ):
        result = agent_main.invoke({"prompt": "こんにちは", "line_user_id": "U1234"})

    # memory 失敗時は session_manager=None でフォールバック
    mock_create.assert_called_once_with(session_manager=None)
    assert result["status"] == "success"


def test_build_session_manager_no_memory_id():
    """BEDROCK_MEMORY_ID が空なら None を返すこと."""
    original_memory_id = agent_main.BEDROCK_MEMORY_ID
    original_available = agent_main._memory_available

    try:
        agent_main.BEDROCK_MEMORY_ID = ""
        agent_main._memory_available = False
        result = agent_main._build_session_manager("U1234")
        assert result is None
    finally:
        agent_main.BEDROCK_MEMORY_ID = original_memory_id
        agent_main._memory_available = original_available


def test_build_session_manager_with_memory_id():
    """BEDROCK_MEMORY_ID が設定されていれば session_manager を生成すること."""
    original_memory_id = agent_main.BEDROCK_MEMORY_ID
    original_available = agent_main._memory_available

    mock_config_cls = MagicMock()
    mock_sm_cls = MagicMock()
    mock_sm_instance = MagicMock()
    mock_sm_cls.return_value = mock_sm_instance

    try:
        agent_main.BEDROCK_MEMORY_ID = "mem-12345"
        agent_main._memory_available = True

        with (
            patch.object(agent_main, "AgentCoreMemoryConfig", mock_config_cls),
            patch.object(agent_main, "AgentCoreMemorySessionManager", mock_sm_cls),
        ):
            result = agent_main._build_session_manager("U9999")

        # config が正しく呼ばれていること
        config_kwargs = mock_config_cls.call_args[1]
        assert config_kwargs["memory_id"] == "mem-12345"
        assert config_kwargs["actor_id"] == "U9999"
        assert "U9999-" in config_kwargs["session_id"]

        # session manager が返されること
        assert result is mock_sm_instance
    finally:
        agent_main.BEDROCK_MEMORY_ID = original_memory_id
        agent_main._memory_available = original_available
