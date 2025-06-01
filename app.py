from flask import request, jsonify, render_template
from curation.components.logger_config import logger
from curation.components.config import TEST
from curation.components.factory import create_app, init_services, app_state
from curation.services.user_service import UserService
from curation.services.settings_service import SettingsService
from curation.components.beem import Blockchain
from curation.utils.vote import VoteManager
import signal
import sys
import os

app = create_app()
blockchain_connector = Blockchain(app=app)  # Istanza globale per la classe Blockchain
vote_manager = VoteManager()

# Definire le route
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

# Nuovo endpoint per ottenere i votanti di un post
@app.route('/api/post_voters', methods=['GET'])
def get_post_voters():
    post_url = request.args.get('post_url')
    min_importance = float(request.args.get('min_importance', 0.0))
    
    if not post_url:
        return jsonify({'error': 'Missing post_url parameter'}), 400
    
    try:
        # Determina la blockchain in base all'URL
        platform = 'hive' if 'peakd.com' in post_url or 'hive.blog' in post_url else 'steem'
        
        # Inizializza l'istanza di blockchain corretta
        for node_url in blockchain_connector.node_urls.get(platform):
            if blockchain_connector.ping_server(node_url):
                if platform == 'steem':
                    from beem import Steem
                    blockchain_connector.blockchain = Steem(node=node_url)
                else:
                    from beem import Hive
                    blockchain_connector.blockchain = Hive(node=node_url)
                break
        
        if blockchain_connector.blockchain is None:
            return jsonify({'error': f'No available {platform} node'}), 503
        
        voters_data = vote_manager.get_post_voters(post_url, min_importance)
        
        # Calcola il tempo ottimale di voto in base ai votanti importanti
        optimal_vote_info = vote_manager.calculate_optimal_vote_time(voters_data)
        
        return jsonify({
            'voters': voters_data[:10],  # Limita ai 10 votanti più importanti
            'total_voters': len(voters_data),
            'platform': platform,
            'optimal_vote_time': optimal_vote_info
        })
    except Exception as e:
        logger.error(f"Errore nel recupero dei votanti per {post_url}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/users', methods=['POST'])
def add_user():
    user_data = request.json
    success = UserService.add_user(user_data)
    if success:
        return jsonify({'message': 'User added successfully'})
    return jsonify({'message': 'Error adding user'}), 500

@app.route('/users/<username>', methods=['PUT'])
def update_user(username):
    user_data = request.json
    success = UserService.update_user(username, user_data)
    if success:
        return jsonify({'message': 'User updated successfully'})
    return jsonify({'message': 'User not found or error updating'}), 404

@app.route('/users/<username>', methods=['DELETE'])
def delete_user(username):
    success = UserService.delete_user(username)
    if success:
        return jsonify({'message': 'User deleted successfully'})
    return jsonify({'message': 'User not found'}), 404

@app.route('/users/<username>', methods=['GET'])
def get_user(username):
    user_data = UserService.get_user_by_username(username)
    if user_data:
        return jsonify(user_data)
    return jsonify({'message': 'User not found'}), 404

@app.route('/users', methods=['GET'])
def get_all_users():
    users = UserService.get_users_by_platform()
    user_list = [{'username': user.username, 'data': user.data} for user in users]
    return jsonify(user_list)

# Routes per la gestione delle impostazioni
@app.route('/api/settings', methods=['GET'])
def get_all_settings():
    """Ottiene tutte le impostazioni dell'applicazione"""
    platform = request.args.get('platform')
    settings = SettingsService.get_all_settings(platform)
    return jsonify(settings)

@app.route('/api/settings/<key>', methods=['GET'])
def get_setting(key):
    """Ottiene un'impostazione specifica"""
    platform = request.args.get('platform')
    value = SettingsService.get_setting(key, platform)
    if value is None:
        return jsonify({'error': f'Setting {key} not found'}), 404
    return jsonify({key: value})

@app.route('/api/settings/<key>', methods=['POST'])
def update_setting(key):
    """Aggiorna un'impostazione specifica"""
    data = request.json
    if not data or 'value' not in data:
        return jsonify({'error': 'Missing value parameter'}), 400
    
    platform = data.get('platform')
    success = SettingsService.set_setting(key, data['value'], platform)
    
    if success:
        return jsonify({'message': f'Setting {key} updated successfully'})
    return jsonify({'error': 'Error updating setting'}), 500

@app.route('/api/curator/info', methods=['GET'])
def get_curator_info():
    """Ottiene le informazioni sul curatore per una piattaforma specifica"""
    platform = request.args.get('platform', 'steem')
    if platform not in ['steem', 'hive']:
        return jsonify({'error': 'Invalid platform. Must be steem or hive'}), 400
    
    curator_info = SettingsService.get_curator_info(platform)
    
    # Non inviamo le chiavi al frontend per motivi di sicurezza
    if 'posting_key' in curator_info:
        curator_info['posting_key_set'] = bool(curator_info['posting_key'])
        del curator_info['posting_key']
    
    if 'active_key' in curator_info:
        curator_info['active_key_set'] = bool(curator_info['active_key'])
        del curator_info['active_key']
    
    return jsonify(curator_info)

@app.route('/api/curator/update', methods=['POST'])
def update_curator_info():
    """Aggiorna le informazioni del curatore"""
    data = request.json
    if not data or 'platform' not in data or 'username' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    platform = data['platform']
    if platform not in ['steem', 'hive']:
        return jsonify({'error': 'Invalid platform. Must be steem or hive'}), 400
    
    # Aggiorna l'username del curatore
    success = SettingsService.set_setting(f'{platform}_curator', data['username'], platform)
    
    # Aggiorna la chiave posting del curatore se fornita
    if 'posting_key' in data and data['posting_key']:
        success = success and SettingsService.set_setting(
            f'{platform}_curator_posting_key', data['posting_key'], platform)
    
    # Aggiorna la chiave active solo per steem se fornita
    if platform == 'steem' and 'active_key' in data and data['active_key']:
        success = success and SettingsService.set_setting(
            'steem_active_key', data['active_key'], platform)
    
    if success:
        return jsonify({'message': f'{platform.capitalize()} curator info updated successfully'})
    return jsonify({'error': 'Error updating curator info'}), 500

@app.route('/api/test_mode', methods=['GET'])
def get_test_mode():
    """Ottiene lo stato della modalità test"""
    test_mode = SettingsService.is_test_mode()
    return jsonify({'test_mode': test_mode})

@app.route('/api/test_mode', methods=['POST'])
def update_test_mode():
    """Aggiorna lo stato della modalità test"""
    data = request.json
    if not data or 'enabled' not in data:
        return jsonify({'error': 'Missing enabled parameter'}), 400
    
    value = 'true' if data['enabled'] else 'false'
    success = SettingsService.set_setting('test_mode', value)
    
    if success:
        return jsonify({'message': 'Test mode updated successfully'})
    return jsonify({'error': 'Error updating test mode'}), 500

@app.route('/api/bot/info', methods=['GET'])
def get_bot_info():
    """Ottiene le informazioni del bot Telegram"""
    admin_ids = SettingsService.get_setting('admin_ids', default='')
    bot_token = SettingsService.get_setting('bot_token', default='')
    
    # Prepara i dati per il frontend (nascondi parzialmente il token per sicurezza)
    masked_token = ""
    if bot_token:
        parts = bot_token.split(':')
        if len(parts) == 2:
            masked_token = f"{parts[0]}:{'*' * (len(parts[1]) - 4)}{parts[1][-4:]}"
    
    return jsonify({
        'admin_ids': admin_ids,
        'bot_token': bot_token,
        'masked_token': masked_token,
        'token_set': bool(bot_token)
    })

@app.route('/api/bot/update', methods=['POST'])
def update_bot_info():
    """Aggiorna le informazioni del bot Telegram"""
    data = request.json
    if not data:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    success = True
    
    # Aggiorna gli admin IDs se forniti
    if 'admin_ids' in data:
        success = success and SettingsService.set_setting('admin_ids', data['admin_ids'])
    
    # Aggiorna il token del bot se fornito
    if 'bot_token' in data and data['bot_token']:
        success = success and SettingsService.set_setting('bot_token', data['bot_token'])
    
    if success:
        return jsonify({'message': 'Bot information updated successfully'})
    return jsonify({'error': 'Error updating bot information'}), 500

@app.route('/api/delegators/steem', methods=['GET'])
def get_steem_delegators_api():
    """Ottiene tutti i delegatori di Steem per il curatore configurato"""
    try:
        # Recupera i delegatori dalla blockchain
        delegators = blockchain_connector.get_steem_delegators()
        
        # Formatta i dati per il frontend
        formatted_delegators = []
        for op in delegators:
            formatted_delegators.append({
                'delegator': op['delegator'],
                'delegatee': op['delegatee'],
                'sp_amount': op['converted_sp'],
                'timestamp': op['timestamp'],
                'vesting_shares': op['vesting_shares']['amount']
            })
        
        # Ordina per quantità delegata (SP) in ordine decrescente
        formatted_delegators.sort(key=lambda x: x['sp_amount'], reverse=True)
        
        return jsonify({
            'delegators': formatted_delegators,
            'total': len(formatted_delegators),
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Errore nel recupero dei delegatori Steem: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

def handle_shutdown(signal, frame):
    """Gestisce l'arresto pulito dell'applicazione"""
    logger.info("Segnale di arresto ricevuto, chiusura dell'applicazione...")
    app_state.stop_all()
    sys.exit(0)

if __name__ == '__main__':
    # Configura i gestori di segnale per il graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Avvia i servizi solo nel processo principale quando non si è in modalità debug
    # o quando si è nel processo principale in modalità debug
    debug_mode = not TEST
    
    # In Flask debug mode, the reloader will spawn a child process, we only want to initialize
    # services in the main process to avoid duplications
    is_main_process = not debug_mode or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    
    if is_main_process:
        logger.info("Inizializzando i servizi nel processo principale...")
        init_services(app)
    else:
        logger.info("Processo secondario, saltando l'inizializzazione dei servizi")
    
    # Avvia l'applicazione
    try:
        app.run(debug=debug_mode, port=8088, host='0.0.0.0', use_reloader=debug_mode)
    except KeyboardInterrupt:
        # Questo blocco è un backup, il gestore di segnale dovrebbe gestire l'interruzione
        app_state.stop_all()
        logger.info("Applicazione arrestata")
