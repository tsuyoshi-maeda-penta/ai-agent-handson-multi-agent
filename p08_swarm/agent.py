import os
import json
import logging
import google.auth
import datetime
import random
import string
from typing import Any
from pydantic import BaseModel, Field

from google.adk import Workflow, Context
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import node, START
from google.genai import types

# ==========================================
# 1. 注文データベースとクーポンの模擬データ定義 (Mock Database)
# ==========================================
MOCK_ORDERS = {
    "ORD-001": {
        "status": "Delivered",
        "purchase_date": "2026-05-15",
        "items": [{"name": "Premium Keyboard", "price": 15000, "qty": 1}],
        "address": "東京都千代田区大手町1-1-1",
        "tracking_num": "TRK-98765432",
        "tracking_status": "Delivered",
        "carrier": "Yamato Transport",
        "refunded": False
    },
    "ORD-002": {
        "status": "Processing",
        "purchase_date": "2026-05-31",
        "items": [{"name": "Ergonomic Mouse", "price": 8000, "qty": 2}],
        "address": "大阪府大阪市北区梅田2-2-2",
        "tracking_num": None,
        "tracking_status": None,
        "carrier": None,
        "refunded": False
    },
    "ORD-003": {
        "status": "Shipped",
        "purchase_date": "2026-05-28",
        "items": [{"name": "Noise Cancelling Headphones", "price": 30000, "qty": 1}],
        "address": "福岡県福岡市中央区天神3-3-3",
        "tracking_num": "TRK-12345678",
        "tracking_status": "In Transit - Delayed due to heavy weather",
        "carrier": "Sagawa Express",
        "refunded": False
    }
}

COUPONS_ISSUED = {}

# ==========================================
# 2. エージェント用共通・専用ツール関数定義 (Tool Functions)
# ==========================================

def get_order_details(order_id: str) -> str:
    """注文データベースから指定された注文IDの詳細情報を取得します。

    Args:
        order_id: ORD-xxx 形式の注文ID（例: 'ORD-001', 'ORD-002'）
    """
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return f"エラー: 注文ID '{order_id}' はデータベースに存在しません。正しい注文IDを確認してください。"
    
    items_str = ", ".join([f"{item['name']} (単価: {item['price']}円, 数量: {item['qty']})" for item in order['items']])
    return (
        f"--- 注文情報: {order_id} ---\n"
        f"ステータス: {order['status']}\n"
        f"購入日: {order['purchase_date']}\n"
        f"購入商品: {items_str}\n"
        f"配送先住所: {order['address']}\n"
        f"返金状況: {'返金済み' if order['refunded'] else '未返金'}\n"
    )

def process_refund(order_id: str) -> str:
    """指定された注文の返品・返金処理を実行します。
    購入後30日以内の注文に限り処理が可能です。

    Args:
        order_id: ORD-xxx 形式 of 注文ID
    """
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return f"エラー: 注文ID '{order_id}' が見つかりません。"
    
    if order['refunded']:
        return f"情報: 注文ID '{order_id}' はすでに返金処理が完了しています。"

    # ポリシー確認: 現在日時（2026年6月1日と仮定）から30日以内であるかを判定
    current_date = datetime(2026, 6, 1)
    try:
        purchase_date = datetime.strptime(order['purchase_date'], "%Y-%m-%d")
        days_diff = (current_date - purchase_date).days
        if days_diff > 30:
            return f"却下: 注文ID '{order_id}' の購入日は {order['purchase_date']} であり、30日間の返品期限を過ぎているため、ポリシーにより返金できません。"
    except Exception:
        pass

    order['refunded'] = True
    order['status'] = 'Refunded'
    return f"成功: 注文ID '{order_id}' の返品・返金手続きを受け付けました。全額返金が適用されます。"

def update_shipping_address(order_id: str, new_address: str) -> str:
    """注文の配送先住所を更新します。
    出荷完了前（ステータスが 'Processing' のもの）に限り変更が可能です。

    Args:
        order_id: ORD-xxx 形式の注文ID
        new_address: 新しい配送先住所（例: '東京都新宿区西新宿1-1-1'）
    """
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return f"エラー: 注文ID '{order_id}' が見つかりません。"
    
    if order['status'] != "Processing":
        return f"却下: 注文ID '{order_id}' のステータスは '{order['status']}' です。出荷完了または配送完了後のため、住所変更はできません。"

    old_address = order['address']
    order['address'] = new_address
    return f"成功: 注文ID '{order_id}' の配送先住所を '{old_address}' から '{new_address}' に変更しました。"

def cancel_order(order_id: str) -> str:
    """注文全体をキャンセルします。
    出荷完了前（ステータスが 'Processing' のもの）に限りキャンセルが可能です。

    Args:
        order_id: ORD-xxx 形式の注文ID
    """
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return f"エラー: 注文ID '{order_id}' が見つかりません。"
    
    if order['status'] != "Processing":
        return f"却下: 注文ID '{order_id}' のステータスは '{order['status']}' です。出荷済みのためキャンセルできません。返品手続きを案内してください。"

    order['status'] = "Cancelled"
    return f"成功: 注文ID '{order_id}' のキャンセル処理が完了しました。"

def track_delivery(order_id: str) -> str:
    """配送キャリアの追跡システムを照会し、現在の配送状況と位置情報を取得します。

    Args:
        order_id: ORD-xxx 形式の注文ID
    """
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return f"エラー: 注文ID '{order_id}' が見つかりません。"
    
    if order['status'] == "Processing":
        return f"情報: 注文ID '{order_id}' は現在出荷準備中です。追跡情報はまだ発行されていません。"
    
    return (
        f"--- 配送追跡情報: {order_id} ---\n"
        f"配送業者: {order['carrier']}\n"
        f"追跡番号: {order['tracking_num']}\n"
        f"現在の配送状況: {order['tracking_status']}\n"
    )

