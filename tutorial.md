# Agent Development Kit (ADK) で作るさまざまな AI エージェントデザインパターン

### 所要時間

<walkthrough-tutorial-duration duration="90"></walkthrough-tutorial-duration>

## はじめに

このハンズオンでは、Agents CLI と Antigravity CLI を使い、さまざまな AI エージェントのデザインパターンを、実際に Agent Development Kit (ADK) 2.0 を使って構築しながら学びます。

### 目標

このハンズオンを通して、次のような事項を学習できます。

- ADK 2.0 の使い方
- Agents CLI の使い方
- Antigravity CLI の使い方
- さまざまな AI エージェントデザインパターンを構築しながら理解する

## Google Cloud Project のセットアップ

まずはじめに、コマンドで使用する Google Cloud Project の指定や使用するサービスの API の有効化を行います。

次のコマンドで、Google Cloud Project を設定します。

```sh
gcloud config set project $GOOGLE_CLOUD_PROJECT
```

次のコマンドで、使用するサービスの API の有効化を行います。

```sh
gcloud services enable aiplatform.googleapis.com
```

## Antigravity CLI のインストール

AI エージェントのプロジェクトは Antigravity CLI を使って行うため、以下のコマンドでインストールします。

Antigravity CLI を使うことで、ターミナルからビルド、デバッグ、デプロイが可能です。タスクを自然言語で記述するだけで、あとは Antigravity がすべて処理します。

```sh
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

次のコマンドが実行できれば、インストールが問題なく完了しています。

```sh
agy --version
```

## Antigravity CLI のセットアップ

Antigravity CLI のセットアップを始めます。次のコマンドを実行します。

```sh
agy
```

まずログイン方法を選択します。`Use a Google Cloud project` を選択します。

```
Welcome to the Antigravity CLI. You are currently not signed in.

 Select login method:
   1. Google OAuth
 > 2. Use a Google Cloud project

 [Use arrow keys to navigate, Enter to select]
```

認証用の URL が表示される画面で、`Click here to authenticate` を `Cmd` キーを押しながらクリックします。

「Do you want Code OSS - Cloud Shell to open the external website?」が表示されたら `OK` をクリックします。クリックすると新しいタブで認証画面が表示されるので、画面の手順に従って認証を進めます。

最後に認証コードが表示されるのでコピーします。

元のタブに戻り、Antigravity CLI の入力欄にペーストします。

```
After authenticating, copy the code displayed in the browser and paste it below:

 authorization code...
```

次に Google Cloud Project ID が求められるので <walkthrough-project-id/> を入力します。

```
 Enter Google Cloud Project ID:
 project id...
```

次にロケーションの選択が求められるので、デフォルトのまま `global` を選択します。

```
Select Google Cloud Location:
 > global
   us
   eu
```

次にカラースキームの選択が求められるので、好きなカラースキームを選択します。

```
Choose your color scheme:
  > terminal
    light
    solarized light
    colorblind-friendly light
    dark
    solarized dark
    colorblind-friendly dark
    tokyo night
```

Gemini CLI のマイグレーション オプションが表示されますが、チェックは付けないようにします（チェックを付けてしまうと、以降の処理がうまく実行できない場合があります）。

```
Migration options:

  > [ ] Import extensions from Gemini CLI (1 found: vertex)
```

`Next` までカーソルキーで移動し、Enter を押下します。

利用規約の同意が求められるので、`Done` のまま Enter を押下します。

```
Terms and Privacy:
  - Terms of Service: https://cloud.google.com/terms
  - Privacy Notice (excluding product analytics data): https://cloud.google.com/terms/cloud-privacy-notice
```

Antigravity CLI へのディレクトリへのアクセス許可を与えます。`Yes, I trust this folder` を選択します。

```
Antigravity CLI requires permission to read, edit, and execute files here.
> Yes, I trust this folder
  No, exit
```

ハンズオンではスムーズに実装を進めるため、パーミッション設定をデフォルトの「レビューが必要な設定」から「自動許可の設定」に変更します。パーミッション設定は `/permission` スラッシュコマンドを実行します。

```
/permission
```

設定を `always-proceed` に変更します。

```
Active Permissions

  request-review Prompt for write, bash, and web tools
  proceed-in-sandbox  Auto-approve terminal commands in sandbox
> always-proceed (current)  Auto-approve all tools
  strict              Prompt for all non-read tools
