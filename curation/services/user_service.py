from ..components.db import User, db
from flask import current_app, Flask
import logging
from ..components.logger_config import logger

class UserService:
    """Servizio centralizzato per la gestione degli utenti"""
    
    @staticmethod
    def _ensure_app_context(app=None):
        """Assicura che ci sia un contesto dell'applicazione attivo
        
        Se app è fornito, crea un nuovo contesto.
        Se current_app è disponibile, lo usa.
        Ritorna il contesto (per uso con 'with') o None se già in un contesto.
        """
        if app is not None:
            return app.app_context()
        
        try:
            # Verifica se siamo già in un contesto
            _ = current_app._get_current_object()
            return None
        except RuntimeError:
            logger.error("Nessun contesto applicazione disponibile e nessun app fornito")
            raise
    
    @staticmethod
    def get_users_by_platform(platform=None, app=None):
        """Recupera utenti filtrati per piattaforma (o tutti se platform=None)"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    users = User.query.all()
                    if platform:
                        return [u for u in users if u.data.get('platform') == platform]
                    return users
            else:
                # Siamo già in un contesto
                users = User.query.all()
                if platform:
                    return [u for u in users if u.data.get('platform') == platform]
                return users
        except Exception as e:
            logger.error(f"Errore nel recupero degli utenti dal database: {e}")
            return []
    
    @staticmethod
    def get_usernames_by_platform(platform, app=None):
        """Restituisce una lista di nomi utente per la piattaforma specificata"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    users = User.query.all()
                    return [u.username for u in users if u.data.get('platform') == platform]
            else:
                # Siamo già in un contesto
                users = User.query.all()
                return [u.username for u in users if u.data.get('platform') == platform]
        except Exception as e:
            logger.error(f"Errore nel recupero dei nomi utente dal database: {e}")
            return []
    
    @staticmethod
    def get_user_by_username(username, app=None):
        """Recupera i dati di un utente specifico"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    user = User.query.filter_by(username=username).first()
                    if user:
                        return user.data
                    return None
            else:
                # Siamo già in un contesto
                user = User.query.filter_by(username=username).first()
                if user:
                    return user.data
                return None
        except Exception as e:
            logger.error(f"Errore nel recupero dell'utente {username} dal database: {e}")
            return None
    
    @staticmethod
    def get_user_for_post(post_link, app=None):
        """Trova l'utente associato a un post tramite il link"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    users = User.query.all()
                    for user in users:
                        if user.username in post_link:
                            return user.data
                    return None
            else:
                # Siamo già in un contesto
                users = User.query.all()
                for user in users:
                    if user.username in post_link:
                        return user.data
                return None
        except Exception as e:
            logger.error(f"Errore nella ricerca dell'utente per il post {post_link}: {e}")
            return None
    
    @staticmethod
    def add_user(user_data, app=None):
        """Aggiunge un nuovo utente al database"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    new_user = User(username=user_data['username'], data=user_data)
                    db.session.add(new_user)
                    db.session.commit()
                    return True
            else:
                # Siamo già in un contesto
                new_user = User(username=user_data['username'], data=user_data)
                db.session.add(new_user)
                db.session.commit()
                return True
        except Exception as e:
            logger.error(f"Errore nell'aggiunta dell'utente al database: {e}")
            return False
    
    @staticmethod
    def update_user(username, user_data, app=None):
        """Aggiorna i dati di un utente esistente"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    user = User.query.filter_by(username=username).first()
                    if user:
                        user.data = user_data
                        db.session.commit()
                        return True
                    return False
            else:
                # Siamo già in un contesto
                user = User.query.filter_by(username=username).first()
                if user:
                    user.data = user_data
                    db.session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento dell'utente {username}: {e}")
            return False
    
    @staticmethod
    def delete_user(username, app=None):
        """Elimina un utente dal database"""
        try:
            ctx = UserService._ensure_app_context(app)
            if ctx:
                with ctx:
                    user = User.query.filter_by(username=username).first()
                    if user:
                        db.session.delete(user)
                        db.session.commit()
                        return True
                    return False
            else:
                # Siamo già in un contesto
                user = User.query.filter_by(username=username).first()
                if user:
                    db.session.delete(user)
                    db.session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Errore nell'eliminazione dell'utente {username}: {e}")
            return False