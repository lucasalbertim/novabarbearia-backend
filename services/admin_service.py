from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import and_

from models import Admin
from schemas import AdminCreate, AdminLogin
from security import get_password_hash, verify_password, create_access_token

class AdminService:
    def create_admin(self, db: Session, admin: AdminCreate) -> Admin:
        # Verificar se username já existe
        if db.query(Admin).filter(Admin.username == admin.username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username já cadastrado"
            )
        
        # Verificar se email já existe
        if db.query(Admin).filter(Admin.email == admin.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado"
            )
        
        # Criar hash da senha
        hashed_password = get_password_hash(admin.password)
        
        db_admin = Admin(
            username=admin.username,
            name=admin.name,
            email=admin.email,
            password_hash=hashed_password
        )
        
        db.add(db_admin)
        db.commit()
        db.refresh(db_admin)
        
        return db_admin
    
    def login_admin(self, db: Session, login_data: AdminLogin):
        # Buscar admin por username
        admin = db.query(Admin).filter(
            Admin.username == login_data.username,
            Admin.is_active == True
        ).first()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas"
            )
        
        # Verificar senha
        if not verify_password(login_data.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas"
            )
        
        # Criar token de acesso
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": admin.username}, expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "admin": admin
        }
    
    def get_admin_by_username(self, db: Session, username: str) -> Optional[Admin]:
        return db.query(Admin).filter(
            Admin.username == username,
            Admin.is_active == True
        ).first()
    
    def get_admin(self, db: Session, admin_id: int) -> Admin:
        admin = db.query(Admin).filter(Admin.id == admin_id).first()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Administrador não encontrado"
            )
        return admin
    
    def update_admin(self, db: Session, admin_id: int, admin_update: AdminCreate) -> Admin:
        db_admin = self.get_admin(db, admin_id)
        
        # Verificar se username já existe (se foi alterado)
        if admin_update.username != db_admin.username:
            if db.query(Admin).filter(and_(Admin.username == admin_update.username, Admin.id != admin_id)).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username já cadastrado"
                )
        
        # Verificar se email já existe (se foi alterado)
        if admin_update.email != db_admin.email:
            if db.query(Admin).filter(and_(Admin.email == admin_update.email, Admin.id != admin_id)).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email já cadastrado"
                )
        
        # Atualizar campos
        db_admin.username = admin_update.username
        db_admin.name = admin_update.name
        db_admin.email = admin_update.email
        
        # Atualizar senha se fornecida
        if admin_update.password:
            db_admin.password_hash = get_password_hash(admin_update.password)
        
        db.commit()
        db.refresh(db_admin)
        
        return db_admin
    
    def delete_admin(self, db: Session, admin_id: int):
        db_admin = self.get_admin(db, admin_id)
        db_admin.is_active = False
        db.commit()

admin_service = AdminService()