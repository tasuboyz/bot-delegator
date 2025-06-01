/**
 * UI Module - Gestisce l'interfaccia utente      const userCard = document.createElement('div');
      userCard.className = 'user-card';      userCard.innerHTML = `
        <div class="user-info">
          <strong><i class="fas fa-user"></i> @${username}</strong>
          <span><i class="fas fa-clock"></i> Vote Delay: ${data.voteDelay} minutes</span>
          <span><i class="fas fa-percentage"></i> Vote Weight: ${data.voteWeight}%</span>
          <span class="${(data.dailyVotesCount || 0) >= (data.votesPerDay || 1) ? 'vote-limit-reached' : ''}">
            <i class="fas fa-calendar-day"></i> Votes: <span class="vote-count-badge">${data.dailyVotesCount || 0}/${data.votesPerDay || 1}</span> today
          </span>
          <div class="votes-progress-container">
            <div class="votes-progress-bar ${(data.dailyVotesCount || 0) >= (data.votesPerDay || 1) ? 'limit-reached' : ''}" 
                 style="width: ${Math.min(((data.dailyVotesCount || 0) / (data.votesPerDay || 1)) * 100, 100)}%">
            </div>
          </div>
          <div class="latest-post" id="latest-post-${username}">
            <div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading latest post...</div>
          </div>
        </div>
        <div class="user-settings">`nti visuali
 */

class UIService {
  constructor() {
    this.statusMessageElement = null;
  }

  /**
   * Inizializza il messaggio di stato se non esiste
   * @private
   */
  _initStatusMessage() {
    if (!this.statusMessageElement) {
      this.statusMessageElement = document.createElement('div');
      this.statusMessageElement.className = 'status-message';
      document.querySelector('.container').appendChild(this.statusMessageElement);
    }
  }
  /**
   * Mostra un messaggio di stato
   * @param {string} message - Messaggio da mostrare
   * @param {string} type - Tipo di messaggio ('info', 'success', 'error')
   * @param {number} duration - Durata in millisecondi (default 3000ms)
   */
  showStatus(message, type = 'info', duration = 3000) {
    this._initStatusMessage();
    this.statusMessageElement.textContent = message;
    this.statusMessageElement.className = `status-message ${type}`;
    this.statusMessageElement.style.display = 'block';
    setTimeout(() => {
      this.statusMessageElement.style.display = 'none';
    }, duration);
  }

  /**
   * Renderizza la lista utenti nella UI
   * @param {Map} users - Mappa degli utenti
   * @param {string} currentPlatform - Piattaforma corrente ('steem', 'hive')
   * @param {Function} displayPostCallback - Callback per visualizzare i post
   */
  renderUsersList(users, currentPlatform, displayPostCallback) {
    const usersList = document.getElementById('usersList');
    usersList.innerHTML = '';

    for (const [username, data] of users) {
      if (data.platform !== currentPlatform) continue;

      // Controlla se l'utente ha informazioni sulla delega
      const delegationInfo = data.sp_amount ? 
        `<span class="delegation-info"><i class="fas fa-hand-holding-usd"></i> Delegated: ${parseFloat(data.sp_amount).toFixed(3)} SP</span>` : '';

      const userCard = document.createElement('div');
      userCard.className = 'user-card';      
      userCard.innerHTML = `
        <div class="user-info">
          <strong><i class="fas fa-user"></i> @${username}</strong>
          ${delegationInfo}
          <span><i class="fas fa-clock"></i> Vote Delay: ${data.voteDelay} minutes</span>
          <span><i class="fas fa-percentage"></i> Vote Weight: ${data.voteWeight}%</span>
          <span class="${(data.dailyVotesCount || 0) >= (data.votesPerDay || 1) ? 'vote-limit-reached' : ''}">
            <i class="fas fa-calendar-day"></i> Votes: <span class="vote-count-badge">${data.dailyVotesCount || 0}/${data.votesPerDay || 1}</span> today
          </span>
          <div class="votes-progress-container">
            <div class="votes-progress-bar ${(data.dailyVotesCount || 0) >= (data.votesPerDay || 1) ? 'limit-reached' : ''}" 
                 style="width: ${Math.min(((data.dailyVotesCount || 0) / (data.votesPerDay || 1)) * 100, 100)}%">
            </div>
          </div>
          <div class="latest-post" id="latest-post-${username}">
            <div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading latest post...</div>
          </div>
        </div>
        <div class="user-settings">
          <button class="edit-btn" data-username="${username}">
            <i class="fas fa-edit"></i>
          </button>
          <button class="delete-btn" data-username="${username}">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      `;
      
      usersList.appendChild(userCard);
      
      // Carica il post più recente
      if (displayPostCallback) {
        displayPostCallback(username, data.platform);
      }
    }
    
    // Aggiungi gli event listener dopo che tutti i pulsanti sono stati renderizzati
    this._attachButtonListeners();
  }
  
