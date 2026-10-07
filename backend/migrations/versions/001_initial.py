from alembic import op
import sqlalchemy as sa
revision='001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('meetings',sa.Column('id',sa.String(36),primary_key=True),sa.Column('title',sa.String(200),nullable=False),sa.Column('held_on',sa.Date(),nullable=False),sa.Column('transcript',sa.Text(),nullable=False),sa.Column('findings',sa.JSON(),nullable=False),sa.Column('state',sa.String(30),nullable=False))
    op.create_table('commitments',sa.Column('id',sa.String(36),primary_key=True),sa.Column('title',sa.String(500),nullable=False),sa.Column('owner',sa.String(120),nullable=False),sa.Column('due_date',sa.Date()),sa.Column('status',sa.String(30),nullable=False),sa.Column('progress',sa.Integer(),nullable=False),sa.Column('condition',sa.Text(),nullable=False),sa.Column('condition_met',sa.Boolean(),nullable=False),sa.Column('blocker',sa.Text(),nullable=False),sa.Column('source_statement',sa.Text(),nullable=False),sa.Column('meeting_id',sa.String(36),sa.ForeignKey('meetings.id'),nullable=False))
    for col in ('owner','due_date','status'): op.create_index('ix_commitments_'+col,'commitments',[col])
    op.create_table('dependencies',sa.Column('commitment_id',sa.String(36),sa.ForeignKey('commitments.id'),primary_key=True),sa.Column('prerequisite_id',sa.String(36),sa.ForeignKey('commitments.id'),primary_key=True))
    op.create_table('events',sa.Column('id',sa.String(36),primary_key=True),sa.Column('commitment_id',sa.String(36),sa.ForeignKey('commitments.id'),nullable=False),sa.Column('meeting_id',sa.String(36),sa.ForeignKey('meetings.id')),sa.Column('kind',sa.String(40),nullable=False),sa.Column('message',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_events_commitment_id','events',['commitment_id'])
def downgrade():
    for table in ('events','dependencies','commitments','meetings'): op.drop_table(table)
