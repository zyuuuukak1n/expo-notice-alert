import requests
from bs4 import BeautifulSoup
import time
import os
from dotenv import load_dotenv
import logging
from urllib.parse import urlparse, urljoin
import datetime

# スクリプトの場所を基準にファイルパスを解決
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, '.env')
SEEN_ARTICLES_FILE = os.path.join(SCRIPT_DIR, 'seen_articles.txt')
LOG_FILE = os.path.join(SCRIPT_DIR, 'bot.log')

# .envファイルから環境変数を読み込む
load_dotenv(dotenv_path=ENV_PATH)

# 環境変数・設定値
APP_ENV = os.getenv('APP_ENV', 'production').lower()
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
# デフォルト値を持たせつつ環境変数で上書き可能に
NEWS_URL = os.getenv('NEWS_URL', 'https://www.expo2025.or.jp/news/category/information/')

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
MAX_TITLE_LENGTH = 200 # タイトルの最大文字数
MAX_RETRIES = 3 # 429時の最大リトライ回数

# ロギング設定
log_format = '%(asctime)s - %(levelname)s - %(message)s'
if APP_ENV == 'development':
    # 開発環境: コンソールにも出力し、詳細なフォーマット
    logging.basicConfig(level=logging.DEBUG, format=log_format, handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ])
else:
    # 本番環境: 最低限の情報のみファイルに出力
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ])

def is_valid_url(url):
    """URLがHTTP/HTTPSプロトコルを使用しているか検証する"""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ['http', 'https'] and bool(parsed.netloc)
    except Exception:
        return False

def sanitize_title(title):
    """タイトルをサニタイズ（長すぎる場合は切り詰め）する"""
    if not title:
        return "No Title"
    title = title.strip()
    if len(title) > MAX_TITLE_LENGTH:
        return title[:MAX_TITLE_LENGTH] + "..."
    return title

