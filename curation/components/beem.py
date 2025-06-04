from beem import Steem, Hive
from beem.account import Account
from beem.comment import Comment
from beem.community import Communities, Community
import requests
import json
import os
import time
import pickle
import aiohttp
from .config import node_list
from .logger_config import logger
from datetime import datetime, timedelta, timezone
from .instance import published_posts, last_check_time
from beem.transactionbuilder import TransactionBuilder
from beembase.operations import Transfer
from .db import db, Delegator
try:
    from ..services.settings_service import SettingsService
except ImportError:
    SettingsService = None

class Blockchain:
    def __init__(self, mode='irreversible', app=None):
        self.mode = mode
        # self.tester = SteemNodeTester()
        self.update_interval = 60
        self.hive_node = ''
        self.node_urls = node_list
        self.last_check_time = last_check_time
        
        # Inizializzazione della cache dei votanti
        self._voters_cache = {}
        self._cache_path = os.path.join(os.path.dirname(__file__), "../../instance/voters_cache.pkl")
        # Inizializza la blockchain di riferimento (usata in get_post_voters)
        self.blockchain = None
        self.app = app  # Salva l'app Flask se fornita
        
        # Carica la cache esistente se disponibile
        self._load_cache()

    def ping_server(self, node_url):
        """Verifica se il nodo è raggiungibile."""
        try:
            response = requests.get(node_url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Error pinging server {node_url}: {e}")
            return False

    def get_steem_profile_info(self, username):  
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo

        data = {
        "jsonrpc": "2.0",
        "method": "condenser_api.get_accounts",
        "params": [[username]],
        "id": 1
        }
        response = requests.post(node_url, data=json.dumps(data))
        if response.status_code == 200:
            data = response.json()
            if len(data['result']) > 0:
                return data
            else:
                logger.error(f"user not exist: username={username}, node={node_url}, response={data}")
                raise Exception("user not exist")
        else:
            raise Exception(response.reason)
            
    def get_hive_profile_info(self, username):  
        for node_url in self.node_urls.get('hive'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo

        data = {
        "jsonrpc": "2.0",
        "method": "condenser_api.get_accounts",
        "params": [[username]],
        "id": 1
        }
        response = requests.post(node_url, data=json.dumps(data))
        if response.status_code == 200:
            data = response.json()
            if len(data['result']) > 0:
                return data
            else:
                raise Exception("user not exist")
        else:
            raise Exception(response.reason)

    def get_posts(self, usernames, platform, max_age_minutes=5):
        post_links = []
        current_time = datetime.now(timezone.utc)

        for node_url in self.node_urls[platform.lower()]:
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo

        headers = {'Content-Type': 'application/json'}

        for username in usernames:
            data = {
                "jsonrpc": "2.0",
                "method": "condenser_api.get_discussions_by_blog",
                "params": [{"tag": username, "limit": 1}],
                "id": 1
            }
            try:
                response = requests.post(node_url, headers=headers, data=json.dumps(data), timeout=5)
                response.raise_for_status()
                result = response.json().get('result', [])
                for post in result:
                    link = post.get('url')
                    created_time = post.get('created')
                    if link and created_time:
                        post_time = datetime.strptime(created_time, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
                        post_age = current_time - post_time
                        age_minutes = post_age.total_seconds() / 60
                        last_check_time = self.last_check_time[username]

                        if link in published_posts:
                            continue

                        if age_minutes <= max_age_minutes:
                            post_links.append(link)
                            published_posts.add(link)
                            self.last_check_time[username] = post_time
            except Exception as e:
                logger.error(f"Errore durante la recupero dei post per {username} su {platform}: {e}")

        return post_links
    
    def get_dynamic_global_properties(self, platform='steem'):
        for node_url in self.node_urls.get(platform):
            if not self.ping_server(node_url):
                logger.error(f"Server non raggiungibile: {node_url}")
                continue
        headers = {'Content-Type': 'application/json'}
        data = {
            "jsonrpc": "2.0",
            "method": "condenser_api.get_dynamic_global_properties",
            "params": [],
            "id": 1
        }
        response = requests.post(node_url, headers=headers, data=json.dumps(data))
        if response.ok:
            return response.json().get('result', {})
        else:
            raise Exception(response.reason)

    def get_steem_cur8_info(self):
        steem_url = 'https://imridd.eu.pythonanywhere.com/api/steem'
        response = requests.get(steem_url)
        if response.status_code == 200:
            data = response.json()
            return data[0]
        else:
            raise Exception(response.reason)
        
    def get_hive_cur8_info(self):
        hive_url = 'https://imridd.eu.pythonanywhere.com/api/hive'
        response = requests.get(hive_url)
        if response.status_code == 200:
            data = response.json()
            return data[0]
        else:
            raise Exception(response.reason)
        
    def get_steem_hive_price(self):
        url = 'https://imridd.eu.pythonanywhere.com/api/prices'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            raise Exception(response.reason)
        
    def get_cur8_history(self):        
        url = 'https://imridd.eu.pythonanywhere.com/api/steem/history/cur8'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            raise Exception(response.reason)
        
    def get_steem_transaction_cur8(self):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
                
            try:
                stm = Steem(node=node_url)
                account = Account("cur8", steem_instance=stm)
                history = account.get_account_history(-1, limit=1000)
                transactions = []
                for operation in history:
                    op_type = operation['type']
                    if op_type == 'transfer':
                        account_to = operation['to']
                        amount = operation['amount']['amount']
                        transactions.append((account_to, amount.strip()))
                return transactions
            except Exception as e:
                logger.error(f"Errore nel recupero delle transazioni con il nodo {node_url}: {str(e)}")
                
        raise Exception("Nessun nodo Steem disponibile")
    
    def get_top_20_steem_transactions(self):
        transactions = self.get_steem_transaction_cur8()
        account_transactions = {}

        for account_to, amount in transactions:
            if account_to not in account_transactions:
                account_transactions[account_to] = 0
            account_transactions[account_to] += float(amount)

        sorted_transactions = sorted(account_transactions.items(), key=lambda item: item[1], reverse=True)

        top_transactions = sorted_transactions[:20]
        return top_transactions
    
    def get_hive_transaction_cur8(self):
        for node_url in self.node_urls.get('hive'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
                
            try:
                hive = Hive(node=node_url)
                account = Account("cur8", steem_instance=hive)
                history = account.get_account_history(-1, limit=1000)
                transactions = []
                for operation in history:
                    op_type = operation['type']
                    if op_type == 'transfer':
                        account_to = operation['to']
                        amount = operation['amount']['amount']
                        transactions.append((account_to, amount.strip()))
                return transactions
            except Exception as e:
                logger.error(f"Errore nel recupero delle transazioni con il nodo {node_url}: {str(e)}")
        
        raise Exception("Nessun nodo Hive disponibile")
    
    def get_top_20_hive_transactions(self):
        transactions = self.get_hive_transaction_cur8()
        account_transactions = {}

        for account_to, amount in transactions:
            if account_to not in account_transactions:
                account_transactions[account_to] = 0
            account_transactions[account_to] += float(amount)

        sorted_transactions = sorted(account_transactions.items(), key=lambda item: item[1], reverse=True)

        top_transactions = sorted_transactions[:20]
        return top_transactions
    
    async def get_steem_top_delegators(self):
        url = 'https://imridd.eu.pythonanywhere.com/api/steem/delegators/cur8'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    raise Exception(response.reason)

    async def get_hive_top_delegators(self):
        url = 'https://imridd.eu.pythonanywhere.com/api/hive/delegators/cur8'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    raise Exception(response.reason)
                
############################################################################################# Delegators
    def get_steem_delegators(self, platform='steem', since_time=None):
        for node_url in self.node_urls.get(platform):
            if not self.ping_server(node_url):
                logger.error(f"Server non raggiungibile: {node_url}")
                continue
            logger.info(f"Trying node: {node_url}")
            try:
                stm = Steem(node=node_url)
                curator_info = self.get_curator_info(platform)                
                acc = Account(curator_info['username'], blockchain_instance=stm)

                virtual_op = acc.virtual_op_count()
                start_from = virtual_op  # Inizia dall'operazione più recente
                batch_size = 10000
                all_delegate_ops = []
                logger.info("Starting history fetch for delegations...")

                consecutive_old_batches = 0
                max_consecutive_old_batches = 3  # Massimo 3 batch consecutivi senza operazioni recenti
                
                while start_from > 0:
                    stop_at = max(start_from - batch_size, 0)
                    logger.info(f"Fetching operations from {start_from} to {stop_at}...")
                    
                    batch_found_recent = False
                    batch_operations = []
                    
                    # Raccoglie tutte le operazioni del batch
                    for h in acc.history_reverse(start=start_from, stop=stop_at, use_block_num=False):
                        if h['type'] == 'delegate_vesting_shares':
                            batch_operations.append(h)
                    
                    # Processa le operazioni del batch (sono in ordine cronologico crescente)
                    for op in batch_operations:
                        if since_time:
                            op_time = datetime.strptime(op['timestamp'], '%Y-%m-%dT%H:%M:%S')
                            if op_time > since_time:
                                # Operazione recente, la includiamo
                                all_delegate_ops.append(op)
                                batch_found_recent = True
                            # Se l'operazione è più vecchia di since_time, la saltiamo
                        else:
                            # Se non c'è filtro temporale, include tutte le operazioni
                            all_delegate_ops.append(op)
                            batch_found_recent = True
                    
                    # Controlla se dobbiamo interrompere la scansione
                    if since_time:
                        if batch_found_recent:
                            consecutive_old_batches = 0  # Reset del contatore
                        else:
                            consecutive_old_batches += 1
                            logger.info(f"Batch senza operazioni recenti: {consecutive_old_batches}/{max_consecutive_old_batches}")
                            
                            # Se abbiamo trovato troppi batch consecutivi senza operazioni recenti, fermiamoci
                            if consecutive_old_batches >= max_consecutive_old_batches:
                                logger.info("Raggiunti troppi batch consecutivi senza operazioni recenti. Interruzione scansione.")
                                break
                        
                    start_from -= batch_size

                # Ordina per timestamp decrescente
                all_delegate_ops.sort(key=lambda op: op['timestamp'], reverse=True)
                # Prendi solo l'ultima operazione per ogni delegator
                latest_ops = {}
                for op in all_delegate_ops:
                    delegator = op['delegator']
                    if delegator not in latest_ops:
                        latest_ops[delegator] = op

                min_sp = SettingsService.get_setting('delegation_min_sp')
                max_sp = SettingsService.get_setting('delegation_max_sp')
                try:
                    min_sp = float(min_sp) if min_sp is not None else 0
                except Exception:
                    min_sp = 0
                try:
                    max_sp = float(max_sp) if max_sp not in (None, '', 'null') else None
                except Exception:
                    max_sp = None

                processed_ops = []
                for op in latest_ops.values():
                    shares = op['vesting_shares']['amount']
                    # Converti le shares in float per il confronto
                    shares_float = float(shares) / (10 ** op['vesting_shares']['precision'])
                    # Procedi solo se le shares sono maggiori di 0
                    if shares_float > 0:
                        converted_sp = stm.vests_to_sp(shares_float)
                        # FILTRO: solo deleghe tra min_sp e max_sp
                        if converted_sp < min_sp:
                            continue
                        if max_sp is not None and converted_sp > max_sp:
                            continue
                        op['converted_sp'] = converted_sp
                        processed_ops.append(op)
                return processed_ops

            except Exception as e:
                logger.error(f"Error fetching delegators from node {node_url}: {e}")
                continue

        logger.error("All nodes failed. Unable to fetch delegators.")
        return []

    def process_delegation_changes(self, operations):
        changes = []
        for op in operations:
            delegator = op['delegator']
            amount = op['vesting_shares']
            entry = Delegator.query.filter_by(username=delegator).first()

            # Controlla se è una nuova delegazione o una modifica
            if not entry:
                changes.append({'type': 'new', 'data': op})
            elif entry.vesting_shares != amount:
                changes.append({'type': 'update', 'data': op})
        
        return changes

    def save_delegation_changes(self, changes):
        for change in changes:
            op = change['data']
            delegator = op['delegator']
            entry = Delegator.query.filter_by(username=delegator).first()

            if change['type'] == 'new':
                new_entry = Delegator(
                    username=delegator,
                    vesting_shares=op['vesting_shares']['amount'],
                    last_operation_id=op['_id'],
                    timestamp=datetime.strptime(op['timestamp'], '%Y-%m-%dT%H:%M:%S')
                )
                db.session.add(new_entry)
            else:
                entry.vesting_shares = op['vesting_shares']
                entry.last_operation_id = op['_id']

        db.session.commit()

    def send_confirmation(self, changes, stm):
        for change in changes:
            op = change['data']
            try:
                memo = "Grazie per la nuova delegazione!" if change['type'] == 'new' else "Grazie per aver aggiornato la tua delegazione!"
                tx = TransactionBuilder(blockchain_instance=stm)
                # Ottieni le credenziali del curatore
                curator_info = self.get_curator_info('steem')
                tx.appendOps(Transfer(
                    **{
                        'from': curator_info['username'],
                        'to': op['delegator'],
                        'amount': '0.001 STEEM',
                        'memo': memo
                    }
                ))
                tx.appendWif(curator_info['active_key'])
                tx.sign()
                tx.broadcast()
                
                logger.info(f"Inviata conferma a {op['delegator']} per {change['type']}")
            except Exception as e:
                logger.error(f"Errore invio a {op['delegator']}: {str(e)}")

##################################################################################### Community command
    
    def create_account(self, new_account_name: str):
        new_account_name = new_account_name.lower()
        url = "http://imridd.eu.pythonanywhere.com/api/steem/create_account"
        headers = {
            "Content-Type": "application/json",
            "API-Key": "your_secret_api_key"
        }
        data = {
            "new_account_name": new_account_name
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Failed to create account. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception("failed to create account")

    ##########################################################################################
    ##########################################################################################
    
    def like_steem_post(self, voter, voted, private_posting_key, permlink, weight=20):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        steem = Steem(keys=[private_posting_key], node=node_url, rpcuser=voter) 
        account = Account(voter, blockchain_instance=steem)
        comment = Comment(authorperm=f"@{voted}/{permlink}", blockchain_instance=steem)
        comment.vote(weight, account=account)

    def like_hive_post(self, voter, voted, private_posting_key, permlink, weight=20):   
        for node_url in self.node_urls.get('hive'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        hive = Hive(keys=[private_posting_key], node=node_url, rpcuser=voter)
        account = Account(voter, blockchain_instance=hive)
        comment = Comment(authorperm=f"@{voted}/{permlink}", blockchain_instance=hive)
        comment.vote(weight, account=account)

    def get_steem_permlink(self, post_url):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        steem = Steem(node=node_url) 
        comment = Comment(post_url, blockchain_instance=steem)
        permlink = comment.permlink
        return permlink
    
    def get_steem_author(self, post_url):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        steem = Steem(node=node_url) 
        comment = Comment(post_url, blockchain_instance=steem)
        author = comment.author
        return author
    
    def get_hive_permlink(self, post_url):
        for node_url in self.node_urls.get('hive'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        hive = Hive(node=node_url)
        comment = Comment(post_url, blockchain_instance=hive)
        permlink = comment.permlink
        return permlink
    
    def get_hive_author(self, post_url):
        for node_url in self.node_urls.get('hive'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        hive = Hive(node=node_url)
        comment = Comment(post_url, blockchain_instance=hive)
        author = comment.author
        return author
    
    def get_user_last_post(self, username):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
            
            steem = Steem(node=node_url)
            try:
                account = Account(username, blockchain_instance=steem)
                result = account.get_blog(start_entry_id=0, limit=1, raw_data=False, short_entries=False, account=None)
                return result
            except Exception as e:
                logger.error(f"Errore con il nodo {node_url}: {str(e)}")
        
        raise Exception("Nessun nodo Steem disponibile")
    
    def get_user_last_hive_post(self, username):
        for node_url in self.node_urls.get('hive'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
            
            hive = Hive(node=node_url)
            try:
                account = Account(username, blockchain_instance=hive)
                result = account.get_blog(start_entry_id=0, limit=1, raw_data=False, short_entries=False, account=None)
                return result
            except Exception as e:
                logger.error(f"Errore con il nodo {node_url}: {str(e)}")
        
        raise Exception("Nessun nodo Hive disponibile")
    
    def get_comment(self, author, permalink, blockchain: str):
        for node_url in self.node_urls.get(blockchain):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue  # Prova il nodo successivo
        if blockchain == 'steem':
            instance = Steem(node=node_url)
        else:
            instance = Hive(node=node_url)
        comment = Comment(f"@{author}/{permalink}", blockchain_instance=instance)
        return comment
    
    def calculate_voting_power(self, timestamp_last_vote, voting_power):
        last_vote_time = datetime.strptime(timestamp_last_vote, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff_seconds = (now - last_vote_time).total_seconds()
        regenerated_vp = (diff_seconds / 432000) * 100  # 432000 secondi = 5 giorni
        current_vp = min(voting_power + regenerated_vp, 100)
        return current_vp
    
    def get_account_info(self, username):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue
        steem = Steem(node=node_url)
        account = Account(username, blockchain_instance=steem)
        return account
    
    def get_reward_fund(self, fund_name="post"):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue
        """Get reward fund information directly from the blockchain.
        
        Args:
            fund_name (str): Name of the reward fund, typically "post"
            
        Returns:
            dict: Reward fund data with relevant information
        """
        try:
            headers = {'Content-Type': 'application/json'}
            payload = {
                "jsonrpc": "2.0",
                "method": "condenser_api.get_reward_fund",
                "params": [fund_name],
                "id": 1
            }
            
            response = requests.post(node_url, json=payload, headers=headers, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result:
                    # Convert amounts to a more usable format
                    reward_data = result['result']
                    return reward_data
                    
            logger.warning(f"Failed to get reward fund data from {node_url}")
            # self.switch_to_backup_node()
            return self.get_reward_fund(fund_name)  # Try again with new node
            
        except Exception as e:
            logger.error(f"Error getting reward fund: {str(e)}")
            # self.switch_to_backup_node()
            return self.get_reward_fund(fund_name)  # Try again with new node
    
    def get_current_median_history_price(self):
        for node_url in self.node_urls.get('steem'):
            if not self.ping_server(node_url):
                logger.error(f"Impossibile raggiungere il server: {node_url}")
                continue
        """Get the current median price history from the blockchain.
        
        Returns:
            dict: Price data with base and quote values
        """
        try:
            headers = {'Content-Type': 'application/json'}
            payload = {
                "jsonrpc": "2.0",
                "method": "condenser_api.get_current_median_history_price",
                "params": [],
                "id": 1
            }
            
            response = requests.post(node_url, json=payload, headers=headers, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result:
                    # Parse price data into a usable format
                    price_data = result['result']
                    
                    # Convert price strings to structured data
                    base_parts = price_data['base'].split(' ')
                    quote_parts = price_data['quote'].split(' ')
                    
                    return {
                        'base': {
                            'amount': float(base_parts[0]),
                            'symbol': base_parts[1]
                        },
                        'quote': {
                            'amount': float(quote_parts[0]),
                            'symbol': quote_parts[1]
                        }
                    }
                    
            logger.warning(f"Failed to get price data from {node_url}")
            # self.switch_to_backup_node()
            return self.get_current_median_history_price()  # Try again with new node
            
        except Exception as e:
            logger.error(f"Error getting current median history price: {str(e)}")
            # self.switch_to_backup_node()
            return self.get_current_median_history_price()  # Try again with new node
        

    def _load_cache(self):
        """Carica la cache dei votanti dal file se esiste."""
        try:
            if os.path.exists(self._cache_path):
                with open(self._cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    # Verifica che la cache non sia vecchia (più di 7 giorni)
                    if 'timestamp' in cached_data and (datetime.now() - cached_data['timestamp']).days < 7:
                        self._voters_cache = cached_data.get('voters', {})
                        logger.info(f"Caricati {len(self._voters_cache)} record dalla cache dei votanti")
                    else:
                        logger.info("Cache dei votanti scaduta, verrà rigenerata")
        except Exception as e:
            logger.warning(f"Errore nel caricamento della cache dei votanti: {e}")
            self._voters_cache = {}
    
    def _save_cache(self):
        """Salva la cache dei votanti su file."""
        try:
            # Assicurati che la directory esista
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            
            cache_data = {
                'timestamp': datetime.now(),
                'voters': self._voters_cache
            }
            
            with open(self._cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.info(f"Salvati {len(self._voters_cache)} record nella cache dei votanti")
        except Exception as e:
            logger.warning(f"Errore nel salvataggio della cache dei votanti: {e}")

    def get_platform_and_instance(self, post_url):
        """
        Determina la piattaforma ('steem' o 'hive') e restituisce l'istanza blockchain corretta.
        """
        if 'peakd.com' in post_url or 'hive.blog' in post_url:
            platform = 'hive'
            for node_url in self.node_urls.get('hive', []):
                if self.ping_server(node_url):
                    from beem import Hive
                    return platform, Hive(node=node_url)
        else:
            platform = 'steem'
            for node_url in self.node_urls.get('steem', []):
                if self.ping_server(node_url):
                    from beem import Steem
                    return platform, Steem(node=node_url)
        raise Exception("No available node for platform")

    def get_previous_author_posts(self, author, platform, limit=1):
        """
        Recupera i post precedenti di un autore per analizzare i pattern di voto.
        
        Args:
            author (str): Nome dell'autore
            platform (str): 'steem' o 'hive'
            limit (int): Numero massimo di post da recuperare
            
        Returns:
            list: Lista di post precedenti dell'autore
        """
        try:
            logger.info(f"Recupero dei {limit} post precedenti di @{author} su {platform}")
            
            # Trova il nodo disponibile
            node_urls = self.node_urls.get(platform.lower(), [])
            node_url = None
            
            for url in node_urls:
                if self.ping_server(url):
                    node_url = url
                    break
            
            if not node_url:
                logger.error(f"Nessun nodo {platform} disponibile")
                return []
            
            # Prepara la richiesta API
            headers = {'Content-Type': 'application/json'}
            data = {
                "jsonrpc": "2.0",
                "method": "condenser_api.get_discussions_by_blog",
                "params": [{"tag": author, "limit": limit+1}],  # +1 per escludere il post attuale
                "id": 1
            }
            
            response = requests.post(node_url, headers=headers, data=json.dumps(data), timeout=10)
            response.raise_for_status()
            
            posts = response.json().get('result', [])
            # Filtra solo i post dell'autore (esclude reblog) e salta il primo (post attuale)
            author_posts = [post for post in posts if post.get('author') == author][1:limit+1]
            
            logger.info(f"Recuperati {len(author_posts)} post precedenti di @{author}")
            return author_posts
            
        except Exception as e:
            logger.error(f"Errore nel recupero dei post precedenti di @{author}: {str(e)}")
            return []
            
    def get_curator_info(self, platform):
        """Ottiene le informazioni del curatore dalla configurazione o dal database"""
        try:
            if SettingsService:
                # Ottieni le informazioni dal servizio di impostazioni
                # Se self.app è disponibile, usa il suo contesto di applicazione
                if self.app:
                    with self.app.app_context():
                        curator_info = SettingsService.get_curator_info(platform, app=self.app)
                        return curator_info
                else:
                    curator_info = SettingsService.get_curator_info(platform, app=None)
                    return curator_info
        except Exception as e:
            logger.debug(f"Fallback alla configurazione per {platform}: {str(e)}")
            
        # Fallback ai valori di configurazione
        from .config import steem_curator, steem_curator_posting_key, steem_active_key, hive_curator, hive_curator_posting_key
        if platform == 'steem':
            return {
                'username': steem_curator,
                'posting_key': steem_curator_posting_key,
                'active_key': steem_active_key
            }
        else:
            return {
                'username': hive_curator,
                'posting_key': hive_curator_posting_key
            }
    
    def get_votes_today(self, curator, author, platform):
        """
        Conta quanti voti il curatore ha dato all'autore nelle ultime 24 ore.
        Usa history_reverse per efficienza: si ferma appena trova una operazione troppo vecchia.
        """
        try:
            cache_key = f"{curator}_{author}_{platform}_votes_today"
            now = datetime.now()
            if hasattr(self, '_local_cache') and cache_key in self._local_cache:
                cached = self._local_cache[cache_key]
                if (now - cached['timestamp']).seconds < 180:
                    return cached['count']
            else:
                if not hasattr(self, '_local_cache'):
                    self._local_cache = {}
            # Scegli la blockchain corretta
            if platform == "steem":
                for node_url in self.node_urls.get('steem'):
                    if self.ping_server(node_url):
                        stm = Steem(node=node_url)
                        break
                else:
                    logger.error("Nessun nodo Steem disponibile")
                    return 0
                account = Account(curator, blockchain_instance=stm)
            else:
                for node_url in self.node_urls.get('hive'):
                    if self.ping_server(node_url):
                        hive = Hive(node=node_url)
                        break
                else:
                    logger.error("Nessun nodo Hive disponibile")
                    return 0
                account = Account(curator, blockchain_instance=hive)
            since = datetime.now(timezone.utc) - timedelta(days=1)
            votes = 0
            virtual_op = account.virtual_op_count()
            batch_size = 500
            start_from = virtual_op
            stop = 0
            for op in account.history_reverse(start=start_from, stop=stop, use_block_num=False):
                if op['type'] == 'vote' and op.get('author') == author:
                    vote_time = op.get('timestamp')
                    if vote_time is None:
                        continue
                    if isinstance(vote_time, str):
                        try:
                            vote_time = datetime.strptime(vote_time, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
                        except ValueError:
                            try:
                                vote_time = datetime.fromisoformat(vote_time.replace('Z', '+00:00'))
                            except Exception:
                                continue
                    if vote_time.tzinfo is None:
                        vote_time = vote_time.replace(tzinfo=timezone.utc)
                    if vote_time > since:
                        votes += 1
                    else:
                        # Appena trovi una operazione troppo vecchia, puoi fermarti
                        break
            self._local_cache[cache_key] = {'timestamp': now, 'count': votes}
            return votes
        except Exception as e:
            logger.error(f"Errore in get_votes_today: {e}")
            return 0