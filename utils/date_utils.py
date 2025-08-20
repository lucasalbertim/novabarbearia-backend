"""
Utilitários para datas e horários usando o fuso horário de Recife (UTC-3)
"""

from datetime import datetime, timezone, timedelta

def get_recife_datetime():
    """
    Obtém a data/hora atual no fuso horário de Recife (UTC-3)
    """
    utc_now = datetime.now(timezone.utc)
    recife_tz = timezone(timedelta(hours=-3))  # UTC-3
    return utc_now.astimezone(recife_tz)

def get_recife_date():
    """
    Obtém apenas a data atual no fuso horário de Recife
    """
    return get_recife_datetime().date()

def utc_to_recife(utc_datetime):
    """
    Converte uma data UTC para o fuso horário de Recife
    """
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
    
    recife_tz = timezone(timedelta(hours=-3))  # UTC-3
    return utc_datetime.astimezone(recife_tz)