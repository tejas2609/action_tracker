"""V2 organization, ownership, sessions and chat; preserves V1 records."""
from alembic import op
import sqlalchemy as sa
import uuid
revision='002'
down_revision='001'
branch_labels=None
depends_on=None
ORG='00000000-0000-0000-0000-000000000001'
def upgrade():
    op.create_table('organizations',sa.Column('id',sa.String(36),primary_key=True),sa.Column('name',sa.String(200),nullable=False))
    op.create_table('users',sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('name',sa.String(120),nullable=False),sa.Column('email',sa.String(200),nullable=False,unique=True),sa.Column('team',sa.String(100),nullable=False),sa.Column('role',sa.String(100),nullable=False),sa.Column('active',sa.Boolean(),nullable=False))
    op.create_index('ix_users_organization_id','users',['organization_id'])
    db=op.get_bind()
    orgs=sa.table('organizations',sa.column('id'),sa.column('name'))
    users=sa.table('users',sa.column('id'),sa.column('organization_id'),sa.column('name'),sa.column('email'),sa.column('team'),sa.column('role'),sa.column('active'))
    db.execute(orgs.insert().values(id=ORG,name='Action Labs'))
    dummy=[('Tejas','Engineering','Engineer'),('Sarah','Quality','QA Engineer'),('Alex','Engineering','Engineer'),('Ben','Engineering','Engineer'),('Maya','Design','Designer'),('Omar','Operations','Operations'),('Priya','Product','Product Manager'),('Nina','Design','Designer'),('Daniel','Sales','Account Executive'),('Leo','Quality','QA Engineer')]
    existing=list(db.execute(sa.text('SELECT DISTINCT owner FROM commitments')))
    names={name.casefold():name for name,team,role in dummy}
    for (name,) in existing:
        if name and name.strip():names.setdefault(name.strip().casefold(),name.strip())
    mapping={}
    for i,(key,name) in enumerate(names.items()):
        id=str(uuid.uuid4());mapping[key]=id
        entry=next(((team,role) for n,team,role in dummy if n.casefold()==key),('Imported','Member'))
        db.execute(users.insert().values(id=id,organization_id=ORG,name=name,email=f'member{i+1}@actionlabs.example',team=entry[0],role=entry[1],active=True))
    with op.batch_alter_table('meetings') as b:
        b.add_column(sa.Column('organization_id',sa.String(36),nullable=True))
        b.create_foreign_key('fk_meeting_organization','organizations',['organization_id'],['id'])
        b.create_index('ix_meetings_organization_id',['organization_id'])
    db.execute(sa.text('UPDATE meetings SET organization_id=:org'),{'org':ORG})
    with op.batch_alter_table('commitments') as b:
        b.add_column(sa.Column('owner_id',sa.String(36),nullable=True))
        b.add_column(sa.Column('analysis_text',sa.Text(),nullable=False,server_default=''))
        b.add_column(sa.Column('analysis_next',sa.Text(),nullable=False,server_default=''))
        b.add_column(sa.Column('analysis_hash',sa.String(64),nullable=False,server_default=''))
        b.create_foreign_key('fk_commitment_owner','users',['owner_id'],['id'])
        b.create_index('ix_commitments_owner_id',['owner_id'])
    for key,id in mapping.items():db.execute(sa.text('UPDATE commitments SET owner_id=:id WHERE lower(trim(owner))=:name'),{'id':id,'name':key})
    op.create_table('login_sessions',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('conversations',sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('user_a_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('user_b_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('organization_id','user_a_id','user_b_id',name='uq_conversation_pair'))
    op.create_table('messages',sa.Column('id',sa.String(36),primary_key=True),sa.Column('conversation_id',sa.String(36),sa.ForeignKey('conversations.id'),nullable=False),sa.Column('sender_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('body',sa.Text(),nullable=False),sa.Column('commitment_id',sa.String(36),sa.ForeignKey('commitments.id',ondelete='SET NULL')),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_messages_conversation_id','messages',['conversation_id'])
    op.create_index('ix_messages_created_at','messages',['created_at'])
    op.create_table('attachments',sa.Column('id',sa.String(36),primary_key=True),sa.Column('message_id',sa.String(36),sa.ForeignKey('messages.id'),nullable=False),sa.Column('filename',sa.String(255),nullable=False),sa.Column('mime_type',sa.String(120),nullable=False),sa.Column('size_bytes',sa.Integer(),nullable=False),sa.Column('storage_key',sa.String(500),nullable=False),sa.Column('uploaded_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_attachments_message_id','attachments',['message_id'])
def downgrade():
    for table in ('attachments','messages','conversations','login_sessions'):op.drop_table(table)
    with op.batch_alter_table('commitments') as b:
        b.drop_index('ix_commitments_owner_id');b.drop_constraint('fk_commitment_owner',type_='foreignkey')
        for col in ('owner_id','analysis_text','analysis_next','analysis_hash'):b.drop_column(col)
    with op.batch_alter_table('meetings') as b:
        b.drop_index('ix_meetings_organization_id');b.drop_constraint('fk_meeting_organization',type_='foreignkey');b.drop_column('organization_id')
    op.drop_table('users');op.drop_table('organizations')
