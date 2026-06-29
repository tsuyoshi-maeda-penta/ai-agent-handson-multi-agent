# AI Agent Design Specification: New Product Idea Generator & Evaluator

## 1. 概要 (Overview)
本ドキュメントは、Antigravity CLI を用いて開発する ADK 2.0 AI Agent のデザイン仕様書である。
本エージェントは、指定されたテーマに基づき **「市場調査」** と **「新商品アイデア提案」** を行い、
そのアイデアが定義された採用基準を満たしているかを **「評価（採点）」** する。
基準に達していない場合は、フィードバックを基に市場調査とアイデア提案を再実行する **「ループパターン」** を採用する。

## 2. システムアーキテクチャ (Architecture)
* **パターン名**: ループパターン (市場調査・提案 ⇄ 評価)
* **構造**: 市場のニーズを捉え、採用基準（スコア 80点以上）を満たす高品質な新商品アイデアを自動生成する。

エージェントは以下の3つの主要コンポーネント（タスク）と、1つの条件分岐（ループ制御）で構成される。

1.  **[Task 1: Market Research]** 指定されたテーマに関する市場トレンド、競合、ユーザーニーズを調査する。
2.  **[Task 2: Idea Generation]** 調査結果を基に、具体的な新商品のコンセプト、ターゲット、独自の強み（USP）を提案する。
3.  **[Task 3: Idea Evaluation]** 提案されたアイデアを独自の評価基準で採点する。
4.  **[Conditional Branch: Loop Check]** 
      * **スコア 80 点以上:** ワークフローを終了し、最終成果物を出力。
      * **スコア 80 点未満:** 不合格理由と改善点をフィードバックとして保持し、**Task 1 へループ** する（最大ループ回数: 3回）。

## 3. 技術仕様
* プログラミング言語は Python で実装します。
* Agent Development Kit (ADK) のバージョンは　2.x を使用する。ADK 1.x 系は互換性がないため使用しません。

### ADK のバージョンの指定方法
作成する Python プロジェクトの `pyproject.toml` には、ADK は次のバージョン指定を行います。

```
"google-adk[gcp]>=2.0.0,<3.0.0"
```

## 4. エージェント定義 (Agent Definitions)

### 4.1. Task 1: Market Research (市場調査)
* **Input:** 
    * `theme` (String): 新商品の大まかなテーマ（例：「20代向け防災グッズ」）
    * `feedback` (String, Optional): 前回の評価で不合格だった場合の改善フィードバック
* **Prompt Template:**
    ```text
    あなたは優秀な市場リサーチャーです。
    以下のテーマについて、現在の市場トレンド、ターゲット層の潜在ニーズ、および主要な競合の状況を分析してください。
    
    テーマ: {{theme}}
    
    ${if(feedback)}
    前回の提案は基準に達しませんでした。以下のフィードバック（改善点）を強く意識して、異なる角度から調査を再実行してください。
    フィードバック: {{feedback}}
    ${endif}
    
    出力は、次の項目を含めてください：
    - 市場の現状とトレンド
    - 見落とされがちなユーザーの不満・ニーズ
    - 競合が未参入のポジショニング
    ```
* **Output:** `research_report` (String)

### 4.2. Task 2: Idea Generation (新商品アイデア提案)
* **Input:** `research_report` (String)
* **Prompt Template:**
    ```text
    あなたは革新的な商品企画者です。
    以下の市場調査レポートを基に、市場の課題を解決する新商品のアイデアを1つ提案してください。
    
    市場調査レポート:
    {{research_report}}
    
    以下のフォーマットで出力してください：
    【商品名】
    【コンセプト】
    【ターゲット層】
    【独自の強み (USP)】
    【想定される利用シーン】
    ```
* **Output:** `product_idea` (String)

### 4.3. Task 3: Idea Evaluation (アイデア評価)
* **Input:** `product_idea` (String)
* **Prompt Template:**
    ```text
    あなたは厳格な投資家および商品開発責任者です。
    提案された新商品アイデアを、以下の4つの基準（各25点満点、計100点満点）で厳しく採点してください。
    
    1. 新規性 (Novelty): 既存商品にない新しさがあるか
    2. 市場性 (Marketability): ターゲット層に確実に刺さるか、売れる見込みがあるか
    3. 実現可能性 (Feasibility): 技術的・コスト的に現実的か
    4. 収益性 (Profitability): 継続的なビジネスとして成立するか
    
    提案されたアイデア:
    {{product_idea}}
    
    出力は必ず以下のJSONフォーマットのみにしてください（他の説明テキストは一切不要です）。
    
    {
      "score": 0, // 4項目の合計点 (0〜100)
      "breakdown": {
        "novelty": 0,
        "marketability": 0,
        "feasibility": 0,
        "profitability": 0
      },
      "feedback": "合格基準に達するための具体的な改善点、または評価の理由を記述"
    }
    ```
* **Output:** `evaluation_result` (JSON Object)