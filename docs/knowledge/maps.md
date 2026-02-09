# Maps 機能 ナレッジ

## 概要

場所検索・おすすめ場所の提案機能。Vercel にデプロイ済みの Next.js API を Router Agent の @tool 経由で呼び出し、LINE 上で Flex Message カルーセル（静的地図画像付き）として表示する。

---

## 外部 API（Vercel: myplace-blush.vercel.app）

### 場所検索 — `GET /api/search`

| 項目 | 値 |
|------|-----|
| URL | `GET https://myplace-blush.vercel.app/api/search?q={query}` |
| 認証 | 不要 |
| 入力 | クエリパラメータ `q`（例: `渋谷カフェ`） |
| 最大件数 | 5件 |
| 内部実装 | Google Places API (New) Text Search を `fetch()` で直接呼び出し |

```json
// レスポンス
[
  {
    "place_id": "ChIJYcfmTGOLGGAR...",
    "display_name": "〒150-0031 東京都渋谷区桜丘町23-18 ...",
    "lat": "35.6558766",
    "lon": "139.6997681"
  }
]
```

※ `lat` / `lon` は文字列

### AI おすすめ — `POST /api/ai/recommend`

| 項目 | 値 |
|------|-----|
| URL | `POST https://myplace-blush.vercel.app/api/ai/recommend` |
| 認証 | 不要 |
| Content-Type | `application/json` |
| 入力 | `{ "prompt": "自然言語", "currentLocation?": { "lat": 35.68, "lng": 139.76 } }` |
| 最大件数 | 3〜5件（AI 判断） |
| 内部実装 | Claude (Bedrock) でおすすめ生成 → Google Places API でジオコーディング |

```json
// レスポンス
{
  "places": [
    {
      "name": "ストリーマー コーヒーカンパニー 渋谷",
      "description": "ラテアートで有名な人気コーヒーショップ",
      "category": "cafe",
      "latitude": 35.6611,
      "longitude": 139.6978,
      "address": "東京都渋谷区宇田川町",
      "url": "https://...",
      "thumbnail": "https://...",
      "minPrice": 600,
      "rating": 4.2
    }
  ],
  "logId": 22
}
```

※ `latitude` / `longitude` は数値

---

## Router Agent ツール（agent/main.py）

### ツール一覧

| ツール | 用途 | 呼び出し条件 | タイムアウト |
|--------|------|-------------|------------|
| `search_place(query)` | 場所・店舗検索 | エリア+ジャンルが明示されている | 15秒 |
| `recommend_place(prompt)` | AI おすすめ場所 | 条件・好み・雰囲気ベースの提案 | 30秒 |
| `request_location(message)` | 位置情報リクエスト | 「近くの」「この辺の」等、エリア未指定 | なし（JSON生成のみ） |

### ルーティング判定（LLM ベース）

- 「渋谷のカフェ」 → `search_place`（エリア明示）
- 「デートにおすすめの表参道のレストラン」 → `recommend_place`（条件+エリア明示）
- 「近くのカフェ」「この辺でおすすめ」 → `request_location`（エリア未指定）
- プロンプトに `[ユーザーの現在地: 緯度XX, 経度XX]` が含まれる → 座標を使って `search_place` / `recommend_place` を直接呼ぶ

### レスポンス JSON 形式

| type | 構造 |
|------|------|
| `place_search` | `{type, message, places: [{place_id, name, lat, lon}]}` |
| `place_recommend` | `{type, message, places: [{name, description, category, latitude, longitude, address, url, minPrice, rating}]}` |
| `location_request` | `{type, message}` |

※ ツールの生 JSON を `_maps_agent_result` に保持し、LLM の後処理をバイパスして Lambda にそのまま返す

---

## Pseudo-GPS フロー（位置情報取得）

```
ユーザー: 「近くのカフェ教えて」
  ↓
Router Agent → request_location(message="近くのカフェをお探しするので、位置情報を送ってもらえますか？")
  ↓
Lambda: DynamoDB に {action: "waiting_location", original_query: "近くのカフェ教えて"} 保存
  ↓
LINE: TextMessage + QuickReply [📍 位置情報を送る]（LocationAction）
  ↓
ユーザー: QuickReply タップ → LINE 地図ピッカー → 位置情報送信（2タップ）
  ↓
Lambda handle_location_message:
  - DynamoDB から元クエリ復元 + ステートクリア
  - プロンプト: "[ユーザーの現在地: 緯度35.XX, 経度139.XX] 近くのカフェ教えて"
  - Router Agent 再呼び出し
  ↓
Router Agent → recommend_place / search_place（座標付き）
  ↓
LINE: Flex Message カルーセル表示
```

- 割り込み処理: 位置情報待ち中にテキストが来た場合 → ステートクリアして通常テキスト処理へ
- 自発的位置情報: ステートなしで位置情報が来た場合 → 「この場所の周辺でおすすめを教えて」で Agent 呼び出し
- ステート保存先: DynamoDB `UserSessionState`（TTL 10分）

---

## LINE 表示（Flex Message カルーセル）

### 構成（place_carousel.py）

- 最大12バブル
- search バブル: 静的地図画像（hero） + 店名 + 「地図を開く」ボタン
- recommend バブル: 静的地図画像（hero） + 店名 + 説明文 + 評価/価格 + 「地図を開く」ボタン
- カラー: 緑 `#06C755`（LINE ブランドカラー）

### 静的地図画像

- Google Static Maps API（`GOOGLE_STATIC_MAPS_KEY` が必要、なければ画像なし）
- URL: `https://maps.googleapis.com/maps/api/staticmap?center={lat},{lon}&zoom=15&size=600x300&markers=color:red|{lat},{lon}&key={key}`

### 「地図を開く」ボタン

- URL: `https://www.google.com/maps/search/?api=1&query={lat},{lon}`

---

## Vercel 側の技術スタック

| パッケージ | 用途 |
|-----------|------|
| next | API Route フレームワーク |
| @aws-sdk/client-bedrock-runtime | AI推薦 (Claude via Bedrock) |
| drizzle-orm / @libsql/client | DB (Turso) |
| langfuse | LLM監視 |
| leaflet / react-leaflet | 地図描画（フロント側のみ） |

Google Maps 専用ライブラリは不使用。素の `fetch()` + REST API で Google Places API を呼び出し。
認証は API キー（`X-Goog-Api-Key` ヘッダー）のみ。OAuth2 は不使用。
