/**
 * Main Application File
 * Coordinatore centrale che utilizza i moduli per implementare la logica dell'applicazione
 */

// Importa i moduli necessari
import apiService from './modules/api.js';
import blockchainService from './modules/blockchain.js';
import uiService from './modules/ui.js';
import storageService from './modules/storage.js';

/**
 * Classe principale dell'applicazione Curation Manager
 */
class CurationApp {  constructor() {
    this.currentPlatform = 'steem';
    this.users = new Map();
    
    // Configura gli event listeners quando il DOM è caricato
    document.addEventListener('DOMContentLoaded', () => {
      this.setupEventListeners();
      
      // Carica gli utenti salvati e il tema
      this.loadSavedUsers().then(() => {
        // Dopo aver caricato gli utenti, avvia l'importazione automatica dei delegatori
        setTimeout(() => {
          this.addAllDelegatorsAsUsers();
        }, 2000); // Attendiamo 2 secondi per assicurarci che tutto sia pronto
      });
      
      this.initializeTheme();
      
      // Mostra notifica iniziale
      setTimeout(() => {
        uiService.showStatus('Importazione automatica delegatori in corso...', 'info', 4000);
      }, 1000);
    });
  }

  /**
   * Configura tutti gli event listener dell'UI
   */
  setupEventListeners() {
    document.getElementById('steemBtn').addEventListener('click', () => this.switchPlatform('steem'));
    document.getElementById('hiveBtn').addEventListener('click', () => this.switchPlatform('hive'));
    document.getElementById('addUserForm').addEventListener('submit', (e) => this.handleAddUser(e));
    document.getElementById('themeToggle').addEventListener('click', () => this.toggleTheme());
    document.getElementById('exportDataBtn').addEventListener('click', () => this.exportData());
    document.getElementById('importDataBtn').addEventListener('click', () => document.getElementById('importInput').click());
    document.getElementById('importInput').addEventListener('change', (e) => this.importData(e));
    document.getElementById('logDataBtn').addEventListener('click', () => this.logData());
    
    // Verifica se il pulsante esiste prima di aggiungere l'event listener
    const showDelegatorsBtn = document.getElementById('showDelegatorsBtn');
    if (showDelegatorsBtn) {
      showDelegatorsBtn.addEventListener('click', () => this.showDelegators());
    }
    
    // Nuovo event listener per il toggle dell'optimal time
    document.getElementById('optimalTimeToggle').addEventListener('change', (e) => {
      const useOptimalTime = e.target.checked;
      const voteDelayInput = document.getElementById('voteDelay');
      
      if (useOptimalTime) {
        voteDelayInput.classList.add('auto-mode');
        voteDelayInput.setAttribute('readonly', true);
        voteDelayInput.setAttribute('placeholder', 'Auto');
        voteDelayInput.value = '';
      } else {
        voteDelayInput.classList.remove('auto-mode');
        voteDelayInput.removeAttribute('readonly');
        voteDelayInput.setAttribute('placeholder', '');
        voteDelayInput.value = '5'; // Default value
      }
    });
    
    // Aggiungi event delegation per i pulsanti delle user card
    document.getElementById('usersList').addEventListener('click', (e) => {
      // Gestisci il pulsante di modifica
      if (e.target.closest('.edit-btn')) {
        const username = e.target.closest('.edit-btn').dataset.username;
        this.updateUserSettings(username);
      }
      
      // Gestisci il pulsante di eliminazione
      if (e.target.closest('.delete-btn')) {
        const username = e.target.closest('.delete-btn').dataset.username;
        this.deleteUser(username);
      }
      
      // Gestisci il pulsante di visualizzazione votanti
      if (e.target.closest('.show-voters-btn')) {
        const username = e.target.closest('.show-voters-btn').getAttribute('id').replace('show-voters-', '');
        const postUrlElement = e.target.closest('.post-info').querySelector('a');
        
        if (postUrlElement) {
          const postUrl = postUrlElement.getAttribute('href').replace('https://cur8.fun/#/', '');
          this.toggleVotersDisplay(username, postUrl);
        }
      }
    });
    
    // Pulsante per svuotare tutti gli utenti/autori
    const clearUsersBtn = document.getElementById('clearUsersBtn');
    if (clearUsersBtn) {
      clearUsersBtn.addEventListener('click', () => {
        if (confirm('Sei sicuro di voler eliminare TUTTI gli utenti/autori sia dal frontend che dal backend?')) {
          this.clearAllUsers();
        }
      });
    }
    
    // Esempio: intercetta il submit del form curatore (se presente)
    const curatorForm = document.getElementById('steemCuratorForm');
    if (curatorForm) {
      curatorForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        // Raccogli dati dal form
        const username = document.getElementById('steemUsername').value;
        const postingKey = document.getElementById('steemPostingKey').value;
        // Prepara payload
        const payload = { platform: 'steem', username };
        if (postingKey) payload.posting_key = postingKey;
        // Chiamata API
        const response = await apiService.sendRequest('/api/curator/update', 'POST', payload);
        if (response && response.success) {
          // Pulizia utenti e reload delegatori
          await window.curationApp.handleCuratorChange(username);
          // Ricarica delegatori del nuovo curatore
          await window.curationApp.addAllDelegatorsAsUsers();
          uiService.showStatus('Curatore aggiornato. Delegatori ricaricati!', 'success');
        } else {
          uiService.showStatus('Errore aggiornamento curatore', 'error');
        }
      });
    }
  }

  /**
   * Passa da una piattaforma all'altra (Steem/Hive)
   * @param {string} platform - 'steem' o 'hive'
   */
  switchPlatform(platform) {
    this.currentPlatform = platform;
    document.getElementById('steemBtn').classList.toggle('active', platform === 'steem');
    document.getElementById('hiveBtn').classList.toggle('active', platform === 'hive');
    this.renderUsersList();
  }

  /**
   * Gestisce l'aggiunta di un nuovo utente
   * @param {Event} e - Evento di submit
   */
  async handleAddUser(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const useOptimalTime = document.getElementById('optimalTimeToggle').checked;
    
    // Se useOptimalTime è true, il valore di voteDelay è "auto", altrimenti usa il valore inserito
    const voteDelay = useOptimalTime ? 'auto' : parseFloat(document.getElementById('voteDelay').value);
    const voteWeight = parseInt(document.getElementById('voteWeight').value);

    try {
      await blockchainService.verifyNodeConnection(this.currentPlatform);
      const accounts = await blockchainService.getAccountInfo(username, this.currentPlatform);
      
      if (!accounts || accounts.length === 0) {
        throw new Error('User not found');
      }      const votesPerDay = parseInt(document.getElementById('votesPerDay').value);
      
      const userData = {
        username,
        platform: this.currentPlatform,
        voteDelay,
        voteWeight,
        votesPerDay,
        useOptimalTime,
        timestamp: Date.now(),
        dailyVotesCount: 0,
        lastVoteDate: null
      };

      // Try API first, but continue even if it fails
      let apiSuccess = false;
      try {
        const apiResponse = await apiService.addUser(userData);
        apiSuccess = apiResponse.success;
      } catch (error) {
        console.warn('API call failed, continuing with local storage:', error);
      }

      // Save to local storage regardless of API response
      this.users.set(username, userData);
      storageService.saveUsers(this.users);
      this.renderUsersList();
      e.target.reset();
      
      uiService.showStatus(
        apiSuccess ? 'User added successfully and synced with API!' : 'User added locally. API sync failed.',
        apiSuccess ? 'success' : 'info'
      );

    } catch (error) {
      uiService.showStatus(`Error: ${error.message}`, 'error');
    }
  }

  /**
   * Apre il modal per aggiornare le impostazioni di un utente
   * @param {string} username - Nome utente
   */
  updateUserSettings(username) {
    const userData = this.users.get(username);
    if (!userData) return;

    // Determina se l'utente ha attivato la modalità auto (voteDelay = 'auto' oppure useOptimalTime = true)
    const useOptimalTime = userData.useOptimalTime || userData.voteDelay === 'auto';
    
    const modalContent = `
      <form id="editUserForm">
        <div class="setting">
          <label for="editVoteDelay">
            <i class="fas fa-clock"></i> Vote Delay (minutes)
          </label>
          <div class="delay-input-container">
            <input 
              type="number" 
              id="editVoteDelay" 
              min="0" 
              max="1440"
              step="0.1"
              value="${useOptimalTime ? '' : userData.voteDelay}" 
              placeholder="${useOptimalTime ? 'Auto' : ''}"
              ${useOptimalTime ? 'readonly' : ''}
              class="${useOptimalTime ? 'auto-mode' : ''}"
              ${useOptimalTime ? '' : 'required'}
            >
            <div class="toggle-container">
              <label class="toggle-switch">
                <input type="checkbox" id="editOptimalTimeToggle" ${useOptimalTime ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
              <span class="toggle-label">Auto Optimal</span>
            </div>
          </div>
          <div class="input-feedback delay-feedback">
            Posts will be voted ${useOptimalTime ? 'at optimal time (auto)' : userData.voteDelay + ' minutes after publication'}
          </div>
        </div>
          <div class="setting">
          <label for="editVoteWeight">
            <i class="fas fa-percentage"></i> Vote Weight
          </label>
          <input 
            type="number" 
            id="editVoteWeight" 
            min="1" 
            max="100" 
            value="${userData.voteWeight}" 
            required
          >
          <div class="input-feedback weight-feedback">
            Votes will be cast at ${userData.voteWeight}% strength
          </div>
        </div>
          <div class="setting votes-per-day-setting">
          <label for="editVotesPerDay">
            <i class="fas fa-calendar-day"></i> Votes Per Day
          </label>          <input
            type="number"
            id="editVotesPerDay"
            min="1"
            max="10"
            value="${userData.votesPerDay || 1}"
            placeholder="1-10"
            aria-label="Votes Per Day"
            title="Set how many times per day to vote for this author (1-10)"
            required
          >
          <div class="input-feedback votes-per-day-feedback">
            Maximum of ${userData.votesPerDay || 1} vote(s) per day for this author
          </div>
        </div>
        
        <div class="modal-buttons">
          <button type="submit" class="save-btn">
            <i class="fas fa-save"></i> Save Changes
          </button>
          <button type="button" class="cancel-btn">
            <i class="fas fa-times"></i> Cancel
          </button>
        </div>
      </form>
    `;

    const modal = uiService.createModal(
      `<i class="fas fa-user-edit"></i> Edit Settings for @${username}`,
      modalContent
    );    // Setup validation feedback
    const delayInput = modal.querySelector('#editVoteDelay');
    const weightInput = modal.querySelector('#editVoteWeight');
    const votesPerDayInput = modal.querySelector('#editVotesPerDay');
    const delayFeedback = modal.querySelector('.delay-feedback');
    const weightFeedback = modal.querySelector('.weight-feedback');
    const votesPerDayFeedback = modal.querySelector('.votes-per-day-feedback');
    const optimalToggle = modal.querySelector('#editOptimalTimeToggle');
    
    // Gestisci il toggle per Auto Optimal Time
    optimalToggle.addEventListener('change', (e) => {
      const useOptimalTime = e.target.checked;
      
      if (useOptimalTime) {
        delayInput.classList.add('auto-mode');
        delayInput.setAttribute('readonly', true);
        delayInput.setAttribute('placeholder', 'Auto');
        delayInput.value = '';
        delayInput.removeAttribute('required');
        delayFeedback.textContent = 'Posts will be voted at optimal time (auto)';
        delayFeedback.classList.remove('invalid');
        delayFeedback.classList.add('valid', 'show');
      } else {
        delayInput.classList.remove('auto-mode');
        delayInput.removeAttribute('readonly');
        delayInput.setAttribute('placeholder', '');
        delayInput.value = '5'; // Default value or previous value
        delayInput.setAttribute('required', true);
        delayFeedback.textContent = `Posts will be voted 5 minutes after publication`;
        delayFeedback.classList.remove('invalid');
        delayFeedback.classList.add('valid', 'show');
      }
    });

    delayInput.addEventListener('input', (e) => {
      const value = e.target.value;
      if (value >= 0 && value <= 1440) {
        delayFeedback.textContent = `Posts will be voted ${value} minutes after publication`;
        delayFeedback.classList.remove('invalid');
        delayFeedback.classList.add('valid', 'show');
      } else {
        delayFeedback.textContent = 'Please enter a value between 0 and 1440 minutes';
        delayFeedback.classList.remove('valid');
        delayFeedback.classList.add('invalid', 'show');
      }
    });    weightInput.addEventListener('input', (e) => {
      const value = e.target.value;
      if (value >= 1 && value <= 100) {
        weightFeedback.textContent = `Votes will be cast at ${value}% strength`;
        weightFeedback.classList.remove('invalid');
        weightFeedback.classList.add('valid', 'show');
      } else {
        weightFeedback.textContent = 'Please enter a value between 1 and 100';
        weightFeedback.classList.remove('valid');
        weightFeedback.classList.add('invalid', 'show');
      }
    });
    
    votesPerDayInput.addEventListener('input', (e) => {
      const value = e.target.value;
      if (value >= 1 && value <= 10) {
        votesPerDayFeedback.textContent = `Maximum of ${value} vote(s) per day for this author`;
        votesPerDayFeedback.classList.remove('invalid');
        votesPerDayFeedback.classList.add('valid', 'show');
      } else {
        votesPerDayFeedback.textContent = 'Please enter a value between 1 and 10';
        votesPerDayFeedback.classList.remove('valid');
        votesPerDayFeedback.classList.add('invalid', 'show');
      }
    });

    // Handle cancel button
    modal.querySelector('.cancel-btn').addEventListener('click', () => {
      uiService.closeModal(modal);
    });
      // Handle form submit
    modal.querySelector('#editUserForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const useOptimalTime = modal.querySelector('#editOptimalTimeToggle').checked;
      const newVoteDelay = useOptimalTime ? 'auto' : parseFloat(delayInput.value);
      const newVoteWeight = parseInt(weightInput.value);
      const newVotesPerDay = parseInt(modal.querySelector('#editVotesPerDay').value);

      if (!useOptimalTime && (newVoteDelay < 0 || newVoteDelay > 1440 || isNaN(newVoteDelay))) {
        return;
      }
      
      if (newVoteWeight < 1 || newVoteWeight > 100 || isNaN(newVoteWeight)) {
        return;
      }
      
      if (newVotesPerDay < 1 || newVotesPerDay > 10 || isNaN(newVotesPerDay)) {
        return;
      }

      const updatedData = {
        ...this.users.get(username),
        voteDelay: newVoteDelay,
        voteWeight: newVoteWeight,
        votesPerDay: newVotesPerDay,
        useOptimalTime: useOptimalTime,
        lastUpdated: Date.now()
      };

      let apiSuccess = false;
      try {
        const apiResponse = await apiService.updateUser(username, updatedData);
        apiSuccess = apiResponse.success;
      } catch (error) {
        console.warn('API update failed, continuing with local storage:', error);
      }

      // Update local storage regardless of API status
      this.users.set(username, updatedData);
      storageService.saveUsers(this.users);
      this.renderUsersList();
      
      const successMsg = document.createElement('div');
      successMsg.style.color = 'var(--success-color)';
      successMsg.innerHTML = apiSuccess ? 
        '<i class="fas fa-check-circle"></i> Settings updated successfully and synced with API!' :
        '<i class="fas fa-check-circle"></i> Settings updated locally. API sync failed.';
      modal.querySelector('.modal-content').appendChild(successMsg);
      
      setTimeout(() => uiService.closeModal(modal), 1000);
      uiService.showStatus(
        apiSuccess ? 'User settings updated and synced!' : 'Settings updated locally. API sync failed.',
        apiSuccess ? 'success' : 'info'
      );
    });
  }

  /**
   * Elimina un utente dalla lista
   * @param {string} username - Nome utente da eliminare
   */
  async deleteUser(username) {
    let apiSuccess = false;
    try {
      const apiResponse = await apiService.deleteUser(username);
      apiSuccess = apiResponse.success;
    } catch (error) {
      console.warn('API delete failed, continuing with local storage:', error);
    }

    // Delete from local storage regardless of API status
    this.users.delete(username);
    storageService.saveUsers(this.users);
    this.renderUsersList();
    
    uiService.showStatus(
      apiSuccess ? 'User deleted successfully and synced with API!' : 'User deleted locally. API sync failed.',
      apiSuccess ? 'success' : 'info'
    );
  }

  /**
   * Elimina tutti gli utenti sia dal frontend che dal backend
   */
  async clearAllUsers() {
    // Svuota localStorage e memoria
    storageService.clearUsers();
    this.users = new Map();
    this.renderUsersList();
    // Svuota anche il backend
    try {
      const response = await apiService.sendRequest('/users/clear', 'POST');
      if (response.success) {
        uiService.showStatus('Tutti gli utenti eliminati dal backend e dal frontend!', 'success');
      } else {
        uiService.showStatus('Utenti eliminati localmente. Errore lato backend.', 'warning');
      }
    } catch (e) {
      uiService.showStatus('Utenti eliminati localmente. Errore lato backend.', 'warning');
    }
  }

  /**
   * Carica gli utenti salvati, prima dall'API e poi dal localStorage se necessario
   */
  async loadSavedUsers() {
    try {
      // Try to load users from API
      const response = await apiService.getUsers();
  
      if (response.success) {
        // If response is positive, update users map
        this.users = new Map(response.data.map(user => [user.username, user.data]));
        this.renderUsersList();
      } else {
        // If error, try to load from localStorage
        console.warn('Failed to load users from API, loading from localStorage instead.');
        this.loadUsersFromLocalStorage();
      }
    } catch (error) {
      console.error('Error loading users from API:', error);
      // If error, try to load from localStorage
      this.loadUsersFromLocalStorage();
    }
    
    // Return a resolved promise for chaining
    return Promise.resolve();
}
  
  /**
   * Carica gli utenti dal localStorage
   */
  loadUsersFromLocalStorage() {
    this.users = storageService.loadUsers();
    this.renderUsersList();
  }

  /**
   * Renderizza la lista degli utenti nell'UI
   */
  renderUsersList() {
    uiService.renderUsersList(this.users, this.currentPlatform, (username, platform) => {
      this.displayLatestPost(username, platform);
    });
  }

  /**
   * Visualizza l'ultimo post di un utente
   * @param {string} username - Nome utente
   * @param {string} platform - 'steem' o 'hive'
   */
  async displayLatestPost(username, platform) {
    try {
      await blockchainService.verifyNodeConnection(platform);
      const posts = await blockchainService.getLatestPosts(username, platform);
      const postContainer = document.getElementById(`latest-post-${username}`);
      
      if (!postContainer) return; // L'elemento potrebbe essere stato rimosso
      
      if (posts && posts.length > 0) {
        const latestPost = posts[0];
        const postDate = new Date(latestPost.created + 'Z');
        const formattedDate = postDate.toLocaleString();
        
        // Use the correct domain based on platform
        const domain = blockchainService.getDomainForPlatform(platform);
        const postUrl = `${domain}/@${username}/${latestPost.permlink}`;
        const viewUrl = `https://cur8.fun/#/@${username}/${latestPost.permlink}`;
        
        // Rendering del post base
        postContainer.innerHTML = `
          <div class="post-info">
            <h4><i class="fas fa-file-alt"></i> ${latestPost.title}</h4>
            <div class="post-meta">
              <span><i class="far fa-clock"></i> ${formattedDate}</span>
              <a href="${viewUrl}" 
                 target="_blank" 
                 rel="noopener noreferrer">
                <i class="fas fa-external-link-alt"></i> View Post
              </a>
              <button class="show-voters-btn" id="show-voters-${username}">
                <i class="fas fa-users"></i> Show Voters
              </button>
            </div>
            <div class="voters-container" id="voters-container-${username}" style="display:none">
              <div class="loading-voters"><i class="fas fa-spinner fa-spin"></i> Loading voters data...</div>
            </div>
          </div>
        `;
      } else {
        postContainer.innerHTML = '<div class="no-posts"><i class="fas fa-info-circle"></i> No posts found</div>';
      }
    } catch (error) {
      const postContainer = document.getElementById(`latest-post-${username}`);
      if (postContainer) {
        postContainer.innerHTML = `<div class="error"><i class="fas fa-exclamation-circle"></i> Error loading latest post: ${error.message}</div>`;
      }
    }
  }

  /**
   * Mostra/nasconde i votanti di un post
   * @param {string} username - Nome utente
   * @param {string} postUrl - URL del post
   */
  async toggleVotersDisplay(username, postUrl) {
    const votersContainer = document.getElementById(`voters-container-${username}`);
    if (!votersContainer) return;
    
    // Toggle visibility
    if (votersContainer.style.display === 'none') {
      votersContainer.style.display = 'block';
      
      try {
        // Request voters data
        const votersResponse = await apiService.getPostVoters(postUrl);
        
        if (votersResponse.success && votersResponse.data.voters) {
          uiService.renderVotersData(votersContainer, votersResponse.data);
        } else {
          votersContainer.innerHTML = '<div class="error"><i class="fas fa-exclamation-triangle"></i> Could not load voters data</div>';
        }
      } catch (error) {
        console.error('Error loading voters:', error);
        votersContainer.innerHTML = `<div class="error"><i class="fas fa-exclamation-circle"></i> Error: ${error.message}</div>`;
      }
    } else {
      votersContainer.style.display = 'none';
    }
  }

  /**
   * Controlla se l'utente ha raggiunto il limite giornaliero di voti
   * @param {string} username - Nome utente
   * @param {Object} userData - Dati dell'utente
   * @returns {boolean} - true se è possibile votare ancora oggi
   */
  checkDailyVoteLimit(username, userData) {
    // Imposta valori predefiniti se non esistono
    if (!userData.votesPerDay) userData.votesPerDay = 1;
    if (!userData.dailyVotesCount) userData.dailyVotesCount = 0;
    if (!userData.lastVoteDate) userData.lastVoteDate = null;
    
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    
    // Se non c'è mai stato un voto o l'ultimo voto è di un giorno precedente, resetta il contatore
    if (!userData.lastVoteDate || new Date(userData.lastVoteDate).getTime() < today) {
      userData.dailyVotesCount = 0;
      return true;
    }
    
    // Altrimenti controlla se abbiamo raggiunto il limite
    return userData.dailyVotesCount < userData.votesPerDay;
  }
    /**
   * Aggiorna il contatore dei voti dopo un voto
   * @param {string} username - Nome utente
   * @param {Object} userData - Dati dell'utente
   */
  updateVoteCounter(username, userData) {
    const now = new Date();
    
    // Incrementa il contatore
    if (!userData.dailyVotesCount) userData.dailyVotesCount = 0;
    userData.dailyVotesCount++;
    
    // Aggiorna la data dell'ultimo voto
    userData.lastVoteDate = now.toISOString();
    
    // Aggiorna i dati nell'utente
    this.users.set(username, userData);
    storageService.saveUsers(this.users);
    
    console.log(`Updated vote counter for ${username}: ${userData.dailyVotesCount}/${userData.votesPerDay} votes today`);
    
    // Se abbiamo raggiunto il limite, mostra una notifica
    if (userData.dailyVotesCount >= userData.votesPerDay) {
      uiService.showStatus(`Daily vote limit reached for @${username} (${userData.votesPerDay} votes)`, 'info');
    }

    // Aggiorna la visualizzazione dei contatori di voto
    this.updateVoteCountersDisplay();
    
    // Apply animation to the updated counter
    setTimeout(() => {
      const userCards = document.querySelectorAll('.user-card');
      for (const card of userCards) {
        if (card.querySelector('.user-info strong').textContent.includes(`@${username}`)) {
          const badge = card.querySelector('.vote-count-badge');
          if (badge) {
            badge.classList.add('updated');
            // Remove the class after animation completes to allow it to animate again
            setTimeout(() => badge.classList.remove('updated'), 600);
          }
          break;
        }
      }
    }, 100);
  }
  /**
   * Aggiorna la visualizzazione dei contatori di voto per tutti gli utenti
   */
  updateVoteCountersDisplay() {
    for (const [username, data] of this.users) {
      // Use a more reliable selector to find the user card
      const userCards = document.querySelectorAll('.user-card');
      let userCardElement = null;
      
      for (const card of userCards) {
        if (card.querySelector('.user-info strong').textContent.includes(`@${username}`)) {
          userCardElement = card;
          break;
        }
      }
      
      if (!userCardElement) continue;
      
      const voteCountSpan = userCardElement.querySelector('span i.fa-calendar-day').parentElement;
      const isLimitReached = (data.dailyVotesCount || 0) >= (data.votesPerDay || 1);
      
      if (voteCountSpan) {
        // Update the vote count with enhanced styling
        voteCountSpan.className = isLimitReached ? 'vote-limit-reached' : '';
        voteCountSpan.innerHTML = `
          <i class="fas fa-calendar-day"></i> Votes: 
          <span class="vote-count-badge">${data.dailyVotesCount || 0}/${data.votesPerDay || 1}</span> today
        `;
        
        // Update progress bar
        const progressContainer = userCardElement.querySelector('.votes-progress-container');
        const progressBar = userCardElement.querySelector('.votes-progress-bar');
        
        if (progressBar) {
          progressBar.style.width = `${Math.min(((data.dailyVotesCount || 0) / (data.votesPerDay || 1)) * 100, 100)}%`;
          progressBar.className = `votes-progress-bar ${isLimitReached ? 'limit-reached' : ''}`;
        }
        
        // If progress bar doesn't exist, create it
        if (!progressContainer) {
          const progressHtml = `
            <div class="votes-progress-container">
              <div class="votes-progress-bar ${isLimitReached ? 'limit-reached' : ''}" 
                   style="width: ${Math.min(((data.dailyVotesCount || 0) / (data.votesPerDay || 1)) * 100, 100)}%">
              </div>
            </div>
          `;
          voteCountSpan.insertAdjacentHTML('afterend', progressHtml);
        }
      }
    }
  }

  /**
   * Inizializza il tema dell'interfaccia
   */
  initializeTheme() {
    const savedTheme = storageService.loadTheme();
    document.documentElement.setAttribute('data-theme', savedTheme);
    uiService.updateThemeIcon();
  }

  /**
   * Alterna tra tema chiaro e scuro
   */
  toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    storageService.saveTheme(newTheme);
    uiService.updateThemeIcon();
  }

  /**
   * Esporta i dati in un file JSON
   */
  exportData() {
    const data = {
      users: Array.from(this.users.entries()),
      currentPlatform: this.currentPlatform,
      exportDate: new Date().toISOString(),
      version: '1.0'
    };

    const success = storageService.exportToFile(data);
    if (success) {
      uiService.showStatus('Data exported successfully!', 'success');
    } else {
      uiService.showStatus('Error exporting data!', 'error');
    }
  }

  /**
   * Importa dati da un file JSON
   * @param {Event} e - Evento del file input
   */
  async importData(e) {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const result = await storageService.importFromFile(file);
      
      if (!result.success) {
        throw new Error(result.error || 'Invalid file format');
      }
      
      const data = result.data;
      if (!data.users || !Array.isArray(data.users)) {
        throw new Error('Invalid data format');
      }

      // Attempt to sync with API
      let apiSuccess = false;
      try {
        for (const [username, userData] of data.users) {
          const apiResponse = await apiService.addUser(userData);
          if (!apiResponse.success) {
            console.warn(`Failed to sync user ${username} with API`);
          }
        }
        apiSuccess = true;
      } catch (error) {
        console.warn('API sync failed during import:', error);
      }

      // Update local storage regardless of API status
      this.users = new Map(data.users);
      this.currentPlatform = data.currentPlatform || 'steem';
      storageService.saveUsers(this.users);
      this.renderUsersList();

      // Reset file input
      e.target.value = '';

      uiService.showStatus(
        apiSuccess ? 'Data imported and synced with API successfully!' : 'Data imported locally. API sync failed.',
        apiSuccess ? 'success' : 'info'
      );

    } catch (error) {
      console.error('Import error:', error);
      uiService.showStatus('Error importing data: ' + error.message, 'error');
      e.target.value = '';
    }
  }

  /**
   * Registra i dati nella console
   */
  logData() {
    const data = {
      users: Array.from(this.users.entries()),
      currentPlatform: this.currentPlatform,
      exportDate: new Date().toISOString(),
      version: '1.0',
      stats: {
        totalUsers: this.users.size,
        steemUsers: Array.from(this.users.values()).filter(u => u.platform === 'steem').length,
        hiveUsers: Array.from(this.users.values()).filter(u => u.platform === 'hive').length
      }
    };

    console.log('Current Curation Data:');
    console.log(JSON.stringify(data, null, 2));
    
    uiService.showStatus('Data logged to console!', 'info');
  }

  /**
   * Visualizza i delegatori in un modal
   */
  async showDelegators() {
    try {
      const response = await apiService.getSteemDelegators();
      
      if (response.success && response.data.delegators) {
        const delegators = response.data.delegators;
        
        // Crea il contenuto del modal
        let modalContent = `
          <div class="delegators-list">
            <div class="delegators-header">
              <div class="delegator-col">Delegator</div>
              <div class="amount-col">Amount (SP)</div>
              <div class="date-col">Date</div>
              <div class="actions-col">Actions</div>
            </div>
        `;
        
        // Aggiungi ogni delegatore alla lista
        delegators.forEach(delegator => {
          modalContent += `
            <div class="delegator-row">
              <div class="delegator-col">@${delegator.delegator}</div>
              <div class="amount-col">${delegator.sp_amount.toFixed(3)}</div>
              <div class="date-col">${new Date(delegator.timestamp).toLocaleDateString()}</div>
              <div class="actions-col">
                <button class="add-delegator-btn" data-username="${delegator.delegator}">
                  <i class="fas fa-user-plus"></i> Add as User
                </button>
              </div>
            </div>
          `;
        });
        
        modalContent += '</div>';
        
        // Crea e mostra il modal
        const modal = uiService.createModal(
          `<i class="fas fa-users"></i> Steem Delegators (${delegators.length})`,
          modalContent
        );
        
        // Aggiungi event listener per il pulsante "Add as User"
        modal.querySelectorAll('.add-delegator-btn').forEach(btn => {
          btn.addEventListener('click', (e) => {
            const username = e.target.closest('.add-delegator-btn').dataset.username;
            this.addDelegatorAsUser(username);
            uiService.closeModal(modal);
          });
        });
        
      } else {
        throw new Error('Failed to load delegators data');
      }
    } catch (error) {
      uiService.showStatus(`Error loading delegators: ${error.message}`, 'error');
    }
  }
  
  /**
   * Aggiunge un delegatore come utente da tracciare
   * @param {string} username - Nome utente del delegatore
   */
  addDelegatorAsUser(username) {
    // Controlla se l'utente esiste già
    if (this.users.has(username)) {
      uiService.showStatus(`User @${username} already exists`, 'info');
      return;
    }
    
    // Crea un nuovo utente con impostazioni predefinite
    const userData = {
      username,
      platform: this.currentPlatform,
      voteDelay: 'auto',
      voteWeight: 100,
      votesPerDay: 1,
      useOptimalTime: true,
      timestamp: Date.now(),
      dailyVotesCount: 0,
      lastVoteDate: null
    };
    
    // Aggiungi l'utente
    this.users.set(username, userData);
    storageService.saveUsers(this.users);
    this.renderUsersList();
    
    // Sincronizza con l'API
    apiService.addUser(userData)
      .then(response => {
        if (response.success) {
          uiService.showStatus(`Delegator @${username} added as user successfully!`, 'success');
        } else {
          uiService.showStatus(`Delegator added locally. API sync failed.`, 'info');
        }
      })
      .catch(() => {
        uiService.showStatus(`Delegator added locally. API sync failed.`, 'info');
      });
  }

  /**
   * Gestisce il cambio curatore: pulisce localStorage e ricarica utenti/delegatori
   * @param {string} newCurator - Username del nuovo curatore
   */
  async handleCuratorChange(newCurator) {
    // Pulisci utenti dal localStorage
    storageService.clearUsers();
    this.users = new Map();
    // Aggiorna il curatore memorizzato
    localStorage.setItem('curator_username', newCurator);
    // Ricarica utenti dal backend
    await this.loadSavedUsers();
    uiService.showStatus('Curatore cambiato: dati locali aggiornati!', 'info', 4000);
  }

  /**
   * Aggiunge automaticamente tutti i delegatori come utenti da tracciare
   */
  async addAllDelegatorsAsUsers() {
    try {
      uiService.showStatus('Importazione delegatori in corso...', 'info');
      const response = await apiService.getSteemDelegators();
      if (response.success && response.data.delegators) {
        // --- GESTIONE CAMBIO CURATORE ---
        const apiCurator = response.data.curator || null;
        const storedCurator = localStorage.getItem('curator_username');
        if (apiCurator && storedCurator && apiCurator !== storedCurator) {
          await this.handleCuratorChange(apiCurator);
          // Dopo il reset, interrompi per evitare doppio import
          return;
        } else if (apiCurator && !storedCurator) {
          localStorage.setItem('curator_username', apiCurator);
        }
        // ...existing code...
        const delegators = response.data.delegators;
        let addedCount = 0;
        let skippedCount = 0;
        delegators.sort((a, b) => b.sp_amount - a.sp_amount);
        for (const delegator of delegators) {
          const username = delegator.delegator;
          if (this.users.has(username)) {
            skippedCount++;
            continue;
          }
          const userData = {
            username,
            platform: this.currentPlatform,
            voteDelay: 'auto',
            voteWeight: 100,
            votesPerDay: 1,
            useOptimalTime: true,
            timestamp: Date.now(),
            dailyVotesCount: 0,
            lastVoteDate: null,
            sp_amount: delegator.sp_amount,
            is_delegator: true
          };
          this.users.set(username, userData);
          apiService.addUser(userData).catch(err => {
            console.warn(`Fallita sincronizzazione API per ${username}:`, err);
          });
          addedCount++;
        }
        storageService.saveUsers(this.users);
        this.renderUsersList();
        uiService.showStatus(
          `Importati ${addedCount} delegatori${skippedCount > 0 ? `, ${skippedCount} già presenti` : ''}`,
          'success',
          5000
        );
      } else {
        throw new Error('Dati delegatori non disponibili');
      }
    } catch (error) {
      uiService.showStatus(`Errore nell'importazione dei delegatori: ${error.message}`, 'error');
    }
  }
}

// Inizializza l'applicazione
const curationApp = new CurationApp();
window.curationApp = curationApp;