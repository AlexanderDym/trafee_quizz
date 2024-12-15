import logging
import os
from dotenv import load_dotenv
from telegram import Poll, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler
)
from datetime import datetime, time, timedelta, timezone
import random
from time import sleep

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from db_api.connection import Database
from db_api import models
from bots.config import file_path, SUPERADMIN_USERNAME

load_dotenv()

FIRST_DATETIME = None
CURRNET_DAY = 1 
QUIZ_TIMEOUT_SECONDS = 30
SUPERADMIN_USERNAME = "Alexander_Dym"

database: Database = Database()


# Class for quiz questions
class QuizQuestion:
    def __init__(self, question, answers, correct_answer):
        self.question = question
        self.answers = answers
        self.correct_answer = correct_answer
        self.correct_answer_position = self.__get_correct_answer_position__()

    def __get_correct_answer_position__(self):
        for index, answer in enumerate(self.answers):
            if answer.strip().lower() == self.correct_answer.strip().lower():
                return index
        return -1

# Quiz questions for 7 days
quiz_questions = [
    QuizQuestion("What's the goal of creatives before Сhristmas? 🎅🎁", ["Cut ad costs for a bigger holiday feast 🍗", "Attract attention with festive deals 🎆", "Boost site performance for holiday orders 🎁"], "Attract attention with festive deals 🎆"),
    QuizQuestion("What page do users land on after clicking a holiday ad? 🎁🎄", ["The homepage, where magical gifts await 🎁🎄", "An ad banner with a festive ribbon 🎀", "A landing page with a shiny offer 🦌"], "A landing page with a shiny offer 🦌"),
    QuizQuestion("What's the magic number that shows how much you earn from one visitor? 🎅💰", ["EPC (Earnings Per Click)", "CTR (Click-Through Rate)", "CPA (Cost Per Action)"], "EPC (Earnings Per Click)"),
    QuizQuestion("What's an offer? 🎄🎅", ["A call-to-action like Hurry, grab the gifts! 🎁", "A product or service the advertiser pays for", "A festive Santa card creative ❄️"], "A product or service the advertiser pays for"),
    QuizQuestion("Which ad format often pops up like a surprise? 🎄🎁", ["Pop-up, like a little Christmas gift 🎁", "Banner, like festive Christmas lights ✨", "Video, with Santa’s holiday greetings 🎅🎥"], "Pop-up, like a little Christmas gift 🎁"),
    QuizQuestion("Which strategy finds the most magical ad this holiday season? 🎅🎄", ["Scaling up", "A/B testing", "Automation"], "RA/B testing"),
    QuizQuestion("Which social network is the affiliate marketer's fave for festive short videos? 🎥✨", ["Facebook", "TikTok", "Pinterest"], "TikTok"),
]


def distribute_gifts_to_participants(
    day: int, 
    participants: list[models.Participant],
    available_gifts: list[models.Gift]
) -> tuple[list[models.Participant], list[models.Gift]]:
    """
    Distribute available gifts for a specific day to participants.
    Number of gifts equals number of winners, distributes them randomly.
    
    Args:
        day (int): Day number (1-7)
        participants (List[Participant]): List of participants to receive gifts
        available_gifts (List[Gift]): List of available gifts for the day
            
    Returns:
        List[Participant]: List of updated participants with assigned gifts
    """
    # Validate day input
    if not 1 <= day <= 7:
        logging.error(f"Invalid day number: {day}, must be between 1 and 7")
        return ()
    
    if not available_gifts or not participants:
        logging.error(f"No gifts or participants available for day {day}")
        return ()
        
    # Create list of gift names and shuffle them
    gift_names = [gift.name for gift in available_gifts]
    updated_gifts = []
    random.shuffle(gift_names)
    
    # Distribute gifts
    day_prize_column = f"day_{day}_prize"
    
    for participant, gift_name in zip(participants, gift_names):
        setattr(participant, day_prize_column, gift_name)
        logging.info(f"{gift_name} goes to {participant.telegram_username}!")

        day_gift_column = f"day_{day}_quantity"
        for gift in available_gifts:
            if gift.name == gift_name:
                current_quantity_for_day = getattr(gift, day_gift_column) - 1
                setattr(gift, day_gift_column, current_quantity_for_day)

                ramain_gifts = getattr(gift, 'remain') - 1
                setattr(gift, 'remain', ramain_gifts)
                updated_gifts.append(gift)

    logging.info(f"Successfully distributed {len(participants)} gifts for day {day}")
    return participants, updated_gifts


