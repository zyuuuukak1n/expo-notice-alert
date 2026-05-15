# 📣 Expo Notice Alert Bot

大阪・関西万博（Expo 2025）の公式サイトを定期的に監視し、新しい「お知らせ」が掲載されたら、即座に Discord の指定チャンネルへ自動通知するボットです。 
重要なアップデートやイベント情報をいち早くキャッチするために役立ちます！✨

## 🌟 主な機能

- **🌐 自動スクレイピング**: 万博公式サイトのお知らせページを定期的にチェックします。
- **🚀 Discord 連携**: 新しいお知らせが見つかると、タイトルとURLを整形して Discord に自動で送信します。
- **🛡️ 堅牢なセキュリティ設計**: 
  - 外部データの厳格なバリデーション（不正なURLや長すぎるタイトルのサニタイズ）
  - 機密情報の環境変数化（APIキーなどのハードコード排除）
  - 運用監視に最適化した安全なエラーロギング
- **⚙️ 自動リトライ機能**: Discord のレート制限 (HTTP 429 Too Many Requests) を考慮し、送信がブロックされた場合でも適切に待機・再試行を行います。

---

## 🛠️ 必須環境

- Python 3.8 以上
- 安定したインターネット接続
- 通知を受け取るための Discord Webhook URL

---

## 📦 セットアップ手順

ボットを動かすまでの準備はとても簡単です！

### 1. リポジトリのクローンと移動

```bash
git clone https://github.com/yourusername/expo-notice-alert.git
cd expo-notice-alert
```

### 2. 依存パッケージのインストール

仮想環境を作成してからインストールすることをおすすめします。

```bash
python -m venv venv
# Windowsの場合: venv\Scripts\activate
# Mac/Linuxの場合: source venv/bin/activate

pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトのルートディレクトリに `.env` という名前のファイルを作成し、以下の内容を記述します。

```env
# アプリケーションの動作環境 (development または production)
# 本番環境では詳細なスタックトレース等の出力が抑制されます。
APP_ENV=production

# 通知を送る Discord の Webhook URL (必須)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN

# 監視対象のURL（デフォルト値から変更したい場合のみ設定してください）
# NEWS_URL=https://www.expo2025.or.jp/news/category/information/
```

> **💡 ヒント:** Discord で Webhook を作成する方法は、[Discordの公式サポートページ](https://support.discord.com/hc/ja/articles/228383668) をご覧ください。

---

## ▶️ 使い方

準備ができたら、以下のコマンドでボットを実行します。

```bash
python expo-notice-alert.py
```

初回実行時は現在の最新記事を「既読」として記録するだけで、通知は行いません。2回目以降の実行時に、前回から新しく追加された記事がある場合のみ Discord へ通知されます。

### 🕒 定期実行について

このボットは1回実行すると処理を終了します。継続的に監視するためには、OSの機能を使って定期実行（クーロンジョブ等）を設定してください。

**Linux / Mac (cron の例: 1時間ごとに実行)**
```bash
0 * * * * cd /path/to/expo-notice-alert && /path/to/venv/bin/python expo-notice-alert.py
```

**Windows (タスクスケジューラの例)**
タスクスケジューラを開き、「トリガー」を特定の時間間隔に、「操作」に Python 実行ファイルとスクリプトのパスを指定してタスクを作成します。

---

## 🧪 テストの実行

プロジェクトにはセキュリティや異常系をカバーするテストコードが含まれています。開発環境で以下のコマンドを実行することで、すべてのテストを走らせることができます。

```bash
pytest tests/
```

---

## 📄 ライセンス

このプロジェクトは [MIT License](LICENSE) のもとで公開されています。自由に改変・再配布してお使いいただけます。
