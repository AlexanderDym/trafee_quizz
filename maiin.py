import logging
import os
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, PollAnswerHandler

from config import file_path, gifts_file_path, SUPERADMIN_USERNAME  
from handlers import start_command_handler, list_handler, participate_handler 
from quiz import send_daily_quiz
from handlers import poll_handler
from notifications import notify_users_about_quiz 
from excel_api import initialize_excel  
from datetime import datetime, timezone
import time
from datetime import datetime, time as dt_time


load_dotenv()

def main():
    # Инициализация Excel
    initialize_excel(file_path=file_path)

    # Получаем токен для бота
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is not set. Exiting.")
        return

    # Создаем updater и dispatcher
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Регистрируем обработчики
    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(CommandHandler("list", list_handler))
    dp.add_handler(CallbackQueryHandler(participate_handler, pattern="participate"))
    dp.add_handler(PollAnswerHandler(poll_handler))

    # Инициализация текущего дня
    dp.bot_data['current_day'] = 0  # Начинаем с 0-го дня

    # Логирование времени сервера
    logging.info(f"Current server UTC time: {datetime.now(timezone.utc)}")

    # Планируем задачи (уведомления и викторину)
    job_queue = updater.job_queue

    # Уведомление за 5 минут до викторины
    job_queue.run_daily(
        notify_users_about_quiz,
        time=dt_time(12, 39),  # Уведомление в 14:55 по UTC
    )
    logging.info("JobQueue task for quiz notifications added at 14:55 UTC.")

    # Планирование самой викторины
    job_queue.run_daily(
        lambda context: send_daily_quiz(context, dp.bot_data['current_day']),
        time=dt_time(12, 40)  # Викторина в 15:00 по UTC
    )
    logging.info("JobQueue task for quiz scheduling added at 15:00 UTC.")

    # Старт бота
    updater.start_polling()
    logging.info("Bot started in polling mode")

# Запуск главной функции
if __name__ == '__main__':
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    main()