# def handle_poll_timeout_for_user(context):
#     """
#     Handle timeout for individual users who haven't answered the quiz
#     """
#     global CURRNET_DAY
#     recorded_users = database.get_registered_participants()

#     for user in recorded_users:
#         chat_id = user.telegram_id

#         user_answer = getattr(user, f'day_{CURRNET_DAY}_answer')

#         if isinstance(user_answer, bool):
#             logging.info(f"User {user.telegram_id} has already answered the question. Timeout skipped.")
#             continue

#         try:
#             context.bot.send_message(
#                 chat_id=chat_id, 
#                 text="⏰ Time's up!\n\nYour response was not counted 🥵."
#             )
#         except Exception as e:
#             logging.error(f"Failed to notify user {user.telegram_username} (Chat ID: {chat_id}): {e}")


def process_answers(context):
    """
    Process all answers after quiz timeout, select winners, and distribute gifts
    """
    global CURRNET_DAY
    sleep(15)
    try:
        recorded_users = database.get_registered_participants()

        correct_users = []
        no_response_users = []
        for user in recorded_users:
            chat_id = user.telegram_id
            user_answer = getattr(user, f'day_{CURRNET_DAY}_answer')

            # Обработка строковых значений в ответах
            if isinstance(user_answer, str):
                user_answer = True if (user_answer == 'true') or (user_answer == 'True') else False
                setattr(user, f'day_{CURRNET_DAY}_answer', user_answer)

            if isinstance(user_answer, bool) and user_answer:
                correct_users.append(user)
            elif user_answer is None:  # Пользователь не дал ответа
                no_response_users.append(user)

        # Уведомление пользователей, которые не ответили
        for user in no_response_users:
            try:
                context.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo="https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/times_is_up.png",  # URL картинки
                    caption="⏰ Time's up!\n\nYour response was not counted 🥵."
                )
                logging.info(f"Notified user {user.telegram_username} about timeout.")
            except Exception as e:
                logging.error(f"Failed to notify user {user.telegram_username} about timeout: {e}")

        # Проверка наличия доступных подарков
        available_gifts_for_day = database.get_available_gifts(day=CURRNET_DAY)
        if not available_gifts_for_day:
            logging.error(f"No available gifts for day {CURRNET_DAY}")
            return

        # Выбор победителей
        winners = select_winners(availble_gifts=available_gifts_for_day)

        # Распределение подарков
        updated_winners, updated_gifts = distribute_gifts_to_participants(
            day=CURRNET_DAY, 
            participants=winners, 
            available_gifts=available_gifts_for_day
        )

        # Сохранение победителей и уведомление их
        if updated_winners:
            database.batch_update_participants(updated_winners)
            database.batch_update_gifts(updated_gifts)
            notify_winners(context=context, winners=updated_winners)
            logging.info(f"Successfully processed answers and distributed gifts for day {CURRNET_DAY}")

        # Исключаем победителей из списка non_winners

        winner_ids = {winner.telegram_id for winner in winners}
        non_winners = [participant for participant in correct_users if participant.telegram_id not in winner_ids]

        # Уведомление тех, кто ответил правильно, но не выиграл
        for participant in non_winners:
            try:
                context.bot.send_photo(
                    chat_id=participant.telegram_id,
                    photo="https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/ohhh_no.png",  # URL картинки
                    caption="Thank you for participating! 😊\n\n"
                            "☹️ Unfortunately, you were not among today’s winners.\n"
                            "🎁 But there are more prizes to win in the upcoming days. Don’t miss out!"
                )
                logging.info(f"Notified non-winning participant @{participant.telegram_username}")
            except Exception as e:
                logging.error(f"Failed to notify non-winning participant @{participant.telegram_username}: {e}")

    except Exception as e:
        logging.error(f"Error processing answers for day {CURRNET_DAY}: {str(e)}")
    finally:
        CURRNET_DAY += 1
        logging.info(f"CURRENT_DAY incremented to {CURRNET_DAY}")








