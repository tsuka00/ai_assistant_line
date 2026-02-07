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

# Google API mocks
sys.modules.setdefault("google.oauth2.credentials", MagicMock())
sys.modules.setdefault("google.auth.transport.requests", MagicMock())
sys.modules.setdefault("googleapiclient", MagicMock())
sys.modules.setdefault("googleapiclient.discovery", MagicMock())

# Make agent importable as a package
if "agent" not in sys.modules:
    sys.path.insert(0, str(ROOT))
    agent_pkg_spec = importlib.machinery.ModuleSpec("agent", None, is_package=True)
    agent_pkg = importlib.util.module_from_spec(agent_pkg_spec)
    agent_pkg.__path__ = [str(ROOT / "agent")]
    sys.modules["agent"] = agent_pkg

# Make agent.tools importable
if "agent.tools" not in sys.modules:
    tools_pkg_spec = importlib.machinery.ModuleSpec("agent.tools", None, is_package=True)
    tools_pkg = importlib.util.module_from_spec(tools_pkg_spec)
    tools_pkg.__path__ = [str(ROOT / "agent" / "tools")]
    sys.modules["agent.tools"] = tools_pkg

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

# -- linebot.v3.webhooks: MessageEvent / TextMessageContent / PostbackEvent --


class _MessageEvent:
    pass


class _TextMessageContent:
    pass


class _PostbackEvent:
    pass


_linebot_v3_webhooks = types.ModuleType("linebot.v3.webhooks")
_linebot_v3_webhooks.MessageEvent = _MessageEvent
_linebot_v3_webhooks.TextMessageContent = _TextMessageContent
_linebot_v3_webhooks.PostbackEvent = _PostbackEvent

# -- linebot.v3.messaging: ShowLoadingAnimationRequest etc. -----------------


class _ShowLoadingAnimationRequest:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
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

# Register lambda sub-packages before importing index
# flex_messages package
if "lambda.flex_messages" not in sys.modules:
    fm_pkg_spec = importlib.machinery.ModuleSpec("lambda.flex_messages", None, is_package=True)
    fm_pkg = importlib.util.module_from_spec(fm_pkg_spec)
    fm_pkg.__path__ = [str(ROOT / "lambda" / "flex_messages")]
    sys.modules["lambda.flex_messages"] = fm_pkg

# Register lambda modules that index.py imports
_lambda_modules = {
    "google_auth": ROOT / "lambda" / "google_auth.py",
    "google_calendar_api": ROOT / "lambda" / "google_calendar_api.py",
    "flex_messages": None,  # package, already registered above
    "flex_messages.calendar_carousel": ROOT / "lambda" / "flex_messages" / "calendar_carousel.py",
    "flex_messages.date_picker": ROOT / "lambda" / "flex_messages" / "date_picker.py",
    "flex_messages.time_picker": ROOT / "lambda" / "flex_messages" / "time_picker.py",
    "flex_messages.event_confirm": ROOT / "lambda" / "flex_messages" / "event_confirm.py",
    "flex_messages.oauth_link": ROOT / "lambda" / "flex_messages" / "oauth_link.py",
}

for mod_name, file_path in _lambda_modules.items():
    if file_path is None:
        continue
    full_name = f"lambda.{mod_name}" if not mod_name.startswith("lambda.") else mod_name
    # Also register without "lambda." prefix since Lambda code uses bare imports
    bare_name = mod_name
    if bare_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(bare_name, str(file_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[bare_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            # Some modules may fail to import due to missing deps, that's OK
            pass

# Also register flex_messages package bare
if "flex_messages" not in sys.modules:
    fm_bare_spec = importlib.machinery.ModuleSpec("flex_messages", None, is_package=True)
    fm_bare = importlib.util.module_from_spec(fm_bare_spec)
    fm_bare.__path__ = [str(ROOT / "lambda" / "flex_messages")]
    sys.modules["flex_messages"] = fm_bare

if "lambda.index" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "lambda.index", str(ROOT / "lambda" / "index.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lambda.index"] = mod
    spec.loader.exec_module(mod)
