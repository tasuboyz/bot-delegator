# delegator_cache_service.py
"""
Servizio per ottimizzare il recupero dei delegatori:
- Recupera i delegatori dalla blockchain solo se non presenti nel DB.
- Salva i nuovi delegatori nel DB.
- Permette aggiornamenti incrementali (solo modifiche recenti).
"""
from datetime import datetime, timedelta
from curation.components.db import db, Delegator
from curation.components.logger_config import logger

class DelegatorCacheService:
    @staticmethod
    def get_all_delegators():
        """Restituisce tutti i delegatori dal DB."""
        return Delegator.query.all()

    @staticmethod
    def save_or_update_delegator(op):
        """Salva o aggiorna un delegator nel DB."""
        delegator = Delegator.query.filter_by(username=op['delegator']).first()
        if not delegator:
            delegator = Delegator(
                username=op['delegator'],
                vesting_shares=op['vesting_shares']['amount'],
                last_operation_id=op.get('_id'),
                timestamp=datetime.strptime(op['timestamp'], '%Y-%m-%dT%H:%M:%S')
            )
            db.session.add(delegator)
        else:
            delegator.vesting_shares = op['vesting_shares']['amount']
            delegator.last_operation_id = op.get('_id')
            delegator.timestamp = datetime.strptime(op['timestamp'], '%Y-%m-%dT%H:%M:%S')
        db.session.commit()

    @staticmethod
    def bulk_save_or_update(ops):
        for op in ops:
            DelegatorCacheService.save_or_update_delegator(op)

    @staticmethod
    def get_last_update_time():
        """Restituisce il timestamp più recente tra i delegatori salvati."""
        last = Delegator.query.order_by(Delegator.timestamp.desc()).first()
        return last.timestamp if last else None

    @staticmethod
    def get_delegators_since(since_time):
        """Restituisce i delegatori aggiornati dopo una certa data."""
        return Delegator.query.filter(Delegator.timestamp > since_time).all()

    @staticmethod
    def clear_all():
        Delegator.query.delete()
        db.session.commit()