def notify_users_about_next_day(context):

    if CURRNET_DAY >= 8:
        return
    
    try:
        participants = database.get_registered_participants()
        
        if not participants:
            logging.warning("No registered participants found to notify about next day")
            return
            
        for participant in participants:
            try:
                # Отправка изображения напрямую по URL
                context.bot.send_photo(
                    chat_id=participant.telegram_id,
                    photo="https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/remind_next_day.png",
                    caption=f"🎄 Reminder!\n\nTomorrow is Day {CURRNET_DAY} of our 7-day holiday giveaway! 🎁✨\n\n"
                            "🎊 Don't miss your chance to win more amazing prizes.\n\n"
                            "🕒 The fun starts at 15:00 UTC sharp!"
                )
            except Exception as e:
                logging.error(f"Failed to send next day reminder to {participant.telegram_username}: {e}")
                
    except Exception as e:
        logging.error(f"Error in notify_users_about_next_day: {str(e)}")




def notify_users_about_final(context):
    try:
        participants = database.get_registered_participants()
        
        if not participants:
            logging.warning("No registered participants found to notify about final day")
            return
            
        for participant in participants:
            try:
                # Отправка изображения с сообщением
                context.bot.send_photo(
                    chat_id=participant.telegram_id,
                    photo="https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/final_img.png",  # URL картинки
                    caption="🎄✨ FINAL 🎄✨\n\n"
                            "Thank you all for participating this quiz🧡\n\n"
                            "On December 24th, we’ll announce the lucky winners on our Telegram channel👇\n\nhttps://t.me/TrafeeCPA\n\n"
                            "Three winners will each receive a PS5 🤯!\n\n"  "Subscribe now not to miss it! 🥳"
                )
            except Exception as e:
                logging.error(f"Failed to send final reminder to {participant.telegram_username}: {e}")
                
    except Exception as e:
        logging.error(f"Error in notify_users_about_final: {str(e)}")


def select_winners(availble_gifts:list) -> list[models.Participant]:
    day_column = f"day_{CURRNET_DAY}_quantity"
    gift_pool = []
    for gift in availble_gifts:
        quantity = getattr(gift, day_column)
        gift_pool.extend([gift.name] * quantity)

    logging.info(f"Selecting winners for Day {CURRNET_DAY}. Available gifts: {len(availble_gifts)}")
    participants = database.get_registered_participants()
    
    correct_users = []
    for participant in participants:
        day_field = f'day_{CURRNET_DAY}_answer'
        participant_answer = getattr(participant, day_field, None)

        if isinstance(participant_answer, str):
            participant_answer = True if (participant_answer=='true') or (participant_answer=='True') else False
            setattr(participant, f'day_{CURRNET_DAY}_answer', participant_answer)
        
        if isinstance(participant_answer, bool) and participant_answer == True:
            correct_users.append(participant)

    if not correct_users:
        logging.info(f"No correct answers for Day {CURRNET_DAY}. No winners selected.")
        return []
        
    winners = random.sample(correct_users, min(len(availble_gifts), len(correct_users)))
    return winners

def add_quiz_question(context, quiz_question, chat_id, day):
    poll_message = context.bot.send_poll(
        chat_id=chat_id,
        question=quiz_question.question,
        options=quiz_question.answers,
        type=Poll.QUIZ,
        correct_option_id=quiz_question.correct_answer_position,
        open_period=QUIZ_TIMEOUT_SECONDS,
        is_anonymous=False,
        explanation="Don't be sad"
    )
    return poll_message

def send_daily_quiz(context) -> None:
    global CURRNET_DAY
    logging.info(f"Preparing to send quiz for day {CURRNET_DAY}")
    
    try:
        if CURRNET_DAY-1 >= len(quiz_questions):
            logging.error(f"Day {CURRNET_DAY} is out of range for questions")
            return
            
        participants = database.get_registered_participants()
        if not participants:
            logging.warning("⚠️ No participants registered for the quiz. Skipping.")
            return
            
        question = quiz_questions[CURRNET_DAY-1]
        
        for participant in participants:
            if not participant.telegram_id:
                logging.warning(f"No telegram_id for participant {participant.trafee_username}. Skipping.")
                continue
                
            try:
                context.bot.send_message(
                    chat_id=participant.telegram_id,
                    text="⚡ Today's quiz question:"
                )
                
                poll_message = add_quiz_question(
                    context=context,
                    quiz_question=question,
                    chat_id=participant.telegram_id,
                    day=CURRNET_DAY
                )

            except Exception as e:
                logging.error(f"Failed to send quiz to {participant.trafee_username}: {str(e)}")

        # After all quizes handle_poll_timeout_for_user done
        context.job_queue.run_once(
            process_answers,
            when=QUIZ_TIMEOUT_SECONDS + 10,  # Run slightly after individual timeouts
            context={'day': CURRNET_DAY}
        )
        
    except Exception as e:
        logging.error(f"Error in send_daily_quiz: {str(e)}")

