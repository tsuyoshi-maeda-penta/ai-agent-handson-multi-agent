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
from google.adk.events import RequestInput
from google.genai import types

# Vertex AI/GCP用の環境変数を設定
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


# --- 状態（State）および入力（Input）スキーマ定義 ---

class PressReleaseState(BaseModel):
    raw_input: str = ""
    current_draft: str = ""
    review_feedback: str = ""
    human_feedback: str = ""
    loop_count: int = 0
    is_approved: bool = False


class HumanApprovalInput(BaseModel):
    status: str = Field(
        description="承認する場合は 'OK'、差し戻す（修正指示を出す）場合は 'NG' を入力してください。"
    )
    feedback: str = Field(
        default="",
        description="'NG' の場合の具体的な修正内容や指示を記述してください。"
    )


# --- エージェント定義 ---

# モデルの初期化
model = Gemini(
    model="gemini-2.5-flash",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# プレスリリース作成エージェント (Sub-Agent 1)
writer_agent = Agent(
    name="writer_agent",
    model=model,
    instruction="""あなたはプロのPRスペシャリストおよびコピーライターです。提供された情報、またはレビューエージェントやユーザーからのフィードバックを基に、メディアの目を引く魅力的なプレスリリースを作成・修正してください。タイトル、リード文、本文、会社概要の標準的な構成を遵守してください。""",
)

# 品質レビューエージェント (Sub-Agent 2)
reviewer_agent = Agent(
    name="reviewer_agent",
    model=model,
    instruction="""あなたは厳格な校正者およびPRコンコンサルタントです。提出されたプレスリリースのドラフトを、以下の観点からレビューしてください：誤字脱字、トーン＆マナーの適切さ、誇大表現の有無、情報の網羅性。
修正が必要な場合は具体的な改善案を返し、問題がない場合は「合格」と明記して出力を完了してください。""",
)


# --- ワークフローノード定義 ---

@node(rerun_on_resume=True)
async def start_node(ctx: Context, node_input: Any):
    query_str = ""
    if isinstance(node_input, str):
        query_str = node_input
    elif hasattr(node_input, "parts"):
        query_str = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, dict):
        query_str = node_input.get("raw_input", "") or node_input.get("input", "") or str(node_input)
    else:
        query_str = str(node_input)

    # 状態の初期化・リセット
    ctx.state["raw_input"] = query_str
    ctx.state["current_draft"] = ""
    ctx.state["review_feedback"] = ""
    ctx.state["human_feedback"] = ""
    ctx.state["loop_count"] = 0
    ctx.state["is_approved"] = False
    
    print(f"\n🚀 インプットを受信しました: {query_str}\n")


@node(rerun_on_resume=True)
async def writer_node(ctx: Context):
    raw_input = ctx.state.get("raw_input", "")
    current_draft = ctx.state.get("current_draft", "")
    review_feedback = ctx.state.get("review_feedback", "")
    human_feedback = ctx.state.get("human_feedback", "")
    loop_count = ctx.state.get("loop_count", 0)

    print(f"✍️ プレスリリース作成エージェントがドラフトを生成中... (ループ {loop_count + 1})")

    # フィードバックや既存のドラフトがあるかどうかに応じてプロンプトを構築
    prompt_str = f"【プレスリリースの元情報】\n{raw_input}\n\n"
    
    if current_draft:
        prompt_str += f"【修正前のドラフト】\n{current_draft}\n\n"
        
    if human_feedback:
        prompt_str += f"【ユーザー（人間）からの修正指示・フィードバック】\n{human_feedback}\n\n"
        
    if review_feedback:
        prompt_str += f"【品質レビューエージェントからの修正指摘】\n{review_feedback}\n\n"
        
    if current_draft:
        prompt_str += "上記の修正前のドラフトに対して、提供されたすべてのフィードバック（人間または品質レビューエージェントからの指摘事項）を真摯に受け止め、該当箇所を大幅に改善・修正した新しいドラフトを出力してください。修正箇所の説明は不要です。プレスリリース本文のみを出力してください。"
    else:
        prompt_str += "上記の元情報を基に、ゼロから魅力的なプレスリリース（タイトル、リード文、本文、会社概要の標準的な構成を遵守したもの）を作成してください。"

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
    print(f"🔍 品質レビューエージェントがドラフトを検証中...")

    prompt_str = f"【レビュー対象のプレスリリース】\n{current_draft}"

    res = await ctx.run_node(reviewer_agent, prompt_str)

    review_text = ""
    if isinstance(res, str):
        review_text = res
    elif hasattr(res, "parts"):
        review_text = "".join(part.text for part in res.parts if part.text)
    elif isinstance(res, dict) and "text" in res:
        review_text = res["text"]
    else:
        review_text = str(res)

    ctx.state["review_feedback"] = review_text
    
    # ループカウントをインクリメント
    ctx.state["loop_count"] = ctx.state.get("loop_count", 0) + 1
    loop_count = ctx.state["loop_count"]

    print(f"📊 ループ {loop_count} 完了。")
    print(f"💡 レビュー結果:\n{review_text}\n")


