from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from fastapi import HTTPException, status
from datetime import datetime, date
from typing import List, Dict, Any

from models import Attendance, Client, Service
from schemas import AttendanceCreate, AttendanceUpdate
from utils.date_utils import get_recife_datetime, get_recife_date

class AttendanceService:
    def create_attendance(self, db: Session, attendance: AttendanceCreate) -> Attendance:
        # Verificar se cliente existe
        client = db.query(Client).filter(Client.id == attendance.client_id).first()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente não encontrado"
            )
        
        # Reativar cliente se estiver inativo
        if not client.is_active:
            client.is_active = True
            client.updated_at = get_recife_datetime()
            db.commit()
            db.refresh(client)
        
        # Buscar e validar serviços
        services = db.query(Service).filter(Service.id.in_(attendance.service_ids), Service.is_active == True).all()
        if not services or len(services) != len(attendance.service_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Um ou mais serviços inválidos/inativos"
            )
        
        payload = attendance.dict()
        payload.pop('service_ids', None)
        
        db_attendance = Attendance(**payload)
        db_attendance.services = services
        # Definir status inicial explicitamente
        db_attendance.status = "waiting"
        db_attendance.payment_status = "pending"
        
        db.add(db_attendance)
        db.commit()
        db.refresh(db_attendance)
        
        return db_attendance
    
    def get_attendance(self, db: Session, attendance_id: int) -> Attendance:
        attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atendimento não encontrado"
            )
        return attendance
    
    def get_today_attendance(self, db: Session) -> List[Attendance]:
        today = get_recife_date()
        
        # Buscar atendimentos de hoje
        attendances = db.query(Attendance).filter(
            func.date(Attendance.appointment_date) == today
        ).order_by(Attendance.appointment_date.desc()).all()
        
        return attendances
    
    def update_attendance(self, db: Session, attendance_id: int, attendance_update: AttendanceUpdate) -> Attendance:
        db_attendance = self.get_attendance(db, attendance_id)
        update_data = attendance_update.dict(exclude_unset=True)

        # Se houver transição de status para finished, marcar pagamento como paid (simulado)
        new_status = update_data.get('status')
        if new_status:
            db_attendance.status = new_status
            if new_status == 'finished':
                db_attendance.payment_status = 'paid'
        
        if 'payment_method' in update_data and update_data['payment_method'] is not None:
            db_attendance.payment_method = update_data['payment_method']
        if 'payment_status' in update_data and update_data['payment_status'] is not None:
            db_attendance.payment_status = update_data['payment_status']
        if 'notes' in update_data:
            db_attendance.notes = update_data['notes']
        
        db_attendance.updated_at = get_recife_datetime()
        db.commit()
        db.refresh(db_attendance)
        
        return db_attendance
    
    def delete_attendance(self, db: Session, attendance_id: int):
        db_attendance = self.get_attendance(db, attendance_id)
        db.delete(db_attendance)
        db.commit()
    
    def get_reports_summary(self, db: Session) -> Dict[str, Any]:
        """Obter resumo de relatórios para dashboard administrativo"""
        today = get_recife_date()
        
        # Total de clientes
        total_clients = db.query(func.count(Client.id)).filter(Client.is_active == True).scalar()
        
        # Total de atendimentos
        total_attendances = db.query(func.count(Attendance.id)).scalar()
        
        # Receita total (soma de serviços dos atendimentos pagos)
        total_revenue = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
            Attendance.payment_status == "paid"
        ).scalar() or 0.0
        
        # Clientes inativos (marcados como inativos no banco)
        inactive_clients = db.query(func.count(Client.id)).filter(Client.is_active == False).scalar()
        
        # Atendimentos de hoje
        today_attendances = db.query(func.count(Attendance.id)).filter(
            func.date(Attendance.appointment_date) == today
        ).scalar()
        
        # Pagamentos pendentes
        pending_payments = db.query(func.count(Attendance.id)).filter(
            Attendance.payment_status == "pending"
        ).scalar()
        
        # Calcular ticket médio
        average_ticket = total_revenue / total_attendances if total_attendances > 0 else 0.0
        
        # Calcular porcentagens de crescimento (mês atual vs mês anterior)
        growth_percentages = self._get_dashboard_growth_percentages(db)
        
        return {
            "totalClients": total_clients,
            "totalAttendances": total_attendances,
            "totalRevenue": float(total_revenue),
            "averageTicket": float(average_ticket),
            "inactiveClients": inactive_clients,
            "todayAttendances": today_attendances,
            "pendingPayments": pending_payments,
            "growthPercentages": growth_percentages
        }
    
    def get_attendance_by_status(self, db: Session, status: str) -> List[Attendance]:
        """Buscar atendimentos por status"""
        return db.query(Attendance).filter(Attendance.status == status).all()
    
    def get_attendance_by_date_range(self, db: Session, start_date: date, end_date: date) -> List[Attendance]:
        """Buscar atendimentos por período"""
        return db.query(Attendance).filter(
            and_(
                func.date(Attendance.appointment_date) >= start_date,
                func.date(Attendance.appointment_date) <= end_date
            )
        ).all()

    def get_client_attendances(self, db: Session, client_id: int) -> List[Attendance]:
        """Buscar atendimentos de um cliente específico"""
        return db.query(Attendance).filter(
            Attendance.client_id == client_id
        ).order_by(Attendance.appointment_date.desc()).all()

    def get_top_clients(self, db: Session) -> List[Dict[str, Any]]:
        """Obter top clientes por número de atendimentos"""
        from sqlalchemy import desc
        
        result = db.query(
            Client.id,
            Client.name,
            Client.phone,
            func.count(Attendance.id).label('attendance_count'),
            func.sum(Service.price).label('total_spent'),
            func.max(Attendance.appointment_date).label('last_visit')
        ).join(Attendance, Client.id == Attendance.client_id)\
         .join(Attendance.services)\
         .filter(Attendance.payment_status == "paid")\
         .group_by(Client.id, Client.name, Client.phone)\
         .order_by(desc('attendance_count'))\
         .limit(10)\
         .all()
        
        return [
            {
                "id": row.id,
                "name": row.name,
                "phone": row.phone,
                "totalVisits": row.attendance_count,
                "totalRevenue": float(row.total_spent) if row.total_spent else 0.0,
                "lastVisit": row.last_visit.isoformat() if row.last_visit else None,
                "status": "active"  # Por enquanto todos são ativos
            }
            for row in result
        ]

    def get_recent_activities(self, db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """Obter atividades recentes do sistema"""
        from sqlalchemy import desc
        
        # Buscar atendimentos recentes
        recent_attendances = db.query(
            Attendance.id,
            Attendance.status,
            Attendance.payment_status,
            Attendance.appointment_date,
            Attendance.updated_at,
            Client.name.label('client_name'),
            func.string_agg(Service.name, ', ').label('services')
        ).join(Client, Attendance.client_id == Client.id)\
         .join(Attendance.services)\
         .group_by(Attendance.id, Attendance.status, Attendance.payment_status, 
                  Attendance.appointment_date, Attendance.updated_at, Client.name)\
         .order_by(desc(Attendance.updated_at))\
         .limit(limit)\
         .all()
        
        activities = []
        
        for attendance in recent_attendances:
            # Determinar tipo de atividade baseado no status
            if attendance.status == "waiting":
                activity_type = "new_attendance"
                title = f"Novo atendimento - {attendance.client_name}"
                description = f"Serviços: {attendance.services}"
            elif attendance.status == "progress":
                activity_type = "attendance_started"
                title = f"Atendimento iniciado - {attendance.client_name}"
                description = f"Serviços: {attendance.services}"
            elif attendance.status == "finished":
                if attendance.payment_status == "paid":
                    activity_type = "attendance_completed"
                    title = f"Atendimento concluído - {attendance.client_name}"
                    description = f"Serviços: {attendance.services}"
                else:
                    activity_type = "attendance_finished"
                    title = f"Atendimento finalizado - {attendance.client_name}"
                    description = f"Serviços: {attendance.services}"
            else:
                activity_type = "attendance_updated"
                title = f"Atendimento atualizado - {attendance.client_name}"
                description = f"Status: {attendance.status}"
            
            activities.append({
                "id": attendance.id,
                "type": activity_type,
                "title": title,
                "description": description,
                "timestamp": attendance.updated_at.isoformat(),
                "client_name": attendance.client_name,
                "services": attendance.services,
                "status": attendance.status,
                "payment_status": attendance.payment_status
            })
        
        return activities

    def get_reports_summary_by_period(self, db: Session, period: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """Obter resumo de relatórios por período específico"""
        from datetime import datetime, timedelta
        
        # Definir período atual
        if start_date and end_date:
            current_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            current_end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            today = date.today()
            if period == 'day':
                current_start = current_end = today
            elif period == 'week':
                current_start = today - timedelta(days=today.weekday())
                current_end = current_start + timedelta(days=6)
            elif period == 'month':
                current_start = today.replace(day=1)
                if today.month == 12:
                    current_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    current_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            elif period == 'quarter':
                quarter_start_month = ((today.month - 1) // 3) * 3 + 1
                current_start = today.replace(month=quarter_start_month, day=1)
                if quarter_start_month == 10:
                    current_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    current_end = today.replace(month=quarter_start_month + 3, day=1) - timedelta(days=1)
            elif period == 'year':
                current_start = today.replace(month=1, day=1)
                current_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                current_start = current_end = today
        
        # Calcular período anterior
        days_diff = (current_end - current_start).days + 1
        previous_start = current_start - timedelta(days=days_diff)
        previous_end = current_start - timedelta(days=1)
        
        # Buscar dados do período atual
        current_metrics = self._get_metrics_for_period(db, current_start, current_end)
        
        # Buscar dados do período anterior
        previous_metrics = self._get_metrics_for_period(db, previous_start, previous_end)
        
        # Calcular porcentagens de crescimento
        growth_percentages = self._calculate_growth_percentages(current_metrics, previous_metrics)
        
        return {
            **current_metrics,
            "growthPercentages": growth_percentages,
            "period": {
                "current": {"start": current_start.isoformat(), "end": current_end.isoformat()},
                "previous": {"start": previous_start.isoformat(), "end": previous_end.isoformat()}
            }
        }
    
    def _get_metrics_for_period(self, db: Session, start_date: date, end_date: date) -> Dict[str, Any]:
        """Obter métricas para um período específico"""
        # Total de clientes ativos (sempre total, não por período)
        total_clients = db.query(func.count(Client.id)).filter(Client.is_active == True).scalar()
        
        # Clientes que fizeram atendimentos no período
        clients_in_period = db.query(func.count(func.distinct(Attendance.client_id))).filter(
            and_(
                func.date(Attendance.appointment_date) >= start_date,
                func.date(Attendance.appointment_date) <= end_date
            )
        ).scalar()
        
        # Atendimentos no período
        attendances_in_period = db.query(func.count(Attendance.id)).filter(
            and_(
                func.date(Attendance.appointment_date) >= start_date,
                func.date(Attendance.appointment_date) <= end_date
            )
        ).scalar()
        
        # Receita no período
        revenue_in_period = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
            and_(
                Attendance.payment_status == "paid",
                func.date(Attendance.appointment_date) >= start_date,
                func.date(Attendance.appointment_date) <= end_date
            )
        ).scalar() or 0.0
        
        # Ticket médio no período
        average_ticket = revenue_in_period / attendances_in_period if attendances_in_period > 0 else 0.0
        
        return {
            "totalClients": total_clients,
            "activeClientsInPeriod": clients_in_period,
            "totalAttendances": attendances_in_period,
            "totalRevenue": float(revenue_in_period),
            "averageTicket": float(average_ticket)
        }
    
    def _calculate_growth_percentages(self, current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, float]:
        """Calcular porcentagens de crescimento"""
        def calculate_percentage(current_val, previous_val):
            if previous_val == 0:
                return 100.0 if current_val > 0 else 0.0
            return ((current_val - previous_val) / previous_val) * 100
        
        return {
            "revenueGrowth": calculate_percentage(current["totalRevenue"], previous["totalRevenue"]),
            "clientsGrowth": calculate_percentage(current["activeClientsInPeriod"], previous["activeClientsInPeriod"]),
            "attendancesGrowth": calculate_percentage(current["totalAttendances"], previous["totalAttendances"]),
            "averageTicketGrowth": calculate_percentage(current["averageTicket"], previous["averageTicket"])
        }

    def _get_dashboard_growth_percentages(self, db: Session) -> Dict[str, float]:
        """Calcular porcentagens de crescimento para dashboard (mês atual vs anterior)"""
        from datetime import datetime, timedelta
        
        today = date.today()
        
        # Mês atual
        current_month_start = today.replace(day=1)
        if today.month == 12:
            current_month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            current_month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        
        # Mês anterior
        if today.month == 1:
            previous_month_start = today.replace(year=today.year - 1, month=12, day=1)
            previous_month_end = today.replace(day=1) - timedelta(days=1)
        else:
            previous_month_start = today.replace(month=today.month - 1, day=1)
            previous_month_end = today.replace(day=1) - timedelta(days=1)
        
        # Buscar dados dos dois meses
        current_metrics = self._get_metrics_for_period(db, current_month_start, current_month_end)
        previous_metrics = self._get_metrics_for_period(db, previous_month_start, previous_month_end)
        
        # Calcular porcentagens
        return self._calculate_growth_percentages(current_metrics, previous_metrics)

    def get_revenue_by_period(self, db: Session, period: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Obter dados de receita por período para gráfico"""
        from datetime import datetime, timedelta
        
        # Definir período
        if start_date and end_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            today = date.today()
            if period == 'day':
                start = today - timedelta(days=30)  # Últimos 30 dias
                end = today
            elif period == 'week':
                start = today - timedelta(days=12 * 7)  # Últimas 12 semanas
                end = today
            elif period == 'month':
                start = today.replace(day=1) - timedelta(days=365)  # Últimos 12 meses
                end = today
            elif period == 'quarter':
                start = today - timedelta(days=4 * 90)  # Últimos 4 trimestres
                end = today
            elif period == 'year':
                start = today.replace(month=1, day=1) - timedelta(days=365 * 3)  # Últimos 3 anos
                end = today
            else:
                start = today - timedelta(days=30)
                end = today
        
        # Gerar pontos de dados baseados no período
        data_points = []
        current = start
        
        while current <= end:
            if period == 'day':
                # Dados diários
                revenue = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
                    and_(
                        Attendance.payment_status == "paid",
                        func.date(Attendance.appointment_date) == current
                    )
                ).scalar() or 0.0
                
                data_points.append({
                    "date": current.isoformat(),
                    "revenue": float(revenue),
                    "label": current.strftime('%d/%m')
                })
                current += timedelta(days=1)
                
            elif period == 'week':
                # Dados semanais
                week_end = min(current + timedelta(days=6), end)
                revenue = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
                    and_(
                        Attendance.payment_status == "paid",
                        func.date(Attendance.appointment_date) >= current,
                        func.date(Attendance.appointment_date) <= week_end
                    )
                ).scalar() or 0.0
                
                data_points.append({
                    "date": current.isoformat(),
                    "revenue": float(revenue),
                    "label": f"Sem {current.strftime('%U')}"
                })
                current += timedelta(days=7)
                
            elif period == 'month':
                # Dados mensais
                if current.month == 12:
                    month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)
                
                revenue = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
                    and_(
                        Attendance.payment_status == "paid",
                        func.date(Attendance.appointment_date) >= current,
                        func.date(Attendance.appointment_date) <= month_end
                    )
                ).scalar() or 0.0
                
                data_points.append({
                    "date": current.isoformat(),
                    "revenue": float(revenue),
                    "label": current.strftime('%b/%Y')
                })
                
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=current.month + 1, day=1)
                    
            elif period == 'quarter':
                # Dados trimestrais
                quarter_end_month = ((current.month - 1) // 3) * 3 + 3
                if quarter_end_month > 12:
                    quarter_end = current.replace(year=current.year + 1, month=quarter_end_month - 12, day=1) - timedelta(days=1)
                else:
                    quarter_end = current.replace(month=quarter_end_month, day=1) - timedelta(days=1)
                
                revenue = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
                    and_(
                        Attendance.payment_status == "paid",
                        func.date(Attendance.appointment_date) >= current,
                        func.date(Attendance.appointment_date) <= quarter_end
                    )
                ).scalar() or 0.0
                
                data_points.append({
                    "date": current.isoformat(),
                    "revenue": float(revenue),
                    "label": f"T{((current.month - 1) // 3) + 1}/{current.year}"
                })
                
                current = quarter_end + timedelta(days=1)
                
            elif period == 'year':
                # Dados anuais
                year_end = current.replace(month=12, day=31)
                
                revenue = db.query(func.sum(Service.price)).select_from(Attendance).join(Attendance.services).filter(
                    and_(
                        Attendance.payment_status == "paid",
                        func.date(Attendance.appointment_date) >= current,
                        func.date(Attendance.appointment_date) <= year_end
                    )
                ).scalar() or 0.0
                
                data_points.append({
                    "date": current.isoformat(),
                    "revenue": float(revenue),
                    "label": str(current.year)
                })
                
                current = current.replace(year=current.year + 1, month=1, day=1)
        
        return data_points

    def export_reports(self, db: Session) -> Dict[str, Any]:
        """Exportar relatórios (simulado)"""
        # Por enquanto retorna dados básicos para simular exportação
        summary = self.get_reports_summary(db)
        top_clients = self.get_top_clients(db)
        
        return {
            "summary": summary,
            "top_clients": top_clients,
            "export_date": datetime.utcnow().isoformat(),
            "message": "Exportação simulada - implementar geração de arquivo Excel"
        }

attendance_service = AttendanceService()