```

以上で Antigravity CLI の初期設定は終了です。簡単なプロンプトを入力し、返答が返ってくることを確認しましょう。

```
今日の東京の天気は？
```

Antigravity CLI を終了します。スラッシュコマンド `/exit` で終了できます。

```
/exit
```

### 途中の選択を誤ってしまった場合

途中の選択を誤ってしまうと、Antigravity CLI がうまく動かなくなってしまう場合があります。

そのような場合は、次のコマンドを実行し、Antigravity CLI の設定情報を一度削除します。

```sh
rm -rf ~/.gemini
```

その後、再度 `agy` コマンドを実行し、Antigravity CLI の設定を最初からやり直します。

## Agents CLI のインストール

Agents CLI は Google Cloud 上で AI エージェントを構築、評価、デプロイするための CLI およびスキル パッケージです。

以下のコマンドでインストールします。

```sh
uvx google-agents-cli setup
```

インストール後、Agents CLI のパスを通すため次のコマンドを実行します。

```sh
export PATH="$HOME/.local/bin:$PATH"
```

次のコマンドが実行できれば、無事にインストールができています。

```sh
agents-cli --version
```

Antigravity CLI で Agents CLI のスキルが使えるようになっているか確認しましょう。

次のコマンドで Antigravity CLI を起動します。

```sh
agy
```

スラッシュコマンドでスキル一覧が確認できます。

```sh
/skills
```

次のように、Agents CLI のスキルが表示されれば無事インストールが成功しています。

```
Workspace skills · Workspace config
  google-agents-cli-adk-code: This skill should be used when the user wants to "write agent code", "build an agent with ADK", "add a tool", "create a callback", "define an ...
  google-agents-cli-deploy: This skill should be used when the user wants to "deploy an agent", "deploy my ADK agent", "set up CI/CD", "configure secrets", "troubleshoot a ...
  google-agents-cli-eval: This skill should be used when the user wants to "run an evaluation", "evaluate my ADK agent", "write an evalset", "debug eval scores", "compare e...
  google-agents-cli-observability: This skill should be used when the user wants to "set up tracing", "monitor my ADK agent", "configure logging", "add observability", "deb...
  google-agents-cli-publish: This skill should be used when the user wants to "publish an agent", "publish my ADK agent", "register an agent with Gemini Enterprise", "publi...
  google-agents-cli-scaffold: This skill should be used when the user wants to "create an agent project", "start a new ADK project", "build me a new agent", "add CI/CD to m...
  google-agents-cli-workflow: This skill should be used when the user wants to "develop an agent", "build an agent using ADK", "run the agent locally", "debug agent code", ...
```

Antigravity CLI を終了します。スラッシュコマンド `/exit` で終了できます。

```
/exit
```

## AI エージェントの作成と実行

このハンズオンでは、まずは Antigravity CLI と Agents CLI を使って 1 つの AI エージェントを作成します。

AI エージェントの中核を担う `agent.py` をさまざまなデザインパターンのコードに置き換え、実行することで、どのようなデザインパターンなのか学んでいきます。

まず Antigravity CLI を起動します。

```sh
agy
```

次のプロンプトを実行します。

```
agents-cli を使って `multi-agent` という名前の AI エージェントの Scaffold を作成してください。ADK のバージョンは 2.0 を指定してください。
```

数分後、作成が完了します。試しに `agents-cli playground` で実行してみましょう。

```sh
cd multi-agent
agents-cli playground
```

数秒後、下記のような結果が表示されていれば、起動できています。

```
+-----------------------------------------------------------------------------+
| ADK Web Server started                                                      |
|                                                                             |
| For local testing, access at http://127.0.0.1:8080.                         |
+-----------------------------------------------------------------------------+

INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
```

`http://127.0.0.1:8080` で立ち上がります。Web プレビューボタン <walkthrough-web-preview-icon></walkthrough-web-preview-icon> のアイコンをクリックし、メニューから「ポート 8080 でプレビュー」を選びます。

アプリケーションを検証するには `Select an App` から `app` を選択します。

チャット画面で何か入力し、正常に返答が得られることを確認しましょう。

「API キーが不足している」旨のエラーが表示される場合は、次のコマンドを実行し `.env` を作成するようにしてください。

```sh
echo "GOOGLE_GENAI_USE_VERTEXAI=True" >> .env
```

最後に、Playground を起動したターミナルで `Ctrl` + `C` を押し、Playground を終了します。

### AI エージェントがうまく作成できないときは…

AI エージェントの作成に失敗してしまい、なかなかうまく作成できないときはサンプルコードを使いましょう。

下記のディレクトリに移動します。

```sh
cd ~/ai-agent-handson-multi-agent/example/multi-agent
```

次のコマンドを実行し、依存関係を解決します。

```sh
agents-cli install
```

Playground を実行します。

```sh
agents-cli playground
```

## 各デザインパターンを試すにあたり

次のステップからは、すでに作成したマルチエージェントアプリケーションの `agent.py` を各デザインパターンのコードに書き換えながら (上書きコピー) 動作を確認していきます。

コピーコマンドを使用しますので、**ターミナルの現在のディレクトリがマルチエージェントアプリケーションのディレクトリ** であるか必ず確認してください。

進めていく中でうまく動作しない状態になってしまった場合も、現在のディレクトリの場所が合っているか確認するようにしてください。

次のコマンドで、現在のディレクトリが確認できます。

```sh
pwd
```

## 01 - シーケンシャル パターン

