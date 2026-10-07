from datetime import date,timedelta
import pytest
from sqlalchemy import create_engine,event,select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.core.database import Base,get_db
from app.main import app
from app.models.people import Organization,User,Message,Conversation
from app.models.entities import Meeting,Commitment,Dependency,Event
from app.ai.provider import get_provider
from app.core.config import settings
class FakeAI:
    def __init__(self):self.calls=0;self.result={'explanation':'Waiting for QA approval.','next_action':'Ask Sarah for QA status.'}
    async def json(self,instruction,payload):self.calls+=1;return self.result
@pytest.fixture
def ctx(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'v2.db'),connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def fk(conn,_):conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Organization(id='o1',name='One'),Organization(id='o2',name='Two')]);db.flush()
        db.add_all([User(id=id,organization_id=org,name=name,email=id+'@test.example',team=team,role=role) for id,org,name,team,role in [('t','o1','Tejas','Engineering','Engineer'),('s','o1','Sarah','Quality','QA Engineer'),('p','o1','Priya','Product','Product Manager'),('outsider','o2','Other','Other','Engineer')]]);db.flush()
        db.add_all([Meeting(id='m',organization_id='o1',title='Launch',held_on=date.today(),transcript="Sarah: I'll finish QA."),Meeting(id='foreign',organization_id='o2',title='Private',held_on=date.today(),transcript='Other promises')]);db.flush()
        db.add_all([Commitment(id='mine',title='Deploy',owner='Tejas',owner_id='t',due_date=date.today()-timedelta(days=1),source_statement='I will deploy',meeting_id='m'),Commitment(id='qa',title='QA',owner='Sarah',owner_id='s',source_statement='I will QA',meeting_id='m'),Commitment(id='after',title='Announce',owner='Priya',owner_id='p',source_statement='I will announce',meeting_id='m'),Commitment(id='secret',title='Secret',owner='Other',owner_id='outsider',source_statement='Secret',meeting_id='foreign')]);db.flush()
        db.add_all([Dependency(commitment_id='mine',prerequisite_id='qa'),Dependency(commitment_id='after',prerequisite_id='mine')]);db.commit()
    def db_session():
        with Session(engine,expire_on_commit=False) as db:
            try:yield db
            except Exception:db.rollback();raise
    fake=FakeAI();app.dependency_overrides[get_db]=db_session;app.dependency_overrides[get_provider]=lambda:fake
    client=TestClient(app)
    def login(id):
        r=client.post('/api/auth/demo-login',json={'user_id':id});assert r.status_code==200
        return {'Authorization':'Bearer '+r.json()['token']}
    yield client,login,engine,fake
    app.dependency_overrides.clear()

def test_scope_permissions_and_graph(ctx):
    c,login,engine,fake=ctx;h=login('t')
    assert c.get('/api/commitments').status_code==401
    assert [x['id'] for x in c.get('/api/commitments',headers=h).json()['items']]==['mine']
    graph=c.get('/api/graph',headers=h).json()
    assert {x['id'] for x in graph['items']}=={'mine','qa','after'}
    assert c.get('/api/commitments/secret',headers=h).status_code==404
    assert c.patch('/api/commitments/qa',headers=h,json={'status':'completed'}).status_code==403
    assert c.patch('/api/commitments/mine',headers=h,json={'status':'completed'}).json()['progress']==100
    assert c.get('/api/dashboard',headers=h).json()['metrics']['completed']==1
    assert c.post('/api/commitments/mine/dependencies',headers=h,json={'prerequisite_id':'secret'}).status_code==404

def test_dashboard_page_size_and_counts(ctx):
    c,login,engine,fake=ctx;h=login('t')
    with Session(engine) as db:
        db.add_all([Commitment(title='Late '+str(i),owner='Tejas',owner_id='t',due_date=date.today()-timedelta(days=2),source_statement='promise',meeting_id='m') for i in range(14)]);db.commit()
    first=c.get('/api/dashboard?page=1',headers=h).json();second=c.get('/api/dashboard?page=2',headers=h).json()
    assert first['metrics']['total']==15 and first['attention']['total']==15
    assert len(first['attention']['items'])==10 and len(second['attention']['items'])==5
    assert not ({x['id'] for x in first['attention']['items']} & {x['id'] for x in second['attention']['items']})

