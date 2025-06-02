# delegator_sync_scheduler.py
"""
Scheduler per sincronizzare periodicamente i delegatori:
- Se il DB è vuoto, recupera tutti i delegatori dalla blockchain e li salva.
- Altrimenti, recupera solo le modifiche recenti (nuove deleghe o cambiamenti).
"""
import time
from datetime import datetime, timedelta
from curation.components.logger_config import logger
from curation.components.beem import Blockchain
from curation.services.delegator_cache_service import DelegatorCacheService

SYNC_INTERVAL_MINUTES = 10  # Ogni 10 minuti

class DelegatorSyncScheduler:
    def __init__(self, app=None, platform='steem'):
        self.app = app
        self.platform = platform
        self.blockchain = Blockchain(app=app)

    def run(self):
        while True:
            try:
                with self.app.app_context():
                    self.sync_delegators()
            except Exception as e:
                logger.error(f"Errore nel sync delegators: {e}")
            time.sleep(SYNC_INTERVAL_MINUTES * 60)

    def sync_delegators(self):
        logger.info(f"[DelegatorSyncScheduler] Avvio sync delegators per {self.platform}")
        db_delegators = DelegatorCacheService.get_all_delegators()
        if not db_delegators:
            logger.info("Nessun delegator nel DB, recupero completo dalla blockchain...")
            ops = self.blockchain.get_steem_delegators(self.platform)
            DelegatorCacheService.bulk_save_or_update(ops)
            logger.info(f"Salvati {len(ops)} delegatori nel DB.")
        else:
            last_time = DelegatorCacheService.get_last_update_time()
            logger.info(f"Ultimo aggiornamento delegatori: {last_time}")
            # Recupera solo le operazioni più recenti dalla blockchain
            ops = self.blockchain.get_steem_delegators(self.platform, since_time=last_time)
            new_ops = [op for op in ops if datetime.strptime(op['timestamp'], '%Y-%m-%dT%H:%M:%S') > last_time]
            if new_ops:
                DelegatorCacheService.bulk_save_or_update(new_ops)
                logger.info(f"Aggiornati {len(new_ops)} delegatori nel DB.")
            else:
                logger.info("Nessun nuovo delegator da aggiornare.")
