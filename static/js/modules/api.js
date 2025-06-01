/**
 * API Module - Gestisce le chiamate al backend
 */

class ApiService {
  constructor() {
    this.retryAttempts = 3;
    this.retryDelay = 1000; // 1 second
  }

  /**
   * Invia una richiesta HTTP al server con gestione automatica dei tentativi
   * @param {string} endpoint - Endpoint API
   * @param {string} method - Metodo HTTP (GET, POST, PUT, DELETE)
   * @param {Object} data - Dati da inviare (opzionale)
   * @returns {Promise} Promise con la risposta o errore
   */
  async sendRequest(endpoint, method, data) {
    let attempts = 0;
    while (attempts < this.retryAttempts) {
      try {
        const response = await fetch(`${endpoint}`, {
          method: method,
          headers: {
            'Content-Type': 'application/json',
          },
          body: data ? JSON.stringify(data) : undefined
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        return { success: true, data: result };

      } catch (error) {
        attempts++;
        console.error(`API request failed (attempt ${attempts}/${this.retryAttempts}):`, error);
        
        if (attempts === this.retryAttempts) {
          return { success: false, error: error.message };
        }
        
        await new Promise(resolve => setTimeout(resolve, this.retryDelay));
      }
    }
  }

  /**
   * Ottiene tutti gli utenti
   * @returns {Promise} Lista utenti
   */
  async getUsers() {
    return await this.sendRequest('/users', 'GET');
  }

  /**
   * Aggiunge un nuovo utente
   * @param {Object} userData - Dati dell'utente
   * @returns {Promise} Risposta dell'API
   */
  async addUser(userData) {
    return await this.sendRequest('/users', 'POST', userData);
  }

  /**
   * Aggiorna un utente esistente
   * @param {string} username - Nome utente
   * @param {Object} userData - Nuovi dati dell'utente
   * @returns {Promise} Risposta dell'API
   */
  async updateUser(username, userData) {
    return await this.sendRequest(`/users/${username}`, 'PUT', userData);
  }

  /**
   * Elimina un utente
   * @param {string} username - Nome utente da eliminare
   * @returns {Promise} Risposta dell'API
   */
  async deleteUser(username) {
    return await this.sendRequest(`/users/${username}`, 'DELETE');
  }

  /**
   * Ottiene i dati dei votanti per un post
   * @param {string} postUrl - URL del post
   * @param {number} minImportance - Importanza minima dei votanti (default: 0.1)
   * @returns {Promise} Dati dei votanti
   */
  async getPostVoters(postUrl, minImportance = 0.1) {
    return await this.sendRequest(
      `/api/post_voters?post_url=${encodeURIComponent(postUrl)}&min_importance=${minImportance}`,
      'GET'
    );
  }

  /**
   * Ottiene la lista dei delegatori per Steem
   * @returns {Promise} Lista dei delegatori
   */
  async getSteemDelegators() {
    return await this.sendRequest('/api/delegators/steem', 'GET');
  }
}

// Esporta un'istanza singleton
const apiService = new ApiService();
export default apiService;