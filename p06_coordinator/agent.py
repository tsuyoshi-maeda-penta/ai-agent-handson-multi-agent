# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import logging
import google.auth
from typing import Any
from pydantic import BaseModel, Field

from google.adk import Workflow, Context
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import node, START
from google.genai import types

# Set up logging
logger = logging.getLogger(__name__)

# Set up project environment
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# Initialize model
model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# --- 1. Schemas for Routing ---
class RoutingResult(BaseModel):
    category: str = Field(
        ...,
        description="The category of the inquiry. Must be exactly one of: 'ORDER', 'RETURN', 'PRODUCT', or 'OTHER'."
    )
    reason: str = Field(
        ...,
        description="Brief reasoning for choosing this category based on the user's intent."
    )


# --- 2. Custom Tools for Specialist Agents ---
def check_order_status(order_id: str) -> str:
    """注文番号を基に、現在の配送ステータスや到着予定日を検索します。

    Args:
        order_id: 注文番号 (例: ORD-12345)

    Returns:
        現在の配送ステータスと到着予定日の情報。
    """
    if not order_id:
        return "エラー: 注文番号が指定されていません。"
        
    order_id = order_id.strip().upper()
    if order_id == "ORD-12345" or "12345" in order_id:
        return "注文番号 ORD-12345: ステータス = '配送中', 到着予定日 = '2026-06-03', 配送業者 = 'Antigravity Express'"
    elif order_id == "ORD-67890" or "67890" in order_id:
        return "注文番号 ORD-67890: ステータス = '出荷準備中', 到着予定日 = '2026-06-05'"
    elif order_id == "ORD-00001" or "00001" in order_id:
        return "注文番号 ORD-00001: ステータス = '配達完了', 配達完了日 = '2026-05-28'"
    else:
        return f"注文番号 {order_id}: 該当する注文が見つかりません。有効な注文番号（例: ORD-12345, ORD-67890）をご指定ください。"


def get_product_details(product_name: str) -> str:
    """商品の仕様や機能、ナレッジベースの情報を取得します。

    Args:
        product_name: 商品名（例: 'スマートウォッチ', 'ワイヤレスイヤホン'）

    Returns:
        仕様や機能のカタログデータやトラブルシューティング。
    """
    if not product_name:
        return "エラー: 商品名が指定されていません。"

    name_lower = product_name.lower()
    if "ウォッチ" in name_lower or "watch" in name_lower:
        return (
            "【商品名】AeroWatch 2.0\n"
            "【サイズ】42mm x 42mm x 11.4mm\n"
            "【仕様】防水 (5ATM), バッテリー寿命 (通常使用で7日間), ディスプレイ (1.4インチ AMOLED)\n"
            "【対応OS】iOS 14以上, Android 9.0以上\n"
            "【トラブルシューティング】電源が入らない場合は、付属の充電器に接続し、10分以上充電してからサイドボタンを長押ししてください。"
        )
    elif "イヤホン" in name_lower or "earphone" in name_lower or "buds" in name_lower:
        return (
            "【商品名】SonicBuds Pro\n"
            "【仕様】アクティブノイズキャンセリング (ANC) 搭載, バッテリー寿命 (本体6時間、ケース併用で24時間)\n"
            "【接続】Bluetooth 5.3\n"
            "【トラブルシューティング】ペアリングできない場合は、両方のイヤホンをケースに戻し、ケースの背面ボタンを10秒間長押ししてリセットを行ってください。"
        )
    else:
        return f"【商品名】{product_name}\n【情報】該当する商品の詳細カタログデータが見つかりません。"


# --- 3. Agent Definitions ---

# Category Classifier Agent
nlu_agent = Agent(
    name="nlu_agent",
    description="Inquiry Classification Specialist",
    model=model,
    instruction="""あなたはユーザーの問い合わせ内容を分析し、最適なカテゴリに分類する専門エージェントです。
以下のカテゴリから、最も適切なものを1つ選択してください：
- 'ORDER': 注文ステータス、配送状況、いつ届くか、注文履歴などの注文や配送に関する問い合わせ。
- 'RETURN': 返品、キャンセル、返金、交換などの手続きやポリシーに関する問い合わせ。
- 'PRODUCT': 商品の使い方、機能、仕様、サイズ、スペック、動かないなどのトラブルシューティングに関する問い合わせ。
- 'OTHER': 上記以外の問い合わせ（一般的な挨拶、雑談、複雑なクレーム、どの専門外にも該当しない特殊な要望など）。

必ず指定された出力スキーマ（RoutingResult）に従ってJSON形式で回答してください。""",
    output_schema=RoutingResult,
)

# Sub-Agent: Order Status Specialist
order_specialist = Agent(
    name="order_status_specialist",
    description="Order Status Specialist",
    model=model,
    instruction="""あなたは注文状況および配送ステータスの確認を専門に行うエージェントです。
ユーザーから提示された注文番号（例: ORD-XXXXX）を基に、注文データベースまたは配送システムをシミュレート（またはツール経由で検索）し、
現在の配送ステータス（出荷準備中、配送中、配達完了など）や到着予定日を正確に回答してください。注文番号が不明な場合は、ユーザーに注文番号の提示を求めてください。""",
    tools=[check_order_status],
)

# Sub-Agent: Return Specialist
return_specialist = Agent(
    name="return_specialist",
    description="Return Specialist",
    model=model,
    instruction="""あなたは商品の返品および返金手続きを専門に行うエージェントです。
当社の返品ポリシー（購入後30日以内、未開封に限るなど）に基づき、ユーザーが返品可能かどうかを判定します。
返品理由や商品の状態をヒアリングし、条件を満たしている場合は返品手順（返送先住所や着払い/元払いの指定など）を案内してください。""",
)

