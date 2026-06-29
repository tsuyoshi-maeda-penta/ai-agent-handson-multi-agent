# ruff: noqa
import os
import google.auth
from pydantic import BaseModel, Field
from typing import Any

from google.adk.agents import Agent, Context
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow, node, START
from google.adk.events.event import Event
from google.genai import types

# Set environment variables for Vertex AI/GCP
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


class ReviewResult(BaseModel):
    score: int = Field(description="総合点 (0-100の整数)")
    is_approved: bool = Field(
        description="総合点が80点以上であれば true、79点以下であれば false (boolean)"
    )
    review_feedback: str = Field(
        description="79点以下の場合は、どの基準が不足しているかと、具体的な修正アクション（例：『〇〇のセクションに具体的なコード例を追加してください』など）を箇条書きで記述。80点以上の場合は 'No corrections needed.' と記述"
    )


class StartQueryParse(BaseModel):
    blog_topic: str = Field(description="The topic of the technical blog post")
    target_audience: str = Field(description="The target audience for the blog post")


class BlogState(BaseModel):
    blog_topic: str = ""
    target_audience: str = ""
    current_draft: str = ""
    review_feedback: str = ""
    score: int = 0
    is_approved: bool = False
    loop_count: int = 0

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Parser Agent: Extracts topic and audience from initial query
parser_agent = Agent(
    name="parser_agent",
    model=model,
    instruction="""Extract the blog topic and target audience from the user prompt.
If the prompt doesn't specify a target audience, use "General Developers" as default.""",
    output_schema=StartQueryParse,
)

# Writer Agent: Writes and refines the blog post
writer_agent = Agent(
    name="writer_agent",
    model=model,
    instruction="""あなたはプロの技術ライターおよびエンジニアです。
読者が理解しやすく、技術的に正確で、実用的なブログ記事を執筆することがあなたの任務です。

【執筆ガイドライン】
1. 構成は Markdown 形式（H2, H3 階層）を正しく使用してください。
2. コードブロックが含まれる場合は、構文が正確で、かつ解説を添えてください。
3. 専門用語は適切に解説し、読者を置き去りにしない表現を心がけてください。

【入力に応じた動き】
- 初回実行時、提示されたテーマとターゲット層に最適な記事をゼロから執筆してください。
- フィードバック（Review Feedback）が提供された場合、指摘事項を真摯に受け止め、該当箇所を大幅に改善・修正した新しいドラフトを出力してください。修正箇所の説明は不要です。記事本文のみを出力してください。""",
)

# Reviewer Agent: Evaluates the draft and scores it
reviewer_agent = Agent(
    name="reviewer_agent",
    model=model,
    instruction="""あなたは厳格かつ建設的な技術ブログの編集者（査読者）です。
提出された技術記事を以下の4つの基準（各25点満点、計100点）で評価してください。

【評価基準】
1. 技術的正確性 (Technical Accuracy): コードや概念に誤りがないか。
2. 読みやすさ (Readability): 文章の論理構成、Markdownの適切な使用、冗長性の排除。
3. 読者への価値 (Value to Reader): ターゲット層にとって有益な情報が含まれているか。
4. 具体性 (Concreteness): 抽象的な説明に終始せず、具体例やユースケースが示されているか。

【出力フォーマット】
必ず以下の JSON フォーマットのみで回答してください。他の挨拶やテキストは一切含めないでください。

{
    "score": 総合点 (0-100の整数),
    "is_approved": 総合点が80点以上であれば true、79点以下であれば false (boolean),
    "review_feedback": "79点以下の場合は、どの基準が不足しているかと、具体的な修正アクション（例：『〇〇のセクションに具体的なコード例を追加してください』など）を箇条書きで記述。80点以上の場合は 'No corrections needed.' と記述"
}""",
    output_schema=ReviewResult,
)


@node(rerun_on_resume=True)
async def start_node(ctx: Context, node_input: Any):
    query_str = ""
    if isinstance(node_input, str):
        query_str = node_input
    elif hasattr(node_input, "parts"):
        query_str = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, dict):
        ctx.state["blog_topic"] = node_input.get("blog_topic", "")
        ctx.state["target_audience"] = node_input.get(
            "target_audience", "General Developers"
        )
        ctx.state["loop_count"] = 0
        ctx.state["current_draft"] = ""
        ctx.state["review_feedback"] = ""
        ctx.state["score"] = 0
        ctx.state["is_approved"] = False
        print(
            f"\n🚀 Processing Topic: {ctx.state['blog_topic']} | Target: {ctx.state['target_audience']}\n"
        )
        return

    # Run the parser agent to extract fields from raw string input
    res = await ctx.run_node(parser_agent, query_str)

    import json

    data = {}
    if isinstance(res, str):
        try:
            data = json.loads(res)
        except Exception:
            data = {"blog_topic": query_str, "target_audience": "General Developers"}
    elif isinstance(res, dict):
        data = res
    elif hasattr(res, "model_dump"):
        data = res.model_dump()
    else:
        data = {"blog_topic": query_str, "target_audience": "General Developers"}

    ctx.state["blog_topic"] = data.get("blog_topic", query_str)
    ctx.state["target_audience"] = data.get("target_audience", "General Developers")
    ctx.state["loop_count"] = 0
    ctx.state["current_draft"] = ""
    ctx.state["review_feedback"] = ""
    ctx.state["score"] = 0
    ctx.state["is_approved"] = False
    print(
        f"\n🚀 Processing Topic: {ctx.state['blog_topic']} | Target: {ctx.state['target_audience']}\n"
    )


