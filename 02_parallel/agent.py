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
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.adk.workflow import Workflow, JoinNode, START
from google.genai import types

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

# Agent A (国内メディア担当)
agent_a = Agent(
    name="agent_a",
    model=model,
    instruction="""あなたは国内メディア（大手新聞社、テレビ局など）の報道内容を調査する専門エージェントです。
指定されたテーマについて、日本のマスメディアがどのような文脈で報じているか、何が注目されているかを客観的に抽出・分析してください。""",
    tools=[google_search],
)

# Agent B (海外メディア担当)
agent_b = Agent(
    name="agent_b",
    model=model,
    instruction="""あなたは海外メディア（ロイター、BBC、CNNなど）の報道内容を調査する専門エージェントです。
指定されたテーマについて、国際社会や主要な海外メディアがどのような視点から報じているか、日本国内の論調との違いを含めて抽出・分析してください。""",
    tools=[google_search],
)

# Agent C (SNS・世論担当)
agent_c = Agent(
    name="agent_c",
    model=model,
    instruction="""あなたはSNS（Xなど）のリアルタイムなトレンドや世論を調査する専門エージェントです。
指定されたテーマについて、一般ユーザーの間でどのようなワードがバズっているか、どのような感情（ポジティブ・ネガティブ等）や意見が多く見られるかをリアルタイムな視点で抽出・分析してください。""",
    tools=[google_search],
)

# Join Node to synchronize and merge parallel research results
join_node = JoinNode(name="join_node")

# Coordinator Agent (オーケストレーター)
coordinator_agent = Agent(
    name="coordinator_agent",
    model=model,
    instruction="""ユーザーから与えられた調査テーマについて、Agent A、Agent B、Agent Cに対して同時に調査タスクを割り振ってください。
すべてのエージェントから調査結果が返ってきたら、それぞれの視点（国内、海外、SNS）の差異や共通点を分析し、多角的な視点を含んだ構造的なトレンドレポートを作成してください。

最終レポートは必ず以下の構成で出力してください：
- **総合サマリー** (全体の要約)
- **国内メディアの視点** (Agent A の結果ベース)
- **海外メディアの視点** (Agent B の結果ベース)
- **SNS・世論の動向** (Agent C の結果ベース)
- **考察・比較分析** (メディア間でのギャップや特徴のまとめ)""",
)

# Workflow Definition using Parallel Orchestration Pattern (Parallel Pattern)
root_agent = Workflow(
    name="root_agent",
    edges=[
        (START, (agent_a, agent_b, agent_c)),
        (agent_a, join_node),
        (agent_b, join_node),
        (agent_c, join_node),
        (join_node, coordinator_agent),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
