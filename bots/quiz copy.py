import logging
import os
from dotenv import load_dotenv
from telegram import Poll, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, PollAnswerHandler
from datetime import datetime, timezone
from datetime import datetime, time as dt_time
import random

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from db_api.connection import Database
from bots.config import file_path, SUPERADMIN_USERNAME  

load_dotenv()

FIRST_DATETIME = None
CURRNET_DAY = 1
# Timer for quiz
QUIZ_TIMEOUT_SECONDS = 30
SUPERADMIN_USERNAME = "Alexander_Dym"

database : Database = Database()


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

    # Проверка авторизации
    if not database.is_authorized_user(update):
        logging.warning(f"Unauthorized user @{username} tried to access the bot.")
        context.bot.send_message(chat_id=chat_id, text="⛔ You are not authorized to use this bot.")
        return

# TODO
    # # Check if the user has already started the bot
    # if username in user_chat_mapping:
    #     logging.warning(f"{datetime.now()} - User @{username} tried to press /start again.")
    #     context.bot.send_message(
    #         chat_id=chat_id,
    #         text="You're already in the quiz 👻\n\nThe next question will be tomorrow!\n\nDon't be sneaky 😜."
    #     )
    #     return

    # # If the user is new, add them to the dictionary
    # user_chat_mapping[username] = {"chat_id": chat_id, "joined": False}

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


def handle_poll_timeout(context):
    poll_id = context.job.context['poll_id']
    day = context.job.context['day']

    # Загружаем Excel и проверяем, кто уже записан

    # Создаём множество с ID пользователей, записанных в Excel
    recorded_users = database.get_registered_participants()

    for user in recorded_users:
        chat_id = user.telegram_id

        if database.get_participant_answer(telegram_id=str(chat_id), day=CURRNET_DAY):
            # Пользователь уже ответил, пропускаем
            logging.info(f"User {user.telegram_id} has already answered the question. Timeout skipped.")
            continue

        # Если пользователь не ответил, уведомляем и записываем результат
        try:
            context.bot.send_message(chat_id=chat_id, text="⏰ Time's up!\n\nYour response was not counted 🥵.")
        except Exception as e:
            logging.error(f"Failed to notify user {user.telegram_username} (Chat ID: {chat_id}): {e}")

    # Переходим к выбору победителей
    select_winners(context, day)



def notify_users_about_next_day(context):
   """
   Notify registered participants about the next day's quiz
   """
   try:
       # Get current day from context and calculate next day
       day = context.job.context.get('day', 0)
       next_day = (day + 1) if (day + 1) <= 7 else 1
       
       participants = database.get_registered_participants()
       
       if not participants:
           logging.warning("No registered participants found to notify about next day")
           return
           
       for participant in participants:
           try:
               context.bot.send_message(
                   chat_id=participant.telegram_id,
                   text=f"🎄 Reminder! Tomorrow is Day {next_day} of our 7-day holiday giveaway! 🎁✨\n\n"
                        "Don't miss your chance to win more amazing prizes.\n\n"
                        "🕒 The fun starts at 15:00 UTC sharp, and we'll send you a reminder 3 minutes before "
                        "to make sure you're ready to shine! 🌟 See you there!"
               )
               logging.info(f"Next day reminder sent to {participant.telegram_username} "
                          f"(Telegram ID: {participant.telegram_id})")
                          
           except Exception as e:
               logging.error(f"Failed to send next day reminder to {participant.telegram_username}: {e}")
               
   except Exception as e:
       logging.error(f"Error getting registered participants for next day notifications: {e}")


    

def select_winners(context, day):
    """
    Select winners from participants who answered correctly for the given day
    
    Args:
        context: Bot context
        day: Current quiz day (0-based index)
    """
    participants = database.get_registered_participants()
    
    # Get correct answer for this day from quiz_questions
    question = quiz_questions[day]
    correct_answer = question.correct_answer
    
    # Filter participants who answered correctly
    correct_users = []
    for participant in participants:
        # Get the answer for the specific day using dynamic field access
        day_field = f'day_{day + 1}_answer'
        participant_answer = getattr(participant, day_field, None)
        
        # Compare participant's answer with correct answer (case-insensitive)
        if participant_answer and participant_answer.strip().lower() == correct_answer.strip().lower():
            correct_users.append((
                participant.telegram_id,
                participant.telegram_username
            ))

    if not correct_users:
        logging.info(f"No correct answers for Day {day + 1}. No winners selected.")
        return
        
    # Select up to 5 random winners
    winners = random.sample(correct_users, min(5, len(correct_users)))
    
    # Distribute gifts to winners
    try:
        database.distribute_gifts_to_participants(day + 1, winners)
        logging.info(f"Gifts distributed to {len(winners)} winners for Day {day + 1}")
    except Exception as e:
        logging.error(f"Error distributing gifts for Day {day + 1}: {str(e)}")

    # Schedule next day reminder
    context.job_queue.run_once(
        notify_users_about_next_day,
        when=5,
        context={'day': day + 1}
    )
    logging.info(f"Reminder for next day scheduled in 5 seconds.")



# Callback for participating in quiz
def participate_handler(update, context):
    query = update.callback_query
    query.answer()

    user = query.from_user
    username = user.username if user.username else "Unknown"

    # Проверка авторизации
    if not database.is_authorized_user(update):
        logging.warning(f"Unauthorized user @{username} tried to join the quiz.")
        query.edit_message_text(text="⛔ You are not authorized to join this quiz.")
        return

    # Проверка: если пользователь уже нажимал Join Quiz
    # if user_chat_mapping.get(username, {}).get("joined"):
    #     logging.info(f"User @{username} tried to join the quiz again.")
    #     query.edit_message_text(text="You are already in the quiz! 🚀")
    #     return

    # Отметить пользователя как присоединившегося
    # user_chat_mapping[username] = {
    #     "chat_id": query.message.chat_id,
    #     "joined": True
    # }
    # logging.info(f"User @{username} joined the quiz for the first time.")
    query.edit_message_text(text="Welcome to the quiz! 🎉")


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


