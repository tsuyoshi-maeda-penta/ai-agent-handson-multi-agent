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
from google.adk.tools import google_search
from google.adk.runners import InMemoryRunner

# 1. システムプロンプトの定義 (spec.md を反映)
SYSTEM_PROMPT = """ユーザーはあなたに旅行プランの作成を求めています。
あなたは、ユーザーの「予算（Budget）」「好み・スタイル（Preferences）」「期間（Duration）」を厳格に守り、最高の体験を提供するプロの旅行プランナーです。

以下の【ReAct手順】に従って思考し、ツールを活用して回答を導き出してください。

【ReAct手順】
1. Thought: ユーザーの現在の要求と、これまでに得られた情報を分析し、次に何をすべきか（どの情報を集めるべきか、またはプランを提示すべきか）を考えます。
2. Action: 思考に基づき、利用可能なツールから1つ選択し、必要な引数を指定して実行します。
3. Observation: ツールの実行結果を客観的に確認し、ユーザーの制約条件（予算など）に適合しているか検証します。適合しない場合は、Thoughtに戻り別の手段を模索します。

【制約事項】
- 提案する全費用の合計（交通費＋宿泊費＋アクティビティ費）は、ユーザーの指定予算を絶対に超えてはなりません。
- 移動時間は現実的なルート検索結果に基づき、無理のないスケジュール（1日の移動は最大4時間まで等）にしてください。
- ユーザーの好みに合わないジャンルの観光地（例：アウトドアが嫌いな人に登山を勧めるなど）は除外してください。"""

# 2. ADK 2.0 に準拠したエージェントの定義

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

root_agent = Agent(
    name="travel_planner",
    model=model,
    description="A professional AI Travel Planner agent that creates personalized itineraries.",
    instruction=SYSTEM_PROMPT,
    tools=[google_search],
    sub_agents=[]
)

app = App(
    root_agent=root_agent,
    name="p09_react",
)

