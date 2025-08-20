from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import Admin
from services.admin_service import admin_service
from security import verify_token

security = HTTPBearer()

async def get_current_admin(
    token: str = Depends(security),
    db: Session = Depends(get_db)
) -> Admin:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    username = verify_token(token.credentials)
    if username is None:
        raise credentials_exception
    
    admin = admin_service.get_admin_by_username(db, username)
    if admin is None:
        raise credentials_exception
    
    return admin