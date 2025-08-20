import os
import requests
from typing import Dict, Any

class WhatsAppService:
    def __init__(self):
        self.api_key = os.getenv("WHATSAPP_API_KEY")
        self.phone_number = os.getenv("WHATSAPP_PHONE_NUMBER")
        self.base_url = "https://graph.facebook.com/v17.0"
        
    def send_message(self, phone: str, message: str) -> Dict[str, Any]:
        """
        Enviar mensagem via WhatsApp Business API
        
        Para produção, você precisará:
        1. Configurar WhatsApp Business API
        2. Obter token de acesso
        3. Configurar webhook
        """
        
        if not self.api_key or not self.phone_number:
            # Simulação para desenvolvimento
            print(f"📱 WhatsApp (SIMULADO): Enviando para {phone}: {message}")
            return {
                "success": True,
                "message_id": "simulated_message_id",
                "status": "sent"
            }
        
        try:
            # Formatar número de telefone (remover caracteres especiais)
            formatted_phone = phone.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
            if not formatted_phone.startswith("55"):  # Código do Brasil
                formatted_phone = "55" + formatted_phone
            
            # Preparar payload para WhatsApp Business API
            payload = {
                "messaging_product": "whatsapp",
                "to": formatted_phone,
                "type": "text",
                "text": {
                    "body": message
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Fazer requisição para WhatsApp Business API
            response = requests.post(
                f"{self.base_url}/{self.phone_number}/messages",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message_id": result.get("messages", [{}])[0].get("id"),
                    "status": "sent"
                }
            else:
                print(f"Erro ao enviar mensagem WhatsApp: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            print(f"Erro ao enviar mensagem WhatsApp: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_welcome_message(self, phone: str, name: str, is_returning: bool = False) -> Dict[str, Any]:
        """Enviar mensagem de boas-vindas personalizada"""
        if is_returning:
            message = f"Bem-vindo de volta, {name}! 🎉\n\nÉ sempre um prazer tê-lo conosco na Matheus Barber.\n\nSeu atendimento está sendo preparado com todo o carinho e qualidade que você merece."
        else:
            message = f"Seja bem-vindo, {name}! 🎉\n\nVocê foi cadastrado com sucesso na Matheus Barber.\n\nEstamos muito felizes em tê-lo como nosso cliente e garantimos que terá uma experiência incrível conosco."
        
        return self.send_message(phone, message)
    
    def send_appointment_confirmation(self, phone: str, name: str, service: str, date: str, time: str) -> Dict[str, Any]:
        """Enviar confirmação de agendamento"""
        message = f"✅ Confirmação de Agendamento\n\nOlá {name}!\n\nSeu agendamento foi confirmado:\n\n📅 Data: {date}\n⏰ Horário: {time}\n💇‍♂️ Serviço: {service}\n\n📍 Local: Matheus Barber\n\nAguardamos você! 🎯"
        
        return self.send_message(phone, message)
    
    def send_marketing_message(self, phone: str, name: str, days_inactive: int) -> Dict[str, Any]:
        """Enviar mensagem de marketing para clientes inativos"""
        message = f"Olá {name}! 👋\n\nFaz {days_inactive} dias que não nos vemos por aqui na Matheus Barber.\n\n💇‍♂️ Que tal renovar o visual?\n\n🎯 Temos promoções especiais para você!\n\n📞 Agende seu horário: (11) 99999-9999\n\nEsperamos você! 😊"
        
        return self.send_message(phone, message)
    
    def send_payment_reminder(self, phone: str, name: str, service: str, amount: float) -> Dict[str, Any]:
        """Enviar lembrete de pagamento"""
        message = f"💳 Lembrete de Pagamento\n\nOlá {name}!\n\nLembramos que você tem um pagamento pendente:\n\n💇‍♂️ Serviço: {service}\n💰 Valor: R$ {amount:.2f}\n\n📱 Formas de pagamento:\n• Dinheiro\n• Cartão\n• PIX\n\nObrigado pela preferência! 🙏"
        
        return self.send_message(phone, message)

whatsapp_service = WhatsAppService()