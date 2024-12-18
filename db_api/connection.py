from typing import Generator, Optional, List
from contextlib import contextmanager
import os
from datetime import datetime, date, time, timedelta
import pytz
from urllib.parse import urlparse
import pandas as pd
from sqlalchemy import create_engine, event, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import logging
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential
import random

from dotenv import load_dotenv

load_dotenv()

SUPERADMIN_USERNAME = "Alexander_Dym"


from db_api import models
# from tg_bot.config import places, workday_start, workday_end, LOCAL_TIMEZONE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    def __init__(self):
        self.database_url = self._get_database_url()
        self.pool_settings = {
            'pool_size': int(os.getenv("DB_POOL_SIZE", "10")),
            'max_overflow': int(os.getenv("DB_MAX_OVERFLOW", "20")),
            'pool_timeout': int(os.getenv("DB_POOL_TIMEOUT", "30")),
            'pool_recycle': int(os.getenv("DB_POOL_RECYCLE", "1800")),
            'pool_pre_ping': True
        }
        self.workday_settings = {
            'workday_start': int(os.getenv("WORKDAY_START", "9")),
            'workday_end': int(os.getenv("WORKDAY_END", "21")),
            'time_buffer': int(os.getenv("TIME_BUFFER", "30")),
            'lookforward_days': int(os.getenv("LOOKFORWARD_DAYS", "30"))
        }
        
    def _get_database_url(self) -> str:
        url = os.getenv("DATABASE_URL")
        if not url:
            url = self._construct_db_url()
        
        if url and "internal" in url:
            url = os.getenv("EXTERNAL_DATABASE_URL", url)
            
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
            
        if not url:
            raise DatabaseConfigError("No database URL configured")
            
        return url
    
    @staticmethod
    def _construct_db_url() -> Optional[str]:
        required_params = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]
        params = {param: os.getenv(param) for param in required_params}
        
        if all(params.values()):
            return f"postgresql://{params['PGUSER']}:{params['PGPASSWORD']}@{params['PGHOST']}:{params['PGPORT']}/{params['PGDATABASE']}"
        return None