def notify_winners(context, winners: list[models.Participant]) -> None:
    """
    Send notification messages to quiz winners informing them of their prizes.
    
    Args:
        context: The telegram bot context containing the bot instance
        winners: List of Participant objects who won prizes
    """
    global CURRNET_DAY
    
    if not winners:
        logging.info("No winners to notify")
        return
        
    try:
        for winner in winners:
            if not winner.telegram_id:
                logging.warning(f"No telegram_id for winner {winner.trafee_username}. Skipping notification.")
                continue
                
            prize = getattr(winner, f'day_{CURRNET_DAY}_prize', None)
            if not prize:
                logging.warning(f"No prize found for winner {winner.telegram_username} on day {CURRNET_DAY}")
                continue
                
            try:
                # Отправка сообщения с изображением
                context.bot.send_photo(
                    chat_id=winner.telegram_id,
                    photo="https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/winner_img.png",  # URL картинки
                    caption=(
                        f"🎉 Congratulations! You're a winner of Day {CURRNET_DAY}'s quiz! 🏆\n\n"
                        f"🎁 Your prize: {prize}\n\n"
                        "Our team will contact you with your prize details.\n\n"
                    )
                )
                
                logging.info(f"Successfully notified winner {winner.telegram_username} about prize {prize}")
                
            except Exception as e:
                logging.error(f"Failed to send winner notification to {winner.telegram_username}: {str(e)}")
                
    except Exception as e:
        logging.error(f"Error in notify_winners: {str(e)}")




def notify_users_about_quiz(context):
    """
    Send quiz reminder notification to all registered participants
    """
    try:
        if CURRNET_DAY >= 8:
            sys.exit()

        participants = database.get_registered_participants()
        
        if not participants:
            logging.warning("No registered participants found to notify")
            return
            
        for participant in participants:
            try:
                # Отправка изображения с текстом
                context.bot.send_photo(
                    chat_id=participant.telegram_id,
                    photo="https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/5_min_reminder.png",  # URL картинки
                    caption="The quiz will start in 5 minutes! 🔔\n\n"
                            "🔥 Get ready!"
                )
                logging.info(f"Reminder sent to {participant.telegram_username} "
                             f"(Telegram ID: {participant.telegram_id})")
                            
            except Exception as e:
                logging.error(f"Failed to send reminder to {participant.telegram_username}: {e}")
                
    except Exception as e:
        logging.error(f"Error getting registered participants for notifications: {e}")



# def notify_users_about_next_day(context):
#     """
#     Send quiz reminder notification to all registered participants
#     """
#     try:
#         participants = database.get_registered_participants()
        
#         if not participants:
#             logging.warning("No registered participants found to notify")
#             return
            
#         for participant in participants:
#             try:
#                 context.bot.send_message(
#                     chat_id=participant.telegram_id,
#                     text="NEXT QUIZ SOON!🔥🔔🔥\n\n"
#                 )
#                 logging.info(f"Reminder sent to {participant.telegram_username} "
#                             f"(Telegram ID: {participant.telegram_id})")
                            
#             except Exception as e:
#                 logging.error(f"Failed to send reminder to {participant.telegram_username}: {e}")
                
#     except Exception as e:
#         logging.error(f"Error getting registered participants for notifications: {e}")


