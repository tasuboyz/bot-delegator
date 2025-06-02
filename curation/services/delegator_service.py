from flask import current_app
from datetime import datetime, timedelta
import threading
import time
from ..components.db import db, Delegator
from ..components.logger_config import logger
from ..services.settings_service import SettingsService

class DelegatorManager:
    def __init__(self, blockchain_connector, app=None):
        self.blockchain = blockchain_connector
        self.app = app
        self.running = False
        self.thread = None
        self.update_interval = 3600  # Default: aggiorna ogni ora
        self.last_update = None
    
    def start(self):
        """Avvia il thread di schedulazione per l'aggiornamento delegatori"""
        if self.thread and self.thread.is_alive():
            logger.info("Thread di aggiornamento delegatori già in esecuzione")
            return False
            
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Thread di aggiornamento delegatori avviato")
        return True
    
    def stop(self):
        """Ferma il thread di schedulazione"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info("Thread di aggiornamento delegatori fermato")
    
    def _scheduler_loop(self):
        """Loop principale che gestisce gli aggiornamenti schedulati"""
        with self.app.app_context():
            # Recupera l'ultimo aggiornamento dal database
            last_update_setting = SettingsService.get_setting('last_delegator_update', default=None)
            force_update = last_update_setting is None
            
            # Imposta l'intervallo di aggiornamento (in secondi)
            interval_mins = int(SettingsService.get_setting('delegator_update_interval', default=60))
            self.update_interval = interval_mins * 60
            
            while self.running:
                try:
                    # Verifica se è necessario un aggiornamento
                    if force_update or self._is_update_due():
                        logger.info("Avvio aggiornamento delegatori schedulato")
                        self._update_delegators()
                        
                        # Aggiorna timestamp ultimo aggiornamento
                        now = datetime.now().isoformat()
                        SettingsService.set_setting('last_delegator_update', now)
                        self.last_update = now
                        force_update = False
                        
                    # Attendi prima del prossimo controllo
                    for _ in range(60):  # Controlla ogni 60 secondi se è ora di aggiornare
                        if not self.running:
                            break
                        time.sleep(1)
                        
                except Exception as e:
                    logger.error(f"Errore nell'aggiornamento delegatori: {e}")
                    time.sleep(60)  # In caso di errore, attendi un minuto prima di riprovare
    
    def _is_update_due(self):
        """Controlla se è necessario un aggiornamento basato sull'intervallo configurato"""
        if not self.last_update:
            last_update_setting = SettingsService.get_setting('last_delegator_update', default=None)
            if not last_update_setting:
                return True
                
            try:
                self.last_update = last_update_setting
            except:
                return True
        
        try:
            last_dt = datetime.fromisoformat(self.last_update)
            next_update = last_dt + timedelta(seconds=self.update_interval)
            return datetime.now() >= next_update
        except:
            return True
    
    def _update_delegators(self):
        """Aggiorna il database dei delegatori"""
        try:
            # Recupera i delegatori dalla blockchain
            delegations = self.blockchain.get_steem_delegators()
            
            if not delegations:
                logger.warning("Nessun delegatore trovato durante l'aggiornamento")
                return
                
            # Prepara le modifiche da processare
            changes = []
            for op in delegations:
                delegator = op['delegator']
                amount = op['vesting_shares']['amount']
                entry = Delegator.query.filter_by(username=delegator).first()
                
                if not entry:
                    changes.append({'type': 'new', 'data': op})
                elif entry.vesting_shares != amount:
                    changes.append({'type': 'update', 'data': op})
            
            # Applica le modifiche al database
            with self.app.app_context():
                for change in changes:
                    op = change['data']
                    delegator = op['delegator']
                    entry = Delegator.query.filter_by(username=delegator).first()
                    
                    if change['type'] == 'new':
                        new_entry = Delegator(
                            username=delegator,
                            vesting_shares=op['vesting_shares']['amount'],
                            last_operation_id=op.get('_id', ''),
                            timestamp=datetime.now()
                        )
                        db.session.add(new_entry)
                    else:
                        entry.vesting_shares = op['vesting_shares']['amount']
                        entry.last_operation_id = op.get('_id', '')
                        entry.timestamp = datetime.now()
                
                db.session.commit()
            
            logger.info(f"Aggiornamento delegatori completato: {len(changes)} modifiche applicate")
            
        except Exception as e:
            logger.error(f"Errore durante l'aggiornamento dei delegatori: {e}")
            raise e

    @staticmethod
    def get_active_delegators(min_sp=0):
        """Recupera tutti i delegatori attivi dal database"""
        try:
            delegators = Delegator.query.all()
            active_delegators = []
            
            for delegator in delegators:
                # Qui dovresti convertire il vesting_shares in SP per confrontarlo con min_sp
                # Per ora utilizziamo una logica semplificata
                if delegator.vesting_shares and float(delegator.vesting_shares) > 0:
                    active_delegators.append(delegator)
            
            return active_delegators
            
        except Exception as e:
            logger.error(f"Errore nel recupero dei delegatori attivi: {e}")
            return []

    @staticmethod
    def get_delegator_usernames():
        """Restituisce solo gli username dei delegatori attivi"""
        try:
            delegators = DelegatorManager.get_active_delegators()
            return [d.username for d in delegators]
        except Exception as e:
            logger.error(f"Errore nel recupero degli username dei delegatori: {e}")
            return []

# Aggiungi un riferimento al delegator_manager nel app_state per fermarlo correttamente
def init_services(app):
    # Inizializza i servizi dell'applicazione
    from .db import init_db
    from ..sniper import SocialMediaPublisher
    
    with app.app_context():
        # Inizializza il database
        init_db(app)
        
        # Avvia il SocialMediaPublisher
        app_state.publisher = SocialMediaPublisher(app)
        app_state.publisher.start()
        
    # Aggiungi il delegator_manager a app_state per poterlo fermare correttamente
    from ..services.delegator_service import DelegatorManager
    from . import beem
    app_state.delegator_manager = DelegatorManager(beem.blockchain_connector, app)
    app_state.delegator_manager.start()

class AppState:
    def __init__(self):
        self.publisher = None
        self.delegator_manager = None
    
    def stop_all(self):
        if self.publisher:
            self.publisher.stop()
            
        if self.delegator_manager:
            self.delegator_manager.stop()