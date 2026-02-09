"""Google Maps 関連ツール (search_place / recommend_place / request_location)."""

import json
import logging
import os
import urllib.parse
import urllib.request

from strands import tool

logger = logging.getLogger(__name__)

MAPS_API_BASE_URL = os.environ.get("MAPS_API_BASE_URL", "https://myplace-blush.vercel.app")

# maps ツールの生レスポンスを保持（LLM の加工をバイパスするため）
_maps_agent_result: str | None = None


def get_maps_result() -> str | None:
    """保持中の maps ツール生レスポンスを取得."""
    return _maps_agent_result


def clear_maps_result() -> None:
    """maps ツール生レスポンスをクリア."""
    global _maps_agent_result
    _maps_agent_result = None


@tool
def search_place(query: str) -> str:
    """場所・店舗・住所を検索します。特定の場所を探したいときに使います。
    例: 「渋谷カフェ」「東京タワー」「新宿駅近くのラーメン屋」"""
    global _maps_agent_result

    url = f"{MAPS_API_BASE_URL.rstrip('/')}/api/search?q={urllib.parse.quote(query)}"

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            places = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("search_place failed: %s", e)
        raw_result = json.dumps(
            {"type": "text", "message": "場所の検索に失敗しました。もう一度お試しください。"},
            ensure_ascii=False,
        )
        _maps_agent_result = raw_result
        return raw_result

    if not places:
        raw_result = json.dumps(
            {"type": "text", "message": f"「{query}」に該当する場所が見つかりませんでした。"},
            ensure_ascii=False,
        )
        _maps_agent_result = raw_result
        return raw_result

    results = []
    for p in places:
        results.append({
            "place_id": p.get("place_id", ""),
            "name": p.get("display_name", ""),
            "lat": p.get("lat", ""),
            "lon": p.get("lon", ""),
        })

    raw_result = json.dumps(
        {"type": "place_search", "message": f"「{query}」で見つかったお店です！", "places": results},
        ensure_ascii=False,
    )
    _maps_agent_result = raw_result
    return raw_result


@tool
def recommend_place(prompt: str) -> str:
    """AI がおすすめの場所を提案します。目的や雰囲気に合った場所を探したいときに使います。
    例: 「デートにおすすめの渋谷のカフェ」「大阪で安くて美味しいお好み焼き屋」"""
    global _maps_agent_result

    url = f"{MAPS_API_BASE_URL.rstrip('/')}/api/ai/recommend"
    payload = json.dumps({"prompt": prompt}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("recommend_place failed: %s", e)
        raw_result = json.dumps(
            {"type": "text", "message": "おすすめ場所の取得に失敗しました。もう一度お試しください。"},
            ensure_ascii=False,
        )
        _maps_agent_result = raw_result
        return raw_result

    places = data.get("places", [])
    if not places:
        raw_result = json.dumps(
            {"type": "text", "message": "条件に合うおすすめの場所が見つかりませんでした。"},
            ensure_ascii=False,
        )
        _maps_agent_result = raw_result
        return raw_result

    results = []
    for p in places:
        results.append({
            "name": p.get("name", ""),
            "description": p.get("description", ""),
            "category": p.get("category", ""),
            "latitude": p.get("latitude"),
            "longitude": p.get("longitude"),
            "address": p.get("address", ""),
            "url": p.get("url", ""),
            "minPrice": p.get("minPrice"),
            "rating": p.get("rating"),
        })

    raw_result = json.dumps(
        {"type": "place_recommend", "message": "こちらのお店はいかがでしょうか？", "places": results},
        ensure_ascii=False,
    )
    _maps_agent_result = raw_result
    return raw_result


@tool
def request_location(message: str) -> str:
    """ユーザーの現在地が必要なときに呼びます。
    エリア名が明示されておらず「近くの」「この辺の」など現在地に依存する質問のときに使います。
    message にはユーザーに位置情報の送信をお願いする親しみやすいメッセージを書いてください。
    例: 「近くのカフェをお探しするので、位置情報を送ってもらえますか？」"""
    global _maps_agent_result
    raw_result = json.dumps(
        {"type": "location_request", "message": message},
        ensure_ascii=False,
    )
    _maps_agent_result = raw_result
    return raw_result
