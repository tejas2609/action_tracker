import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, JSON, ForeignKey, DateTime, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
class Meeting(Base):
    __tablename__='meetings'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    organization_id: Mapped[str|None]=mapped_column(ForeignKey('organizations.id'),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(200))
    held_on: Mapped[datetime]=mapped_column(Date)
    transcript: Mapped[str]=mapped_column(Text)
    findings: Mapped[list]=mapped_column(JSON,default=list)
    state: Mapped[str]=mapped_column(String(30),default='draft')
class Commitment(Base):
    __tablename__='commitments'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    title: Mapped[str]=mapped_column(String(500))
    owner: Mapped[str]=mapped_column(String(120),index=True)
    owner_id: Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True,index=True)
    analysis_text: Mapped[str]=mapped_column(Text,default='')
    analysis_next: Mapped[str]=mapped_column(Text,default='')
    analysis_hash: Mapped[str]=mapped_column(String(64),default='')
    due_date: Mapped[datetime|None]=mapped_column(Date,nullable=True,index=True)
    status: Mapped[str]=mapped_column(String(30),default='active',index=True)
    progress: Mapped[int]=mapped_column(Integer,default=0)
    condition: Mapped[str]=mapped_column(Text,default='')
    condition_met: Mapped[bool]=mapped_column(default=False)
    blocker: Mapped[str]=mapped_column(Text,default='')
    source_statement: Mapped[str]=mapped_column(Text)
    meeting_id: Mapped[str]=mapped_column(ForeignKey('meetings.id'))
class Dependency(Base):
    __tablename__='dependencies'
    commitment_id: Mapped[str]=mapped_column(ForeignKey('commitments.id'),primary_key=True)
    prerequisite_id: Mapped[str]=mapped_column(ForeignKey('commitments.id'),primary_key=True)
class Event(Base):
    __tablename__='events'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    commitment_id: Mapped[str]=mapped_column(ForeignKey('commitments.id'),index=True)
    meeting_id: Mapped[str|None]=mapped_column(ForeignKey('meetings.id'),nullable=True)
    kind: Mapped[str]=mapped_column(String(40))
    message: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

from app.models import people
