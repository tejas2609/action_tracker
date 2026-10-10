from alembic import context
from app.core.database import Base, engine
from app.models import (
    entities,
    people,
    integrations,
    email_actions,
    logs,
    source_actions,
    security,
    notifications,
)

if context.is_offline_mode():
    context.configure(
        url=str(engine.url), target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    else:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
