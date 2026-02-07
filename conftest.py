"""Root conftest — register agent/ and lambda/ as importable modules."""

import importlib
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent

# ============================================================================
# agent/main.py
# ============================================================================
# Mock heavy dependencies BEFORE importing agent.main so module-level code
# that instantiates BedrockAgentCoreApp / loads .env doesn't fail.

# BedrockAgentCoreApp().entrypoint must act as a pass-through decorator
# so that `@app.entrypoint def invoke(...)` keeps the original function.
_mock_bedrock_agentcore = MagicMock()
_mock_app_instance = _mock_bedrock_agentcore.BedrockAgentCoreApp.return_value
_mock_app_instance.entrypoint = lambda fn: fn  # pass-through decorator

sys.modules.setdefault("bedrock_agentcore", _mock_bedrock_agentcore)
sys.modules.setdefault("dotenv", MagicMock())
sys.modules.setdefault("strands", MagicMock())
sys.modules.setdefault("strands.models", MagicMock())

# Make agent importable as a package
if "agent" not in sys.modules:
    sys.path.insert(0, str(ROOT))
    agent_pkg_spec = importlib.machinery.ModuleSpec("agent", None, is_package=True)
    agent_pkg = importlib.util.module_from_spec(agent_pkg_spec)
    agent_pkg.__path__ = [str(ROOT / "agent")]
    sys.modules["agent"] = agent_pkg

if "agent.main" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "agent.main", str(ROOT / "agent" / "main.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agent.main"] = mod
    spec.loader.exec_module(mod)

# ============================================================================
# lambda/index.py
# ============================================================================
# "lambda" is a Python keyword — we must register modules manually.

# -- linebot.v3.exceptions: InvalidSignatureError must be a real Exception ---


class _InvalidSignatureError(Exception):
    pass


_linebot = types.ModuleType("linebot")
_linebot_v3 = types.ModuleType("linebot.v3")
_linebot_v3_exceptions = types.ModuleType("linebot.v3.exceptions")
_linebot_v3_exceptions.InvalidSignatureError = _InvalidSignatureError

# -- linebot.v3.webhooks: MessageEvent / TextMessageContent need isinstance --


class _MessageEvent:
    pass


class _TextMessageContent:
    pass


_linebot_v3_webhooks = types.ModuleType("linebot.v3.webhooks")
_linebot_v3_webhooks.MessageEvent = _MessageEvent
_linebot_v3_webhooks.TextMessageContent = _TextMessageContent

# -- linebot.v3.messaging: ShowLoadingAnimationRequest etc. -----------------


class _ShowLoadingAnimationRequest:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            # LINE SDK uses camelCase params but exposes snake_case attrs
            setattr(self, k, v)
            # Also set snake_case version
            import re

            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", k).lower()
            setattr(self, snake, v)


_linebot_v3_messaging = MagicMock()
_linebot_v3_messaging.ShowLoadingAnimationRequest = _ShowLoadingAnimationRequest
# WebhookParser needs to be a MagicMock so parser = WebhookParser(...) works
_linebot_v3.WebhookParser = MagicMock()

sys.modules.setdefault("linebot", _linebot)
sys.modules.setdefault("linebot.v3", _linebot_v3)
sys.modules.setdefault("linebot.v3.exceptions", _linebot_v3_exceptions)
sys.modules.setdefault("linebot.v3.messaging", _linebot_v3_messaging)
sys.modules.setdefault("linebot.v3.webhooks", _linebot_v3_webhooks)

# Register lambda package
if "lambda" not in sys.modules:
    lambda_pkg_spec = importlib.machinery.ModuleSpec("lambda", None, is_package=True)
    lambda_pkg = importlib.util.module_from_spec(lambda_pkg_spec)
    lambda_pkg.__path__ = [str(ROOT / "lambda")]
    sys.modules["lambda"] = lambda_pkg

if "lambda.index" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "lambda.index", str(ROOT / "lambda" / "index.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lambda.index"] = mod
    spec.loader.exec_module(mod)
