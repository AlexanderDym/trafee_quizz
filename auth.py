import logging
import csv
from config import csv_file_path, SUPERADMIN_USERNAME 


def is_authorized_user(update):
    user = update.effective_user
    username = user.username

    logging.info(f"Checking authorization for @{username}")

    if username == SUPERADMIN_USERNAME:
        logging.info(f"User @{username} is the superadmin. Access granted.")
        return True

    try:
        # Читаем CSV
        with open(csv_file_path, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)

            logging.info(f"Reading {csv_file_path} for @{username}.")

            for row in reader:
                logging.debug(f"Checking row: {row}")
                # Проверяем соответствие Telegram Username
                if len(row) > 1 and row[1] == username:
                    logging.info(f"Access granted for user @{username}")
                    return True

        logging.info(f"User @{username} not found in the list.")
    except FileNotFoundError:
        logging.warning(f"⚠️ File {csv_file_path} not found. No user authorization possible.")
    except Exception as e:
        logging.error(f"⚠️ Error reading file {csv_file_path}: {e}")

    # Если пользователь не найден
    logging.warning(f"Access denied for user @{username}")
    return False

