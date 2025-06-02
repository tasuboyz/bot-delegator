import requests
from ..components.logger_config import logger

class TelegramNotifier:
    def __init__(self, app=None):
        self.app = app
        
    def send_message(self, bot_token, chat_id, message, disable_web_page_preview=False):
        """
        Invia un messaggio Telegram a uno o più utenti.
        
        Args:
            bot_token (str): Token del bot Telegram
            chat_id (str): ID chat o lista di ID separati da virgola
            message (str): Messaggio da inviare
            disable_web_page_preview (bool): Se disattivare l'anteprima dei link
        
        Returns:
            list: Lista dei risultati dell'invio per ogni chat_id
        """
        if not bot_token or not chat_id:
            logger.warning("Token del bot o chat_id mancanti, impossibile inviare messaggio Telegram")
            return False
            
        # Supporto per più admin ID
        chat_ids = [id.strip() for id in str(chat_id).split(',') if id.strip()]
        
        results = []
        for id in chat_ids:
            try:
                params = {
                    'chat_id': id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': disable_web_page_preview
                }
                
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                response = requests.get(url, params=params)
                results.append(response.json())
                logger.debug(f"Messaggio Telegram inviato a {id}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Errore comunicazione con server Telegram per chat_id {id}: {e}")
                results.append({"error": str(e)})
        
        return results

# Instanza singleton
telegram_notifier = TelegramNotifier()