def poll_handler(update: Update, context) -> None:
    """Handle quiz poll answers from users"""
    try:
        answer = update.poll_answer
        if not answer or not answer.option_ids:
            logging.error("Invalid poll answer update")
            return
            
        user_id = str(answer.user.id)
        poll_id = answer.poll_id
        selected_option_id = answer.option_ids[0]

        poll_data = context.bot_data.get(poll_id, {})
        if CURRNET_DAY - 1 >= len(quiz_questions):
            logging.error(f"Invalid day {CURRNET_DAY} for poll {poll_id}")
            return
            
        question = quiz_questions[CURRNET_DAY - 1]
        is_correct = bool(selected_option_id == question.correct_answer_position)

        save_response_res = database.save_participant_response_to_db(
            telegram_id=user_id, day=CURRNET_DAY, answer_is_correct=is_correct
        )
        if not save_response_res:
            logging.error(f"Failed to record response for user {user_id}")
            return

        if is_correct:
            message = (
                "🎉 Yeah, your answer is correct!\n\n"
                "🏁 We will now wait for all participants to complete the game.\n\n"
                "✨ After that, we will randomly select a number of winners from those who answered correctly.\n\n"
                "☘️ Good luck!"
            )
            image_url = "https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/correct.png"
        else:
            message = (
                "❌ Oops, that's the wrong answer!\n\n"
                "But don't give up!\n\n"
                "🤗 Try again next time."
            )
            image_url = "https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/wrong.png"

        # Отправляем сообщение с картинкой
        context.bot.send_photo(
            chat_id=user_id,
            photo=image_url,
            caption=message
        )
        
    except Exception as e:
        logging.error(f"Error in poll_handler: {str(e)}")


def start_command_handler(update, context):
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username if user.username else "Unknown"

    # Authorization check
    if not database.is_authorized_user(update):
        logging.warning(f"Unauthorized user @{username} tried to access the bot.")
        context.bot.send_message(chat_id=chat_id, text="⛔ You are not authorized to use this bot.")
        return

    # Message text and image URL
    text_message = (
        "🎉 The quiz has started!\n\n"
        "The question will appear at \n15:00 UTC ⏰\n\n"
        "📢 Don’t worry, we’ll send you a reminder 5 minutes before the quiz starts!"
    )
    image_url = "https://mailer.ucliq.com/wizz/frontend/assets/files/customer/kd629xy3hj208/Trafee_quiz/start_img.png"

    # Send photo with text message
    context.bot.send_photo(
        chat_id=chat_id,
        photo=image_url,
        caption=text_message
    )

    # Logging
    logging.info(f"Sent quiz start message with image to @{username}")


    
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

def main():
    TELEGRAM_TOKEN = os.getenv("QUIZ_TOKEN")
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is not set. Exiting.")
        return

    try:
        updater = Updater(TELEGRAM_TOKEN, use_context=True)
        dp = updater.dispatcher

        # Add handlers
        dp.add_handler(CommandHandler("start", start_command_handler))
        dp.add_handler(CommandHandler("list", list_handler))
        dp.add_handler(CallbackQueryHandler(participate_handler, pattern="participate"))
        dp.add_handler(PollAnswerHandler(poll_handler))

        # Log server time
        datetime_now = datetime.now(timezone.utc)
        logging.info(f"Current server UTC time: {datetime_now}")

        # Schedule jobs
        job_queue = updater.job_queue

        # Начальная дата и время первого дня
        start_date = datetime(2024, 12, 15, 10, 30, tzinfo=timezone.utc)
        end_date = datetime(2024, 12, 23, 14, 1, tzinfo=timezone.utc)
        current_date = start_date

        while current_date <= end_date:
            day_number = (current_date - start_date).days + 1

            # Напоминание за 5 минут до квиза
            job_queue.run_once(
                notify_users_about_quiz,
                when=current_date - timedelta(minutes=5)
            )

            # Квиз
            job_queue.run_once(
                send_daily_quiz,
                when=current_date
            )

            # Напоминание о следующем дне через 90 секунд после квиза
            job_queue.run_once(
                notify_users_about_next_day,
                when=current_date + timedelta(seconds=90)
            )

            logging.info(f"Scheduled quiz for Day {day_number} on {current_date.isoformat()}")
            current_date += timedelta(days=1)  # Следующий день

        # Напоминание о финале после последнего дня квиза
        job_queue.run_once(
            notify_users_about_final,
            when=end_date + timedelta(seconds=50)  # Отправить через 50 секунд после конца последнего дня
        )

        logging.info("Scheduled final reminder after the last quiz day")

        # Start the bot with error handling
        logging.info("Starting bot...")
        updater.start_polling()
        logging.info("Bot started successfully!")

    except Exception as e:
        logging.error(f"Error starting bot: {str(e)}")

        logging.error(f"Error starting bot: {str(e)}")


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# main()