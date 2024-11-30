import time
import logging
import os
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, PollAnswerHandler, JobQueue, CallbackContext
from datetime import datetime, time as dt_time
from dotenv import load_dotenv
import openpyxl
from openpyxl.styles import PatternFill
from openpyxl import Workbook, load_workbook
import csv
from datetime import datetime, timezone
import random


# Load environment variables
load_dotenv(dotenv_path=Path('.') / 'trafee.env')

# Timer for quiz
QUIZ_TIMEOUT_SECONDS = 30

# Global mapping of usernames to chat IDs
joined_users = {}  # username -> chat_id
user_chat_mapping = {}
poll_participants = {}  # poll_id -> set(user_id)
user_participation = {} # Обработка нажатия команды старт
quiz_participation= {} # Обработка нажатия Участия в викторине
notified_winners_global = set()

# Список призов для каждого дня викторины
prizes = [
    "is a 1-month Spotify Premium subscription!",
    "is a $20 Amazon gift card!",
    "is a 1-month Netflix subscription!",
    "is exclusive merchandise from our company!",
    "is a 1-month YouTube Premium subscription!",
    "is a bestselling e-book!",
    "is a $15 food delivery voucher!"
]


# Function to update chat ID mapping
def update_user_chat_mapping(username, chat_id):
    if username and chat_id:
        user_chat_mapping[username] = chat_id

def get_chat_id_by_username(username):
    return user_chat_mapping.get(username)

