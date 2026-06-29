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

import datetime
import json
import logging
import os
from typing import Any

import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.genai import types

logger = logging.getLogger(__name__)

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# --- エージェントの定義 ---

creative_agent = Agent(
    name="creative_agent",
    model=model,
    instruction="""
あなたは一流のデジタルマーケティング・コピーライターです。
与えられた商材情報とターゲット層 of インサイトを深く分析し、指定されたSNSに最適化された、クリック率（CTR）を高めるキャッチコピーを生成してください。
2回目以降の実行時は、提供される「プロンプト修正指示」および「フィードバック」を厳格に反映させ、前回のコピーをさらに魅力的にブラッシュアップしてください。
""".strip(),
)

review_agent = Agent(
    name="review_agent",
    model=model,
    instruction="""
あなたは厳格な広告クリエイティブディレクターおよびデータサイエンティストです。
提出されたキャッチコピー案を、以下の基準で100点満点で採点してください。
  1. ターゲットへの訴求力 (30点)
  2. プラットフォーム適合性（文字数、トーン＆マナー） (30点)
  3. 感情を動かすフック・独自性 (40点)

総合スコアが85点以上、またはループ上限（3回目）に達した場合は、合格として処理を終了します。
85点未満の場合は不合格とし、なぜその点数なのか、具体的にどこをどう直すべきか（「もっとベネフィットを具体的に」「専門用語を排除して」など）の詳細なフィードバックを作成してください。

出力は必ず以下のJSONフォーマットに従い、純粋なJSONオブジェクトのみを返却してください。マークダウンのコードブロック等で囲まないで、直接JSON文字列のみを出力してください。

JSONフォーマット：
{
  "score": 85,
  "passed": true,
  "feedback": "ここには具体的なフィードバックテキストを記載します。"
}
""".strip(),
)

refinement_agent = Agent(
    name="refinement_agent",
    model=model,
    instruction="""
あなたはプロンプトエンジニアリングの専門家です。
クリエイティブエージェントが「レビューエージェントからの手厳しいフィードバック」を完全に克服するための、次回の生成用最適化指示（プロンプトの修正・追加分）を構築してください。
レビューで指摘された弱点（例: ターゲットのペルソナに響いていない、インパクトが薄いなど）をピンポイントで補強するための制約条件や、ペルソナの深掘り指示を既存のプロンプトに動的に注入・ブレンドした、新しいプロンプトを出力してください。
""".strip(),
)

# --- ユーティリティ関数 ---

def clean_json_text(text: str) -> str:
    """JSONテキストからマークダウンのコードブロック等を取り除く。"""
    text = text.strip()
    if text.startswith("```"):
        # ```json や ``` をトリム
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

# --- オーケストレーターノード ---

