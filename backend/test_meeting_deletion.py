from datetime import date
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.entities import Meeting, Commitment, Dependency, Event
from app.services.meeting_deletion import deletion_plan, delete_meeting

@pytest.fixture
def data():
    engine=create_engine('sqlite://')
    @event.listens_for(engine, 'connect')
    def enable_fk(connection, _): connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        a=Meeting(title='Delete this',held_on=date.today(),transcript='A promise')
        b=Meeting(title='Keep meeting',held_on=date.today(),transcript='Other promises',findings=[])
        db.add_all([a,b]);db.flush()
        cs=[Commitment(title=str(i),owner='Sarah',source_statement='I promise',meeting_id=a.id if i==0 else b.id) for i in range(5)]
        db.add_all(cs);db.flush()
        # 0 depends on 1; 2 depends on 0; 3 depends on 2. 4 is unrelated.
        db.add_all([Dependency(commitment_id=cs[0].id,prerequisite_id=cs[1].id),Dependency(commitment_id=cs[2].id,prerequisite_id=cs[0].id),Dependency(commitment_id=cs[3].id,prerequisite_id=cs[2].id)])
        db.add_all([Event(commitment_id=c.id,meeting_id=c.meeting_id,kind='created',message='created') for c in cs])
        b.findings=[{'existing_id':cs[0].id,'prerequisite_ids':[cs[1].id,cs[4].id]}]
        db.commit()
        yield db,a,b,cs

def test_connected_component_deleted_fk_safe(data):
    db,a,b,cs=data
    p=deletion_plan(db,a.id)
    assert set(p['commitment_ids'])=={c.id for c in cs[:4]}
    assert p['dependency_count']==3 and p['event_count']==4
    assert p['other_meetings']==[{'id':b.id,'title':b.title}]
    result=delete_meeting(db,a.id,p['commitment_ids'])
    assert result['deleted_commitment_count']==4
    db.expire_all()
    assert db.get(Meeting,a.id) is None and db.get(Meeting,b.id) is not None
    assert list(db.scalars(select(Commitment.id)))==[cs[4].id]
    assert len(list(db.scalars(select(Event))))==1
    assert not list(db.scalars(select(Dependency)))
    assert b.findings[0]['existing_id'] is None
    assert b.findings[0]['prerequisite_ids']==[cs[4].id]

def test_changed_preview_rejected_without_deletion(data):
    db,a,b,cs=data
    with pytest.raises(HTTPException) as error: delete_meeting(db,a.id,[])
    assert error.value.status_code==409
    assert db.get(Meeting,a.id)
    assert len(list(db.scalars(select(Commitment))))==5

def test_unreviewed_empty_meeting(data):
    db,a,b,cs=data
    m=Meeting(title='Empty',held_on=date.today(),transcript='Discussion only')
    db.add(m);db.commit();id=m.id
    assert deletion_plan(db,id)['commitment_count']==0
    delete_meeting(db,id,[])
    db.expire_all()
    assert db.get(Meeting,id) is None

def test_cross_meeting_mention_is_related(data):
    db,a,b,cs=data
    m=Meeting(title='Continuity',held_on=date.today(),transcript='Mentioning old promise')
    db.add(m);db.flush();db.add(Event(commitment_id=cs[4].id,meeting_id=m.id,kind='meeting_mention',message='same promise'));db.commit()
    assert deletion_plan(db,m.id)['commitment_ids']==[cs[4].id]

def test_rest_preview_and_delete(data):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db
    db,a,b,cs=data
    def session(): yield db
    # Keep SQLite session calls on the test thread with sync dependency overrides
    # by exercising the route functions directly; REST wiring covered separately.
    from app.api.meeting_deletion import preview,remove,DeleteConfirmation
    from types import SimpleNamespace
    actor=SimpleNamespace(organization_id=None)
    p=preview(a.id,db,actor)
    result=remove(a.id,DeleteConfirmation(expected_commitment_ids=p['commitment_ids']),db,actor)
    assert result['deleted_commitment_count']==4
    paths=app.openapi()['paths']
    assert 'delete' in paths['/api/meetings/{meeting_id}']
    assert 'get' in paths['/api/meetings/{meeting_id}/deletion-preview']
