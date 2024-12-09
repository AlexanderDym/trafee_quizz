from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, Date
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # User identification
    trafee_username = Column(String, unique=True, index=True)
    name = Column(String)
    telegram_id = Column(String)
    telegram_username = Column(String)
    
    # Day 1
    day_1_answer = Column(Boolean)
    day_1_prize = Column(String)
    
    # Day 2
    day_2_answer = Column(Boolean)
    day_2_prize = Column(String)
    
    # Day 3
    day_3_answer = Column(Boolean)
    day_3_prize = Column(String)
    
    # Day 4
    day_4_answer = Column(Boolean)
    day_4_prize = Column(String)
    
    # Day 5
    day_5_answer = Column(Boolean)
    day_5_prize = Column(String)
    
    # Day 6
    day_6_answer = Column(Boolean)
    day_6_prize = Column(String)
    
    # Day 7
    day_7_answer = Column(Boolean)
    day_7_prize = Column(String)
    
    # Final
    final_prize = Column(String)


    class Gift(Base):
        __tablename__ = "gifts"

        id = Column(Integer, primary_key=True, index=True)
        gift_name = Column(String, nullable=False)  # Название подарка

        # Количество подарков на каждый день
        day_1_quantity = Column(Integer, nullable=False, default=0)
        day_2_quantity = Column(Integer, nullable=False, default=0)
        day_3_quantity = Column(Integer, nullable=False, default=0)
        day_4_quantity = Column(Integer, nullable=False, default=0)
        day_5_quantity = Column(Integer, nullable=False, default=0)
        day_6_quantity = Column(Integer, nullable=False, default=0)
        day_7_quantity = Column(Integer, nullable=False, default=0)