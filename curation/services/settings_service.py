from ..components.db import Settings, db
from flask import current_app
from ..components.logger_config import logger
import json

class SettingsService:
    """Servizio per la gestione delle impostazioni dell'applicazione"""
    
    DEFAULT_SETTINGS = {
        'test_mode': 'true',
        'steem_curator': 'tasuboyz',
        'steem_curator_posting_key': '',  # Le chiavi vengono impostate tramite UI
        'steem_active_key': '',  # Chiave di backup per operazioni che richiedono active key
        'hive_curator': 'menny.trx',
        'hive_curator_posting_key': '',  # Le chiavi vengono impostate tramite UI
        'admin_ids': '1026795763',  # Lista di admin IDs separati da virgola
        'bot_token': '',  # Token del bot
    }
    
    @staticmethod
    def _ensure_app_context(app=None):
        """Assicura che ci sia un contesto dell'applicazione attivo"""
        if app is not None:
            return app.app_context()
        
        try:
            # Verifica se siamo già in un contesto
            _ = current_app._get_current_object()
            return None
        except RuntimeError:
            logger.error("Nessun contesto applicazione disponibile e nessun app fornito")
            # Importa Flask per una soluzione di fallback
            try:
                from flask import Flask
                from curation.components.factory import create_app
                # Crea un'app temporanea se possibile
                temp_app = create_app()
                return temp_app.app_context()
            except Exception as e:
                logger.error(f"Impossibile creare un'app temporanea: {e}")
                # Invece di sollevare un'eccezione, restituiamo None e lasciamo
                # che il chiamante gestisca il caso in cui il contesto non è disponibile
                return None
    
    @staticmethod
    def initialize_default_settings(app=None):
        """Inizializza le impostazioni predefinite se non esistono"""
        ctx = SettingsService._ensure_app_context(app)
        if ctx:
            with ctx:
                return SettingsService._do_initialize_default_settings()
        else:
            return SettingsService._do_initialize_default_settings()
    
    @staticmethod
    def _do_initialize_default_settings():
        """Implementazione effettiva dell'inizializzazione delle impostazioni predefinite"""
        try:
            # Verifica se esistono già le impostazioni
            existing_keys = [s.key for s in Settings.query.all()]
            settings_added = 0
            
            # Aggiungi le impostazioni mancanti
            for key, value in SettingsService.DEFAULT_SETTINGS.items():
                # Determina la piattaforma in base alla chiave
                platform = None
                if key.startswith('steem_'):
                    platform = 'steem'
                elif key.startswith('hive_'):
                    platform = 'hive'
                
                # Aggiungi solo se non esiste già
                if key not in existing_keys:
                    new_setting = Settings(key=key, value=value, platform=platform)
                    db.session.add(new_setting)
                    settings_added += 1
            
            if settings_added > 0:
                db.session.commit()
                logger.info(f"Inizializzate {settings_added} impostazioni predefinite")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Errore nell'inizializzazione delle impostazioni predefinite: {e}")
            return False
    
    @staticmethod
    def get_setting(key, platform=None, default=None, app=None):
        """Recupera un'impostazione dal database"""
        try:
            ctx = SettingsService._ensure_app_context(app)
            if ctx:
                with ctx:
                    return SettingsService._do_get_setting(key, platform, default)
            else:
                return SettingsService._do_get_setting(key, platform, default)
        except Exception as e:
            logger.error(f"Errore nel recupero dell'impostazione {key}: {e}")
            return default
    
    @staticmethod
    def _do_get_setting(key, platform, default):
        """Implementazione effettiva del recupero delle impostazioni"""
        query = Settings.query.filter_by(key=key)
        if platform:
            query = query.filter_by(platform=platform)
        setting = query.first()
        if setting:
            return setting.value
        return default
    
    @staticmethod
    def set_setting(key, value, platform=None, app=None):
        """Imposta o aggiorna un'impostazione nel database"""
        try:
            ctx = SettingsService._ensure_app_context(app)
            if ctx:
                with ctx:
                    return SettingsService._do_set_setting(key, value, platform)
            else:
                return SettingsService._do_set_setting(key, value, platform)
        except Exception as e:
            logger.error(f"Errore nell'impostazione {key}={value}: {e}")
            return False
    
    @staticmethod
    def _do_set_setting(key, value, platform):
        """Implementazione effettiva dell'aggiornamento delle impostazioni"""
        try:
            query = Settings.query.filter_by(key=key)
            if platform:
                query = query.filter_by(platform=platform)
            setting = query.first()
            
            if setting:
                setting.value = value
            else:
                new_setting = Settings(key=key, value=value, platform=platform)
                db.session.add(new_setting)
            
            db.session.commit()
            logger.info(f"Impostazione aggiornata: {key}={value} ({platform or 'global'})")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Errore nell'aggiornamento dell'impostazione: {e}")
            return False
    
    @staticmethod
    def get_all_settings(platform=None, app=None):
        """Recupera tutte le impostazioni, opzionalmente filtrate per piattaforma"""
        try:
            ctx = SettingsService._ensure_app_context(app)
            if ctx:
                with ctx:
                    return SettingsService._do_get_all_settings(platform)
            else:
                return SettingsService._do_get_all_settings(platform)
        except Exception as e:
            logger.error(f"Errore nel recupero delle impostazioni: {e}")
            return {}
    
    @staticmethod
    def _do_get_all_settings(platform):
        """Implementazione effettiva del recupero di tutte le impostazioni"""
        query = Settings.query
        if platform:
            query = query.filter_by(platform=platform)
        
        settings = query.all()
        result = {}
        for setting in settings:
            result[setting.key] = setting.value
        
        return result
    
    @staticmethod
    def is_test_mode(app=None):
        """Verifica se l'applicazione è in modalità test"""
        test_mode = SettingsService.get_setting('test_mode', default='true', app=app)
        return test_mode.lower() == 'true'
    
    @staticmethod
    def get_curator_info(platform, app=None):
        """Recupera le informazioni del curatore per una specifica piattaforma"""
        result = {
            'username': SettingsService.get_setting(f'{platform}_curator', app=app),
            'posting_key': SettingsService.get_setting(f'{platform}_curator_posting_key', app=app)
        }
        
        if platform == 'steem':
            result['active_key'] = SettingsService.get_setting('steem_active_key', app=app)
        
        return result