  /**
   * Collega gli event listener ai pulsanti
   * @private
   */
  _attachButtonListeners() {
    // Gli event listener saranno collegati dall'app principale
    // perché hanno bisogno di accedere alle funzioni dell'app
  }

  /**
   * Crea una finestra modale
   * @param {string} title - Titolo della modale
   * @param {string} content - Contenuto HTML della modale
   * @param {Function} onSubmit - Funzione da eseguire al submit
   * @returns {HTMLElement} - L'elemento modale
   */
  createModal(title, content) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-content">
        <h3>${title}</h3>
        ${content}
      </div>
    `;

    document.body.appendChild(modal);

    // Chiudi la modale quando si clicca fuori
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        this.closeModal(modal);
      }
    });

    // Gestisci la pressione del tasto Escape
    const escapeHandler = (e) => {
      if (e.key === 'Escape') {
        this.closeModal(modal);
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    document.addEventListener('keydown', escapeHandler);

    return modal;
  }
  
  /**
   * Chiudi una modale con animazione
   * @param {HTMLElement} modal - L'elemento modale da chiudere
   */
  closeModal(modal) {
    modal.classList.add('fade-out');
    setTimeout(() => modal.remove(), 300);
  }

  /**
   * Aggiorna l'icona del tema in base al tema corrente
   */
  updateThemeIcon() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const themeButton = document.getElementById('themeToggle');
    if (themeButton) {
      const moonIcon = themeButton.querySelector('.fa-moon');
      const sunIcon = themeButton.querySelector('.fa-sun');
      
      if (currentTheme === 'dark') {
        moonIcon.style.display = 'none';
        sunIcon.style.display = 'block';
      } else {
        moonIcon.style.display = 'block';
        sunIcon.style.display = 'none';
      }
    }
  }
  
  /**
   * Renderizza i dati dei votanti
   * @param {HTMLElement} container - Container dove visualizzare i dati
   * @param {Object} data - Dati dei votanti
   */
  renderVotersData(container, data) {
    const {voters, total_voters, optimal_vote_time} = data;
    
    let votersHtml = `
      <div class="optimal-vote-time">
        <h5><i class="fas fa-stopwatch"></i> Tempo ottimale di voto</h5>
        <div class="vote-timing-recommendation">
          <span class="optimal-time">${optimal_vote_time.optimal_time} minuti</span>
          <div class="vote-window">
            (finestra ottimale: ${optimal_vote_time.vote_window[0]}-${optimal_vote_time.vote_window[1]} min)
          </div>
          <div class="vote-explanation">${optimal_vote_time.explanation}</div>
        </div>
      </div>      <h5><i class="fas fa-chart-bar"></i> Top Voters (${total_voters} total)</h5>
      <div class="voters-info">
        <i class="fas fa-info-circle"></i> 
        Ordinati per impatto economico (valore in STEEM)
      </div>
    `;
    
    if (voters.length > 0) {
      votersHtml += '<div class="voters-list">';
      voters.forEach(voter => {        // Calcola il peso del voto come percentuale
        const voteWeight = (voter.weight / 100).toFixed(0);
        // Visualizza il ritardo del voto
        const voteDelay = voter.vote_delay_minutes;
        
        // Formatta il valore del voto in STEEM - ora principale metrica di importanza
        const voteValue = voter.steem_vote_value > 0 ? voter.steem_vote_value.toFixed(3) : "0.000";
        
        // Formatta l'importanza tradizionale - ora secondaria
        const importance = voter.importance.toFixed(2);
        
        // Evidenzia i votanti principali menzionati nella strategia di voto
        const isKeyVoter = optimal_vote_time.top_voters && 
                          optimal_vote_time.top_voters.includes(voter.voter);
        const keyVoterClass = isKeyVoter ? 'key-voter' : '';
        
        votersHtml += `
          <div class="voter-item ${keyVoterClass}">
            <strong>@${voter.voter}</strong> 
            <div class="voter-main-stats">
              <span class="vote-value" title="Estimated vote value in STEEM">${voteValue} STEEM</span>
              <span class="vote-timing" title="Vote timing">after ${voteDelay} min</span>
            </div>
            <span class="vote-stats">
              <span class="vote-weight">${voteWeight}%</span>
              <span class="vote-power" title="Traditional influence score">rank: ${importance}</span>
            </span>
          </div>
        `;
      });
      votersHtml += '</div>';
    } else {
      votersHtml += '<div class="no-voters">No significant voters yet</div>';
    }
    
    container.innerHTML = votersHtml;
  }
}

// Esporta un'istanza singleton
const uiService = new UIService();
export default uiService;