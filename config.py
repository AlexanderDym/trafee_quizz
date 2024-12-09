import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path('.') / 'trafee.env')


QUIZ_TIMEOUT_SECONDS = 30
csv_file_path = "registration_log.csv"
file_path = "updated_bot_list.xlsx"
gifts_file_path = "gifts.xlsx"
SUPERADMIN_USERNAME = "AlexanderDym"
