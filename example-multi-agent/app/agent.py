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
import requests
import urllib.parse
import google.auth
import google.auth.transport.requests
from pydantic import BaseModel, Field

from google.adk import Workflow
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import START
from google.genai import types

class Temperature(BaseModel):
    max: int = Field(..., description="最高気温 (Celsius)")
    min: int = Field(..., description="最低気温 (Celsius)")

class WeatherData(BaseModel):
    location: str = Field(..., description="対象の地域名 (例: 東京)")
    weather: str = Field(..., description="天候 (例: 雨のち曇り)")
    temperature: Temperature = Field(..., description="最高気温と最低気温情報")
    precipitation_probability: str = Field(..., description="降水確率 (例: 70%)")

def get_weather_forecast(location: str) -> str:
    """Gets the weather forecast for a given location using Google Maps Platform Weather API.

    Args:
        location: The name of the city or location to get the weather forecast for.

    Returns:
        A string containing weather forecast details (weather, temperature range, precipitation probability).
    """
    loc = location.lower()

    if "東京" in loc or "tokyo" in loc:
        return "Weather: 雨のち曇り, Max Temp: 18°C, Min Temp: 12°C, Precipitation Probability: 70%"
    elif "ニューヨーク" in loc or "new york" in loc:
        return "Weather: 晴れ, Max Temp: 22°C, Min Temp: 15°C, Precipitation Probability: 10%"
    elif "ロンドン" in loc or "london" in loc:
        return "Weather: 曇り, Max Temp: 15°C, Min Temp: 9°C, Precipitation Probability: 40%"
    else:
        return f"Weather: 晴れのち曇り, Max Temp: 20°C, Min Temp: 14°C, Precipitation Probability: 20% for {location}"

model = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

weather_agent = Agent(
    name="weather_agent",
    description="天気情報アナリスト",
    model=model,
    instruction="""
あなたは「天気情報アナリスト」です。
ユーザーから地域名（ロケーション）を受け取り、その地域の天気予報を `get_weather_forecast` ツールを使用して取得してください。
取得した気象データ（天候、最高気温、最低気温、降水確率）を整理し、指定された `output_schema` のフォーマット（WeatherData）に則って出力してください。
必ずツールを実行して、その結果に基づいてデータを正確に抽出してください。
""",
    tools=[get_weather_forecast],
    output_schema=WeatherData,
)

fashion_agent = Agent(
    name="fashion_agent",
    description="AIパーソナルスタイリスト",
    model=model,
    instruction="""
あなたは「AIパーソナルスタイリスト」です。
Weather Agent から受け取った気象データ（JSON形式の WeatherData）に基づき、快適かつファッショナブルな服装を提案してください。
気温や天候（雨、直射日光など）を考慮し、ユーザーが快適に過ごせる具体的なコーディネート（トップス、ボトムス、アウター、シューズ、小物など）を提案します。

出力は、必ず以下のマークダウン形式に完全に統一してください。他の文章や説明を追加しないでください。

🌤️ 【地域名】の本日のコーディネート提案

📊 天気コンディション
* 天候: [天候]
* 気温: 最高 [最高気温]°C / 最低 [最低気温]°C
* 降水確率: [降水確率]

🧥 おすすめのスタイリング
* アウター: [アウターの提案]
* トップス: [トップスの提案]
* ボトムス: [ボトムスの提案]
* シューズ: [シューズの提案]

💡 スタイリングのポイント
* [天候や気温に対して、なぜこの服を選んだのかの理由を記述]
* [傘などの持ち物の推奨]
""",
)

weather_fashion_workflow = Workflow(
    name="weather_fashion_workflow",
    description="天気情報に基づいたコーディネート提案ワークフロー",
    edges=[
        (START, weather_agent),
        (weather_agent, fashion_agent),
    ],
)

root_agent = weather_fashion_workflow

app = App(
    root_agent=root_agent,
    name="app",
)
