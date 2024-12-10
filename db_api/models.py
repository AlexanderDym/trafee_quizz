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
    
    # Gift information
    name = Column(String, nullable=False)
    
    # Quantities available for each day
    day_1_quantity = Column(Integer, default=0)
    day_2_quantity = Column(Integer, default=0)
    day_3_quantity = Column(Integer, default=0)
    day_4_quantity = Column(Integer, default=0)
    day_5_quantity = Column(Integer, default=0)
    day_6_quantity = Column(Integer, default=0)
    day_7_quantity = Column(Integer, default=0)
    remain         = Column(Integer, default=0)

    def __init__(self, name: str, quantities: list[int]):
        self.name = name
        if quantities and len(quantities) == 7:
            self.day_1_quantity = quantities[0]
            self.day_2_quantity = quantities[1]
            self.day_3_quantity = quantities[2]
            self.day_4_quantity = quantities[3]
            self.day_5_quantity = quantities[4]
            self.day_6_quantity = quantities[5]
            self.day_7_quantity = quantities[6]
            self.remain = sum(quantities)