# Function to load authorized usernames from CSV
def load_authorized_usernames(file_path):
    usernames = []
    try:
        with open(file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if "Telegram Username" in row:
                    usernames.append(row["Telegram Username"])
    except FileNotFoundError:
        logging.warning(f"⚠️ File {file_path} not found. Authorized user list will be empty.")
    except Exception as e:
        logging.error(f"⚠️ Error reading file {file_path}: {e}")
    return usernames

# Configuration for users and admins
csv_file_path = "registration_log.csv"
authorized_usernames = load_authorized_usernames(csv_file_path)
SUPERADMIN_USERNAME = "Alexander_Dym"
file_path = "updated_bot_list.xlsx"

# Initialize the Excel file
def initialize_excel():
    if not os.path.exists(file_path):
        wb = Workbook()
        for i in range(1, 8):
            sheet = wb.create_sheet(title=f"Day {i}")
            headers = ["User ID", "Username", "Response Time", "Correct Answer", "Winner"]
            sheet.append(headers)
        wb.remove(wb["Sheet"])
        wb.save(file_path)
        logging.info(f"Excel file initialized with sheets for each quiz day at {file_path}")


# Class for quiz questions
class QuizQuestion:
    def __init__(self, question="", answers=None, correct_answer=""):
        self.question = question
        self.answers = answers if answers is not None else []
        self.correct_answer = correct_answer
        self.correct_answer_position = self.__get_correct_answer_position__()

    def __get_correct_answer_position__(self):
        for index, answer in enumerate(self.answers):
            if answer.strip().lower() == self.correct_answer.strip().lower():
                return index
        return -1

# Quiz questions for 7 days
quiz_questions = [
    QuizQuestion("What is an offer? 🎄🎅", ["A call-to-action on a landing page like Hurry up for gifts! 🎁", "A product or service that the advertiser pays for", "Creative content used in advertising, like a holiday card from Santa ❄️"], "A product or service that the advertiser pays for"),
    QuizQuestion("Which button is most commonly used for calls-to-action on Christmas's landing pages? 🎄🎁", ["Read more", "Share", "Buy now"], "Buy now"),
    QuizQuestion("Which social media became the favourite among affiliates during the holiday season thanks to short and dynamic videos? 🎥✨", ["Facebook", "TikTok", "Twitter"], "TikTok"),
    QuizQuestion("Which advertising strategy сan find the most magical ad for the upcoming holidays? 🎅🎄", ["Scaling", "A/B testing", "Retargeting"], "A/B testing"),
    QuizQuestion("What's the metric that measures your earnings per visitor? 🎅💰", ["EPC (Earnings Per Click)", "CTR (Click-Through Rate)", "CPA (Cost Per Action)"], "EPC (Earnings Per Click)"),
    QuizQuestion("What is ROI in affiliate marketing? 🎁📈", ["Ad impressions", "Return on investment and campaign profitability", "Revenue per individual sale"], "Return on investment and campaign profitability"),
    QuizQuestion("What Does CPM Mean in Holiday Advertising? 🎅📊", ["Cost Per Million (cost for one million clicks)", "Cost Per Millisecond (cost for one millisecond)", "Cost Per Mille (cost for one thousand impressions)"], "Cost Per Mille (cost for one thousand impressions)"),
]

# Record user response in Excel
def record_user_response(user_id, username, day, response_time, result):
    wb = load_workbook(file_path)
    sheet_name = f"Day {day + 1}"

    if sheet_name not in wb.sheetnames:
        wb.create_sheet(title=sheet_name)
    sheet = wb[sheet_name]

    green_fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    result_text = "Верно" if result else "Неверно"
    result_fill = green_fill if result else red_fill

    # Проверяем, существует ли уже запись для этого пользователя
    user_found = False
    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
        if row[0].value == user_id:  # Проверяем по user_id
            row[2].value = response_time  # Обновляем время ответа
            row[3].value = result_text  # Обновляем результат
            row[3].fill = result_fill  # Применяем цвет
            user_found = True
            break

    if not user_found:
        # Если записи нет, добавляем новую
        new_row = [user_id, username, response_time, result_text]
        sheet.append(new_row)

        # Применяем цвет заливки к новой строке
        for cell in sheet.iter_rows(min_row=sheet.max_row, max_row=sheet.max_row, min_col=1, max_col=4):
            if cell[3].value == "Верно":
                cell[3].fill = green_fill
            elif cell[3].value == "Неверно":
                cell[3].fill = red_fill

    wb.save(file_path)
    logging.info(f"Результат для пользователя {username} записан: {result_text}")




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

# Command to start the quiz for the user
def start_command_handler(update, context):
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username if user.username else "Unknown"

    # Check if the user has already started the bot
    if username in user_participation:
        # Log the repeated start attempt
        logging.warning(f"{datetime.now()} - User @{username} tried to press /start again.")
        # Send a message to the user
        context.bot.send_message(
            chat_id=chat_id,
            text="You're already in the quiz 👻\n\nThe next question will be tomorrow!\n\nDon't be sneaky 😜."
        )
        return

    # If the user is new, add them to the dictionary
    user_participation[username] = {"participated": True, "timestamp": datetime.now()}
    
    # Send the welcome message
    update_user_chat_mapping(username, chat_id)
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




def handle_poll_timeout(context):
    poll_id = context.job.context['poll_id']
    day = context.job.context['day']

    # List of users who have already answered
    answered_users = poll_participants.get(poll_id, set())

    # Load Excel and check who is already recorded
    wb = load_workbook(file_path)
    sheet_name = f"Day {day + 1}"
    sheet = wb[sheet_name]

    # List of users already recorded in Excel
    recorded_users = {row[0] for row in sheet.iter_rows(min_row=2, values_only=True) if row[0]}

    for username, chat_id in user_chat_mapping.items():
        user_id = chat_id  # Assuming chat_id corresponds to user_id
        if user_id in answered_users or user_id in recorded_users:
            # User has already answered, skip
            logging.info(f"User {username} has already answered the question. Timeout skipped.")
            continue

        # If the user hasn't answered, notify them and record the result
        context.bot.send_message(chat_id=chat_id, text="⏰ Time's up!\n\nYour response was not counted 🥵.")
        response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        record_user_response(user_id=user_id, username=username, day=day, response_time=response_time, result=False)

    # Proceed to selecting winners
    select_winners(context, day)


from telegram.ext import JobQueue, CallbackContext

def notify_users_about_next_day(context):
    for username, chat_id in joined_users.items():  # Используем список пользователей, которые нажали Join Quiz
        try:
            context.bot.send_message(
                chat_id=chat_id,
                text="🎄 Reminder! Tomorrow is Day 2 of our 7-day holiday giveaway! 🎁✨\n\n"
                     "Don’t miss your chance to win more amazing prizes.\n\n"
                     "🕒 The fun starts at 15:00 sharp, and we’ll send you a reminder 3 minutes before "
                     "to make sure you're ready to shine! 🌟 See you there!"
            )
            logging.info(f"Reminder for next day sent to {username} (Chat ID: {chat_id})")
        except Exception as e:
            logging.error(f"Failed to send next day reminder to {username}: {e}")
    

def select_winners(context, day):
    global notified_winners_global
    wb = load_workbook(file_path)
    sheet_name = f"Day {day + 1}"
    sheet = wb[sheet_name]

    # Собираем правильные ответы только для текущего дня
    correct_users = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[3] == "Верно" and row[4] != "Winner":  # Ответ "Верно" и не отмечен как победитель
            correct_users.append(row)

    if not correct_users:
        logging.info(f"No correct answers for Day {day + 1}. No winners selected.")
    else:
        # Выбираем победителей
        if len(correct_users) > 5:
            winners = random.sample(correct_users, 5)
        else:
            winners = correct_users

        prize_message = prizes[day] if day < len(prizes) else "🎁 Today's prize will be announced later!"

        # Отправляем сообщение только победителям
        for winner in winners:
            user_id = winner[0]
            if user_id not in notified_winners_global:
                try:
                    # Отправляем сообщение победителю
                    context.bot.send_message(
                        chat_id=user_id,
                        text=f"🎉 Congratulations!\n\nYou are the winner of the day! 🏆✨\n\n🎁Your prize {prize_message}\n\n🤑Please contact your manager to claim your prize."
                    )
                    logging.info(f"Winner notification sent to user ID: {user_id}")
                    notified_winners_global.add(user_id)

                    # Обновляем запись в таблице
                    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
                        if row[0].value == user_id:  # Сравниваем user_id
                            row[len(row) - 1].value = "Winner"
                            row[len(row) - 1].fill = PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid")

                except Exception as e:
                    logging.error(f"Failed to send winner notification to user ID: {user_id}: {e}")

    # Сохраняем изменения в таблице
    wb.save(file_path)
    logging.info(f"Winners for Day {day + 1} have been recorded in the Excel sheet.")

    # Проверяем, есть ли уже активная задача для уведомления
    existing_jobs = [job.name for job in context.job_queue.jobs()]
    if "next_day_reminder" not in existing_jobs:
        # Отправляем напоминание всем, кто присоединился к викторине
        context.job_queue.run_once(
            lambda _: notify_users_about_next_day(context),
            when=5,  # Задержка в 5 секунд
            name="next_day_reminder"  # Название задачи для предотвращения дублирования
        )
    else:
        logging.warning("Reminder job for the next day already exists. Skipping duplicate scheduling.")


# Callback for participating in quiz
def participate_handler(update, context):
    query = update.callback_query
    query.answer()

    user = query.from_user
    chat_id = query.message.chat_id
    username = user.username if user.username else "Unknown"

    # Сохраняем пользователя, если он нажал Join Quiz
    if username not in joined_users:
        joined_users[username] = chat_id
        logging.info(f"User @{username} joined the quiz for the first time.")
    
    context.bot.send_message(
        chat_id=chat_id,
        text="Welcome aboard!🚀\n\nThe quiz starts sharp at 15:00 🤩.\n\nRelax for now!😎\n\nWe'll send you a reminder 3 minutes before it begins!"
    )



# Function to send quiz question
def send_daily_quiz(context, day):
    logging.info(f"Preparing to send quiz for day {day + 1}")

    if day < len(quiz_questions):
        question = quiz_questions[day]

        if not user_chat_mapping:
            logging.warning("⚠️ No users registered for the quiz. Skipping.")
            return

        for username, chat_id in user_chat_mapping.items():
            # Send the quiz question without mentioning the prize
            context.bot.send_message(
                chat_id=chat_id,
                text="⚡ Today's quiz question:"
            )
            add_quiz_question(context, question, chat_id, day)

        # Update current day
        next_day = (day + 1) % len(quiz_questions)
        context.dispatcher.bot_data['current_day'] = next_day

        # Log when the next question will be sent
        next_quiz_time = context.job_queue.jobs()[1].next_t.replace(tzinfo=None)  # Get the time for the next quiz
        logging.info(f"The next question (day {next_day + 1}) will be sent at {next_quiz_time}.")
    else:
        logging.error(f"Day {day + 1} is out of range for questions.")



# Function to notify users about the quiz
def notify_users_about_quiz(context):
    for username, chat_id in joined_users.items():  # Используем список пользователей, которые нажали Join Quiz
        try:
            context.bot.send_message(
                chat_id=chat_id,
                text="The quiz will start in 3 minutes!🔔\n\n"
                "🔥Get ready!"
            )
            logging.info(f"Reminder sent to {username} (Chat ID: {chat_id})")
        except Exception as e:
            logging.error(f"Failed to send reminder to {username}: {e}")



# Function to send quiz question to user
def add_quiz_question(context, quiz_question, chat_id, day):
    message = context.bot.send_poll(
        chat_id=chat_id,
        question=quiz_question.question,
        options=quiz_question.answers,
        type=Poll.QUIZ,
        correct_option_id=quiz_question.correct_answer_position,
        open_period=QUIZ_TIMEOUT_SECONDS,
        is_anonymous=False,
        explanation="Don't be sad"
    )
    
    # Сохраняем данные опроса
    context.bot_data.update({message.poll.id: {'chat_id': message.chat.id, 'day': day}})
    
    # Планируем таймаут
    context.job_queue.run_once(
        handle_poll_timeout,
        when=QUIZ_TIMEOUT_SECONDS,
        context={'poll_id': message.poll.id, 'day': day}
    )


# Poll answer handler
def poll_handler(update, context):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    poll_id = poll_answer.poll_id
    selected_option_id = poll_answer.option_ids[0]

    poll_data = context.bot_data.get(poll_id, {})
    day = poll_data.get('day', 0)
    question = quiz_questions[day]
    correct_option_id = question.correct_answer_position
    is_correct = (selected_option_id == correct_option_id)

    response_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    username = poll_answer.user.username if poll_answer.user.username else "Unknown"

    # Add the user to poll_participants if they are not already in it
    if poll_id not in poll_participants:
        poll_participants[poll_id] = set()
    poll_participants[poll_id].add(user_id)

    # Record the result in the table
    record_user_response(user_id=user_id, username=username, day=day, response_time=response_time, result=is_correct)

    # Send a message to the user
    if is_correct:
        context.bot.send_message(
            chat_id=user_id,
            text="🎉Congratulations, your answer is correct!\n\n🏁We will now wait for all participants to complete the game.\n\n✨After that, we will randomly select 20 winners from those who answered correctly.\n\n☘️Good luck!"
        )
    else:
        context.bot.send_message(
            chat_id=user_id,
            text="❌ Oops, that’s the wrong answer!\n\nBut don’t give up!\n\n🤗Try again tomorrow."
        )

# Check if user is authorized
def is_authorized_user(update):
    user = update.effective_user
    return user.username == SUPERADMIN_USERNAME or user.username in authorized_usernames

# Main function
def main():
    initialize_excel()

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is not set. Exiting.")
        return

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(CommandHandler("list", list_handler))
    dp.add_handler(CallbackQueryHandler(participate_handler, pattern="participate"))
    dp.add_handler(PollAnswerHandler(poll_handler))

    # Инициализация текущего дня
    dp.bot_data['current_day'] = 0  # Начинаем с 0-го дня

    # Логирование времени сервера
    logging.info(f"Current server UTC time: {datetime.now(timezone.utc)}")

    # Планирование задач
    job_queue = updater.job_queue
    # Уведомление за 5 минут до викторины
    job_queue.run_daily(
        notify_users_about_quiz,
        time=dt_time(8, 35),  # Уведомление в 14:55 по UTC
    )
    logging.info("JobQueue task for quiz notifications added at 14:55 UTC.")

    # Планирование самой викторины
    job_queue.run_daily(
        lambda context: send_daily_quiz(context, dp.bot_data['current_day']),
        time=dt_time(8, 40)  # Викторина в 15:00 по UTC
    )
    logging.info("JobQueue task for quiz scheduling added at 15:00 UTC.")
    updater.start_polling()
    logging.info("Bot started in polling mode")


logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
main()