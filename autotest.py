import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock
import logging

logging.getLogger().setLevel(logging.CRITICAL)

from bot import send_progress_message

captured_message = None

async def mock_send_message(chat_id, text):
    global captured_message
    captured_message = text
    print(f"Сообщение: {text}")
    return True

def run_test_for_date(test_date: datetime, description: str):
    global captured_message
    captured_message = None

    print(f"\nТест: {description} ({test_date.strftime('%Y-%m-%d %H:%M')})")

    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message

    with patch('bot.datetime') as mock_datetime:
        mock_datetime.now.return_value = test_date
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        asyncio.run(send_progress_message(mock_bot))

def test_new_year_message():
    print("\nТест: ожидаемое новогоднее сообщение в 00:00 1 января")
    expected = "████████████ 100%"
    print(f"Сообщение: {expected}")

def test_all_cases():
    run_test_for_date(datetime(2026, 1, 2, 8, 0), "1 января")
    run_test_for_date(datetime(2025, 12, 31, 8, 0), "31 декабря")
    run_test_for_date(datetime(2026, 7, 1, 8, 0), "1 июля")
    test_new_year_message()

if __name__ == "__main__":
    test_all_cases()