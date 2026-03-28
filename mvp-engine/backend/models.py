from sqlalchemy import Column, Integer, String, Float, Boolean, Enum
import enum
from database import Base

class IncentiveType(str, enum.Enum):
    tax_rebate = "tax_rebate"
    grant = "grant"
    equity = "equity"

class RecoupmentPosition(str, enum.Enum):
    none = "none"
    soft = "soft"
    pari_passu = "pari_passu"

class Incentive(Base):
    __tablename__ = "incentives"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    country = Column(String, index=True)
    type = Column(Enum(IncentiveType))
    
    gross_rebate_percent = Column(Float)
    max_cap = Column(Float, nullable=True) # None means no cap
    min_local_spend_percent = Column(Float)
    
    net_yield_multiplier = Column(Float, default=1.0)
    recoupment_position = Column(Enum(RecoupmentPosition))
    
    requires_territory_rights = Column(Boolean, default=False)
    state_aid_eligible = Column(Boolean, default=False)

class Treaty(Base):
    __tablename__ = "treaties"

    id = Column(Integer, primary_key=True, index=True)
    country_a = Column(String, index=True)
    country_b = Column(String, index=True)
    min_financial_share_a = Column(Float)
    min_financial_share_b = Column(Float)
    requires_official_copro_status = Column(Boolean, default=True)
