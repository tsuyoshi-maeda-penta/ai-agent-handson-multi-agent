from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.context import Context
from google.adk.workflow import Workflow, START
from pydantic import BaseModel, Field
from google.adk.apps import App
import uuid

# ==========================================
# 1. 共有ステートの定義 (Shared State)
# ==========================================
class RefundSystemState(BaseModel):
    user_id: str = Field(default="", description="購入者のユーザーID")
    order_id: str = Field(default="", description="対象注文ID")
    reason: str = Field(default="", description="返金リクエストの理由")
    
    buyer_verified: bool | None = Field(default=None, description="購入者検証が成功したかどうか")
    buyer_verification_reason: str = Field(default="", description="購入者検証の理由や詳細")
    
    refund_eligible: bool | None = Field(default=None, description="返金適格性チェックが成功したかどうか")
    refund_eligibility_reason: str = Field(default="", description="返金適格性検証の理由や詳細")
    
    refund_status: str = Field(default="", description="返金ステータス ('VALID' or 'INVALID')")
    
    refund_success: bool | None = Field(default=None, description="返金処理が成功したかどうか")
    transaction_id: str = Field(default="", description="返金トランザクションID")
    refund_amount: int = Field(default=0, description="返金された金額")
    
    credit_grantable: bool | None = Field(default=None, description="クレジット付与可能かどうか")
    credit_granted_amount: int = Field(default=0, description="付与されたクレジット額")
    credit_status: str = Field(default="", description="クレジット付与処理のステータス")
    
    final_response: str = Field(default="", description="ユーザー向けの最終案内テキスト")

# ==========================================
# 2. 各種ツールの定義 (Tools / Functions)
# ==========================================

def initialize_refund_request(ctx: Context, user_id: str, order_id: str, reason: str) -> str:
    """返金リクエストの基本情報（ユーザーID、注文ID、理由）をステートに記録します。"""
    ctx.state['user_id'] = user_id
    ctx.state['order_id'] = order_id
    ctx.state['reason'] = reason
    return f"リクエスト情報を初期化しました: user_id={user_id}, order_id={order_id}, reason={reason}"

def set_buyer_verification_result(ctx: Context, verified: bool, reason: str) -> str:
    """購入者チェックの結果（検証成否、理由）をステートに記録します。"""
    ctx.state['buyer_verified'] = verified
    ctx.state['buyer_verification_reason'] = reason
    return f"購入者チェック結果を記録しました: verified={verified}, reason={reason}"

def set_refund_eligibility_result(ctx: Context, eligible: bool, reason: str) -> str:
    """返金適格性チェックの結果（適格成否、理由）をステートに記録します。"""
    ctx.state['refund_eligible'] = eligible
    ctx.state['refund_eligibility_reason'] = reason
    return f"返金適格性チェック結果を記録しました: eligible={eligible}, reason={reason}"

def determine_overall_refund_validity(ctx: Context) -> str:
    """購入者チェックと返金適格性チェックの結果を統合し、返金ステータス（VALID/INVALID）を設定します。
    また、ワークフローの条件分岐先を決定するため、ctx.route にステータスをセットします。"""
    verified = ctx.state.get('buyer_verified')
    eligible = ctx.state.get('refund_eligible')
    
    if verified and eligible:
        ctx.state['refund_status'] = "VALID"
        ctx.route = "VALID"
        return "VALID"
    else:
        ctx.state['refund_status'] = "INVALID"
        ctx.route = "INVALID"
        return "INVALID"

def execute_refund_transaction(ctx: Context, amount: int) -> str:
    """決済システムと連携して実際の返金処理を実行し、結果を記録します。"""
    transaction_id = f"tx_{uuid.uuid4().hex[:12]}"
    ctx.state['refund_success'] = True
    ctx.state['transaction_id'] = transaction_id
    ctx.state['refund_amount'] = amount
    return f"決済システムとの連携に成功しました。返金額: {amount}円, トランザクションID: {transaction_id}"

def check_and_set_credit_limit(ctx: Context, eligible: bool) -> str:
    """対象ユーザーがクレジット付与可能なアカウント状態か確認し、記録します。"""
    ctx.state['credit_grantable'] = eligible
    return f"クレジット付与可否状態を記録しました: grantable={eligible}"

def grant_store_credit(ctx: Context, amount: int) -> str:
    """最適なクレジット額を決定し、付与を確定して記録します。"""
    if ctx.state.get('credit_grantable'):
        ctx.state['credit_granted_amount'] = amount
        ctx.state['credit_status'] = "SUCCESS"
        return f"ストアクレジット {amount}円 を付与しました。"
    else:
        ctx.state['credit_status'] = "FAILED_NOT_GRANTABLE"
        return "ユーザーがクレジット付与可能な状態ではないため、付与できませんでした。"

def record_final_response(ctx: Context, response: str) -> str:
    """ユーザーへの最終案内テキストをステートに記録します。"""
    ctx.state['final_response'] = response
    return "最終回答を記録しました。"


# ==========================================
# 3. サブエージェントの定義 (Sub-Agents)
# ==========================================