@node
async def router_node(ctx: Context):
    review_feedback = ctx.state.get("review_feedback", "")
    loop_count = ctx.state.get("loop_count", 0)

    # 「合格」という文言が含まれているか、または最大ループ上限（3回）に達したかをチェック
    if "合格" in review_feedback:
        print("✅ 品質レビューに合格しました。人間による承認フェーズに進みます。")
        return Event(route="human_check")
    elif loop_count >= 3:
        print("⚠️ 自動生成・レビューの最大ループ数（3回）に達しました。強制的に人間による承認フェーズに進みます。")
        return Event(route="human_check")
    else:
        print(f"🔄 修正点があるため、プレスリリース作成エージェントに戻ります (現在のループ数: {loop_count}/3)...")
        return Event(route="loop")


@node(rerun_on_resume=True)
async def human_approval_node(ctx: Context):
    current_draft = ctx.state.get("current_draft", "")
    review_feedback = ctx.state.get("review_feedback", "")
    
    # ユーザーからの応答がすでに受信されているか確認
    human_response = ctx.resume_inputs.get("human_approval")
    
    if human_response is not None:
        status = ""
        feedback = ""
        
        # HumanApprovalInput スキーマにより、Pydantic モデルインスタンスまたは辞書として受信される
        if hasattr(human_response, "status"):
            status = human_response.status
            feedback = human_response.feedback
        elif isinstance(human_response, dict):
            status = human_response.get("status", "")
            feedback = human_response.get("feedback", "")
        else:
            status = str(human_response)
            
        status_clean = str(status).strip().upper()
        
        if "OK" in status_clean:
            print("👤 人間による承認: OK (承認されました)")
            ctx.state["is_approved"] = True
            return Event(route="approved")
        else:
            print(f"👤 人間による承認: NG (差し戻されました)。フィードバック: {feedback}")
            ctx.state["human_feedback"] = feedback
            # 差し戻し時はループカウントをリセットし、レビューフィードバックをクリアして再作成ループに入ります
            ctx.state["loop_count"] = 0
            ctx.state["review_feedback"] = ""
            return Event(route="rejected")

    # ユーザー応答がまだ存在しない場合、入力を要求（HITL 割り込み）
    message = (
        f"【プレスリリース最終確認 (Human-In-The-Loop)】\n"
        f"作成されたプレスリリース案と、品質レビューエージェントからのフィードバックを提示します。\n\n"
        f"--- 作成されたプレスリリース ---\n"
        f"{current_draft}\n\n"
        f"--- 品質レビュー結果 ---\n"
        f"{review_feedback}\n\n"
        f"上記の内容で確定してよろしいですか？\n"
        f"承認する場合は status に 'OK' を、差し戻して再作成させる場合は 'NG' と具体的なフィードバック（feedback）を入力してください。"
    )
    
    return RequestInput(
        interrupt_id="human_approval",
        message=message,
        response_schema=HumanApprovalInput
    )


@node
async def end_node(ctx: Context):
    current_draft = ctx.state.get("current_draft", "")
    
    print("\n✨ プロセスが正常に完了し、人間による最終承認が得られました！")
    
    output_text = f"""# 【最終確定】プレスリリース公開稿

{current_draft}

---
*人間による最終承認が完了しました。公開確定として処理を終了します。*
"""
    return Event(output=output_text)


# --- ワークフロー構成定義 ---

press_release_workflow = Workflow(
    name="press_release_workflow",
    state_schema=PressReleaseState,
    edges=[
        (START, start_node),
        (start_node, writer_node),
        (writer_node, reviewer_node),
        (reviewer_node, router_node),
        (
            router_node,
            {
                "loop": writer_node,
                "human_check": human_approval_node,
            },
        ),
        (
            human_approval_node,
            {
                "approved": end_node,
                "rejected": writer_node,
            }
        )
    ],
)

# アプリケーションコンテナの定義
app = App(
    root_agent=press_release_workflow,
    name="app",
)
