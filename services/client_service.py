from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from typing import List, Optional

from models import Client, Attendance
from schemas import ClientCreate, ClientLogin
from services.whatsapp_service import whatsapp_service


def _only_digits(value: str) -> str:
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def _normalize_email(value: Optional[str]) -> Optional[str]:
    return (value or '').strip().lower() or None


def _is_valid_cpf(cpf: str) -> bool:
    digits = _only_digits(cpf)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False
    def calc(base: str) -> int:
        total = sum(int(base[i]) * (len(base) + 1 - i) for i in range(len(base)))
        mod = total % 11
        return 0 if mod < 2 else 11 - mod
    d1 = calc(digits[:9])
    d2 = calc(digits[:9] + str(d1))
    return digits.endswith(f"{d1}{d2}")


class ClientService:
    def create_client(self, db: Session, client: ClientCreate) -> Client:
        # Sanitização
        cpf_digits = _only_digits(client.cpf)
        phone_digits = _only_digits(client.phone)
        email_norm = _normalize_email(client.email)

        # Validação
        if not _is_valid_cpf(cpf_digits):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CPF inválido")
        if len(phone_digits) not in (10, 11):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telefone inválido")

        # Verificar se CPF já existe
        if db.query(Client).filter(Client.cpf == cpf_digits).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CPF já cadastrado"
            )
        
        # Verificar se telefone já existe
        if db.query(Client).filter(Client.phone == phone_digits).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telefone já cadastrado"
            )
        
        payload = client.dict()
        payload["cpf"] = cpf_digits
        payload["phone"] = phone_digits
        payload["email"] = email_norm
        payload["name"] = payload["name"].strip()
        db_client = Client(**payload)
        db.add(db_client)
        db.commit()
        db.refresh(db_client)
        
        # Enviar mensagem de boas-vindas via WhatsApp
        try:
            welcome_message = f"Seja bem-vindo, {db_client.name}! Você foi cadastrado com sucesso na Matheus Barber."
            whatsapp_service.send_message(db_client.phone, welcome_message)
        except Exception as e:
            print(f"Erro ao enviar mensagem WhatsApp: {e}")
        
        return db_client
    
    def login_client(self, db: Session, login_data: ClientLogin) -> Client:
        # Buscar cliente por CPF ou telefone (sanitizado)
        identifier = _only_digits(login_data.identifier)
        client = db.query(Client).filter(
            and_(
                Client.is_active == True,
                (Client.cpf == identifier) | (Client.phone == identifier)
            )
        ).first()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente não encontrado"
            )
        
        # Verificar se é cliente retornante (tem atendimentos anteriores)
        is_returning = db.query(Client).filter(
            and_(
                Client.id == client.id,
                Client.attendances.any()
            )
        ).first() is not None
        
        # Enviar mensagem de boas-vindas
        try:
            if is_returning:
                message = f"Bem-vindo de volta, {client.name}!"
            else:
                message = f"Seja bem-vindo, {client.name}!"
            
            whatsapp_service.send_message(client.phone, message)
        except Exception as e:
            print(f"Erro ao enviar mensagem WhatsApp: {e}")
        
        return client
    
    def get_client(self, db: Session, client_id: int) -> Client:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente não encontrado"
            )
        return client
    
    def get_clients(self, db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
        return db.query(Client).offset(skip).limit(limit).all()
    
    def update_client(self, db: Session, client_id: int, client_update: ClientCreate) -> Client:
        db_client = self.get_client(db, client_id)
        
        cpf_digits = _only_digits(client_update.cpf)
        phone_digits = _only_digits(client_update.phone)
        email_norm = _normalize_email(client_update.email)

        if not _is_valid_cpf(cpf_digits):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CPF inválido")
        if len(phone_digits) not in (10, 11):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telefone inválido")
        
        # Verificar se CPF já existe (se foi alterado)
        if cpf_digits != db_client.cpf:
            if db.query(Client).filter(and_(Client.cpf == cpf_digits, Client.id != client_id)).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CPF já cadastrado"
                )
        
        # Verificar se telefone já existe (se foi alterado)
        if phone_digits != db_client.phone:
            if db.query(Client).filter(and_(Client.phone == phone_digits, Client.id != client_id)).first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Telefone já cadastrado"
                )
        
        db_client.name = client_update.name.strip()
        db_client.cpf = cpf_digits
        db_client.phone = phone_digits
        db_client.email = email_norm
        
        db_client.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_client)
        
        return db_client
    
    def delete_client(self, db: Session, client_id: int):
        """Excluir cliente definitivamente do banco"""
        db_client = self.get_client(db, client_id)
        db.delete(db_client)
        db.commit()
    
    def inactivate_client(self, db: Session, client_id: int):
        """Marcar cliente como inativo (após 45 dias sem visita)"""
        db_client = self.get_client(db, client_id)
        db_client.is_active = False
        db_client.updated_at = datetime.utcnow()
        db.commit()
    
    def get_clients_with_status(self, db: Session, status_filter: str = "all", skip: int = 0, limit: int = 100) -> List[Client]:
        """Buscar clientes com filtro de status"""
        query = db.query(Client)
        
        if status_filter == "active":
            query = query.filter(Client.is_active == True)
        elif status_filter == "inactive":
            query = query.filter(Client.is_active == False)
        # Se "all", não aplica filtro
        
        return query.offset(skip).limit(limit).all()
    
    def get_inactive_clients(self, db: Session, days_inactive: int = 45) -> List[Client]:
        """Buscar clientes inativos por X dias"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        return db.query(Client).filter(
            and_(
                Client.is_active == True,
                Client.updated_at < cutoff_date
            )
        ).all()
    
    def auto_inactivate_clients(self, db: Session, days_inactive: int = 45) -> int:
        """Inativar automaticamente clientes que não vieram há X dias"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        
        # Buscar clientes ativos que não tiveram atendimentos recentes
        clients_to_inactivate = db.query(Client).filter(
            and_(
                Client.is_active == True,
                ~Client.id.in_(
                    db.query(Attendance.client_id).filter(
                        func.date(Attendance.appointment_date) >= cutoff_date.date()
                    ).distinct()
                )
            )
        ).all()
        
        # Inativar clientes
        count = 0
        for client in clients_to_inactivate:
            client.is_active = False
            client.updated_at = datetime.utcnow()
            count += 1
        
        db.commit()
        return count

client_service = ClientService()