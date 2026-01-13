import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import ApplicationBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_MISSED
import pytz
from config import BOT_TOKEN, CHANNEL_CHAT_ID

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

is_sent_successfully = False
max_attempts = 30  # Максимальное количество попыток отправки сообщения

async def send_progress_message(bot_instance: Bot) -> bool:
    global is_sent_successfully
    today = datetime.now()
    start_of_year = datetime(today.year, 1, 1)
    end_of_year = datetime(today.year + 1, 1, 1)
    total_days = (end_of_year - start_of_year).days
    completed_days = (today - start_of_year).days
    percent = round((completed_days / total_days) * 100, 2)
    progress_bar_length = 12  # Длина прогресс-бара
    filled_length = int(progress_bar_length * completed_days // total_days)
    bar = '▓' * filled_length + '░' * (progress_bar_length - filled_length)
    message = f"{bar} {percent:.2f}%"  # Формируем текст сообщения

    try:
        logger.debug("Попытка отправки сообщения")
        start_time = datetime.now()
        await bot_instance.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Сообщение успешно отправлено за {duration:.4f} секунд")
        is_sent_successfully = True
    except Exception as e:
        logger.exception(f"Ошибка отправки сообщения: {e}")
        is_sent_successfully = False
    return is_sent_successfully

# Проверка часового пояса
def log_timezone():
    server_timezone = datetime.now(pytz.timezone('Europe/Moscow')).strftime(
        '%Z %z')  # Получаем текущий часовой пояс сервера
    logger.info(f"Часовой пояс сервера: {server_timezone}")  # Логируем часовой пояс

def setup_scheduler(scheduler: AsyncIOScheduler, bot_instance: Bot) -> None:
    async def scheduled_send_progress_message():
        # Проверяем, является ли сегодняшняя дата 1 января
        today_date = datetime.now().date()
        if today_date.month == 1 and today_date.day == 1:
            logger.info("Пропуск ежедневного сообщения о прогрессе 1 января")
            return  # Пропускаем выполнение для 1 января

        global is_sent_successfully
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            logger.debug(f"Запуск задачи по расписанию. Попытка #{attempts}")

            result = await send_progress_message(bot_instance)
            if result:
                logger.info("Сообщение успешно отправлено")
                break
            else:
                logger.warning(f"Попытка #{attempts} не удалась. Повтор через 10 секунд...")
                await asyncio.sleep(10)
        else:
            logger.error(f"Превышено максимальное количество попыток ({max_attempts})")

    # Функция для отправки специального сообщения 1 января в 00:00
    async def send_new_year_progress():
        message = "████████████ 100%"
        try:
            await bot_instance.send_message(chat_id=CHANNEL_CHAT_ID, text=message)
            logger.info("Новогоднее сообщение успешно отправлено")
        except Exception as e:
            logger.exception(f"Не удалось отправить новогоднее сообщение: {e}")

    log_timezone()

    # Определяем время первого запуска для ежедневной задачи (начиная с 2 января)
    now = datetime.now()
    first_run_time = now.replace(hour=8, minute=0, second=0, microsecond=0)

    if now.date().month == 1 and now.date().day == 1:
        first_run_time = datetime(now.year, 1, 2, 8, 0, 0)
    elif now.hour >= 8:
        first_run_time += timedelta(days=1)
        if first_run_time.date().month == 1 and first_run_time.date().day == 1:
            first_run_time += timedelta(days=1)

    scheduler.add_job(
        scheduled_send_progress_message,
        CronTrigger(day_of_week='mon-sun', hour="8", minute="0"),
        next_run_time=first_run_time,
        misfire_grace_time=60,
        coalesce=True
    )

    scheduler.add_job(
        send_new_year_progress,
        CronTrigger(month='1', day='1', hour='0', minute='0'),
        id='new_year_message',
        replace_existing=True
    )
    logger.info("Запланировано специальное новогоднее сообщение на 1 января в 00:00")

    date_str = first_run_time.strftime("%Y-%m-%d")
    time_str = first_run_time.strftime("%H:%M:%S")
    formatted_datetime = f"{date_str} в {time_str}"
    logger.info(f"Первое ежедневное сообщение будет отправлено {formatted_datetime}.")

    scheduler.add_listener(
        lambda event: logger.warning(f"Задача пропущена: {event}"),
        EVENT_JOB_MISSED
    )

async def main():
    app_builder = ApplicationBuilder().token(BOT_TOKEN)
    app = app_builder.build()

    scheduler = AsyncIOScheduler()
    setup_scheduler(scheduler, bot)
    scheduler.start()

    await app.initialize()
    await app.start()
    print("Бот запущен")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())