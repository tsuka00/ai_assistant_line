"""Tests for agent/tools/tavily_search.py."""

import json
import sys
from unittest.mock import MagicMock, patch

tavily_search = sys.modules["tools.tavily_search"]


class TestWebSearch:
    """web_search ツールのテスト."""

    def test_success(self):
        """正常系: 検索結果が JSON で返ること."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "Python 3.13 が最新です。",
            "results": [
                {
                    "title": "Python 3.13 リリース",
                    "url": "https://example.com/python313",
                    "content": "Python 3.13 がリリースされました。",
                },
                {
                    "title": "Python 公式サイト",
                    "url": "https://python.org",
                    "content": "Welcome to Python.org",
                },
            ],
        }

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.web_search("Python 最新バージョン")

        data = json.loads(result)
        assert data["answer"] == "Python 3.13 が最新です。"
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "Python 3.13 リリース"
        assert data["results"][0]["url"] == "https://example.com/python313"
        mock_client.search.assert_called_once_with(
            query="Python 最新バージョン",
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )

    def test_no_api_key(self):
        """API キー未設定でエラーが返ること."""
        with patch.dict("os.environ", {}, clear=True):
            # TAVILY_API_KEY を確実に削除
            import os
            os.environ.pop("TAVILY_API_KEY", None)
            result = tavily_search.web_search("テスト")

        data = json.loads(result)
        assert "error" in data
        assert "TAVILY_API_KEY" in data["error"]

    def test_api_error(self):
        """API 呼び出しエラー時にエラー JSON が返ること."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API rate limit exceeded")

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.web_search("テスト")

        data = json.loads(result)
        assert "error" in data
        assert "API rate limit exceeded" in data["error"]

    def test_custom_params(self):
        """search_depth と max_results が渡されること."""
        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "", "results": []}

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                tavily_search.web_search("テスト", search_depth="advanced", max_results=3)

        mock_client.search.assert_called_once_with(
            query="テスト",
            search_depth="advanced",
            max_results=3,
            include_answer=True,
        )

    def test_empty_results(self):
        """検索結果が空の場合."""
        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "", "results": []}

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.web_search("非常にマイナーな検索")

        data = json.loads(result)
        assert data["answer"] == ""
        assert data["results"] == []


class TestExtractContent:
    """extract_content ツールのテスト."""

    def test_success(self):
        """正常系: コンテンツが JSON で返ること."""
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "results": [
                {
                    "url": "https://example.com/article",
                    "raw_content": "これは記事の内容です。" * 10,
                }
            ]
        }

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.extract_content("https://example.com/article")

        data = json.loads(result)
        assert data["url"] == "https://example.com/article"
        assert "これは記事の内容です。" in data["raw_content"]
        mock_client.extract.assert_called_once_with(urls=["https://example.com/article"])

    def test_no_api_key(self):
        """API キー未設定でエラーが返ること."""
        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("TAVILY_API_KEY", None)
            result = tavily_search.extract_content("https://example.com")

        data = json.loads(result)
        assert "error" in data
        assert "TAVILY_API_KEY" in data["error"]

    def test_api_error(self):
        """API 呼び出しエラー時にエラー JSON が返ること."""
        mock_client = MagicMock()
        mock_client.extract.side_effect = Exception("Connection timeout")

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.extract_content("https://example.com")

        data = json.loads(result)
        assert "error" in data
        assert "Connection timeout" in data["error"]

    def test_empty_results(self):
        """抽出結果が空の場合."""
        mock_client = MagicMock()
        mock_client.extract.return_value = {"results": []}

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.extract_content("https://example.com/empty")

        data = json.loads(result)
        assert "error" in data
        assert "抽出できません" in data["error"]

    def test_long_content_truncated(self):
        """3000 文字を超えるコンテンツが切り詰められること."""
        long_content = "あ" * 5000
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "results": [
                {
                    "url": "https://example.com/long",
                    "raw_content": long_content,
                }
            ]
        }

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            with patch("tavily.TavilyClient", return_value=mock_client):
                result = tavily_search.extract_content("https://example.com/long")

        data = json.loads(result)
        # 3000 文字 + "..." = 3003 文字
        assert len(data["raw_content"]) == 3003
        assert data["raw_content"].endswith("...")
