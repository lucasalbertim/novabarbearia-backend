from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
from datetime import datetime

from database import get_db, engine
from models import Base, Admin
from schemas import (
    ClientCreate, ClientResponse, ClientLogin,
    AdminCreate, AdminLogin, AdminResponse,
    ServiceCreate, ServiceResponse,
    AttendanceCreate, AttendanceResponse,
    AttendanceUpdate
)
from services import (
    client_service, admin_service, service_service,
    attendance_service, whatsapp_service
)
from auth import get_current_admin

# Criar tabelas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Metheus Barber API",
    description="API para sistema de barbearia",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração para servir arquivos estáticos do frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

# Rota para servir o frontend
@app.get("/")
async def serve_frontend():
    """Servir o frontend React"""
    if os.path.exists(frontend_path):
        index_path = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    
    return {"message": "Frontend não encontrado. Execute 'npm run build' no diretório frontend."}

# Rota para manifest.json
@app.get("/manifest.json")
async def serve_manifest():
    """Servir o manifest.json"""
    manifest_path = os.path.join(frontend_path, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path)
    
    # Fallback para desenvolvimento
    dev_manifest_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "manifest.json")
    if os.path.exists(dev_manifest_path):
        return FileResponse(dev_manifest_path)
    
    raise HTTPException(status_code=404, detail="Manifest não encontrado")

# Health check
@app.get("/health")
async def health_check():
    """Verificar status da API"""
    return {"status": "healthy", "message": "Metheus Barber API funcionando"}

# Rotas de Cliente
@app.post("/clients/", response_model=ClientResponse)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    """Cadastrar novo cliente"""
    return client_service.create_client(db, client)

@app.post("/clients/login", response_model=ClientResponse)
def client_login(login_data: ClientLogin, db: Session = Depends(get_db)):
    """Login do cliente via CPF ou telefone"""
    return client_service.login_client(db, login_data)

@app.get("/clients/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Obter cliente por ID"""
    return client_service.get_client(db, client_id)

@app.get("/clients/{client_id}/attendances", response_model=List[AttendanceResponse])
def get_client_attendances(client_id: int, db: Session = Depends(get_db)):
    """Obter atendimentos de um cliente específico"""
    return attendance_service.get_client_attendances(db, client_id)

# Rotas de Administrador
@app.post("/admins/", response_model=AdminResponse)
def create_admin(admin: AdminCreate, db: Session = Depends(get_db)):
    """Cadastrar novo administrador"""
    return admin_service.create_admin(db, admin)

@app.post("/admins/login")
def admin_login(login_data: AdminLogin, db: Session = Depends(get_db)):
    """Login do administrador"""
    return admin_service.login_admin(db, login_data)

@app.get("/admins/me", response_model=AdminResponse)
def get_current_admin_info(current_admin: Admin = Depends(get_current_admin)):
    """Obter informações do administrador logado"""
    return current_admin

# Rotas de Cliente (Administrativas)
@app.get("/admin/clients/", response_model=List[ClientResponse])
def list_clients(
    status: str = Query("all", description="Filtro de status: all, active, inactive"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Listar clientes com filtro de status (apenas admin)"""
    return client_service.get_clients_with_status(db, status, skip, limit)

@app.get("/admin/clients/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Obter cliente específico (apenas admin)"""
    return client_service.get_client(db, client_id)

@app.post("/admin/clients/", response_model=ClientResponse)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Criar novo cliente (apenas admin)"""
    return client_service.create_client(db, client)

@app.put("/admin/clients/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    client_update: ClientCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Atualizar cliente (apenas admin)"""
    return client_service.update_client(db, client_id, client_update)

@app.delete("/admin/clients/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Excluir cliente (apenas admin)"""
    client_service.delete_client(db, client_id)
    return {"message": "Cliente excluído com sucesso"}

@app.post("/admin/clients/auto-inactivate")
def auto_inactivate_clients(
    days_inactive: int = 45,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Inativar automaticamente clientes inativos (apenas admin)"""
    count = client_service.auto_inactivate_clients(db, days_inactive)
    return {"message": f"{count} clientes foram inativados automaticamente"}

@app.post("/admin/clients/{client_id}/reactivate")
def reactivate_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Reativar cliente inativo (apenas admin)"""
    client = client_service.get_client(db, client_id)
    if client.is_active:
        raise HTTPException(status_code=400, detail="Cliente já está ativo")
    
    client.is_active = True
    client.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(client)
    
    return {"message": "Cliente reativado com sucesso"}

# Rotas de Serviços
@app.post("/services/", response_model=ServiceResponse)
def create_service(
    service: ServiceCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Criar novo serviço (apenas admin)"""
    return service_service.create_service(db, service)

@app.get("/services/", response_model=List[ServiceResponse])
def list_services(db: Session = Depends(get_db)):
    """Listar todos os serviços"""
    return service_service.get_services(db)

@app.put("/services/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: int,
    service_update: ServiceCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Atualizar serviço (apenas admin)"""
    return service_service.update_service(db, service_id, service_update)

@app.delete("/services/{service_id}")
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Inativar serviço (apenas admin)"""
    service_service.delete_service(db, service_id)
    return {"message": "Serviço inativado com sucesso"}

# Rotas de Atendimento
@app.post("/attendance/", response_model=AttendanceResponse)
def create_attendance(
    attendance: AttendanceCreate,
    db: Session = Depends(get_db)
):
    """Criar novo atendimento"""
    return attendance_service.create_attendance(db, attendance)

@app.get("/attendance/today", response_model=List[AttendanceResponse])
def get_today_attendance(db: Session = Depends(get_db)):
    """Obter atendimentos do dia"""
    return attendance_service.get_today_attendance(db)

@app.put("/attendance/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: int,
    attendance_update: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Atualizar atendimento (apenas admin)"""
    return attendance_service.update_attendance(db, attendance_id, attendance_update)

@app.delete("/attendance/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Excluir atendimento (apenas admin)"""
    attendance_service.delete_attendance(db, attendance_id)
    return {"message": "Atendimento excluído com sucesso"}

# Rotas de Relatórios
@app.get("/admin/reports/summary")
def get_reports_summary(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Obter resumo de relatórios (apenas admin)"""
    return attendance_service.get_reports_summary(db)

@app.get("/admin/reports/summary-by-period")
def get_reports_summary_by_period(
    period: str,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Obter resumo de relatórios por período (apenas admin)"""
    return attendance_service.get_reports_summary_by_period(db, period, start_date, end_date)

@app.get("/admin/reports/top-clients")
def get_top_clients(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Obter top clientes (apenas admin)"""
    return attendance_service.get_top_clients(db)

@app.get("/admin/reports/recent-activities")
def get_recent_activities(
    limit: int = Query(10, description="Número de atividades a retornar"),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Obter atividades recentes (apenas admin)"""
    return attendance_service.get_recent_activities(db, limit)

@app.get("/admin/reports/revenue-chart")
def get_revenue_chart(
    period: str,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Obter dados de receita para gráfico (apenas admin)"""
    return attendance_service.get_revenue_by_period(db, period, start_date, end_date)

@app.get("/admin/reports/export")
def export_reports(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Exportar relatórios (apenas admin)"""
    return attendance_service.export_reports(db)

# Rotas de WhatsApp
@app.post("/whatsapp/send-message")
def send_whatsapp_message(
    phone: str,
    message: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """Enviar mensagem via WhatsApp (apenas admin)"""
    return whatsapp_service.send_message(phone, message)