# --- 3.1. 初期化エージェント ---
request_initializer_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='request_initializer_agent',
    description='返金リクエストを受け取り、ユーザーID、注文ID、理由を抽出して記録します。',
    instruction='''お客様のメッセージから、ユーザーID (user_id)、注文ID (order_id)、および返金理由 (reason) を抽出してください。
抽出した情報を initialize_refund_request ツールを呼び出して共有ステートに記録してください。
もし情報が不足している場合は、お客様に尋ねて情報を取得してから記録してください。''',
    tools=[initialize_refund_request],
    state_schema=RefundSystemState,
)

# --- 3.2. 返金有効チェックエージェント (Refund Validity Check) ---
# 4.2.1 購入者チェックエージェント
buyer_verification_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='buyer_verification_agent',
    description='購入者が返金対応を受ける権利を保持しているか検証します。',
    instruction='''共有ステートの user_id と order_id を参照し、購入者が返金対応を受ける権利（会員ランク、過去の不正履歴、購入からの経過日数など）を保持しているか検証してください。
検証後、検証結果（True/False）と理由を set_buyer_verification_result ツールを使用して共有ステートに記録してください。''',
    tools=[set_buyer_verification_result],
    state_schema=RefundSystemState,
)

# 4.2.2 返金適格性チェックエージェント
eligibility_check_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='eligibility_check_agent',
    description='申請された事象が返金ポリシーの対象に該当するか検証します。',
    instruction='''共有ステートの reason を参照し、申請された事象が返品・返金ポリシーの対象に該当するか適格性を検証してください。
検証後、検証結果（True/False）と理由を set_refund_eligibility_result ツールを使用して共有ステートに記録してください。''',
    tools=[set_refund_eligibility_result],
    state_schema=RefundSystemState,
)

# 並列チェックエージェント (ParallelAgent)
refund_validity_parallel = ParallelAgent(
    name='refund_validity_parallel',
    description='購入者チェックと返金適格性チェックを並列に実行します。',
    sub_agents=[buyer_verification_agent, eligibility_check_agent],
    state_schema=RefundSystemState,
)


# --- 3.3. 返金処理エージェント (Refund Execution) ---
refund_execution_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='refund_execution_agent',
    description='実際の返金処理（決済トランザクションの取り消し等）を実行します。',
    instruction='''共有ステートの order_id を確認し、execute_refund_transaction ツールを呼び出して、実際の返金処理（トランザクションの取り消しなど）を実行してください。
完了後、返金完了ステータスを報告してください。''',
    tools=[execute_refund_transaction],
    state_schema=RefundSystemState,
)


# --- 3.4. クレジット付与エージェント (Credit Granting) ---
# 4.4.1 クレジット管理エージェント
credit_management_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='credit_management_agent',
    description='対象ユーザーがクレジット付与可能な状態か確認します。',
    instruction='''対象のユーザーがクレジット付与可能な状態か（上限に達していないか、アカウントが有効かなど）確認し、
check_and_set_credit_limit ツールを使用して結果を記録してください。''',
    tools=[check_and_set_credit_limit],
    state_schema=RefundSystemState,
)

# 4.4.2 クレジット付与決定エージェント
credit_determination_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='credit_determination_agent',
    description='最適なクレジット額を決定し、付与を実行します。',
    instruction='''ユーザーの状況や不便の度合いに応じて、付与すべき最適なクレジット額（補填額）を算出し、
grant_store_credit ツールを呼び出して付与を実行してください。''',
    tools=[grant_store_credit],
    state_schema=RefundSystemState,
)

# シーケンシャル・オーケストレーター (SequentialAgent)
credit_granting_agent = SequentialAgent(
    name='credit_granting_agent',
    description='代替案としてストアクレジットの付与プロセスを逐次実行します。',
    sub_agents=[credit_management_agent, credit_determination_agent],
    state_schema=RefundSystemState,
)


# --- 3.5. 返答エージェント (Response Generation) ---
response_generation_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='response_generation_agent',
    description='各プロセスの実行結果を統合し、親切で明確な最終案内文を生成します。',
    instruction='''共有ステートから、これまでの処理結果（返金成功、またはクレジット付与結果など）をすべて読み取ってください。
購入者に対して親切かつ明確で、心のこもった最終的な案内文（チャットテキスト）を日本語で生成し、
record_final_response ツールを呼び出してステートに記録してください。
その後、そのメッセージをそのまま出力してください。''',
    tools=[record_final_response],
    state_schema=RefundSystemState,
)


# ==========================================
# 4. ワークフロー構築 / ルートエージェント (Root Agent)
# ==========================================
root_agent = Workflow(
    name='refund_handling_workflow',
    description='返金対応 AI エージェントシステム。ポリシーの検証、代替案提示、最終回答の生成までを自動化します。',
    edges=[
        # 1. リクエスト情報の初期化
        (START, request_initializer_agent),
        
        # 2. 並列チェックの開始
        (request_initializer_agent, refund_validity_parallel),
        
        # 3. 並列チェック完了後、統合判定を実行
        (refund_validity_parallel, determine_overall_refund_validity),
        
        # 4. 判定結果（VALID / INVALID）に基づく条件分岐
        (determine_overall_refund_validity, {
            "VALID": refund_execution_agent,
            "INVALID": credit_granting_agent
        }),
        
        # 5. 各分岐の処理が終わったら、最終的な返答生成へ
        (refund_execution_agent, response_generation_agent),
        (credit_granting_agent, response_generation_agent)
    ],
    state_schema=RefundSystemState,
)

app = App(
    root_agent=root_agent,
    name="app",
)