def issue_apology_coupon(customer_id: str, discount_amount: int = 1000) -> str:
    """お客様へのお詫びとして、次回使える割引クーポンコードを発行します。

    Args:
        customer_id: お客様ID（例: 'CUST-888'）
        discount_amount: クーポンの金額（デフォルトは1000円）
    """
    code = "SORRY-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    COUPONS_ISSUED[code] = {"customer": customer_id, "amount": discount_amount}
    return f"成功: クーポンコード '{code}'（{discount_amount}円引き）を発行しました。お客様 {customer_id} に提示してください。"

def escalate_to_human(customer_id: str, complaint_summary: str) -> str:
    """問題を人間のスーパーバイザーまたはカスタマーサポートマネージャーへエスカレーションします。

    Args:
        customer_id: お客様ID
        complaint_summary: クレームや問題の要約・経緯
    """
    return f"成功: お客様 {customer_id} の問題を、経緯「{complaint_summary}」としてスーパーバイザーへエスカレーションしました。追って担当者よりご連絡いたします。"

# ==========================================
# 3. エージェント定義 (エージェント定義 & 階層構造)
# ==========================================

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# 4.2 返金・返品専門エージェント (Refund & Return Agent)
refund_return_agent = Agent(
    name="Refund_Return_Agent",
    description="返金・返品専門エージェント。ポリシー（購入後30日以内、未開封など）の確認、商品の返品手続き、返金の受付、注文ステータスの参照を行います。",
    instruction="""あなたは返金・返品専門のエージェントです。
注文データベースを参照して商品のステータスを確認し、社内の返金・返品ポリシー（例：購入後30日以内、未開封に限るなど）に合致しているかを厳密に判定します。
条件を満たしている場合は、返品受付プロセスを自律的に進めてください。
もしユーザーが配送遅延への不満を述べ始めた場合は、配送トラブル専門エージェントへハンドオーバーしてください。""",
    model=model,
    tools=[get_order_details, process_refund]
)

# 4.3 注文変更エージェント (Order Modification Agent)
order_modification_agent = Agent(
    name="Order_Modification_Agent",
    description="注文変更・キャンセル専門エージェント。配送先住所の変更、注文商品の数量やカラー・サイズの変更、注文キャンセルなどを、出荷完了前であれば実行します。",
    instruction="""あなたは注文変更専門のエージェントです。
注文が「出荷準備完了」または「発送済み」ステータスになる前であるかを確認し、変更可能な範囲で注文内容の書き換えを行います。
すでに発送済みの場合は変更ができない旨を丁寧に伝え、必要に応じて配送トラブル専門エージェント、または返品専門エージェントへ相談を促すかハンドオーバーしてください。""",
    model=model,
    tools=[get_order_details, update_shipping_address, cancel_order]
)

# 4.4 配送トラブル専門エージェント (Delivery Trouble Agent)
delivery_trouble_agent = Agent(
    name="Delivery_Trouble_Agent",
    description="配送トラブル専門エージェント。配送状況の追跡（トラッキング）、配送業者への確認、紛失や大幅遅延時の調査受付、補償や再送の手配を検討します。",
    instruction="""あなたは配送トラブル専門のエージェントです。
配送追跡システムと連携し、ユーザーの荷物が現在どこにあるかを正確に把握・報告します。
大幅な遅延や紛失の疑いがある場合、補償手続きや再送の手配を検討し、返金が必要な場合は返金・返品専門エージェントへコンテキストを引き継ぎます。""",
    model=model,
    tools=[get_order_details, track_delivery]
)

# 4.5 クレーム対応エージェント (Complaint Handling Agent)
complaint_handling_agent = Agent(
    name="Complaint_Handling_Agent",
    description="クレーム対応専門エージェント。不満や怒りを感じているお客様の心情に寄り添い、真摯に共感的な対応を行います。お詫びのクーポン発行や、人間のマネージャーへのエスカレーション手続きを行います。",
    instruction="""あなたはクレーム対応専門の特級エージェントです。
最優先事項は、不満や怒りを感じているお客様の心情に寄り添い、丁寧かつ共感的な態度で対応することです。
テクニカルな解決（返金や配送確認など）が必要な場合は、バックグラウンドで他のエージェントのツールや知見を借りるか、または合意の上でハンドオーバーを試みてください。
必要に応じて、お詫びのクーポン発行や、人間のスーパーバイザーへのエスカレーション手続きを行います。""",
    model=model,
    tools=[issue_apology_coupon, escalate_to_human]
)

# 4.1 受付エージェント (Dispatcher Agent)
# サブエージェントとして他のすべての専門エージェントを持ちます。
dispatcher_agent = Agent(
    name="Dispatcher",
    description="総合受付エージェント。ユーザーの最初の問い合わせを受け、どの専門エージェントに対応を任せるべきかを判断して振り分けます。自分で問題を解決しようとせず、適切な専門エージェントへ速やかに引継ぎを行います。",
    instruction="""あなたはECサイトの総合受付エージェント（Dispatcher）です。
ユーザーの最初の入力を注意深く分析し、ユーザーが何を求めているかを特定してください。
自分で問題を解決しようとせず、速やかに適切な専門エージェントへ制御権を移譲（Handover）してください。
複数の要望が含まれる場合は、最も優先度の高いもの、または時系列的に先に行うべきタスクのエージェントへ引き継ぎます。""",
    model=model,
    sub_agents=[
        refund_return_agent,
        order_modification_agent,
        delivery_trouble_agent,
        complaint_handling_agent
    ]
)

app = App(
    root_agent=dispatcher_agent,
    name="p08_swarm",
)

