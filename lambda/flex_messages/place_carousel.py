"""場所カルーセル Flex Message ビルダー."""

import os
from urllib.parse import quote


def build_place_carousel(places: list[dict], message: str = "", place_type: str = "search") -> dict:
    """場所のカルーセル Flex Message を生成.

    place_type: "search" (search_place) or "recommend" (recommend_place)
    """
    if not places:
        return {
            "type": "text",
            "text": message or "場所が見つかりませんでした。",
        }

    bubbles = []
    for place in places[:12]:  # カルーセルは最大12バブル
        if place_type == "recommend":
            bubbles.append(_build_recommend_bubble(place))
        else:
            bubbles.append(_build_search_bubble(place))

    return {
        "type": "flex",
        "altText": message or "場所の検索結果",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }


def _get_static_map_url(lat: float | str, lon: float | str) -> str:
    """Google Static Maps API の URL を生成."""
    api_key = os.environ.get("GOOGLE_STATIC_MAPS_KEY", "")
    markers = quote(f"color:red|{lat},{lon}")
    return (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lon}&zoom=15&size=600x300"
        f"&markers={markers}"
        f"&key={api_key}"
    )


def _get_google_maps_url(lat: float | str, lon: float | str) -> str:
    """Google Maps を開く URL を生成."""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def _build_search_bubble(place: dict) -> dict:
    """search_place 用バブルを生成."""
    name = place.get("name", "(不明)")
    lat = place.get("lat", "")
    lon = place.get("lon", "")

    hero = _build_hero_image(lat, lon)

    body_contents = [
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "md",
            "wrap": True,
        },
    ]

    bubble = {
        "type": "bubble",
        "size": "kilo",
    }

    if hero:
        bubble["hero"] = hero

    bubble["body"] = {
        "type": "box",
        "layout": "vertical",
        "contents": body_contents,
        "spacing": "sm",
        "paddingAll": "15px",
    }

    if lat and lon:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "地図を開く",
                        "uri": _get_google_maps_url(lat, lon),
                    },
                    "style": "primary",
                    "color": "#06C755",
                    "height": "sm",
                },
            ],
        }

    return bubble


def _build_recommend_bubble(place: dict) -> dict:
    """recommend_place 用バブルを生成."""
    name = place.get("name", "(不明)")
    description = place.get("description", "")
    lat = place.get("latitude", "")
    lon = place.get("longitude", "")
    rating = place.get("rating")
    min_price = place.get("minPrice")

    hero = _build_hero_image(lat, lon)

    body_contents = [
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "md",
            "wrap": True,
        },
    ]

    if description:
        body_contents.append({
            "type": "text",
            "text": description,
            "size": "sm",
            "color": "#666666",
            "wrap": True,
        })

    # 評価 & 価格行
    info_parts = []
    if rating is not None:
        info_parts.append(f"★ {rating}")
    if min_price is not None:
        info_parts.append(f"¥{min_price}〜")
    if info_parts:
        body_contents.append({
            "type": "text",
            "text": "  ".join(info_parts),
            "size": "sm",
            "color": "#999999",
        })

    bubble = {
        "type": "bubble",
        "size": "kilo",
    }

    if hero:
        bubble["hero"] = hero

    bubble["body"] = {
        "type": "box",
        "layout": "vertical",
        "contents": body_contents,
        "spacing": "sm",
        "paddingAll": "15px",
    }

    if lat and lon:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "地図を開く",
                        "uri": _get_google_maps_url(lat, lon),
                    },
                    "style": "primary",
                    "color": "#06C755",
                    "height": "sm",
                },
            ],
        }

    return bubble


def _build_hero_image(lat, lon) -> dict | None:
    """静的地図画像の hero セクションを生成. API キーがなければ None."""
    if not lat or not lon or not os.environ.get("GOOGLE_STATIC_MAPS_KEY", ""):
        return None
    return {
        "type": "image",
        "url": _get_static_map_url(lat, lon),
        "size": "full",
        "aspectRatio": "2:1",
        "aspectMode": "cover",
    }
