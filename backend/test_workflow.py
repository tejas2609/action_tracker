import asyncio
from datetime import date,timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
from app.models.entities import Meeting,Commitment,Dependency,Event
from app.repositories.store import Store
from app.services.commitments.workflow import Workflow
from app.services.commitments.intelligence import assess,descendants
from app.schemas.contracts import Review,Update
class FakeAI:
    def __init__(self,result): self.result=result;self.payload=None
    async def json(self,instruction,payload): self.payload=payload;return self.result
@pytest.fixture
def env():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        s=Store(db)
        m=s.save(Meeting(title='Readiness',held_on=date.today(),transcript="Sarah: I'll finish QA tomorrow. Alex: I'll deploy after approval.",findings=[{'kind':'commitment','title':'Finish QA','owner':'Sarah','statement':"I'll finish QA tomorrow.",'due_date':None,'condition':''},{'kind':'commitment','title':'Deploy','owner':'Alex','statement':"I'll deploy after approval.",'due_date':None,'condition':'QA approval'}],state='analyzed'))
        db.commit()
        yield Workflow(s,FakeAI({})),m

def confirm(w,m):
    w.review(m.id,Review(items=[{'index':i,'action':'confirm','title':f['title'],'owner':f['owner'],'condition':f['condition']} for i,f in enumerate(m.findings)]))
    return w.s.all(Commitment)
def test_review_dependency_impact_and_cycle(env):
    w,m=env;a,b=confirm(w,m)
    w.edge(b.id,a.id)
    rows,edges=w.snapshot()
    assert descendants(a.id,edges)=={b.id}
    assert assess(b,rows,edges)['state']=='waiting'
    with pytest.raises(HTTPException) as e:w.edge(a.id,b.id)
    assert e.value.status_code==422
    w.update(a.id,Update(status='completed'))
    w.update(b.id,Update(condition_met=True))
    assert next(x for x in w.listing() if x['id']==b.id)['risk']['state']=='on-track'
    assert a.progress==100
    with pytest.raises(HTTPException):w.review(m.id,Review(items=[]))
def test_continuity_audited_deadline(env):
    w,m=env;a,b=confirm(w,m)
    new=w.s.save(Meeting(title='Next sync',held_on=date.today(),transcript='Sarah: QA will be ready Friday.',findings=[{'statement':'QA will be ready Friday.'}],state='analyzed'));w.s.db.commit()
    due=date.today()+timedelta(days=5)
    w.review(new.id,Review(items=[{'index':0,'action':'link','existing_id':a.id,'owner':'Sarah','title':a.title,'due_date':due}]))
    assert len(w.s.all(Commitment))==2 and a.due_date==due
    events=[e for e in w.s.all(Event) if e.commitment_id==a.id]
    assert {'created','meeting_mention','deadline_change'}<=set(e.kind for e in events)
def test_risk_keeps_waiting_and_overdue(env):
    w,m=env;a,b=confirm(w,m)
    b.due_date=date.today()-timedelta(days=2)
    rows,edges=w.snapshot();risk=assess(b,rows,edges)
    assert risk['level']=='high' and risk['state']=='waiting' and risk['overdue']
def test_invalid_quotation_not_saved(env):
    w,m=env
    w.ai=FakeAI({'findings':[{'kind':'commitment','title':'Invented','statement':'Made up quotation','owner':'Sarah'}]})
    with pytest.raises(HTTPException) as e:asyncio.run(w.analyze(m.id))
    assert e.value.status_code==502 and len(m.findings)==2
def test_search_grounded_followup_audited(env):
    w,m=env;a,b=confirm(w,m)
    w.ai=FakeAI({'ids':[a.id,'invented'],'interpretation':'Sarah promises'})
    result=asyncio.run(w.search('What did Sarah promise?'))
    assert [c['id'] for c in result['results']]==[a.id]
    w.ai=FakeAI({'message':'Sarah, can you confirm QA approval before deployment?'})
    assert 'Sarah' in asyncio.run(w.followup(a.id))['message']
    assert w.ai.payload['commitment']['owner']=='Sarah'
    assert any(e.kind=='followup_generated' for e in w.s.all(Event))
def test_transitive_impact(env):
    w,m=env;a,b=confirm(w,m)
    c=w.s.save(Commitment(title='Launch',owner='Priya',source_statement='I will launch',meeting_id=m.id))
    w.edge(b.id,a.id);w.edge(c.id,b.id)
    assert descendants(a.id,w.s.all(Dependency))=={b.id,c.id}

def test_api_validation_and_full_flow(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db
    from app.ai.provider import get_provider
    engine=create_engine('sqlite:///'+str(tmp_path/'api.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    def session():
        with Session(engine,expire_on_commit=False) as db:
            try: yield db
            except Exception: db.rollback();raise
    fake=FakeAI({'findings':[{'kind':'commitment','title':'Deliver QA','owner':'Sarah','statement':"I'll deliver QA.",'confidence':0.9}]})
    from app.core.auth import current_user
    from app.models.people import User,Organization
    with Session(engine) as seed:
        seed.add(Organization(id='org',name='Test'));seed.flush();seed.add(User(id='sarah',organization_id='org',name='Sarah',email='sarah@test.example',team='QA',role='Engineer'));seed.commit()
    actor=User(id='sarah',organization_id='org',name='Sarah',email='sarah@test.example',team='QA',role='Engineer')
    app.dependency_overrides[current_user]=lambda:actor
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_provider]=lambda:fake
    try:
        client=TestClient(app)
        assert client.get('/api/health').status_code==200
        assert client.post('/api/meetings',json={'title':'','held_on':'bad','transcript':'a'}).status_code==422
        m=client.post('/api/meetings',json={'title':'QA sync','held_on':str(date.today()),'transcript':"Sarah: I'll deliver QA."}).json()
        assert client.post(f"/api/meetings/{m['id']}/analyze").status_code==200
        assert client.post(f"/api/meetings/{m['id']}/review",json={'items':[{'index':0,'action':'confirm','title':'Deliver QA','owner':'Sarah'}]}).status_code==200
        c=client.get('/api/commitments').json()['items'][0]
        assert client.patch('/api/commitments/'+c['id'],json={'progress':101}).status_code==422
        assert client.patch('/api/commitments/'+c['id'],json={'status':'completed'}).json()['progress']==100
        detail=client.get('/api/commitments/'+c['id']).json()
        assert detail['meeting']['title']=='QA sync' and len(detail['timeline'])>=2
        fake.result={'explanation':'No unresolved blockers.','next_action':'No action needed.'}
        assert client.post('/api/commitments/'+c['id']+'/analysis').status_code==200
    finally: app.dependency_overrides.clear()

def test_review_applies_suggested_dependencies(env):
    w,m=env
    items=[{'index':i,'action':'confirm','title':f['title'],'owner':f['owner'],'condition':f['condition'],'depends_on_indices':[0] if i==1 else []} for i,f in enumerate(m.findings)]
    w.review(m.id,Review(items=items))
    a,b=w.s.all(Commitment)
    assert w.s.db.get(Dependency,(b.id,a.id)) is not None
    assert b.id in descendants(a.id,w.s.all(Dependency))
