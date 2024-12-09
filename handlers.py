import logging
from datetime import datetime

# Telegram API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import CallbackContext

# Модули бота
from winners import select_winners
from quiz import quiz_questions
from excel_api import record_user_response
from auth import is_authorized_user
from shared import poll_participants, user_chat_mapping

from config import SUPERADMIN_USERNAME, file_path



# Command to start the quiz for the user
def start_command_handler(update, context):
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username if user.username else "Unknown"

    # Проверка авторизации
    if not is_authorized_user(update):
        logging.warning(f"Unauthorized user @{username} tried to access the bot.")
        context.bot.send_message(chat_id=chat_id, text="⛔ You are not authorized to use this bot.")
        return

    # Check if the user has already started the bot
    if username in user_chat_mapping:
        logging.warning(f"{datetime.now()} - User @{username} tried to press /start again.")
        context.bot.send_message(
            chat_id=chat_id,
            text="You're already in the quiz 👻\n\nThe next question will be tomorrow!\n\nDon't be sneaky 😜."
        )
        return

    # If the user is new, add them to the dictionary
    user_chat_mapping[username] = {"chat_id": chat_id, "joined": False}

    # Send the welcome message
    image_url = "https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz.png"
    welcome_text = (
        "*🎄✨ Welcome to the ultimate holiday quiz challenge! 🎅🎁*\n\n"
        "🔥 From *December 17 to 23*, we'll light up your festive spirit with daily quizzes\n\n"
        "🎯 Answer questions, compete with others, and *grab amazing prizes every day!*\n\n"
        "*🎁 And the grand finale?*\nA special gift waiting for the ultimate champion on Christmas Eve 🎉\n\n"
    )
    context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=welcome_text, parse_mode="Markdown")

    keyboard = [[InlineKeyboardButton("🚀 Join the Quiz", callback_data="participate")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=chat_id, text="Click 'Join the Quiz' to get started.\n\nLet the fun begin! 🎉", reply_markup=reply_markup)

    # Command for superadmin to get the results file
def list_handler(update, context):
    user = update.message.from_user

    if user.username == SUPERADMIN_USERNAME:
        try:
            with open(file_path, 'rb') as file:
                context.bot.send_document(chat_id=update.effective_chat.id, document=file, filename="quiz_results.xlsx")
                update.message.reply_text("👉Here are the current quiz results👈")
        except Exception as e:
            update.message.reply_text(f"Failed to send the file: {str(e)}")
    else:
        update.message.reply_text("⛔ You don't have access to this command.")

        # Callback for participating in quiz
def participate_handler(update, context):
    query = update.callback_query
    query.answer()

    user = query.from_user
    username = user.username if user.username else "Unknown"

    # Проверка авторизации
    if not is_authorized_user(update):
        logging.warning(f"Unauthorized user @{username} tried to join the quiz.")
        query.edit_message_text(text="⛔ You are not authorized to join this quiz.")
        return

    # Проверка: если пользователь уже нажимал Join Quiz
    if user_chat_mapping.get(username, {}).get("joined"):
        logging.info(f"User @{username} tried to join the quiz again.")
        query.edit_message_text(text="You are already in the quiz! 🚀")
        return

    # Отметить пользователя как присоединившегося
    user_chat_mapping[username] = {
        "chat_id": query.message.chat_id,
        "joined": True
    }
    logging.info(f"User @{username} joined the quiz for the first time.")
    query.edit_message_text(text="Welcome to the quiz! 🎉")


def poll_handler(update, context):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id  # Get user_id
    poll_id = poll_answer.poll_id  # Get poll_id
    selected_option_id = poll_answer.option_ids[0]  # Get the user's selected answer

    # Retrieve poll data
    poll_data = context.bot_data.get(poll_id, {})
    day = poll_data.get('day', 0)
    question = quiz_questions[day]
    correct_option_id = question.correct_answer_position
    is_correct = (selected_option_id == correct_option_id)

    # Log poll answer
    logging.info(f"Poll answer received. User: {user_id}, Poll ID: {poll_id}, Selected Option: {selected_option_id}, Correct: {is_correct}")

    # Initialize poll participants if not already done
    if poll_id not in poll_participants:
        poll_participants[poll_id] = set()

    # Add the user to poll_participants
    poll_participants[poll_id].add(user_id)
    logging.info(f"User {user_id} added to poll_participants for poll_id {poll_id}. Current participants: {poll_participants[poll_id]}")

    # Record the result in the table
    response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    username = poll_answer.user.username if poll_answer.user.username else "Unknown"
    record_user_response(file_path, user_id=user_id, username=username, day=day, response_time=response_time, result=is_correct)

    # Notify the user
    if is_correct:
        context.bot.send_message(
            chat_id=user_id,
            text="🎉 Congratulations, your answer is correct!\n\n🏁 We will now wait for all participants to complete the game.\n\n✨ After that, we will randomly select 20 winners from those who answered correctly.\n\n☘️ Good luck!"
        )
    else:
        context.bot.send_message(
            chat_id=user_id,
            text="❌ Oops, that’s the wrong answer!\n\nBut don’t give up!\n\n🤗 Try again tomorrow."
        )