def get_latest_news():
    """お知らせサイトから最新ニュースのリスト（タイトルとURL）を取得する"""
    headers = {'User-Agent': USER_AGENT}
    news_list = []
    try:
        logging.info("お知らせページにアクセスします。")
        response = requests.get(NEWS_URL, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        news_list_container = soup.find('div', class_='news_list')
        if not news_list_container:
            logging.warning("お知らせリストのコンテナが見つかりませんでした。")
            return []

        ol_element = news_list_container.find('ol')
        if not ol_element:
            logging.warning("お知らせリストのol要素が見つかりませんでした。")
            return []

        articles = ol_element.find_all('li', class_='news_item')
        if not articles:
            logging.warning("お知らせアイテムが見つかりませんでした。")
            return []
        
        logging.info(f"{len(articles)}件の記事候補が見つかりました。")

        for item_count, item in enumerate(articles):
            link_tag = item.find('a')
            title_div = item.find('div', class_='txt')

            if link_tag and link_tag.has_attr('href') and title_div:
                url = link_tag['href']
                if not url.startswith('http'):
                     url = urljoin(NEWS_URL, url)
                
                # [SECURITY] URLのバリデーション
                if not is_valid_url(url):
                    logging.warning(f"無効なURLが検出されたためスキップします。")
                    continue

                # [SECURITY] タイトルのサニタイズ
                title = sanitize_title(title_div.text)
                
                news_list.append({'title': title, 'url': url})
            else:
                logging.warning(f"アイテムのパースに一部失敗しました。")

        return news_list

    except requests.exceptions.Timeout:
        logging.error("ウェブサイトからのニュース取得中にタイムアウトしました。")
        return []
    except requests.exceptions.RequestException as e:
        # [SECURITY] スタックトレースや詳細なURLを隠蔽
        logging.error("ウェブサイトへのアクセス中に通信エラーが発生しました。")
        if APP_ENV == 'development':
            logging.error(f"詳細: {e}")
        return []
    except Exception as e:
        logging.error("ニュースのパース中に予期せぬエラーが発生しました。")
        if APP_ENV == 'development':
            logging.error(f"詳細: {e}", exc_info=True)
        return []

def load_seen_articles():
    """通知済み記事のURLリストをファイルから読み込む"""
    if not os.path.exists(SEEN_ARTICLES_FILE):
        return set()
    try:
        with open(SEEN_ARTICLES_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    except Exception as e:
        logging.error("既読記事ファイルの読み込み中にエラーが発生しました。")
        if APP_ENV == 'development':
             logging.error(f"詳細: {e}")
        return set()

def save_seen_articles(seen_urls):
    """通知済み記事のURLリストをファイルに保存する"""
    try:
        with open(SEEN_ARTICLES_FILE, 'w', encoding='utf-8') as f:
            for url in seen_urls:
                f.write(url + '\n')
    except Exception as e:
        logging.error("既読記事ファイルの書き込み中にエラーが発生しました。")
        if APP_ENV == 'development':
             logging.error(f"詳細: {e}")

def send_to_discord_with_retry(payload, headers):
    """レート制限を考慮したDiscordへの送信"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 429:
                # [ARCHITECTURE] Discordのレート制限(429)に対応
                try:
                    retry_after = float(response.json().get('retry_after', 1.0))
                except ValueError:
                    retry_after = 1.0
                logging.warning(f"Discord レート制限に到達しました。{retry_after}秒待機してリトライします（{attempt+1}/{MAX_RETRIES}）。")
                time.sleep(retry_after)
                continue
                
            response.raise_for_status()
            return True
            
        except requests.exceptions.Timeout:
            logging.error("Discordへの通知送信中にタイムアウトしました。")
            return False
        except requests.exceptions.RequestException as e:
            logging.error("Discordへの通知送信中にエラーが発生しました。")
            if APP_ENV == 'development':
                 status_code = response.status_code if 'response' in locals() and hasattr(response, 'status_code') else 'N/A'
                 logging.error(f"詳細: {e} (Status: {status_code})")
            return False
        except Exception as e:
            logging.error("Discord通知の処理中に予期せぬエラーが発生しました。")
            if APP_ENV == 'development':
                logging.error(f"詳細: {e}", exc_info=True)
            return False
            
    logging.error(f"最大リトライ回数({MAX_RETRIES})に達したため、通知の送信を諦めました。")
    return False

def send_bulk_discord_notification(articles_to_send, total_new_articles_count):
    """複数の記事をDiscordにEmbed形式でまとめて送信する"""
    if not DISCORD_WEBHOOK_URL:
        logging.error("Discord Webhook URLが設定されていません。")
        return

    MAX_EMBEDS_PER_MESSAGE = 10
    EXPO_ORANGE_COLOR = 15258703 
    
    chunks = [articles_to_send[i:i + MAX_EMBEDS_PER_MESSAGE] for i in range(0, len(articles_to_send), MAX_EMBEDS_PER_MESSAGE)]

    for chunk_index, chunk in enumerate(chunks):
        embeds = []
        for article in chunk:
            embed = {
                "title": article['title'],
                "url": article['url'],
                "color": EXPO_ORANGE_COLOR,
            }
            embeds.append(embed)

        if not embeds:
            continue

        content_message = ""
        if chunk_index == 0:
            content_message = f"公式サイトに {total_new_articles_count}件の新しいお知らせが掲載されました！"
            if embeds: 
                embeds[0]["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        payload = {
            "content": content_message,
            "embeds": embeds
        }
        
        headers = {'Content-Type': 'application/json'}
        logging.info(f"Discordに通知チャンク {chunk_index + 1}/{len(chunks)} を送信します。")
        
        success = send_to_discord_with_retry(payload, headers)
        if success:
            logging.info("チャンクの送信に成功しました。")
            if len(chunks) > 1 and chunk_index < len(chunks) - 1:
                time.sleep(1) # 通常のバッチ間隔
        else:
            logging.error("チャンクの送信に失敗しました。")

def main():
    logging.info("お知らせ監視処理を開始します。")

    if not DISCORD_WEBHOOK_URL:
        logging.error("DISCORD_WEBHOOK_URLが設定されていません。処理を中断します。")
        return

    initial_run = not os.path.exists(SEEN_ARTICLES_FILE)
    seen_articles_urls = load_seen_articles()
    latest_news = get_latest_news()

    if not latest_news:
        logging.info("お知らせの取得なし、またはエラーにより終了します。")
        return

    new_articles_to_notify = []
    current_article_urls_on_site = set()

    for news_item in latest_news:
        current_article_urls_on_site.add(news_item['url'])
        if news_item['url'] not in seen_articles_urls:
            new_articles_to_notify.append(news_item)

    if initial_run:
        logging.info("初回実行のため通知は行わず、状態を保存します。")
        save_seen_articles(current_article_urls_on_site)
    elif new_articles_to_notify:
        total_new_count = len(new_articles_to_notify)
        logging.info(f"{total_new_count}件の新規お知らせがありました。")
        
        # 古い順に通知するためリバース
        articles_for_discord = list(reversed(new_articles_to_notify))
        send_bulk_discord_notification(articles_for_discord, total_new_count)
        save_seen_articles(current_article_urls_on_site)
    else:
        logging.info("新しいお知らせはありませんでした。")
        save_seen_articles(current_article_urls_on_site)

    logging.info("お知らせ監視処理を終了します。")

if __name__ == '__main__':
    main()