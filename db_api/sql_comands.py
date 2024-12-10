import os
import psycopg2
from psycopg2.extensions import connection
from typing import Optional
import psycopg2.extras
import json
from dotenv import load_dotenv

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from db_api.models import Gift

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS participants (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    trafee_username VARCHAR UNIQUE,
    name VARCHAR,
    telegram_id VARCHAR,
    telegram_username VARCHAR,
    
    day_1_answer BOOLEAN,
    day_1_prize VARCHAR,
    
    day_2_answer BOOLEAN,
    day_2_prize VARCHAR,
    
    day_3_answer BOOLEAN,
    day_3_prize VARCHAR,
    
    day_4_answer BOOLEAN,
    day_4_prize VARCHAR,
    
    day_5_answer BOOLEAN,
    day_5_prize VARCHAR,
    
    day_6_answer BOOLEAN,
    day_6_prize VARCHAR,
    
    day_7_answer VARCHAR,
    day_7_prize VARCHAR,
    
    final_prize VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_trafee_username ON participants(trafee_username);
"""

CREATE_GIFT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS gifts (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    day_1_quantity INTEGER DEFAULT 0,
    day_2_quantity INTEGER DEFAULT 0,
    day_3_quantity INTEGER DEFAULT 0,
    day_4_quantity INTEGER DEFAULT 0,
    day_5_quantity INTEGER DEFAULT 0,
    day_6_quantity INTEGER DEFAULT 0,
    day_7_quantity INTEGER DEFAULT 0,
    remain INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_gift_name ON gifts(name);
"""

TRUNCATE_TABLE_SQL = "TRUNCATE TABLE participants RESTART IDENTITY;"
DROP_TABLE_SQL = "DROP TABLE IF EXISTS participants;"

TRUNCATE_GIFT_TABLE_SQL = "TRUNCATE TABLE gifts RESTART IDENTITY;"
DROP_GIFT_TABLE_SQL = "DROP TABLE IF EXISTS gifts;"

load_dotenv()

def get_db_connection() -> connection:
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise

def clear_table(conn: Optional[connection] = None) -> bool:
    """Delete all records from the reservations table but keep the structure"""
    should_close_conn = conn is None
    try:
        if conn is None:
            conn = get_db_connection()
        
        cur = conn.cursor()
        cur.execute(TRUNCATE_TABLE_SQL)
        conn.commit()
        print("Successfully cleared all records from reservations table")
        return True
        
    except Exception as e:
        print(f"Error clearing table: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if should_close_conn and conn:
            conn.close()

def clear_gifts_table(conn: Optional[connection] = None) -> bool:
    """Delete all records from the reservations table but keep the structure"""
    should_close_conn = conn is None
    try:
        if conn is None:
            conn = get_db_connection()
        
        cur = conn.cursor()
        cur.execute(TRUNCATE_GIFT_TABLE_SQL)
        conn.commit()
        print("Successfully cleared all records from reservations table")
        return True
        
    except Exception as e:
        print(f"Error clearing table: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if should_close_conn and conn:
            conn.close()

def reset_table(conn: Optional[connection] = None) -> bool:
    """Drop and recreate the reservations table"""
    should_close_conn = conn is None
    try:
        if conn is None:
            conn = get_db_connection()
            
        cur = conn.cursor()
        cur.execute(DROP_TABLE_SQL)
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("Successfully reset participants table")
        return True
        
    except Exception as e:
        print(f"Error resetting table: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if should_close_conn and conn:
            conn.close()


def reset_gift_table(conn: Optional[connection] = None) -> bool:
    """Drop and recreate the gifts table"""
    should_close_conn = conn is None
    try:
        if conn is None:
            conn = get_db_connection()
            
        cur = conn.cursor()
        cur.execute(DROP_GIFT_TABLE_SQL)
        cur.execute(CREATE_GIFT_TABLE_SQL)
        conn.commit()
        print("Successfully reset gifts table")
        return True
        
    except Exception as e:
        print(f"Error resetting table: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if should_close_conn and conn:
            conn.close()


def fill_participants_from_json(json_file_path: str, conn: Optional[connection] = None) -> bool:
    """
    Fill the participants table with data from a JSON file containing trafee usernames.
    
    Args:
        json_file_path (str): Path to the JSON file containing list of trafee usernames
        conn (Optional[connection]): Database connection object. If None, creates new connection
        
    Returns:
        bool: True if operation was successful, False otherwise
        
    The JSON file should be in the format:
    {
        "participants": [
            {"trafee_username": "user1"},
            {"trafee_username": "user2"},
            ...
        ]
    }
    """
    should_close_conn = conn is None
    try:
        # Create connection if not provided
        if conn is None:
            conn = get_db_connection()
            
        # Read JSON file
        with open(json_file_path, 'r') as file:
            data = json.load(file)
            
        if not isinstance(data, dict) or 'participants' not in data:
            raise ValueError("JSON file must contain a 'participants' key with list of usernames")
            
        participants = data['participants']
        if not participants:
            print("Warning: Empty participants list in JSON file")
            return True
            
        # Prepare data for insertion
        insert_data = []
        
        for participant in participants:
            if not isinstance(participant, dict) or 'trafee_username' not in participant:
                print(f"Warning: Skipping invalid participant entry: {participant}")
                continue
                
            username = participant['trafee_username']
            if not username:
                print("Warning: Skipping empty username")
                continue
                
            insert_data.append({
                'trafee_username': username,
            })
        
        if not insert_data:
            print("No valid participants to insert")
            return True
            
        # Perform bulk insert
        cur = conn.cursor()
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO participants (trafee_username)
            VALUES %s
            ON CONFLICT (trafee_username) DO NOTHING
            """,
            [(d['trafee_username'], ) for d in insert_data]
        )
        
        conn.commit()
        print(f"Successfully inserted {len(insert_data)} participants")
        return True
        
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in file: {e}")
        return False
    except Exception as e:
        print(f"Error filling table from JSON: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if should_close_conn and conn:
            conn.close()



def fill_gifts_from_list(gifts_list: list[Gift], conn: Optional[connection] = None) -> bool:
    """
    Fill the gifts table with data from a list of Gift objects.
    
    Args:
        gifts_list (List[Gift]): List of Gift objects containing gift information
        conn (Optional[connection]): Database connection object. If None, creates new connection
        
    Returns:
        bool: True if operation was successful, False otherwise
    """
    should_close_conn = conn is None
    try:
        # Create connection if not provided
        if conn is None:
            conn = get_db_connection()
            
        if not gifts_list:
            print("Warning: Empty gifts list")
            return True
            
        # Prepare data for insertion
        insert_data = []
        
        for gift in gifts_list:
            if not gift.name:
                print("Warning: Skipping gift with empty name")
                continue
                
            insert_data.append({
                'name': gift.name,
                'day_1_quantity': gift.day_1_quantity,
                'day_2_quantity': gift.day_2_quantity,
                'day_3_quantity': gift.day_3_quantity,
                'day_4_quantity': gift.day_4_quantity,
                'day_5_quantity': gift.day_5_quantity,
                'day_6_quantity': gift.day_6_quantity,
                'day_7_quantity': gift.day_7_quantity,
                'remain' : gift.remain,
            })
        
        if not insert_data:
            print("No valid gifts to insert")
            return True
            
        # Perform bulk insert
        cur = conn.cursor()
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO gifts (
                name,
                day_1_quantity, day_2_quantity, day_3_quantity,
                day_4_quantity, day_5_quantity, day_6_quantity,
                day_7_quantity, remain
            )
            VALUES %s
            """,
            [(
                d['name'],
                d['day_1_quantity'], d['day_2_quantity'], d['day_3_quantity'],
                d['day_4_quantity'], d['day_5_quantity'], d['day_6_quantity'],
                d['day_7_quantity'], d['remain']
            ) for d in insert_data]
        )

        conn.commit()
        print(f"Successfully inserted/updated {len(insert_data)} gifts")
        return True
        
    except Exception as e:
        print(f"Error filling gifts table: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if should_close_conn and conn:
            conn.close()


if __name__ == "__main__":
    # Example usage
    try:
        conn = get_db_connection()
        
        # Choose one of these operations:
        clear_table(conn)  # Just delete all records
        reset_table(conn)  # Drop and recreate table
        fill_participants_from_json('participants.json',conn)  # Drop and recreate table

        clear_gifts_table()
        reset_gift_table()

        gifts = [
            Gift("Amazon Gift Card or Yandex Gift Card",                quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("Google Gift Card",                                    quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("Netflix 1 month or Amediateka Subscription 3 month",  quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("YouTube Premium for 3 month or Yandex plus",          quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("Telegram Subscription for 3 month",                   quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("Telegram Subscription 1year",                         quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("Spotify Premium 3 month/ yandex музыка",              quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("VPN Subscription 1year",                              quantities=[1, 1, 1, 1, 1, 1, 1]),
            Gift("Trafee Bonus",                                        quantities=[1, 1, 1, 1, 1, 1, 1])
        ]
        fill_gifts_from_list(gifts)
        
    except Exception as e:
        print(f"Operation failed: {e}")