シーケンシャル パターンは、サブエージェントを直列で実行します。このパターンでは、1 つのエージェントの出力が次のエージェントの直接入力として使用されます。このパターンでは、サブエージェントのオーケストレーションのために AI モデルを参照することなく、事前定義されたロジックでワークフロー エージェントを使用します。

シーケンシャルパターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/01_sequential/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 02 - パラレル パターン

パラレル パターンは、サブエージェントがタスクまたはサブタスクを同時に独立して実行します。サブエージェントの出力が統合され、最終的な統合レスポンスが生成されます。シーケンシャル パターンと同様に、パラレル パターンではワークフロー エージェントを使用して、他のエージェントの実行方法と実行タイミングを管理します。

パラレル パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/02_parallel/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 03 - ループ エージェント パターン

ループ エージェント パターンは、特定の終了条件が満たされるまで、一連のサブエージェントを繰り返し実行します。このパターンでは、他のワークフロー エージェントと同様に、オーケストレーションのために AI モデルを参照することなく、事前定義されたロジックで動作するワークフロー エージェントを使用します。

ループ エージェント パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/03_loop/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 04 - レビューと批評パターン

レビューと批評パターン（ジェネレータと批評パターンとも呼ばれます）は、通常はシーケンシャル ワークフローで 2 つの専門エージェントを使用して、生成されたコンテンツの品質と信頼性を向上させます。レビューと批評パターンは、ループ エージェント パターンの実装です。

レビューと批評パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/04_review-and-critique/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 05 - 反復的な改良パターン

反復的な改善パターンでは、ループ メカニズムを使用して、複数のサイクルにわたって出力を段階的に改善します。反復的な改善パターンは、ループ エージェント パターンの実装です。

反復的な改善パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/05_iterative-refinement/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 06 - コーディネーター パターン

マルチエージェント コーディネーター パターンでは、中央エージェントであるコーディネーターを使用してワークフローを指示します。コーディネーターは、ユーザーのリクエストを分析してサブタスクに分解し、各サブタスクを実行する専門のエージェントにディスパッチします。各専門エージェントは、データベースのクエリや API の呼び出しなど、特定の機能の専門家です。

コーディネーター パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/06_coordinator/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 07 - 階層型タスク分解パターン

階層型タスク分解パターンは、エージェントをマルチレベルの階層に編成して、広範な計画を必要とする複雑な問題を解決します。階層型タスク分解パターンは、コーディネーター パターンの実装です。最上位の親エージェント（ルートエージェント）は複雑なタスクを受け取り、そのタスクを複数の小さな管理可能なサブタスクに分解します。ルート エージェントは、各サブタスクを下位レベルの専門サブエージェントに委任します。このプロセスは複数のレイヤで繰り返される可能性があります。エージェントは、割り当てられたタスクを、最下位レベルのワーカー エージェントが直接実行できるほど単純になるまで、段階的に分解します。

階層型タスク分解パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/07_hierarchical-task-decomposition/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 08 - スウォーム パターン

スウォーム パターンでは、協調的な全対全通信アプローチが使用されます。このパターンでは、複数の専門エージェントが連携して、複雑な問題に対するソリューションを反復的に改善します。

スウォーム パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/08_swarm/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 09 - ReAct パターン

ReAct パターンは、AI モデルを使用して思考プロセスとアクションを自然言語のインタラクションのシーケンスとしてフレーム化するアプローチです。このパターンでは、終了条件が満たされるまで、エージェントは思考、行動、観察の反復ループで動作します。

ReAct パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/09_react/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 10 - 人間参加型 (Human-in-the-Loop) パターン

人間参加型パターンでは、人間による介入ポイントがエージェントのワークフローに直接統合されます。事前定義されたチェックポイントで、エージェントは実行を一時停止し、外部システムを呼び出して、人間が作業をレビューするのを待ちます。このパターンを使用すると、エージェントが続行する前に、ユーザーが決定を承認したり、エラーを修正したり、必要な入力を提供したりできます。

人間参加型パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/10_human-in-the-loop/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## 11 - カスタム ロジック パターン

カスタム ロジック パターンを使用すると、ワークフロー設計の柔軟性を最大限に高めることができます。このアプローチでは、コード（条件ステートメントなど）を使用して、複数の分岐パスを持つ複雑なワークフローを作成する特定のオーケストレーション ロジックを実装できます。

カスタム ロジック パターンを試すには、サンプルコードをコピーします。

```sh
cp ~/ai-agent-handson-multi-agent/11_custom-logic/agent.py app/agent.py
```

Playground を実行します。

```sh
agents-cli playground
```

確認が終わったら `Ctrl` + `C` を押し、Playground を終了します。

## お疲れ様でした！

以上で AI エージェントのデザインパターンを学ぶハンズオンは終了です。お疲れ様でした！

<walkthrough-conclusion-trophy></walkthrough-conclusion-trophy>