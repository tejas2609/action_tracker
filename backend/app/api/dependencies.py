from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import current_user
from app.models.people import User
from app.ai.provider import get_provider
from app.repositories.store import Store
from app.services.commitments.workflow import Workflow


def service(
    db: Session = Depends(get_db),
    ai=Depends(get_provider),
    actor: User = Depends(current_user),
):
    from app.ai.session_provider import SessionAwareProvider

    return Workflow(Store(db, actor), SessionAwareProvider(ai, db))
