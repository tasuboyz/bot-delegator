from flask import Flask
import os
import threading
from curation.components.db import db
from curation.components.config import TEST, update_config_from_db
from apscheduler.schedulers.background import BackgroundScheduler
from curation.components.logger_config import logger
from curation.services.settings_service import SettingsService

# Singleton per gestire lo stato globale dell'applicazione
class AppState:
    """Classe per gestire lo stato globale dell'applicazione e i suoi servizi"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppState, cls).__new__(cls)
            cls._instance.scheduler = None
            cls._instance.threads = []
        return cls._instance
    
    def register_thread(self, thread):
        """Registra un thread per la gestione centralizzata"""
        self.threads.append(thread)
        return thread
    
    def start_threads(self):
        """Avvia tutti i thread registrati"""
        for thread in self.threads:
            if not thread.is_alive():
                thread.daemon = True
                thread.start()
                logger.info(f"Thread avviato: {thread.name}")
    
    def stop_all(self):
        """Ferma tutte le risorse dell'applicazione"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Scheduler fermato")
        
        # I thread daemon verranno fermati automaticamente quando il programma termina
        logger.info(f"Registrati {len(self.threads)} thread daemon che verranno fermati con l'app")

# Istanza globale dello stato dell'applicazione
app_state = AppState()

def setup_scheduler(app):
    """Configura lo scheduler con il contesto dell'applicazione"""
    with app.app_context():
        scheduler = BackgroundScheduler()
        # Non è più necessario get_user_data poiché ora accediamo direttamente al database
        # scheduler.add_job(func=get_user_data, trigger="interval", seconds=600)
        scheduler.start()
        app_state.scheduler = scheduler
        logger.info("Scheduler avviato")
        return scheduler

def create_app():
    """Factory pattern per creare l'istanza dell'applicazione Flask"""
    # Ottieni il percorso base del progetto (directory principale)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    instance_dir = os.path.join(base_dir, 'instance')
    
    # Assicuriamoci che la directory instance esista
    if not os.path.exists(instance_dir):
        logger.info(f"Creazione directory instance: {instance_dir}")
        os.makedirs(instance_dir, exist_ok=True)
    
    logger.info(f"Base directory: {base_dir}")
    logger.info(f"Template directory: {template_dir}")
    logger.info(f"Static directory: {static_dir}")
    logger.info(f"Instance directory: {instance_dir}")
    
    # Crea l'app Flask con i percorsi corretti per template e static
    app = Flask(__name__, 
                template_folder=template_dir, 
                static_folder=static_dir,
                instance_path=instance_dir)
    
    # Configurazione del database con percorso assoluto
    database_path = os.path.join(instance_dir, 'yourdatabase.db')
    database_uri = f'sqlite:///{database_path}'
    logger.info(f"Database path: {database_path}")
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Inizializza le estensioni
    db.init_app(app)    # Inizializza il database
    with app.app_context():
        try:
            logger.info("Creazione delle tabelle del database...")
            db.create_all()
            logger.info("Tabelle create con successo")
            
            # Inizializza le impostazioni predefinite
            logger.info("Inizializzazione delle impostazioni predefinite...")
            SettingsService.initialize_default_settings()
            
            # Aggiorna le variabili di configurazione con i valori dal database
            update_config_from_db(SettingsService)
            logger.info("Configurazione aggiornata dal database")
            
        except Exception as e:
            logger.error(f"Errore nella creazione delle tabelle o inizializzazione: {e}")
            raise
    
    # Registra blueprints, gestori errori, ecc qui se necessario
    
    return app

def init_services(app):
    """Inizializza tutti i servizi dell'applicazione"""
    # Aggiorna le configurazioni da database nel contesto dell'applicazione
    with app.app_context():
        update_config_from_db(SettingsService)
    
    # Setup dello scheduler
    setup_scheduler(app)
    
    # Importa qui per evitare import circolari
    from curation.sniper import SocialMediaPublisher
    
    # Registra il thread per il publisher
    publisher = SocialMediaPublisher(app)
    publisher_thread = threading.Thread(
        target=publisher.publish_posts, 
        name="PublisherThread",
        daemon=True
    )
    app_state.register_thread(publisher_thread)
    
    # Avvia tutti i thread
    app_state.start_threads()