from ..components.db import User, db
from ..components.instance import local_data_list
from flask import current_app
import functools

def get_user_data():
    """Funzione legacy che carica dati dal DB in memory list (deprecata)"""
    local_data_list.clear()
    users = User.query.all()
    for user in users:
        user_data = {
            'username': user.data['username'],
            'platform': user.data['platform'],
            'voteDelay': user.data['voteDelay'],
            'voteWeight': user.data['voteWeight'],
            'timestamp': user.data['timestamp']
        }   
        local_data_list.append(user_data)

def get_users_by_platform(platform=None):
    """Ottiene gli utenti per una specifica piattaforma direttamente dal database
    
    Args:
        platform (str, optional): 'steem' o 'hive'. Se None, restituisce tutti gli utenti.
    
    Returns:
        list: Lista degli utenti con i loro dati
    """
    query = User.query
    if platform:
        # Filtra gli utenti in base alla piattaforma
        query = query.filter(User.data.op("->>")("platform") == platform)
    
    return [user.data for user in query.all()]

def get_usernames_by_platform(platform):
    """Ottiene gli username per una specifica piattaforma
    
    Args:
        platform (str): 'steem' o 'hive'
    
    Returns:
        list: Lista degli username
    """
    users = get_users_by_platform(platform)
    return [user['username'] for user in users]

def find_user_by_username(username):
    """Trova un utente in base allo username
    
    Args:
        username (str): Username da cercare
    
    Returns:
        dict: Dati dell'utente o None se non trovato
    """
    user = User.query.filter_by(username=username).first()
    return user.data if user else None

def with_db_context(f):
    """Decoratore che assicura che la funzione venga eseguita all'interno del contesto dell'app
    
    Args:
        f: Funzione da decorare
    
    Returns:
        function: Funzione decorata che esegue all'interno del contesto dell'app
    """
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if current_app:
            return f(*args, **kwargs)
        else:
            from ..components.factory import create_app
            app = create_app()
            with app.app_context():
                return f(*args, **kwargs)
    return wrapped
