"""Tavily Web Research ツール (web_search / extract_content)."""

import json
import logging
import os

from strands import tool

logger = logging.getLogger(__name__)


@tool
def web_search(query: str, search_depth: str = "basic", max_results: int = 5) -> str:
    """Web 検索。最新ニュースや時事問題、調べ物など、リアルタイムの情報が必要なときに使います。
    例: 「最新のニュース」「Pythonの最新バージョン」「東京の天気」"""
    from tavily import TavilyClient

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return json.dumps({"error": "TAVILY_API_KEY が設定されていません。"}, ensure_ascii=False)

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=True,
        )
    except Exception as e:
        logger.error("web_search failed: %s", e)
        return json.dumps({"error": f"Web 検索に失敗しました: {e}"}, ensure_ascii=False)

    results = []
    for r in response.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        })

    return json.dumps(
        {
            "answer": response.get("answer", ""),
            "results": results,
        },
        ensure_ascii=False,
    )


@tool
def extract_content(url: str) -> str:
    """指定 URL のコンテンツを抽出します。記事の要約や詳細確認に使います。
    例: ユーザーが URL を共有して「この記事を要約して」と聞いたとき"""
    from tavily import TavilyClient

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return json.dumps({"error": "TAVILY_API_KEY が設定されていません。"}, ensure_ascii=False)

    try:
        client = TavilyClient(api_key=api_key)
        response = client.extract(urls=[url])
    except Exception as e:
        logger.error("extract_content failed: %s", e)
        return json.dumps({"error": f"コンテンツの抽出に失敗しました: {e}"}, ensure_ascii=False)

    extracted = response.get("results", [])
    if not extracted:
        return json.dumps({"error": "コンテンツを抽出できませんでした。"}, ensure_ascii=False)

    item = extracted[0]
    raw_content = item.get("raw_content", "")
    # 長すぎるコンテンツは先頭 3000 文字に制限
    if len(raw_content) > 3000:
        raw_content = raw_content[:3000] + "..."

    return json.dumps(
        {
            "url": item.get("url", url),
            "raw_content": raw_content,
        },
        ensure_ascii=False,
    )
