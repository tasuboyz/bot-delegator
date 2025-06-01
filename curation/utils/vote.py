import asyncio
from flask import current_app
from ..components.logger_config import logger
from ..components.beem import Blockchain
from ..components.config import steem_curator as CURATOR
from beem.comment import Comment
from beem.account import Account
import time
from datetime import datetime, timezone, timedelta
from beem.vote import Vote
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import threading

# Cache locale degli account
_account_cache = {}
_account_cache_lock = threading.RLock()

# Istanza globale del BlockchainConnector
blockchain_connector = Blockchain(app=current_app)

class VoteManager:
    def __init__(self, blockchain_connector_instance=None):
        self.blockchain_connector = blockchain_connector_instance or blockchain_connector
        # Cache temporanea per account e voti durante una singola chiamata
        self._local_cache = {}
    
    def _get_cached_account(self, voter_name, blockchain_instance):
        """Ottiene un account dalla cache o dalla blockchain con meccanismo di caching"""
        cache_key = f"{voter_name}_{id(blockchain_instance)}"
        
        # Prima controlla la cache locale della classe
        if cache_key in self._local_cache:
            return self._local_cache[cache_key]
        
        # Poi controlla la cache globale con lock per thread safety
        with _account_cache_lock:
            if cache_key in _account_cache:
                self._local_cache[cache_key] = _account_cache[cache_key]
                return _account_cache[cache_key]
        
        # Se non in cache, ottieni dall'API e salva in cache
        try:
            account = Account(voter_name, blockchain_instance=blockchain_instance)
            # Salva nelle cache
            with _account_cache_lock:
                _account_cache[cache_key] = account
                self._local_cache[cache_key] = account
            return account
        except Exception as e:
            logger.debug(f"Errore nel recupero dell'account {voter_name}: {str(e)}")
            return None

    def calculate_vote_value(self, vote_percent, effective_vests=None, voting_power=9200):
        """Calculate vote value based on blockchain parameters, similar to the JS implementation."""
        try:
            # Step 1: Get dynamic global properties
            props = blockchain_connector.get_dynamic_global_properties()
            
            # Step 2: Calculate SP/VESTS ratio
            total_vesting_fund_steem = float(props['total_vesting_fund_steem'].split(' ')[0])
            total_vesting_shares = float(props['total_vesting_shares'].split(' ')[0])
            steem_per_vests = total_vesting_fund_steem / total_vesting_shares
            
            # Step 3: If no vesting shares provided, use current user's
            vesting_shares = effective_vests
            if not vesting_shares:
                # Usiamo blockchain_connector invece di blockchain
                account = blockchain_connector.get_account_info(CURATOR)
                if not account:
                    raise Exception('Unable to get account info')
                
                # Ottieni i vesting shares dall'account
                account_vests = float(account['vesting_shares'].amount)
                delegated_out = float(account['delegated_vesting_shares'].amount)
                received_vests = float(account['received_vesting_shares'].amount)
                vesting_shares = account_vests - delegated_out + received_vests
            
            # Step 4: Convert vests to Steem Power
            sp = vesting_shares * steem_per_vests
            
            # Step 5: Calculate 'r' (SP/spv ratio)
            r = sp / steem_per_vests
            
            # Step 6: Calculate 'p' (voting power)
            weight = vote_percent  # Convert percentage to weight (100% = 10000)
            p = (voting_power * weight / 10000 + 49) / 50
            
            # Step 7: Get reward fund con il nuovo metodo - utilizziamo blockchain_connector
            reward_fund = blockchain_connector.get_reward_fund("post")
            
            # Step 8: Calculate rbPrc
            recent_claims = float(reward_fund['recent_claims'])
            # Controlla il formato e adatta di conseguenza
            if 'reward_balance' in reward_fund:
                if isinstance(reward_fund['reward_balance'], str):
                    reward_balance = float(reward_fund['reward_balance'].split(' ')[0])
                else:
                    reward_balance = float(reward_fund['reward_balance'].amount)
            else:
                raise Exception("Format of reward_fund not recognized")
                
            rb_prc = reward_balance / recent_claims
            
            # Step 9: Get median price con il nuovo metodo - utilizziamo blockchain_connector
            price_info = blockchain_connector.get_current_median_history_price()
            
            base_amount = float(price_info['base']['amount'])
            quote_amount = float(price_info['quote']['amount'])
            steem_to_sbd_rate = base_amount / quote_amount
            
            # Step 10: Apply the official Steem formula
            steem_value = r * p * 100 * rb_prc
            
            # Convert STEEM to USD/SBD using the median price
            usd_value = steem_value * steem_to_sbd_rate
            
            logger.info(f"""Vote Value Calculation:
            - SP: {sp:.3f}
            - Vote Weight: {weight}
            - Voting Power: {voting_power}
            - Price ratio: {steem_to_sbd_rate:.4f}
            - Result: {steem_value:.4f} STEEM (${usd_value:.4f})""")
            
            return {
                "steem_value": float(f"{steem_value:.4f}"),
                "sbd_value": float(f"{usd_value:.4f}"),
                "formula": {
                    "r": r,
                    "p": p,
                    "rb_prc": rb_prc,
                    "median": steem_to_sbd_rate
                }
            }
        except Exception as e:
            logger.error(f'Error calculating vote value: {str(e)}')
            return {
                "steem_value": 0,
                "sbd_value": 0,
                "error": str(e)
            }    
        
    def get_post_voters(self, post_url, min_importance=0.0, use_cache=True, max_workers=5):
        """Get the voters of a post sorted by importance (vesting shares or rshares)
        
        Args:
            post_url (str): The URL or identifier of the post
            min_importance (float): Minimum importance threshold to filter voters
            use_cache (bool): Whether to use cached voters data if available
            max_workers (int): Maximum number of threads to use for parallel processing
            
        Returns:
            list: List of dictionaries with voter information
        """
    
        try:
            # Reset local cache for this call
            self._local_cache = {}
            start_time = time.time()
            
            max_detailed_voters = 10  # Limite per analisi dettagliate
            max_total_voters = 30  # Limite totale di votanti da considerare
            
            platform, blockchain_instance = self.blockchain_connector.get_platform_and_instance(post_url)
            curator_info = blockchain_connector.get_curator_info(platform)
            curator_username = (curator_info.get('username') or '').lower()
            comment = Comment(post_url, blockchain_instance=blockchain_instance)
            
            # Ottiene i dati completi del post
            comment_data = comment.json()
            
            # Estrai la data di creazione del post e assicurati che abbia timezone UTC
            post_created = comment_data.get('created')
            if isinstance(post_created, str):
                post_created = datetime.strptime(post_created, '%Y-%m-%dT%H:%M:%S')
                # Assicurati che post_created sia timezone-aware (UTC)
                if post_created.tzinfo is None:
                    post_created = post_created.replace(tzinfo=timezone.utc)
            
            # Ottiene i voti con i dettagli completi
            active_votes = comment_data.get('active_votes', [])
            if not active_votes and hasattr(comment, 'get_active_votes'):
                active_votes = comment.get_active_votes()
            
            total_votes = len(active_votes)
            logger.info(f"Trovati {total_votes} voti per il post {post_url}")
            
            # Ottimizzazione 1: Pre-filtraggio migliorato
            # Prima ordina in base a rshares se disponibili (solo se ci sono più voti del limite)
            if total_votes > max_total_voters and active_votes and 'rshares' in active_votes[0]:
                active_votes.sort(key=lambda v: float(v.get('rshares', 0)), reverse=True)
                active_votes = active_votes[:max_total_voters]
                logger.info(f"Pre-filtrati i top {max_total_voters} voti per {post_url} basati su rshares")
            elif total_votes > max_total_voters:
                # Limitazione semplice se non possiamo ordinare
                active_votes = active_votes[:max_total_voters]
                logger.info(f"Limitati a {max_total_voters} voti senza pre-ordinamento per {post_url}")
            
            # Dividi i voti in due gruppi: quelli che richiedono analisi dettagliata e quelli che richiedono analisi base
            detailed_votes = active_votes[:min(max_detailed_voters, len(active_votes))]
            basic_votes = active_votes[min(max_detailed_voters, len(active_votes)):]
            
            logger.info(f"Analisi dettagliata per {len(detailed_votes)} voti, analisi base per {len(basic_votes)} voti")
            
            # Prepara le liste per i risultati
            voters_data = []
            
            # Ottimizzazione 2: Processa in parallelo i voti che richiedono analisi dettagliata
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Prepara i futures per l'analisi dettagliata
                detailed_futures = {
                    executor.submit(
                        self._process_vote_data, 
                        vote_data, 
                        post_url, 
                        blockchain_instance, 
                        post_created,
                        curator_username,
                        True,  # process_details
                        min_importance
                    ): vote_data for vote_data in detailed_votes
                }
                
                # Aggiungi futures per voti con analisi base (quelli con rshares alti)
                important_basic_votes = [v for v in basic_votes 
                                        if float(v.get('rshares', 0)) >= 1e9]  # 1B rshares come soglia
                basic_futures = {
                    executor.submit(
                        self._process_vote_data, 
                        vote_data, 
                        post_url, 
                        blockchain_instance, 
                        post_created,
                        curator_username,
                        False,  # no process_details
                        min_importance
                    ): vote_data for vote_data in important_basic_votes
                }
                
                # Processa i voti meno importanti direttamente (senza threads)
                remaining_votes = [v for v in basic_votes if float(v.get('rshares', 0)) < 1e9]
                
                # Raccolta risultati dai thread dettagliati
                for future in as_completed(detailed_futures):
                    result = future.result()
                    if result:
                        voters_data.append(result)
                
                # Raccolta risultati dai thread di base
                for future in as_completed(basic_futures):
                    result = future.result()
                    if result:
                        voters_data.append(result)
            
            # Processa rimanenti voti senza threads (per quelli con rshares troppo bassi)
            for vote_data in remaining_votes:
                result = self._process_vote_data(
                    vote_data, post_url, blockchain_instance, post_created, 
                    curator_username, False, min_importance
                )
                if result:
                    voters_data.append(result)
            
            # Ordina i dati finali
            voters_data.sort(key=lambda x: (x.get('steem_vote_value', 0) or 0, x.get('importance', 0)), reverse=True)
            
            # Limita il risultato finale ai votanti più importanti
            final_voters_limit = max(20, max_detailed_voters)  # Mantieni almeno questo numero di votanti
            if len(voters_data) > final_voters_limit:
                voters_data = voters_data[:final_voters_limit]
            
            # Logga il tempo totale di esecuzione e i primi votanti importanti
            execution_time = time.time() - start_time
            logger.info(f"Analisi votanti completata in {execution_time:.2f} secondi (utilizzo cache: {use_cache})")
            
            if voters_data:
                top_voters = [f"{v['voter']} (dopo {v['vote_delay_minutes']} min., importanza: {v.get('importance', 0):.2f})" 
                             for v in voters_data[:3]]
                logger.info(f"Top votanti per {post_url}: {', '.join(top_voters)}")
            
            return voters_data
            
        except Exception as e:
            logger.error(f"Error getting post voters: {str(e)}")
            return []    
        
    def calculate_optimal_vote_time(self, voters_data, buffer_minutes=0.2, max_top_voters=8, consider_delayed_votes=True, min_vote_time=1.0, curator_username=None):
        """Calcola il tempo ottimale per votare in base ai votanti importanti
        
        Args:
            voters_data (list): Lista di dati sui votanti con 'importance' e 'vote_delay_minutes'
            buffer_minutes (float): Minuti di anticipo rispetto al primo votante importante
            max_top_voters (int): Numero massimo di votanti importanti da considerare
            consider_delayed_votes (bool): Se considerare anche votanti che votano oltre il primo minuto
            min_vote_time (float): Tempo minimo di voto in minuti, per evitare voti troppo precoci
            curator_username (str): Nome utente del curatore da escludere dal calcolo
            
        Returns:
            dict: Dizionario con 'optimal_time' (in minuti) e 'explanation'
        """
        # Ottieni il nome del curatore se non è fornito
        if not curator_username and hasattr(self, 'blockchain_connector'):
            try:
                platform = 'steem'  # Default, ma sarà lo stesso algoritmo per entrambe le piattaforme
                curator_info = self.blockchain_connector.get_curator_info(platform)
                curator_username = (curator_info.get('username') or '').lower()
            except Exception as e:
                logger.debug(f"Non è stato possibile ottenere il nome del curatore: {e}")
                curator_username = None
                
        # Filtra il curatore dai dati dei votanti se presente
        if curator_username:
            voters_data = [v for v in voters_data if v.get('voter', '').lower() != curator_username.lower()]
                
        if not voters_data:
            return {
                'optimal_time': 5,  # Default se non ci sono dati
                'explanation': 'Nessun dato sui votanti disponibile, usando il tempo predefinito di 5 minuti',
                'vote_window': (4.5, 5.5),  # Finestra di voto predefinita
                'voter_groups': {}
            }
        
        # Ordina i votanti per valore del voto in STEEM (decrescente)
        important_voters = sorted(voters_data, key=lambda x: x.get('steem_vote_value', 0) or 0, reverse=True)
        
        # Calcola dinamicamente il numero di top voters da considerare in base al loro valore
        # Conta quanti votanti hanno almeno 10 STEEM di valore
        default_top_count = 3
        high_value_voters = [v for v in important_voters if (v.get('steem_vote_value', 0) or 0) >= 10.0]
        num_high_value = len(high_value_voters)
        
        # Se ci sono votanti con almeno 10 STEEM, allarga la considerazione per includere almeno questi
        if num_high_value > 0:
            # Usa max_top_voters ma assicurati di includere almeno tutti quelli con alto valore
            effective_top_voters = max(num_high_value, min(max_top_voters, len(important_voters)))
        else:
            # Altrimenti usa solo il conteggio predefinito
            effective_top_voters = default_top_count
        
        logger.debug(f"Trovati {num_high_value} votanti con valore ≥ 10 STEEM, "
                     f"utilizzando {effective_top_voters} top voters su {len(important_voters)} totali")
        
        # Prendi un numero appropriato di votanti importanti, se disponibili
        top_voters = important_voters[:min(effective_top_voters, len(important_voters))]
        
        # Calcola il valore totale in STEEM di questi votanti
        total_steem_value = sum(v.get('steem_vote_value', 0) or 0 for v in top_voters)
        
        # Usa il valore tradizionale dell'importanza come fallback se non ci sono valori STEEM
        if total_steem_value <= 0:
            important_voters = sorted(voters_data, key=lambda x: x.get('importance', 0), reverse=True)
            top_voters = important_voters[:min(max_top_voters, len(important_voters))]
            total_importance = sum(v.get('importance', 0) for v in top_voters)
        else:
            total_importance = total_steem_value  # Usa il valore STEEM come importanza totale
        
        if total_importance <= 0:
            return {
                'optimal_time': 5,  # Default in caso di importanza zero
                'explanation': 'Importanza dei votanti troppo bassa, usando il tempo predefinito di 5 minuti',
                'vote_window': (4.5, 5.5),
                'voter_groups': {}
            }
          # NUOVA LOGICA: Trova il tempo del top voter più veloce e votalo prima
        # Ordinamento dei top_voters per tempo di voto (crescente), gestendo correttamente valori None
        top_voters_by_time = sorted(top_voters, key=lambda x: x.get('vote_delay_minutes') if x.get('vote_delay_minutes') is not None else 30)
        
        # Trova il primo votante tra i top_voters
        if top_voters_by_time:
            earliest_top_voter = top_voters_by_time[0]
            earliest_top_time = earliest_top_voter.get('vote_delay_minutes', 30)
            earliest_top_value = earliest_top_voter.get('steem_vote_value', 0) or earliest_top_voter.get('importance', 0)
            
            # Calcola il tempo ottimale: anticipa il primo top voter di buffer_minutes
            calculated_time = max(0.5, earliest_top_time - buffer_minutes)
            optimal_time = max(min_vote_time, calculated_time)
            
            # Costruisci la spiegazione
            if optimal_time == min_vote_time and calculated_time < min_vote_time:
                strategy_explanation = f"Anticipiamo tutti i top voters (primo: @{earliest_top_voter.get('voter', 'sconosciuto')}, {earliest_top_value:.3f} STEEM a {earliest_top_time} min), rispettando il tempo minimo di {min_vote_time} min."
            else:
                strategy_explanation = f"Anticipiamo tutti i top voters (primo: @{earliest_top_voter.get('voter', 'sconosciuto')}, {earliest_top_value:.3f} STEEM a {earliest_top_time} min)"
            
            # Finestra di voto più precisa per garantire di votare prima del primo top voter
            vote_window = (optimal_time - 0.1, optimal_time + 0.1)
            
            # Genera una spiegazione più dettagliata
            detailed_explanation = strategy_explanation + "\n"
            
            # Aggiungi dettagli sui top voters ordinati per tempo
            if len(top_voters_by_time) > 0:
                top_3_voters = top_voters_by_time[:min(3, len(top_voters_by_time))]
                voter_details = [f"@{v.get('voter', 'sconosciuto')} (valore: {v.get('steem_vote_value', 0) or v.get('importance', 0):.3f} STEEM, dopo {v.get('vote_delay_minutes', 0):.1f} min)" 
                                for v in top_3_voters]
                detailed_explanation += f"Top voters ordinati per tempo: {', '.join(voter_details)}"
                
                # Aggiungi anche dettagli sui top voters per valore
                top_3_value_voters = top_voters[:min(3, len(top_voters))]
                value_details = [f"@{v.get('voter', 'sconosciuto')} (valore: {v.get('steem_vote_value', 0) or v.get('importance', 0):.3f} STEEM, dopo {v.get('vote_delay_minutes', 0):.1f} min)" 
                                for v in top_3_value_voters]
                detailed_explanation += f"\nTop voters per valore: {', '.join(value_details)}"
            
            # Raggruppa i votanti per fasce temporali (per retrocompatibilità)
            immediate_voters = [v for v in top_voters if v.get('vote_delay_minutes', 30) <= 1]
            quick_voters = [v for v in top_voters if 1 < v.get('vote_delay_minutes', 30) <= 5]
            delayed_voters = [v for v in top_voters if v.get('vote_delay_minutes', 30) > 5]
            
            # Calcola l'importanza totale per ciascun gruppo
            immediate_importance = sum(v.get('steem_vote_value', 0) or v.get('importance', 0) for v in immediate_voters)
            quick_importance = sum(v.get('steem_vote_value', 0) or v.get('importance', 0) for v in quick_voters)
            delayed_importance = sum(v.get('steem_vote_value', 0) or v.get('importance', 0) for v in delayed_voters)
            
            # Prepara i gruppi di votanti per l'output
            voter_groups = {
                "immediate": [v.get('voter') for v in immediate_voters],
                "quick": [v.get('voter') for v in quick_voters],
                "delayed": [v.get('voter') for v in delayed_voters],
                "top_by_time": [v.get('voter') for v in top_voters_by_time[:min(3, len(top_voters_by_time))]]
            }
            
            # Formatta i valori di importance per i gruppi
            group_importance = {
                "immediate": round(immediate_importance, 3),
                "quick": round(quick_importance, 3),
                "delayed": round(delayed_importance, 3)
            }
            
            # Aggiungi informazione sui votanti di alto valore
            high_value_count = num_high_value
            high_value_info = f"{high_value_count} votanti con valore ≥ 10 STEEM" if high_value_count > 0 else "Nessun votante con alto valore"
            
            return {
                'optimal_time': round(optimal_time, 1),
                'explanation': detailed_explanation,
                'strategy': strategy_explanation,
                'top_voters': [v.get('voter', 'sconosciuto') for v in top_voters[:min(5, len(top_voters))]],
                'vote_window': (round(vote_window[0], 1), round(vote_window[1], 1)),
                'voter_groups': voter_groups,
                'group_importance': group_importance,
                'high_value_info': high_value_info,
                'high_value_count': high_value_count,
                'earliest_top_voter': earliest_top_voter.get('voter', 'sconosciuto'),
                'earliest_top_time': earliest_top_time
            }
        else:
            # Nessun votante significativo trovato
            return {
                'optimal_time': 5,
                'explanation': 'Nessun votante significativo trovato, usando il tempo predefinito di 5 minuti',
                'vote_window': (4.5, 5.5),
                'voter_groups': {}
            }
    
    @lru_cache(maxsize=128)
    def calculate_vote_value_cached(self, vote_percent, effective_vests=None, voting_power=9200):
        """Versione con cache del metodo calculate_vote_value per migliorare le prestazioni"""
        return self.calculate_vote_value(vote_percent, effective_vests, voting_power)
        
    def calculate_vote_values_batch(self, vote_data_list, max_workers=5):
        """Calcola il valore di voto per un lotto di votanti in parallelo
        
        Args:
            vote_data_list (list): Lista di dizionari con 'voter_name', 'vote_percent', 'vests'
            max_workers (int): Numero massimo di thread worker 
            
        Returns:
            dict: Dizionario con chiavi voter_name e valori con risultati del calcolo
        """
        results = {}
        
        def process_single_vote(vote_info):
            try:
                voter = vote_info['voter_name']
                percent = vote_info.get('vote_percent', 10000)
                vests = vote_info.get('vests', None)
                # Usa la versione cached del metodo
                result = self.calculate_vote_value_cached(percent, vests)
                return voter, result
            except Exception as e:
                logger.debug(f"Errore nel calcolo del valore di voto per {vote_info.get('voter_name')}: {e}")
                return vote_info.get('voter_name'), {
                    "steem_value": 0,
                    "sbd_value": 0,
                    "error": str(e)
                }
                
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_vote, vote_data): vote_data for vote_data in vote_data_list}
            
            for future in as_completed(futures):
                try:
                    voter, result = future.result()
                    results[voter] = result
                except Exception as e:
                    logger.error(f"Errore imprevisto nel processing del voto: {e}")
        
        return results
    
    def _process_vote_data(self, vote_data, post_url, blockchain_instance, post_created, 
                          curator_username, process_details=False, min_importance=0.0):
        """Processa un singolo voto e restituisce i dati del votante"""
        try:
            voter_name = vote_data['voter']
            # Escludi il curatore stesso
            if voter_name.lower() == curator_username:
                return None
                
            # Prima prova a ottenere rshares direttamente dal voto (più veloce)
            vote_rshares = float(vote_data.get('rshares', 0))
            vote_time = None
            vote_percent = float(vote_data.get('percent', 0))
            
            # Se richiesta analisi dettagliata o se il voto ha rshares significativi
            if process_details or vote_rshares >= 1e9:  # 1B rshares come soglia
                try:
                    vote = Vote(voter_name, post_url, blockchain_instance=blockchain_instance)
                    vote_time = vote.time
                    vote_percent = vote.percent
                    if vote_time.tzinfo is None:
                        vote_time = vote_time.replace(tzinfo=timezone.utc)
                    
                    if not vote_rshares or vote_rshares == 0:
                        vote_rshares = float(vote.rshares)
                        
                except Exception as vote_error:
                    logger.debug(f"Errore nel recupero dati voto per {voter_name}: {vote_error}")
                    vote_time = None
            
            # Se non abbiamo il tempo del voto, usa una stima
            if vote_time is None:
                vote_time = post_created + timedelta(hours=1)  # stima
                
            # Calcola il ritardo del voto in minuti
            vote_delay_minutes = int((vote_time - post_created).total_seconds() / 60)
            
            # Calcola l'importanza usando rshares direttamente se disponibili
            importance = vote_rshares / 1e12  # Normalizza per leggibilità
            
            # Variabili predefinite
            vests = 0
            reputation = 0
            steem_vote_value = 0
            sbd_vote_value = 0
            calculate_vote_value = None
            
            # Per i voti con dettagli o con rshares significativi, ottieni dettagli aggiuntivi
            if process_details or vote_rshares >= 1e9:
                # Ottieni account dalla cache o dalla blockchain
                voter_account = self._get_cached_account(voter_name, blockchain_instance)
                if voter_account:
                    try:
                        vests = float(voter_account['vesting_shares'].amount) + \
                               float(voter_account['received_vesting_shares'].amount) - \
                               float(voter_account['delegated_vesting_shares'].amount)
                        
                        calculate_vote_value = self.calculate_vote_value(vote_percent, effective_vests=vests)
                        steem_vote_value = calculate_vote_value.get('steem_value', 0)
                        sbd_vote_value = calculate_vote_value.get('sbd_value', 0)
                        
                        # Calcola l'importanza considerando sia i vesting shares che il valore in STEEM
                        steem_importance = steem_vote_value * 10  # Diamo più peso al valore effettivo in STEEM
                        vest_importance = vests / 1e6
                        # Usa una media ponderata con più peso al valore STEEM (70% STEEM, 30% vesting)
                        importance = 0.7 * steem_importance + 0.3 * vest_importance
                        
                        reputation = voter_account.get_reputation()
                    except Exception as e:
                        logger.debug(f"Non è stato possibile calcolare tutti i dettagli per {voter_name}: {e}")
            
            # Verifica se il votante supera la soglia di importanza minima
            if importance >= min_importance or vote_rshares >= min_importance * 1e12:
                return {
                    'voter': voter_name,
                    'weight': vote_percent,
                    'rshares': vote_rshares,
                    'vesting_shares': vests,
                    'importance': importance,
                    'vote_time': vote_time.strftime('%Y-%m-%d %H:%M:%S') if hasattr(vote_time, 'strftime') else vote_time,
                    'vote_delay_minutes': vote_delay_minutes,
                    'reputation': reputation,
                    'steem_vote_value': steem_vote_value,
                    'sbd_vote_value': sbd_vote_value
                }
            return None
                
        except Exception as e:
            logger.debug(f"Error processing voter {vote_data.get('voter', 'unknown')}: {str(e)}")
            return None

    # Funzioni di utility per la cache degli account
def clear_account_cache():
    """Pulisce la cache globale degli account"""
    with _account_cache_lock:
        _account_cache.clear()
    
def get_account_cache_stats():
    """Restituisce statistiche sulla cache degli account"""
    with _account_cache_lock:
        return {
            "cache_size": len(_account_cache),
            "memory_usage_estimate": len(_account_cache) * 500  # Stima grezza in KB
        }

# Aggiungi un timer per pulire la cache periodicamente (ogni ora)
def _setup_cache_cleanup_timer():
    """Configura un timer per la pulizia periodica della cache"""
    import threading
    
    def cleanup_task():
        clear_account_cache()
        logger.debug("Account cache cleaned up")
        threading.Timer(3600, cleanup_task).start()  # 3600 secondi = 1 ora
    
    threading.Timer(3600, cleanup_task).start()

# Avvia il timer di pulizia all'importazione del modulo
_setup_cache_cleanup_timer()