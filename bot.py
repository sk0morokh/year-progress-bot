import logging  # Импортируем модуль для логирования
import asyncio  # Импортируем модуль для асинхронного программирования
from datetime import datetime, timedelta  # Импортируем классы для работы с датой и временем
from telegram import Bot  # Импортируем класс Bot из библиотеки Telegram
from telegram.ext import ApplicationBuilder  # Импортируем ApplicationBuilder для создания приложения Telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Импортируем планировщик задач для асинхронных задач
from apscheduler.triggers.cron import CronTrigger  # Импортируем триггер для запуска задач по расписанию
from apscheduler.events import EVENT_JOB_MISSED  # Импортируем событие пропуска задачи
import pytz  # Импортируем модуль для работы с часовыми поясами
from config import BOT_TOKEN, CHANNEL_CHAT_ID  # Импортируем токен бота и ID канала из конфигурационного файла

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Формат логов: время, имя, уровень, сообщение
    level=logging.INFO  # Устанавливаем уровень логирования на INFO (только важные события)
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Отключаем детальные логи HTTP-запросов
logger = logging.getLogger(__name__)  # Создаем объект логгера для текущего модуля

bot = Bot(token=BOT_TOKEN)  # Создаем экземпляр бота с использованием токена

# Глобальные переменные для управления количеством попыток
is_sent_successfully = False  # Флаг успешной отправки сообщения
max_attempts = 30  # Максимальное количество попыток отправки сообщения


# Функция для отправки сообщения о прогрессе
async def send_progress_message(bot_instance: Bot) -> bool:
    global is_sent_successfully  # Объявляем глобальную переменную для флага успешной отправки
    today = datetime.now()  # Получаем текущую дату и время
    start_of_year = datetime(today.year, 1, 1)  # Определяем начало года
    end_of_year = datetime(today.year + 1, 1, 1)  # Определяем начало следующего года
    total_days = (end_of_year - start_of_year).days  # Вычисляем общее количество дней в году
    completed_days = (today - start_of_year).days  # Вычисляем количество прошедших дней с начала года
    percent = round((completed_days / total_days) * 100, 2)  # Вычисляем процент завершения года
    progress_bar_length = 12  # Длина прогресс-бара
    filled_length = int(progress_bar_length * completed_days // total_days)  # Вычисляем заполненную часть прогресс-бара
    bar = '▓' * filled_length + '░' * (progress_bar_length - filled_length)  # Создаем строку прогресс-бара
    message = f"{bar} {percent:.2f}%"  # Формируем текст сообщения

    try:
        logger.debug("Starting send_message call...")  # Логируем начало отправки сообщения
        start_time = datetime.now()  # Записываем время начала отправки
        await bot_instance.send_message(chat_id=CHANNEL_CHAT_ID, text=message)  # Отправляем сообщение в канал
        end_time = datetime.now()  # Записываем время окончания отправки
        duration = (end_time - start_time).total_seconds()  # Вычисляем время выполнения отправки
        logger.info(f"Message sent successfully in {duration:.4f} seconds.")  # Логируем успешную отправку
        is_sent_successfully = True  # Устанавливаем флаг успешной отправки
    except Exception as e:
        logger.exception(f"Failed to send message: {e}")  # Логируем ошибку отправки
        is_sent_successfully = False  # Сбрасываем флаг успешной отправки
    return is_sent_successfully  # Возвращаем результат отправки

# Проверка часового пояса
def log_timezone():
    server_timezone = datetime.now(pytz.timezone('Europe/Moscow')).strftime(
        '%Z %z')  # Получаем текущий часовой пояс сервера
    logger.info(f"Server timezone: {server_timezone}")  # Логируем часовой пояс


# Планировщик задач
def setup_scheduler(scheduler: AsyncIOScheduler, bot_instance: Bot) -> None:
    async def scheduled_send_progress_message():
        global is_sent_successfully  # Объявляем глобальную переменную для флага успешной отправки
        attempts = 0  # Счетчик попыток отправки
        while attempts < max_attempts:  # Цикл повторных попыток отправки
            attempts += 1  # Увеличиваем счетчик попыток
            logger.debug(f"Scheduled job starting... Attempt #{attempts}")  # Логируем начало попытки

            result = await send_progress_message(bot_instance)  # Выполняем отправку сообщения
            if result:  # Если отправка успешна
                logger.info("Message sent successfully.")  # Логируем успех
                break  # Выходим из цикла
            else:  # Если отправка не удалась
                logger.warning(f"Attempt #{attempts} failed. Retrying in 10 seconds...")  # Логируем неудачу
                await asyncio.sleep(10)  # Ждем 10 секунд перед следующей попыткой
        else:  # Если все попытки исчерпаны
            logger.error(f"Max retries exceeded ({max_attempts}) without success.")  # Логируем ошибку

    # Логируем часовой пояс при инициализации
    log_timezone()

    # Определяем время первого запуска
    now = datetime.now()  # Получаем текущее время
    first_run_time = now.replace(hour=8, minute=0, second=0,
                                 microsecond=0)  # Устанавливаем время первого запуска на 8:00
    if now.hour >= 8:  # Если текущее время уже после 8:00
        first_run_time += timedelta(days=1)  # Переносим первый запуск на следующий день

    # Добавляем задачу с параметрами misfire_grace_time и coalesce
    scheduler.add_job(
        scheduled_send_progress_message,  # Функция для выполнения
        CronTrigger(day_of_week='mon-sun', hour="8", minute="0"),  # Триггер для ежедневного запуска в 8:00
        next_run_time=first_run_time,  # Время первого запуска
        misfire_grace_time=60,  # Допустимое время пропуска (60 секунд)
        coalesce=True  # Объединение пропущенных запусков
    )

    # Логируем запланированное время старта
    date_str = first_run_time.strftime("%Y-%m-%d")  # Форматируем дату
    time_str = first_run_time.strftime("%H:%M:%S")  # Форматируем время
    formatted_datetime = f"{date_str} в {time_str}"  # Комбинируем дату и время
    logger.info(f"First message will be sent at {formatted_datetime}.")  # Логируем время первого запуска

    # Логируем события пропуска задач
    scheduler.add_listener(
        lambda event: logger.warning(f"Misfire detected: {event}"),  # Логируем событие пропуска задачи
        EVENT_JOB_MISSED  # Слушаем событие пропуска задачи
    )


# Главная функция
async def main():
    app_builder = ApplicationBuilder().token(BOT_TOKEN)  # Создаем билдер приложения с токеном бота
    app = app_builder.build()  # Строим приложение

    # Запуск планировщика
    scheduler = AsyncIOScheduler()  # Создаем планировщик задач
    setup_scheduler(scheduler, bot)  # Настраиваем планировщик
    scheduler.start()  # Запускаем планировщик

    # Запуск бота
    await app.initialize()  # Инициализируем приложение
    await app.start()  # Запускаем приложение
    print("Bot started!")  # Выводим сообщение о запуске бота
    while True:  # Бесконечный цикл для поддержания работы бота
        await asyncio.sleep(3600)  # Пауза каждые 60 минут


if __name__ == "__main__":
    asyncio.run(main())  # Запускаем главную функцию