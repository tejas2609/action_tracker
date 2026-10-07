import hashlib
from datetime import datetime,timezone
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.people import User,LoginSession
security=HTTPBearer(auto_error=False)
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(security),db:Session=Depends(get_db)):
    if not credentials:raise HTTPException(401,'Choose a demo user to sign in.')
    token_hash=hashlib.sha256(credentials.credentials.encode()).hexdigest()
    session=db.get(LoginSession,token_hash)
    if not session:raise HTTPException(401,'Session expired. Sign in again.')
    expiry=session.expires_at
    if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
    if expiry<=datetime.now(timezone.utc):raise HTTPException(401,'Session expired. Sign in again.')
    user=db.get(User,session.user_id)
    if not user or not user.active:raise HTTPException(401,'User unavailable.')
    return user
