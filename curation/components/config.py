
import os
from dotenv import load_dotenv
import logging

load_dotenv()

# Queste variabili saranno in seguito sovrascrite dai valori nel database
# ma dobbiamo avere dei valori di default all'avvio
TEST = True

node_list = {
        "steem": [
            "https://api.moecki.online",
            "https://api.steemit.com",
            "https://api.justyy.com"
            
        ],
        "hive": [
            "https://api.deathwing.me",
            "https://api.hive.blog",
            "https://api.openhive.network"
        ]
    }

# Il livello di log dipenderà dal valore di TEST che verrà caricato in seguito
log_level = logging.INFO
log_file_path = "log.txt"

steem_domain ="https://steemit.com"
hive_domain ="https://peakd.com"

admin_id = "1026795763"
TOKEN = ""

# Valori predefiniti che verranno sostituiti dalle impostazioni nel database
steem_curator = "tasuboyz"
steem_curator_posting_key = ""  # Per sicurezza, non definiamo più chiavi hardcoded
hive_curator = "menny.trx"
hive_curator_posting_key = ""  # Per sicurezza, non definiamo più chiavi hardcoded
steem_active_key = ""  # Per sicurezza, non definiamo più chiavi hardcoded

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///yourdatabase.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SOCIAL_PUBLISHER_INTERVAL = 300  # 5 minuti

# Funzione per aggiornare le impostazioni dal database
def update_config_from_db(settings_service):
    """Aggiorna le variabili di configurazione utilizzando i valori dal database"""
    global TEST, log_level, steem_curator, steem_curator_posting_key
    global hive_curator, hive_curator_posting_key, steem_active_key
    global admin_id, TOKEN
    
    # Recupera la modalità test
    test_mode = settings_service.get_setting('test_mode', default='true')
    TEST = test_mode.lower() == 'true'
    
    # Aggiorna il livello di log in base alla modalità test
    log_level = logging.INFO if TEST else logging.ERROR
    
    # Recupera le informazioni del curatore per Steem
    steem_curator = settings_service.get_setting('steem_curator', default=steem_curator)
    steem_curator_posting_key = settings_service.get_setting('steem_curator_posting_key', default='')
    steem_active_key = settings_service.get_setting('steem_active_key', default='')
    
    # Recupera le informazioni del curatore per Hive
    hive_curator = settings_service.get_setting('hive_curator', default=hive_curator)
    hive_curator_posting_key = settings_service.get_setting('hive_curator_posting_key', default='')
    
    # Recupera admin_ids e bot_token
    admin_id = settings_service.get_setting('admin_ids', default=admin_id)
    TOKEN = settings_service.get_setting('bot_token', default=TOKEN)