class Database:
    def __init__(self):
        self.config = DatabaseConfig()
        self.engine = self._create_engine()
        self.SessionLocal = self._create_session_factory()
        self._setup_engine_events()

    def _create_engine(self) -> Engine:
        return create_engine(
            self.config.database_url,
            poolclass=QueuePool,
            **self.config.pool_settings
        )

    def _create_session_factory(self) -> sessionmaker:
        return sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )

    def _setup_engine_events(self):
        @event.listens_for(self.engine, "connect")
        def connect(dbapi_connection, connection_record):
            logger.info("Database connection established")
            
        @event.listens_for(self.engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Connection checked out from pool")

    def get_all_participants(self) -> List[models.Participant]:
        """Get all participants from the database"""
        try:
            with self.get_db() as session:
                return session.query(models.Participant).all()
        except Exception as e:
            logger.error(f"Error getting all participants: {str(e)}")
            return []
        
    def get_registered_participants(self) -> List[models.Participant]:
        """
        Get all participants who have registered with their Telegram ID from the database
        
        Returns:
            List[models.Participant]: List of registered participants, empty list if error occurs
        """
        try:
            with self.get_db() as session:
                return session.query(models.Participant).filter(
                    models.Participant.telegram_id.isnot(None)
                ).all()
        except Exception as e:
            logger.error(f"Error getting registered participants: {str(e)}")
            return []

    def get_first_record_date(self) -> Optional[datetime]:
        """
        Get the timestamp of the first record added to the participants table
        
        Returns:
            datetime object of the earliest created_at timestamp if records exist,
            None if table is empty or on error
        """
        try:
            with self.get_db() as session:
                # Query the earliest created_at timestamp
                first_record = session.query(models.Participant.created_at)\
                    .order_by(models.Participant.created_at.asc())\
                    .first()
                
                # Return the datetime if record exists
                return first_record[0] if first_record else None
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error getting first record date: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error getting first record date: {str(e)}")
            return None

    def update_participant(self, participant: models.Participant) -> bool:
        """
        Update a participant's information.
        
        Args:
            participant: Participant object containing the updated information
                
        Returns:
            Boolean indicating success or failure of update
        """
        try:
            with self.get_db() as session:
                # Find the existing participant
                existing_participant = session.query(models.Participant).filter(
                    models.Participant.trafee_username == participant.trafee_username
                ).first()
                
                if not existing_participant:
                    logger.error(f"Participant not found for username: {participant.trafee_username}")
                    return False
                
                # List of fields to check for updates
                fields_to_update = [
                    'name', 'telegram_id', 'telegram_username',
                    'day_1_answer', 'day_1_prize',
                    'day_2_answer', 'day_2_prize',
                    'day_3_answer', 'day_3_prize',
                    'day_4_answer', 'day_4_prize',
                    'day_5_answer', 'day_5_prize',
                    'day_6_answer', 'day_6_prize',
                    'day_7_answer', 'day_7_prize',
                    'final_prize'
                ]
                
                # Update fields from the provided participant object
                for field in fields_to_update:
                    new_value = getattr(participant, field)
                    if new_value is not None:
                        setattr(existing_participant, field, new_value)
                
                session.commit()
                return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error updating participant {participant.trafee_username}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error updating participant {participant.trafee_username}: {str(e)}")
            return False

    def batch_update_participants(self, participants: list[models.Participant]) -> bool:
        """
        Batch update multiple participants in the database.
        
        Args:
            participants (List[Participant]): List of participant objects to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            with self.get_db() as session:
                for participant in participants:
                    # Get existing participant from database
                    db_participant = session.query(models.Participant)\
                        .filter(models.Participant.telegram_id == participant.telegram_id)\
                        .first()
                    
                    if db_participant:
                        # Update all prize fields
                        for day in range(1, 8):
                            prize_field = f'day_{day}_prize'
                            if hasattr(participant, prize_field):
                                setattr(db_participant, prize_field, getattr(participant, prize_field))
                
                session.commit()
                logging.info(f"Successfully updated {len(participants)} participants")
                return True
                
        except SQLAlchemyError as e:
            logging.error(f"Database error in batch update participants: {str(e)}")
            if 'session' in locals():
                session.rollback()
            return False
        except Exception as e:
            logging.error(f"Error in batch update participants: {str(e)}")
            if 'session' in locals():
                session.rollback()
            return False
        
    def batch_update_gifts(self, gifts: list[models.Gift]) -> bool:
        """
        Batch update multiple gifts in the database efficiently.
        
        Args:
            gifts (List[Gift]): List of gift objects to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            with self.get_db() as session:
                # Create a mapping of gift IDs to their objects
                gift_map = {gift.id: gift for gift in gifts}
                
                # Get all existing gifts in one query
                db_gifts = session.query(models.Gift)\
                    .filter(models.Gift.id.in_(gift_map.keys()))\
                    .all()
                
                # Update each gift's attributes
                for db_gift in db_gifts:
                    updated_gift = gift_map[db_gift.id]
                    for attr in [
                        'name', 'day_1_quantity', 'day_2_quantity', 
                        'day_3_quantity', 'day_4_quantity', 'day_5_quantity', 
                        'day_6_quantity', 'day_7_quantity', 'remain'
                    ]:
                        if hasattr(updated_gift, attr):
                            setattr(db_gift, attr, getattr(updated_gift, attr))
                
                session.commit()
                logging.info(f"Successfully updated {len(db_gifts)} gifts")
                return True
            
        except SQLAlchemyError as e:
            logging.error(f"Database error in batch_update_gifts: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Error in batch_update_gifts: {str(e)}")
            return False
    
    def get_participant_by_telegram_id(self, telegram_id: str) -> models.Participant|None:
        """
        Check if user exists in Participant table by their Telegram ID
        
        Args:
            telegram_id: User's Telegram ID to check
                
        Returns:
            Participant object if found, None otherwise
        """
        try:
            with self.get_db() as session:
                participant = session.query(models.Participant).filter(
                    models.Participant.telegram_id == telegram_id
                ).first()
                return participant
                
        except Exception as e:
            logging.error(f"Error checking user with Telegram ID {telegram_id}: {str(e)}")
            return None

    def save_participant_response_to_db(self, telegram_id: str, day: int, answer_is_correct: bool) -> bool:
        """
        Record a user's quiz response in the database
        
        Args:
            telegram_id (str): User's Telegram ID
            day (int): Quiz day number (0-based index)
            answer (bool): User's selected answer
            response_time (datetime): Time when answer was submitted
            is_correct (bool): Whether the answer was correct
            
        Returns:
            bool: True if successfully recorded, False otherwise
        """
        try:
            # Validate day input
            if not 0 < day <= 7:  # 1-based index for 7 days
                logger.error(f"Invalid day number: {day}, must be between 0 and 6")
                return False
                
            with self.get_db() as session:
                # Find participant
                participant = session.query(models.Participant).filter(
                    models.Participant.telegram_id == telegram_id
                ).first()
                
                if not participant:
                    logger.error(f"No participant found with telegram_id {telegram_id}")
                    return False
                    
                # Update fields for the specific day
                setattr(participant, f'day_{day}_answer', bool(answer_is_correct))
                
                # Commit the changes
                session.commit()
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error recording response for telegram_id {telegram_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error recording response for telegram_id {telegram_id}: {str(e)}")
            return False
    
    def get_participant_answer(self, telegram_id: str, day: int) -> Optional[str]:
        """
        Get participant's answer for a specific day by their telegram ID
        
        Args:
            telegram_id (str): Participant's Telegram ID
            day (int): Day number (1-7)
            
        Returns:
            Optional[str]: The participant's answer for the specified day,
                            None if participant not found, day invalid, or no answer exists
        """
        try:
            # Validate day input
            if not 1 <= day <= 7:
                logger.error(f"Invalid day number: {day}, must be between 1 and 7")
                return None
                
            with self.get_db() as session:
                # Get participant's answer for the specific day
                participant = session.query(models.Participant).filter(
                    models.Participant.telegram_id == telegram_id
                ).first()
                
                if not participant:
                    logger.warning(f"No participant found with telegram_id {telegram_id}")
                    return None
                    
                answer_field = f'day_{day}_answer'
                answer = getattr(participant, answer_field, None)
                
                # Return None if answer is empty string or whitespace
                if answer is not None and answer.strip():
                    return answer.strip()
                    
                return None
                
        except Exception as e:
            logger.error(f"Error getting answer for telegram_id {telegram_id} day {day}: {str(e)}")
            return None
    
    def register_user_by_trafee_username(self, username: str) -> models.Participant|None:
        """
        Check if user exists in Participant table and if they're registered
        
        Args:
            username: User's username to check
            
        Returns:
            Tuple of (exists, is_registered)
        """
        try:
            with self.get_db() as session:
                participant = session.query(models.Participant).filter(
                    models.Participant.trafee_username == username
                ).first()
                return participant
                
        except Exception as e:
            logging.error(f"Error checking user {username}: {str(e)}")
            return None

    def get_gifts_for_day(self, day: int) -> List[models.Gift]:
        """
        Get all available gifts for a specific day
        
        Args:
            day (int): Day number (1-7)
            
        Returns:
            List[Gift]: List of Gift objects that have quantity > 0 for the specified day,
                    empty list if none found or on error
        """
        try:
            with self.get_db() as session:
                # Validate day input
                if not 1 <= day <= 7:
                    logger.error(f"Invalid day number: {day}, must be between 1 and 7")
                    return []
                
                # Construct the column name for the day
                day_column = f"day_{day}_quantity"
                
                # Query gifts where the specified day's quantity is greater than 0
                gifts = session.query(models.Gift)\
                    .filter(getattr(models.Gift, day_column) > 0)\
                    .order_by(models.Gift.name)\
                    .all()
                
                return gifts
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error getting gifts for day {day}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error getting gifts for day {day}: {str(e)}")
            return []
        

    def get_available_gifts(self, day: int) -> list:
        """
        Get all available gifts for a specific day that have quantity > 0
        
        Args:
            day (int): Day number (1-7)
            
        Returns:
            List[Gift]: List of available gift objects with their quantities
        """
        try:
            with self.get_db() as session:
                # Validate day input
                if not 1 <= day <= 7:
                    logging.error(f"Invalid day number: {day}, must be between 1 and 7")
                    return []
                
                # Construct the column name for the specific day
                day_column = f"day_{day}_quantity"
                
                # Query gifts where the specified day's quantity is greater than 0
                available_gifts = session.query(models.Gift)\
                    .filter(getattr(models.Gift, day_column) > 0)\
                    .all()
                
                # Log the results
                logging.info(f"Found {len(available_gifts)} available gifts for day {day}")
                
                return available_gifts
                    
        except SQLAlchemyError as e:
            logging.error(f"Database error getting available gifts for day {day}: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Error getting available gifts for day {day}: {str(e)}")
            return []

    def is_authorized_user(self, update):
        """
        Check if a user is authorized to use the bot by verifying their username
        against the database or superadmin status.
        
        Args:
            update: Telegram update object containing user information
            
        Returns:
            bool: True if user is authorized, False otherwise
        """
        user = update.effective_user
        username = user.username
        id = str(user.id)

        logging.info(f"Checking authorization for @{username}")

        # First check if user is superadmin
        if username == SUPERADMIN_USERNAME:
            logging.info(f"User @{username} is the superadmin. Access granted.")
            return True
            
        try:
            # Check if user exists in participants database
            with self.get_db() as session:
                participant = session.query(models.Participant).filter(
                    models.Participant.telegram_id == id
                ).first()
                
                if participant:
                    logging.info(f"Access granted for user @{username}")
                    return participant
                    
                logging.info(f"User @{username} not found in participants database")
                return False
                
        except Exception as e:
            logging.error(f"Database error while checking authorization for @{username}: {str(e)}")
            return False


    # [Previous methods remain unchanged...]
    @contextmanager
    def get_db(self) -> Generator[Session, None, None]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise DatabaseError(f"Database operation failed: {str(e)}")
        except Exception as e:
            session.rollback()
            logger.error(f"Unexpected error: {str(e)}")
            raise
        finally:
            session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def execute_with_retry(self, session: Session, operation):
        try:
            return operation(session)
        except OperationalError as e:
            logger.warning(f"Database operation failed, retrying: {str(e)}")
            session.rollback()
            raise


class DatabaseError(Exception):
    pass

class DatabaseConfigError(DatabaseError):
    pass

class DatabaseConnectionError(DatabaseError):
    pass

class DatabaseOperationError(DatabaseError):
    pass