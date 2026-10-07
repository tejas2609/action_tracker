from sqlalchemy import select
from app.models.entities import Commitment,Meeting,Dependency,Event
from fastapi import HTTPException
class Store:
    def __init__(self,db,actor=None):self.db=db;self.actor=actor
    def all(self,model):
        q=select(model)
        if self.actor:
            org=self.actor.organization_id
            if model is Meeting:q=q.where(Meeting.organization_id==org)
            elif model is Commitment:q=q.join(Meeting,Commitment.meeting_id==Meeting.id).where(Meeting.organization_id==org)
            elif model is Dependency:q=q.join(Commitment,Dependency.commitment_id==Commitment.id).join(Meeting,Commitment.meeting_id==Meeting.id).where(Meeting.organization_id==org)
            elif model is Event:q=q.join(Commitment,Event.commitment_id==Commitment.id).join(Meeting,Commitment.meeting_id==Meeting.id).where(Meeting.organization_id==org)
        return list(self.db.scalars(q))
    def get(self,model,id):
        row=self.db.get(model,id)
        if not row:raise HTTPException(404,'Record not found')
        if self.actor:
            m=row if model is Meeting else self.db.get(Meeting,row.meeting_id) if model is Commitment else None
            if m and m.organization_id!=self.actor.organization_id:raise HTTPException(404,'Record not found')
        return row
    def event(self,c,kind,message,meeting_id=None):self.db.add(Event(commitment_id=c.id,kind=kind,message=message,meeting_id=meeting_id))
    def save(self,row):self.db.add(row);self.db.flush();return row
