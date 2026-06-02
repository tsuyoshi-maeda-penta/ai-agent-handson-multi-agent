# ruff: noqa
import logging
import os
import re
import json
from typing import Any

import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from google.adk import Workflow, Context
from google.adk.workflow import node

# Set up logging
logger = logging.getLogger(__name__)

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


@node
async def init_state(ctx: Context, node_input: Any) -> str:
    """Initializes the state with the theme and loop_count."""
    if isinstance(node_input, dict):
        theme = node_input.get("theme", "")
    else:
        theme = str(node_input)

    ctx.state["theme"] = theme
    ctx.state["feedback"] = ""
    ctx.state["loop_count"] = 0
    return theme


@node
async def format_research_prompt(
    ctx: Context, theme: str = "", feedback: str = ""
) -> str:
    """Formats the prompt for market research, incorporating feedback if available."""
    if not theme:
        theme = ctx.state.get("theme", "")
    if not feedback:
        feedback = ctx.state.get("feedback", "")

    feedback_section = ""
    if feedback:
        feedback_section = (
            f"前回の提案は基準に達しませんでした。以下のフィードバック（改善点）を強く意識して、異なる角度から調査を再実行してください。\n"
            f"フィードバック: {feedback}"
        )

    prompt = (
        f"あなたは優秀な市場リサーチャーです。\n"
        f"以下のテーマについて、現在の市場トレンド、ターゲット層の潜在ニーズ、および主要な競合の状況を分析してください。\n\n"
        f"テーマ: {theme}\n\n"
        f"{feedback_section}\n\n"
        f"出力は、次の項目を含めてください：\n"
        f"- 市場の現状とトレンド\n"
        f"- 見落とされがちなユーザーの不満・ニーズ\n"
        f"- 競合が未参入のポジショニング"
    )
    return prompt

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

market_research_agent = Agent(
    name="market_research_agent",
    model=model,
    instruction="あなたは優秀な市場リサーチャーです。与えられたプロンプトに従って市場調査を行ってください。",
)

@node
async def format_generation_prompt(ctx: Context, node_input: str) -> str:
    """Formats the prompt for product idea generation using the market research report."""
    research_report = node_input
    ctx.state["research_report"] = research_report

    prompt = (
        f"あなたは革新的な商品企画者です。\n"
        f"以下の市場調査レポートを基に、市場の課題を解決する新商品のアイデアを1つ提案してください。\n\n"
        f"市場調査レポート:\n"
        f"{research_report}\n\n"
        f"以下のフォーマットで出力してください：\n"
        f"【商品名】\n"
        f"【コンセプト】\n"
        f"【ターゲット層】\n"
        f"【独自の強み (USP)】\n"
        f"【想定される利用シーン】"
    )
    return prompt

idea_generation_agent = Agent(
    name="idea_generation_agent",
    model=model,
    instruction="あなたは革新的な商品企画者です。与えられた市場調査レポートに基づいて素晴らしい新商品のアイデアを提案してください。",
)

@node
async def format_evaluation_prompt(ctx: Context, node_input: str) -> str:
    """Formats the prompt for product idea evaluation and caches the product idea in state."""
    product_idea = node_input
    ctx.state["product_idea"] = product_idea

    prompt = (
        f"あなたは厳格な投資家および商品開発責任者です。\n"
        f"提案された新商品アイデアを、以下の4つの基準（各25点満点、計100点満点）で厳しく採点してください。\n\n"
        f"1. 新規性 (Novelty): 既存商品にない新しさがあるか\n"
        f"2. 市場性 (Marketability): ターゲット層に確実に刺さるか、売れる見込みがあるか\n"
        f"3. 実現可能性 (Feasibility): 技術的・コスト的に現実的か\n"
        f"4. 収益性 (Profitability): 継続的なビジネスとして成立するか\n\n"
        f"提案されたアイデア:\n"
        f"{product_idea}\n\n"
        f"出力は必ず以下のJSONフォーマットのみにしてください（他の説明テキストは一切不要です）。\n\n"
        f"{{\n"
        f'  "score": 0,\n'
        f'  "breakdown": {{\n'
        f'    "novelty": 0,\n'
        f'    "marketability": 0,\n'
        f'    "feasibility": 0,\n'
        f'    "profitability": 0\n'
        f"  }},\n"
        f'  "feedback": "合格基準に達するための具体的な改善点、または評価の理由を記述"\n'
        f"}}"
    )
    return prompt

idea_evaluation_agent = Agent(
    name="idea_evaluation_agent",
    model=model,
    instruction="あなたは厳格な投資家および商品開発責任者です。提案されたアイデアを採点し、指定されたJSONフォーマットで回答してください。JSON以外のテキストは出力しないでください。",
)

@node
async def check_evaluation_score(ctx: Context, node_input: str) -> str:
    """Evaluates the score from the evaluation agent, updates state, and routes to end or loop."""
    raw_output = node_input
    cleaned = raw_output.strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = cleaned

    try:
        data = json.loads(json_str)
    except Exception as e:
        logger.error(
            f"Failed to parse evaluation result JSON: {e}. Raw content: {raw_output}"
        )
        data = {
            "score": 0,
            "feedback": "Failed to parse JSON. Please regenerate and make sure output is strictly in JSON format.",
        }

    raw_score = data.get("score", 0)
    try:
        score = int(raw_score)
    except Exception:
        score = 0
    feedback = data.get("feedback", "No feedback provided.")

    loop_count = ctx.state.get("loop_count", 0) + 1
    ctx.state["loop_count"] = loop_count

    if score >= 80:
        ctx.state["final_score"] = score
        ctx.state["final_feedback"] = feedback
        ctx.state["status"] = "PASSED"
        ctx.route = "PASSED"
        return f"SUCCESS: Score {score}/100 achieved after {loop_count} loop(s)!\n\n【最終提案商品】\n{ctx.state.get('product_idea')}"
    elif loop_count >= 3:
        ctx.state["final_score"] = score
        ctx.state["final_feedback"] = feedback
        ctx.state["status"] = "FAILED"
        ctx.route = "FAILED"
        return f"FAILED: Max loops (3) reached. Last score was {score}/100.\n\n【最終提案商品】\n{ctx.state.get('product_idea')}\n\n【フィードバック】\n{feedback}"
    else:
        ctx.state["feedback"] = feedback
        ctx.route = "LOOP"
        return f"LOOPING: Score {score}/100 is below 80. Loop count: {loop_count}.\nFeedback: {feedback}"

workflow = Workflow(
    name="product_generator_workflow",
    edges=[
        ("START", init_state),
        (init_state, format_research_prompt),
        (format_research_prompt, market_research_agent),
        (market_research_agent, format_generation_prompt),
        (format_generation_prompt, idea_generation_agent),
        (idea_generation_agent, format_evaluation_prompt),
        (format_evaluation_prompt, idea_evaluation_agent),
        (idea_evaluation_agent, check_evaluation_score),
        (
            check_evaluation_score,
            {
                "LOOP": format_research_prompt,
            },
        ),
    ],
)

app = App(
    root_agent=workflow,
    name="app",
)
