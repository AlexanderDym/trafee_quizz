import csv
import psycopg2
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Настройка подключения к базе данных
def get_db_connection():
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except Exception as e:
        raise RuntimeError(f"Error connecting to database: {e}")

# Функция для выгрузки данных в CSV
def export_participants_to_csv(output_file):
    query = """
        SELECT id, created_at, trafee_username, name, telegram_id, telegram_username, 
               day_1_answer, day_1_prize, 
               day_2_answer, day_2_prize, 
               day_3_answer, day_3_prize, 
               day_4_answer, day_4_prize, 
               day_5_answer, day_5_prize, 
               day_6_answer, day_6_prize, 
               day_7_answer, day_7_prize, 
               final_prize
        FROM participants;
    """

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            headers = [desc[0] for desc in cur.description]

        # Запись данных в CSV
        with open(output_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)  # Заголовки
            writer.writerows(rows)   # Данные

        print(f"Participants exported successfully to {output_file}")

    except Exception as e:
        raise RuntimeError(f"Error exporting participants to CSV: {e}")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    output_csv_file = "participants_export.csv"
    export_participants_to_csv(output_csv_file)