@node(rerun_on_resume=True)
async def writer_node(ctx: Context):
    blog_topic = ctx.state.get("blog_topic", "")
    target_audience = ctx.state.get("target_audience", "")
    current_draft = ctx.state.get("current_draft", "")
    review_feedback = ctx.state.get("review_feedback", "")
    loop_count = ctx.state.get("loop_count", 0)

    print(f"✍️ Writer Agent is generating draft... (Loop {loop_count + 1})")

    if loop_count == 0:
        prompt_str = f"【テーマ】\n{blog_topic}\n\n【ターゲット層】\n{target_audience}"
    else:
        prompt_str = f"【現在の草稿】\n{current_draft}\n\n【フィードバック / 修正指示】\n{review_feedback}"

    res = await ctx.run_node(writer_agent, prompt_str)

    draft_text = ""
    if isinstance(res, str):
        draft_text = res
    elif hasattr(res, "parts"):
        draft_text = "".join(part.text for part in res.parts if part.text)
    elif isinstance(res, dict) and "text" in res:
        draft_text = res["text"]
    else:
        draft_text = str(res)

    ctx.state["current_draft"] = draft_text


@node(rerun_on_resume=True)
async def reviewer_node(ctx: Context):
    current_draft = ctx.state.get("current_draft", "")
    print(f"🔍 Reviewer Agent is evaluating draft...")

    prompt_str = f"【評価対象の技術ブログ記事】\n{current_draft}"

    res = await ctx.run_node(reviewer_agent, prompt_str)

    import json

    data = {}
    if isinstance(res, str):
        try:
            data = json.loads(res)
        except Exception:
            data = {
                "score": 70,
                "is_approved": False,
                "review_feedback": "Could not parse review output properly. Please improve formatting and accuracy.",
            }
    elif isinstance(res, dict):
        data = res
    elif hasattr(res, "model_dump"):
        data = res.model_dump()
    else:
        data = {
            "score": 70,
            "is_approved": False,
            "review_feedback": "Could not parse review output.",
        }

    ctx.state["score"] = data.get("score", 0)
    ctx.state["is_approved"] = data.get("is_approved", False)
    ctx.state["review_feedback"] = data.get("review_feedback", "")

    print(f"📊 Score: {ctx.state['score']}/100 | Approved: {ctx.state['is_approved']}")
    if not ctx.state["is_approved"]:
        print(f"💡 Feedback:\n{ctx.state['review_feedback']}\n")

    ctx.state["loop_count"] = ctx.state.get("loop_count", 0) + 1


@node
async def router_node(ctx: Context):
    is_approved = ctx.state.get("is_approved", False)
    loop_count = ctx.state.get("loop_count", 0)

    if is_approved or loop_count >= 3:
        return Event(route="end")
    else:
        return Event(route="loop")


@node
async def end_node(ctx: Context):
    current_draft = ctx.state.get("current_draft", "")
    score = ctx.state.get("score", 0)
    is_approved = ctx.state.get("is_approved", False)
    review_feedback = ctx.state.get("review_feedback", "")
    loop_count = ctx.state.get("loop_count", 0)

    print(f"\n✨ Workflow completed in {loop_count} loop(s)!")
    print(f"🏆 Final Score: {score}/100")
    print(f"✅ Approved: {is_approved}\n")

    output_text = f"""# Final Article Generation Result
- **Final Score**: {score}/100
- **Approved**: {is_approved}
- **Loops Run**: {loop_count}

## Review Feedback
{review_feedback}

## Final Draft
{current_draft}
"""
    return Event(output=output_text)


# Workflow Definition
review_and_critique_workflow = Workflow(
    name="review_and_critique_workflow",
    state_schema=BlogState,
    edges=[
        (START, start_node),
        (start_node, writer_node),
        (writer_node, reviewer_node),
        (reviewer_node, router_node),
        (
            router_node,
            {
                "loop": writer_node,
                "end": end_node,
            },
        ),
    ],
)

# App Container
app = App(
    root_agent=review_and_critique_workflow,
    name="p04_review_and_critique",
)
