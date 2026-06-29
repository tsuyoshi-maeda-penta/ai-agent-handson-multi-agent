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

# =====================================================================
# 1. 専門実行層 (Specialist Agents)
# =====================================================================

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# 企業情報調査エージェント (Company Profile Agent)
company_profile_agent = Agent(
    model=model,
    name='CompanyProfileAgent',
    description='企業の概要、主要事業、沿革などの基本データを調査する専門エージェント。',
    instruction="""あなたは企業の基礎情報を調査する専門エージェントです。
指定された企業について、以下の情報を正確に調査し、レポーティングしてください。
- 正式社名、本社所在地、設立年、代表者
- 主な事業セグメントとそれぞれの概要
- 従業員数、展開している主な国・地域
客観的な事実のみを記載し、推測や主観的な意見は含めないでください。""",
)

# 企業ニュース調査エージェント (Company News Agent)
company_news_agent = Agent(
    model=model,
    name='CompanyNewsAgent',
    description='対象企業に関する直近のニュース、トピックス、社会的評価の調査を行う専門エージェント。',
    instruction="""あなたは企業の最新動向およびニュースを追跡する専門エージェントです。
指定された企業に関する直近（特に過去1年間）の主要なニュース、新規製品/サービスの発表、業務提携、不祥事や法的リスク、M&Aなどの情報を収集してください。
タイムライン形式、または重要度順に整理し、情報のソースが信頼できるものであることを意識してまとめてください。""",
)

# ビジネス分析エージェント (Business Analysis Agent)
business_analysis_agent = Agent(
    model=model,
    name='BusinessAnalysisAgent',
    description='競争優位性、市場環境、ビジネスモデルの強み・弱みの定性分析を担当する専門エージェント。',
    instruction="""あなたは企業のビジネス戦略と市場環境を分析する専門エージェントです。
指定された企業について、以下の視点から定性分析を行ってください。
- 主な収益源（マネタイズモデル）
- 競合他社と比較した際の強み（コアコンピタンス、参入障壁）
- 対象企業が属する業界の市場トレンドおよびPEST（政治・経済・社会・技術）要因の影響
- 3C分析（Company, Competitor, Customer）の視点を取り入れた考察""",
)

# 財務調査エージェント (Financial Analysis Agent)
financial_analysis_agent = Agent(
    model=model,
    name='FinancialAnalysisAgent',
    description='決算書に基づく収益性、安全性、成長性、キャッシュフロー構造の定量分析を担当する専門エージェント。',
    instruction="""あなたは企業の財務状況を評価する財務分析の専門エージェントです。
指定された企業の直近の決算データ（公開されている有価証券報告書や決算短信など）を基に、以下の指標と推移を分析してください。
- 収益性指標（売上高営業利益率、ROE、ROA）
- 安全性指標（自己資本比率、流動比率、ネットキャッシュ状態）
- 成長性指標（売上高成長率、営業利益成長率）
- キャッシュフローの構造（営業CF、投資CF、財務CFのバランス）
数値的なファクトに基づき、企業の財務的な健康状態や懸念点を明確に指摘してください。""",
)


# =====================================================================
# 2. 中間コーディネーター層 (Coordinator Agents)
# =====================================================================

# 調査コーディネーター (Research Coordinator)
research_coordinator = Agent(
    model=model,
    name='ResearchCoordinator',
    description='企業情報およびニュースに関する下位の専門調査エージェントの管理・統合を担当する中間コーディネーター。',
    instruction="""あなたは調査領域の中間コーディネーターです。ルートエージェントから指示された企業について、ファクトベースの情報を集める責務を持ちます。
1. 企業情報調査エージェント(CompanyProfileAgent)に、企業の概要、主要事業、沿革などの基本データの調査を指示する。
2. 企業ニュース調査エージェント(CompanyNewsAgent)に、直近1年間の主要なニュース、プレスリリース、評判の調査を指示する。
3. 各エージェントから得られた結果を整理・構造化し、重複を排除した「一次調査報告書」としてまとめてルートエージェントに返却してください。""",
    sub_agents=[company_profile_agent, company_news_agent],
)

# 分析コーディネーター (Analysis Coordinator)
analysis_coordinator = Agent(
    model=model,
    name='AnalysisCoordinator',
    description='ビジネスおよび財務に関する下位の専門分析エージェントの管理・統合を担当する中間コーディネーター。',
    instruction="""あなたは分析領域の中間コーディネーターです。ルートエージェントから指示された企業について、定量・定性の両面から深いインサイトを導き出す責務を持ちます。
1. ビジネス分析エージェント(BusinessAnalysisAgent)に、競争優位性、市場環境、ビジネスモデルの強み・弱みの分析を指示する。
2. 財務調査エージェント(FinancialAnalysisAgent)に、決算書に基づく収益性、安全性、成長性の分析を指示する。
3. 両専門エージェントの分析結果をクロス分析し、事業戦略と財務状態の連動性に焦点を当てた「専門分析報告書」としてまとめてルートエージェントに返却してください。""",
    sub_agents=[business_analysis_agent, financial_analysis_agent],
)


# =====================================================================
# 3. ルートエージェント (Root Agent)
# =====================================================================

# 総合企業分析コーディネーター (Corporate Analysis Coordinator)
root_agent = Agent(
    model=model,
    name='CorporateAnalysisCoordinator',
    description='総合企業分析コーディネーター。ユーザーからのリクエストを受け付け、下位コーディネーターへのタスク割り当て、最終レポートの統合を行います。',
    instruction="""あなたは高度な企業分析エージェントシステムのルートエージェント（総合コーディネーター）です。
ユーザーから提示された企業について、深遠な分析を行うために以下のステップを実行してください。
1. 調査コーディネーター(ResearchCoordinator)に、企業の基礎情報および最新ニュースの収集・要約を依頼する。
2. 分析コーディネーター(AnalysisCoordinator)に、ビジネスモデルおよび財務状況の分析を依頼する。
3. 両コーディネーターから上がってきた報告書を統合し、投資家や経営層が意思決定に使用できるレベルの「最終企業分析レポート」を作成してください。レポートには必ず、エグゼクティブサマリー、市場での位置づけ、財務健全性、今後のリスクと機会を含めること。""",
    sub_agents=[research_coordinator, analysis_coordinator],
)

app = App(
    root_agent=root_agent,
    name="p07_hierarchical_task_decomposition",
)
