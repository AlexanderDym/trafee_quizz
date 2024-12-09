import logging
from telegram.ext import CallbackContext

# Custom modules
from shared import user_chat_mapping  # Для получения данных пользователей

QUIZ_TIMEOUT_SECONDS = 30

def notify_users_about_quiz(context):
    for username, user_data in user_chat_mapping.items():  # Используем user_chat_mapping вместо joined_users
        chat_id = user_data["chat_id"]
        try:
            context.bot.send_message(
                chat_id=chat_id,
                text="The quiz will start in 5 minutes!🔔\n\n"
                     "🔥Get ready!"
            )
            logging.info(f"Reminder sent to {username} (Chat ID: {chat_id})")
        except Exception as e:
            logging.error(f"Failed to send reminder to {username}: {e}")



def notify_users_about_next_day(context):
    day = context.job.context.get('day', 0)  # Получаем текущий день
    next_day = day + 1  # Завтрашний день

    # Убедимся, что номер дня не превышает 7
    if next_day > 7:
        next_day -= 7

    for username, user_data in user_chat_mapping.items():
        if user_data.get("joined"):
            chat_id = user_data.get("chat_id")
            try:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎄 Reminder! Tomorrow is Day {next_day} of our 7-day holiday giveaway! 🎁✨\n\n"
                         "Don’t miss your chance to win more amazing prizes.\n\n"
                         "🕒 The fun starts at 15:00 UTC sharp, and we’ll send you a reminder 3 minutes before "
                         "to make sure you're ready to shine! 🌟 See you there!"
                )
                logging.info(f"Reminder for next day sent to {username} (Chat ID: {chat_id})")
            except Exception as e:
                logging.error(f"Failed to send next day reminder to {username}: {e}")           