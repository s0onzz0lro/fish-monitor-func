# Azure Functions の HTTP 用ライブラリを読み込み（HTTP入出力に必須）
import azure.functions as func

# 標準ライブラリ（OS環境変数/JSON/ログ/時刻）
import os, json, logging
from datetime import datetime, timezone

# Azure Table Storage クライアント（requirements.txtで導入）
from azure.data.tables import TableServiceClient, TableEntity

# Function App（v2モデル）のエントリポイントを作成
app = func.FunctionApp()

# /api/ingest で呼べるHTTPトリガー関数を定義（?code=... の関数キーが必要）
@app.function_name(name="ingest")                                        # 関数名（ポータル上の識別）
@app.route(route="ingest", auth_level=func.AuthLevel.FUNCTION)           # ルートと認証レベル
def ingest(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # 受信したHTTPリクエストからJSON本文を取得
        body = req.get_json()

        # 必須パラメータを取り出し：水槽ID（例: "main"）
        tank_id = body["tank_id"]

        # 温度（数値）を float 型に変換（文字列でも受け取れるよう安全に）
        temp_c = float(body["temperature_c"])

        # タイムスタンプ：指定されていなければ現在のUTC（ISO形式, 秒精度, +00:00）
        ts = body.get("ts_utc") or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        # Azure Functions 既定のストレージ接続文字列（環境変数）を取得
        conn = os.environ["AzureWebJobsStorage"]

        # Table Storage へ接続するクライアントを作成
        svc = TableServiceClient.from_connection_string(conn)

        # テーブルクライアントを取得（無ければ後続で作成）
        table = svc.get_table_client("FishTankTemps")

        # 初回はテーブルが無い可能性があるので作成を試みる（存在時の例外は握りつぶす）
        try:
            table.create_table()
        except Exception:
            pass

        # 保存する1行分のエンティティ（辞書）を組み立て
        entity: TableEntity = {
            "PartitionKey": tank_id,   # 分割キー（同じ水槽IDでグルーピング）
            "RowKey": ts,              # 一意キー（UTCのISO文字列）
            "TemperatureC": temp_c     # 記録する温度(℃)
        }

        # upsert：同じキーがあれば更新、無ければ新規作成
        table.upsert_entity(entity)

        # 正常終了：200 OK を返す
        return func.HttpResponse("OK", status_code=200)

    except Exception as e:
        # 例外はログに出しつつ 400 を返す（原因の可視化）
        logging.exception("ingest error")
        return func.HttpResponse(str(e), status_code=400)