def test_chat_persistence_isolation_followup_and_disabled_attachments(ctx):
    c,login,engine,fake=ctx;t=login('t');s=login('s');p=login('p')
    r=c.post('/api/chat/s',headers=t,json={'body':'Sarah, can you confirm QA?','commitment_id':'qa'});assert r.status_code==201
    assert c.get('/api/chat/t',headers=s).json()['items'][0]['body']=='Sarah, can you confirm QA?'
    assert c.get('/api/chat/s',headers=p).json()['items']==[]
    assert c.post('/api/chat/outsider',headers=t,json={'body':'Leak'}).status_code==404
    assert c.post('/api/chat/s/attachments',headers=t).status_code==501
    assert c.post('/api/chat/s',headers=t,json={'body':'Help unblock my deployment','commitment_id':'mine'}).status_code==201
    with Session(engine) as db:assert db.scalar(select(Event).where(Event.kind=='followup_sent')) is not None

def test_chat_cursor(ctx):
    c,login,engine,fake=ctx;h=login('t')
    for i in range(5):assert c.post('/api/chat/s',headers=h,json={'body':str(i)}).status_code==201
    page=c.get('/api/chat/s?limit=2',headers=h).json()
    assert [m['body'] for m in page['items']]==['3','4'] and page['has_more']
    older=c.get('/api/chat/s?limit=2&before='+page['before'],headers=h).json()
    assert [m['body'] for m in older['items']]==['1','2']

def test_blocker_cache_refreshes_on_dependency_change(ctx):
    c,login,engine,fake=ctx;h=login('t');s=login('s')
    assert c.post('/api/commitments/mine/analysis',headers=h).status_code==200
    assert c.post('/api/commitments/mine/analysis',headers=h).json()['cached']
    assert fake.calls==1
    c.patch('/api/commitments/qa',headers=s,json={'status':'completed'})
    assert c.get('/api/commitments/mine',headers=h).json()['analysis']['stale']
    assert c.post('/api/commitments/mine/analysis',headers=h).status_code==200
    assert fake.calls==2

def test_dependency_replace_atomic_cycle_rejection(ctx):
    c,login,engine,fake=ctx;h=login('t')
    r=c.post('/api/commitments/mine/dependencies/qa/replace',headers=h,json={'prerequisite_id':'after'})
    assert r.status_code==422
    assert c.get('/api/commitments/mine',headers=h).json()['dependencies']==['qa']

def test_source_lines_and_owner_assignment(ctx):
    c,login,engine,fake=ctx;h=login('t')
    fake.result={'findings':[{'kind':'commitment','title':'QA report','owner':'Sarah','source_line':1,'statement':'AI paraphrase'}]}
    meeting=c.post('/api/meetings',headers=h,json={'title':'Source test','held_on':str(date.today()),'transcript':"Sarah: I'll finish the report. No, wait, Thursday."}).json()
    r=c.post('/api/meetings/'+meeting['id']+'/analyze',headers=h);assert r.status_code==200
    assert r.json()['findings'][0]['statement']==meeting['transcript']
    r=c.post('/api/meetings/'+meeting['id']+'/review',headers=h,json={'items':[{'index':0,'action':'confirm','title':'QA report','owner':'Sarah','owner_id':'s'}]});assert r.status_code==200
    mine=c.get('/api/commitments',headers=login('s')).json()['items']
    assert any(x['title']=='QA report' for x in mine)

def test_deletion_preserves_chat_and_tenant(ctx):
    c,login,engine,fake=ctx;h=login('t')
    c.post('/api/chat/s',headers=h,json={'body':'QA follow-up','commitment_id':'qa'})
    assert c.get('/api/meetings/foreign/deletion-preview',headers=h).status_code==404
    preview=c.get('/api/meetings/m/deletion-preview',headers=h).json()
    assert set(preview['commitment_ids'])=={'mine','qa','after'}
    assert c.request('DELETE','/api/meetings/m',headers=h,json={'expected_commitment_ids':preview['commitment_ids']}).status_code==200
    messages=c.get('/api/chat/s',headers=h).json()['items']
    assert messages[0]['commitment_id'] is None and messages[0]['body']=='QA follow-up'
    with Session(engine) as db:assert db.get(Commitment,'secret') is not None

