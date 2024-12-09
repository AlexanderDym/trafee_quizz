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

from dotenv import load_dotenv

load_dotenv()



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
        
        if url and "postgres.railway.internal" in url:
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
                    'day_1_time', 'day_1_answer', 'day_1_prize',
                    'day_2_time', 'day_2_answer', 'day_2_prize',
                    'day_3_time', 'day_3_answer', 'day_3_prize',
                    'day_4_time', 'day_4_answer', 'day_4_prize',
                    'day_5_time', 'day_5_answer', 'day_5_prize',
                    'day_6_time', 'day_6_answer', 'day_6_prize',
                    'day_7_time', 'day_7_answer', 'day_7_prize',
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

    def get_gifts_table(self):
        ...


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