@node(rerun_on_resume=True)
async def orchestrate_copy_refinement(ctx: Context, node_input: Any) -> Any:
    """Iterative Refinement（反復推敲）パターンに従って、SNS広告用キャッチコピーを洗練させるノード。"""
    # 1. 入力のパース
    # 入力は辞書、JSON文字列、あるいはPydanticモデルなどの可能性がある。
    product_description = ""
    target_audience = ""
    sns_platform = ""
    appeal_point = ""

    if isinstance(node_input, dict):
        product_description = node_input.get("product_description", "")
        target_audience = node_input.get("target_audience", "")
        sns_platform = node_input.get("sns_platform", "")
        appeal_point = node_input.get("appeal_point", "")
    elif isinstance(node_input, str):
        node_input_str = node_input.strip()
        if (node_input_str.startswith("{") and node_input_str.endswith("}")) or (node_input_str.startswith("[") and node_input_str.endswith("]")):
            try:
                data = json.loads(node_input_str)
                product_description = data.get("product_description", "")
                target_audience = data.get("target_audience", "")
                sns_platform = data.get("sns_platform", "")
                appeal_point = data.get("appeal_point", "")
            except Exception:
                product_description = node_input
        else:
            product_description = node_input
    elif hasattr(node_input, "product_description"):
        product_description = getattr(node_input, "product_description", "")
        target_audience = getattr(node_input, "target_audience", "")
        sns_platform = getattr(node_input, "sns_platform", "")
        appeal_point = getattr(node_input, "appeal_point", "")
    else:
        product_description = str(node_input)

    # デフォルト値の補完
    if not target_audience:
        target_audience = "一般消費者"
    if not sns_platform:
        sns_platform = "Instagram"
    if not appeal_point:
        appeal_point = "商品の魅力、使いやすさ"

    # 初回のクリエイティブプロンプト構築
    current_creative_prompt = f"""
以下の情報を基に、配信先SNSに最適化された、クリック率（CTR）を高める広告キャッチコピーを3案生成してください。
それぞれの案について、キャッチコピーと、そのコピーの意図や狙いを詳しく説明してください。

【商材概要】: {product_description}
【ターゲット属性】: {target_audience}
【配信SNS】: {sns_platform}
【訴求軸】: {appeal_point}
""".strip()

    history = []
    final_copy = ""
    final_score = 0
    passed = False

    for loop_i in range(1, 4):
        logger.info(f"--- Loop {loop_i}/3 Start ---")
        
        # 1. クリエイティブエージェントによる生成
        creative_res = await ctx.run_node(creative_agent, node_input=current_creative_prompt)
        creative_text = creative_res.text if hasattr(creative_res, "text") else str(creative_res)
        logger.info(f"Creative Agent output:\n{creative_text}")

        # 2. レビューエージェントによる評価
        review_prompt = f"""
元のユーザー要求:
【商材概要】: {product_description}
【ターゲット属性】: {target_audience}
【配信SNS】: {sns_platform}
【訴求軸】: {appeal_point}

提出されたキャッチコピー案:
{creative_text}
""".strip()

        review_res = await ctx.run_node(review_agent, node_input=review_prompt)
        review_text = review_res.text if hasattr(review_res, "text") else str(review_res)
        logger.info(f"Review Agent output:\n{review_text}")

        # JSONパース
        score = 0
        passed_flag = False
        feedback = ""
        try:
            cleaned_review = clean_json_text(review_text)
            review_data = json.loads(cleaned_review)
            score = int(review_data.get("score", 0))
            passed_flag = bool(review_data.get("passed", False))
            feedback = review_data.get("feedback", "")
        except Exception as e:
            logger.error(f"Failed to parse review JSON: {e}")
            # パース失敗時の簡易処理
            score = 70  # 仮スコア
            passed_flag = False
            feedback = f"パースエラーが発生したためフォールバックしました。評価テキスト: {review_text}"

        final_copy = creative_text
        final_score = score
        passed = passed_flag

        history_item = {
            "loop_count": loop_i,
            "creative_output": creative_text,
            "score": score,
            "feedback": feedback,
            "new_prompt": None
        }

        # 早期終了または最大ループ終了の判定
        if passed_flag or loop_i == 3:
            history.append(history_item)
            logger.info(f"Loop finished. Passed: {passed_flag}, Loop: {loop_i}")
            break

        # 3. プロンプトリファインメントエージェントによるプロンプト改善
        refine_prompt = f"""
【直前のループで生成されたキャッチコピー】:
{creative_text}

【レビューエージェントからのフィードバック】:
{feedback}

【現在のクリエイティブ用プロンプト】:
{current_creative_prompt}
""".strip()

        refine_res = await ctx.run_node(refinement_agent, node_input=refine_prompt)
        refine_text = refine_res.text if hasattr(refine_res, "text") else str(refine_res)
        logger.info(f"Refinement Agent output:\n{refine_text}")

        current_creative_prompt = refine_text
        history_item["new_prompt"] = refine_text
        history.append(history_item)

    # 最終的な出力を辞書で返す
    result = {
        "final_copy": final_copy,
        "final_score": final_score,
        "passed": passed,
        "history": history
    }
    return json.dumps(result, ensure_ascii=False, indent=2)

# --- アプリケーション定義 ---

app = App(
    root_agent=orchestrate_copy_refinement,
    name="p05_iterative_refinement",
)