def test_user_filters_and_session_logout(ctx):
    c,login,engine,fake=ctx;h=login('t')
    users=c.get('/api/users?team=Quality',headers=h).json()['items'];assert [u['id'] for u in users]==['s']
    assert c.get('/api/users?role=Engineer',headers=h).json()['items'][0]['id']=='t'
    assert c.post('/api/auth/logout',headers=h).status_code==200
    assert c.get('/api/auth/me',headers=h).status_code==401

def test_blocker_stale_generation_rejected(ctx):
    c,login,engine,fake=ctx;h=login('t')
    class ChangingAI:
        async def json(self,instruction,payload):
            with Session(engine) as db:
                db.get(Commitment,'qa').status='completed';db.commit()
            return {'explanation':'Outdated explanation','next_action':'Outdated action'}
    app.dependency_overrides[get_provider]=lambda:ChangingAI()
    assert c.post('/api/commitments/mine/analysis',headers=h).status_code==409
    with Session(engine) as db:assert db.get(Commitment,'mine').analysis_text==''

def test_followup_recipient_passed_to_provider(ctx):
    c,login,engine,fake=ctx;h=login('t')
    class RecipientAI:
        async def json(self,instruction,payload):
            assert payload['recipient']['id']=='s'
            return {'message':'Sarah, could you unblock QA?'}
    app.dependency_overrides[get_provider]=lambda:RecipientAI()
    result=c.post('/api/commitments/mine/followup',headers=h,json={'recipient_id':'s'})
    assert result.status_code==200 and result.json()['message'].startswith('Sarah')
    assert c.post('/api/commitments/mine/followup',headers=h,json={'recipient_id':'outsider'}).status_code==404

def test_migration_preserves_v1_data_and_maps_owners(tmp_path):
    import subprocess,os,sys
    from pathlib import Path
    backend=Path(__file__).parent
    database='sqlite:///'+str(tmp_path/'upgrade.db')
    env={**os.environ,'DATABASE_URL':database}
    def migrate(revision,direction='upgrade'):
        result=subprocess.run([sys.executable,'-m','alembic',direction,revision],cwd=backend,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stdout+result.stderr
    migrate('001')
    engine=create_engine(database)
    from sqlalchemy import text
    with engine.begin() as db:
        db.execute(text("INSERT INTO meetings (id,title,held_on,transcript,findings,state) VALUES ('legacy','Legacy','2026-10-04','Sarah promised QA','[]','reviewed')"))
        db.execute(text("INSERT INTO commitments (id,title,owner,due_date,status,progress,condition,condition_met,blocker,source_statement,meeting_id) VALUES ('old','QA report','Sarah','2026-10-09','active',10,'',false,'','I will QA','legacy')"))
    migrate('head')
    with engine.connect() as db:
        row=db.execute(text('SELECT c.title,u.name,m.organization_id FROM commitments c JOIN users u ON c.owner_id=u.id JOIN meetings m ON c.meeting_id=m.id')).one()
        assert row[0]=='QA report' and row[1]=='Sarah' and row[2]
        assert db.execute(text('SELECT count(*) FROM users')).scalar()>=10
    migrate('001','downgrade')
    with engine.connect() as db:assert db.execute(text('SELECT title FROM commitments')).scalar()=='QA report'
    migrate('head')

def test_logout_only_revokes_current_session(ctx):
    c,login,engine,fake=ctx;first=login('t');second=login('t')
    assert c.post('/api/auth/logout',headers=first).status_code==200
    assert c.get('/api/auth/me',headers=first).status_code==401
    assert c.get('/api/auth/me',headers=second).status_code==200

def test_attachment_ids_cannot_be_sent(ctx):
    c,login,engine,fake=ctx
    assert c.post('/api/chat/s',headers=login('t'),json={'body':'upload','attachment_ids':['file']}).status_code==422
    assert c.get('/api/messaging/capabilities',headers=login('t')).json()['attachments'] is False