def send_daily_quiz(context, day: int) -> None:
    global CURRNET_DAY
    """
    Send daily quiz questions to all registered participants
    
    Args:
        context: Telegram bot context
        day (int): Current quiz day (0-based index)
    """
    logging.info(f"Preparing to send quiz for day {day}")
    
    try:
        # Validate day and questions
        if day >= len(quiz_questions):
            logging.error(f"Day {day} is out of range for questions")
            return
            
        # Get participants from database
        participants = database.get_registered_participants()
        if not participants:
            logging.warning("⚠️ No participants registered for the quiz. Skipping.")
            return
            
        # Get current day's question
        question = quiz_questions[day]
        
        # Send question to each participant
        for participant in participants:
            if not participant.telegram_id:
                logging.warning(f"No telegram_id for participant {participant.trafee_username}. Skipping.")
                continue
                
            try:
                # Send intro message
                context.bot.send_message(
                    chat_id=participant.telegram_id,
                    text="⚡ Today's quiz question:"
                )
                
                # Send actual question (assuming this function exists)
                add_quiz_question(context=context,quiz_question=question,chat_id=participant.telegram_id,day=day)
                
                logging.info(f"Quiz sent to participant {participant.trafee_username} "
                           f"(Telegram ID: {participant.telegram_id})")
                           
            except Exception as e:
                logging.error(f"Failed to send quiz to {participant.trafee_username}: {str(e)}")
        
        # Update current day
        CURRNET_DAY += 1
        
    except Exception as e:
        logging.error(f"Error in send_daily_quiz: {str(e)}")




def notify_users_about_quiz(context):
    """
    Send quiz reminder notification to all registered participants
    """
    try:
        participants = database.get_registered_participants()
        
        if not participants:
            logging.warning("No registered participants found to notify")
            return
            
        for participant in participants:
            try:
                context.bot.send_message(
                    chat_id=participant.telegram_id,
                    text="The quiz will start in 5 minutes!🔔\n\n"
                        "🔥Get ready!"
                )
                logging.info(f"Reminder sent to {participant.telegram_username} "
                            f"(Telegram ID: {participant.telegram_id})")
                            
            except Exception as e:
                logging.error(f"Failed to send reminder to {participant.telegram_username}: {e}")
                
    except Exception as e:
        logging.error(f"Error getting registered participants for notifications: {e}")



# Poll answer handler
async def poll_handler(update: Update, context) -> None:
   """Handle quiz poll answers from users"""
   try:
       # Get answer info from update
       answer = update.poll_answer
       if not answer or not answer.option_ids:
           logging.error("Invalid poll answer update")
           return
           
       user_id = str(answer.user.id)
       poll_id = answer.poll_id
       selected_option_id = answer.option_ids[0]

       # Get poll data and validate
       poll_data = context.bot_data.get(poll_id, {})
       day = poll_data.get('day', 0)
       if day >= len(quiz_questions):
           logging.error(f"Invalid day {day} for poll {poll_id}")
           return
           
       # Check if answer is correct
       question = quiz_questions[day]
       is_correct = (selected_option_id == question.correct_answer_position)

       # Log the response
       logging.info(f"Poll answer received. User: {user_id}, Poll ID: {poll_id}, "
                   f"Selected Option: {selected_option_id}, Correct: {is_correct}")

       # Record in database
       answer_text = question.answers[selected_option_id]
       if not database.save_participant_response_to_db(telegram_id=user_id, day=day, answer=answer_text):
           logging.error(f"Failed to record response for user {user_id}")
           return

       # Send feedback message
       message = (
           "🎉 Congratulations, your answer is correct!\n\n"
           "🏁 We will now wait for all participants to complete the game.\n\n"
           "✨ After that, we will randomly select 20 winners from those who answered correctly.\n\n"
           "☘️ Good luck!"
       ) if is_correct else (
           "❌ Oops, that's the wrong answer!\n\nBut don't give up!\n\n🤗 Try again tomorrow."
       )
       
       await context.bot.send_message(chat_id=user_id, text=message)
       
   except Exception as e:
       logging.error(f"Error in poll_handler: {str(e)}")





# Main function
def main():
    TELEGRAM_TOKEN = os.getenv("QUIZ_TOKEN")
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is not set. Exiting.")
        return

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(CommandHandler("list", list_handler))
    dp.add_handler(CallbackQueryHandler(participate_handler, pattern="participate"))
    dp.add_handler(PollAnswerHandler(poll_handler))

    # Логирование времени сервера
    logging.info(f"Current server UTC time: {datetime.now(timezone.utc)}")

    # Планирование задач
    job_queue = updater.job_queue
    # Уведомление за 5 минут до викторины
    job_queue.run_daily(
        notify_users_about_quiz,
        time=dt_time(0, 11),  # Уведомление в 14:55 по UTC
    )
    logging.info("JobQueue task for quiz notifications added at 14:55 UTC.")

    # Планирование самой викторины
    job_queue.run_daily(
        lambda context: send_daily_quiz(context, CURRNET_DAY),
        time=dt_time(0, 12)  # Викторина в 15:00 по UTC
    )
    logging.info("JobQueue task for quiz scheduling added at 15:00 UTC.")
    updater.start_polling()
    logging.info("Bot started in polling mode")


logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
main()