# Sub-Agent: Product Info Specialist
product_specialist = Agent(
    name="product_info_specialist",
    description="Product Info Specialist",
    model=model,
    instruction="""あなたは取り扱い商品の仕様、機能、およびトラブルシューティングを専門に解説するエージェントです。
商品のカタログデータや取扱説明書（ナレッジベース）を基に、ユーザーからの「この商品のサイズは？」「〇〇に対応している？」といった質問に対して、
具体的かつ分かりやすく回答してください。問題が発生している場合は、ステップ・バイ・ステップで解決策を提示してください。""",
    tools=[get_product_details],
)

# Coordinator Agent: OmniSupport Coordinator (Ultimate Responder)
coordinator_agent = Agent(
    name="omni_support_coordinator",
    description="OmniSupport Coordinator",
    model=model,
    instruction="""あなたは大手ECサイトの優秀なカスタマーサポート統括AI（Coordinator）です。
ユーザーからの問い合わせ内容を分析し、自身で直接回答するのではなく、最適な専門サブエージェント（Order Status Specialist, Return Specialist, Product Info Specialist）を呼び出して処理を委ねてください。
サブエージェントから回答を受け取ったら、ユーザーに対して親切かつ丁寧な言葉遣いで最終的な案内を行ってください。対応外の複雑なクレームや特殊な要望の場合は、人間のオペレーターへの引き継ぎを提案してください。""",
)


# --- 4. Workflow Nodes ---

@node
async def init_state(ctx: Context, node_input: Any) -> str:
    """Initializes the state with the user's inquiry."""
    if isinstance(node_input, dict):
        query = node_input.get("query", "")
        if not query:
            query = next(iter(node_input.values())) if node_input else ""
    else:
        query = str(node_input)

    ctx.state["query"] = query
    ctx.state["route"] = "OTHER"
    logger.info(f"Initialized workflow with query: {query}")
    return query


@node
async def route_decision(ctx: Context, node_input: Any) -> str:
    """Parses the categorization result from nlu_agent and directs the workflow."""
    category = "OTHER"
    
    # Extract classification result from nlu_agent
    if hasattr(node_input, "category"):
        category = node_input.category
    elif isinstance(node_input, dict):
        category = node_input.get("category", "OTHER")
    elif isinstance(node_input, str):
        cleaned = node_input.strip()
        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                data = json.loads(cleaned)
                category = data.get("category", "OTHER")
            except Exception:
                pass
        
        # Fallback string searching if needed
        if category == "OTHER":
            if "ORDER" in cleaned.upper():
                category = "ORDER"
            elif "RETURN" in cleaned.upper():
                category = "RETURN"
            elif "PRODUCT" in cleaned.upper():
                category = "PRODUCT"

    category = category.upper()
    if category not in ["ORDER", "RETURN", "PRODUCT", "OTHER"]:
        category = "OTHER"

    ctx.state["route"] = category
    ctx.route = category
    logger.info(f"Routed inquiry category as: {category}")
    
    # Return the user inquiry to feed into the chosen specialist agent
    return ctx.state["query"]


@node
async def format_coordinator_prompt(ctx: Context, specialist_output: str ) -> str:
    """Formats the final prompt for the coordinator, combining user query and specialist response."""
    query = ctx.state.get("query", "")
    category = ctx.state.get("route", "SPECIALIST")
    
    prompt = (
        f"ユーザーからの問い合わせ:\n"
        f"{query}\n\n"
        f"【専門担当エージェント ({category}) からの回答・調査結果】:\n"
        f"{specialist_output}\n\n"
        f"指示:\n"
        f"上記の専門エージェントの回答をベースとして、ユーザーに対して非常に親切、丁寧、かつ温かみのある言葉遣いで、"
        f"最終的なカスタマーサポートの回答文を構成してください。"
    )
    return prompt


@node
async def format_coordinator_direct_prompt(ctx: Context, node_input: Any) -> str:
    """Formats the coordinator prompt for the 'OTHER' route, where no specialist agent is involved."""
    query = ctx.state.get("query", "")

    prompt = (
        f"ユーザーからの問い合わせ:\n"
        f"{query}\n\n"
        f"指示:\n"
        f"この問い合わせは特定の専門カテゴリ（注文・返品・製品）に該当しません。"
        f"カスタマーサポートとして、非常に親切、丁寧、かつ温かみのある言葉遣いで、"
        f"ユーザーに対する最終的な回答文を構成してください。"
    )
    return prompt


# --- 5. Workflow Graph Definition (Coordinator/Router Pattern) ---

coordinator_workflow = Workflow(
    name="coordinator_workflow",
    description="OmniSupport Coordinator Customer Support Workflow",
    edges=[
        (START, init_state),
        (init_state, nlu_agent),
        (nlu_agent, route_decision),
        (
            route_decision,
            {
                "ORDER": order_specialist,
                "RETURN": return_specialist,
                "PRODUCT": product_specialist,
                "OTHER": format_coordinator_direct_prompt,
            },
        ),
        (order_specialist, coordinator_agent),
        (return_specialist, coordinator_agent),
        (product_specialist, coordinator_agent),
        (format_coordinator_direct_prompt, coordinator_agent),
    ],
)

root_agent = coordinator_workflow

app = App(
    root_agent=root_agent,
    name="p06_coordinator",
)
