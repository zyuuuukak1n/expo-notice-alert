import pytest
import requests
from unittest.mock import patch, mock_open, MagicMock

import os
import sys
# テスト対象のモジュールパスを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# モジュール名にハイフンが含まれているため、importlibを使用するか、ファイル名変更が必要ですが、
# importlibを使用して無理やり読み込みます。
import importlib.util
spec = importlib.util.spec_from_file_location("expo_notice_alert", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expo-notice-alert.py"))
alert_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alert_module)

def test_is_valid_url():
    """正常系と異常系（セキュリティ含む）のURL検証テスト"""
    assert alert_module.is_valid_url("http://example.com") is True
    assert alert_module.is_valid_url("https://example.com/path?q=1") is True
    assert alert_module.is_valid_url("ftp://example.com") is False
    assert alert_module.is_valid_url("javascript:alert(1)") is False # セキュリティ
    assert alert_module.is_valid_url("file:///etc/passwd") is False # セキュリティ
    assert alert_module.is_valid_url("invalid_url") is False

def test_sanitize_title():
    """正常系と異常系（境界値）のタイトル検証テスト"""
    # 正常
    assert alert_module.sanitize_title("Normal Title") == "Normal Title"
    
    # トリムの検証
    assert alert_module.sanitize_title("  Spaced Title  ") == "Spaced Title"
    
    # 境界値 (200文字制限)
    long_title = "a" * 200
    assert alert_module.sanitize_title(long_title) == long_title
    
    too_long_title = "a" * 201
    assert alert_module.sanitize_title(too_long_title) == ("a" * 200) + "..."
    
    # Nullや空文字
    assert alert_module.sanitize_title("") == "No Title"
    assert alert_module.sanitize_title(None) == "No Title"

@patch('requests.get')
def test_get_latest_news_success(mock_get):
    """HTML解析の正常系テスト"""
    mock_html = """
    <div class="news_list">
        <ol>
            <li class="news_item">
                <a href="https://example.com/news/1">
                    <div class="txt">News Title 1</div>
                </a>
            </li>
            <li class="news_item">
                <a href="/news/2">
                    <div class="txt">News Title 2</div>
                </a>
            </li>
            <li class="news_item">
                <a href="javascript:alert(1)">
                    <div class="txt">Malicious URL</div>
                </a>
            </li>
        </ol>
    </div>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # モジュールの NEWS_URL を一時的に変更
    original_news_url = alert_module.NEWS_URL
    alert_module.NEWS_URL = "https://example.com"
    
    try:
        news = alert_module.get_latest_news()
        assert len(news) == 2 # 1つは無効なURLなのでスキップされる
        assert news[0]['title'] == 'News Title 1'
        assert news[0]['url'] == 'https://example.com/news/1'
        
        assert news[1]['title'] == 'News Title 2'
        assert news[1]['url'] == 'https://example.com/news/2' # urljoinで補完されること
    finally:
         alert_module.NEWS_URL = original_news_url

@patch('requests.get')
def test_get_latest_news_error(mock_get):
    """タイムアウト時の異常系テスト"""
    mock_get.side_effect = requests.exceptions.Timeout("Timeout")
    news = alert_module.get_latest_news()
    assert news == []

@patch('requests.post')
def test_send_to_discord_with_retry_success(mock_post):
    """Discord通知の正常系テスト"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # 一時的にWebhook URLを設定
    original_webhook = alert_module.DISCORD_WEBHOOK_URL
    alert_module.DISCORD_WEBHOOK_URL = "http://dummy.webhook"

    try:
         result = alert_module.send_to_discord_with_retry({"test": "data"}, {})
         assert result is True
         assert mock_post.call_count == 1
    finally:
         alert_module.DISCORD_WEBHOOK_URL = original_webhook

@patch('time.sleep')
@patch('requests.post')
def test_send_to_discord_with_retry_429(mock_post, mock_sleep):
    """Discordレート制限 (429) 時のリトライテスト"""
    
    # 1回目は429、2回目は200を返す
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.json.return_value = {'retry_after': 0.5}
    
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    
    mock_post.side_effect = [mock_response_429, mock_response_200]

    original_webhook = alert_module.DISCORD_WEBHOOK_URL
    alert_module.DISCORD_WEBHOOK_URL = "http://dummy.webhook"

    try:
         result = alert_module.send_to_discord_with_retry({"test": "data"}, {})
         assert result is True
         assert mock_post.call_count == 2
         mock_sleep.assert_called_once_with(0.5)
    finally:
         alert_module.DISCORD_WEBHOOK_URL = original_webhook

@patch('time.sleep')
@patch('requests.post')
def test_send_to_discord_with_retry_max_retries(mock_post, mock_sleep):
    """Discordレート制限 (429) が続き、最大リトライ回数を超えた場合のテスト"""
    
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.json.return_value = {'retry_after': 0.1}
    
    # ずっと429を返す
    mock_post.return_value = mock_response_429

    original_webhook = alert_module.DISCORD_WEBHOOK_URL
    alert_module.DISCORD_WEBHOOK_URL = "http://dummy.webhook"

    try:
         result = alert_module.send_to_discord_with_retry({"test": "data"}, {})
         assert result is False # 最終的に失敗する
         assert mock_post.call_count == alert_module.MAX_RETRIES # 最大回数呼ばれる
    finally:
         alert_module.DISCORD_WEBHOOK_URL = original_webhook
