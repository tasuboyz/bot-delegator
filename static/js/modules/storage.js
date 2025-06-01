/**
 * Storage Module - Gestisce il salvataggio e il caricamento dei dati dal localStorage
 */

class StorageService {
  constructor() {
    this.USERS_KEY = 'curatedUsers';
    this.THEME_KEY = 'theme';
    this.DEFAULT_THEME = 'light';
  }

  /**
   * Salva gli utenti nel localStorage
   * @param {Map} users - Mappa degli utenti da salvare
   */
  saveUsers(users) {
    try {
      localStorage.setItem(this.USERS_KEY, JSON.stringify(Array.from(users.entries())));
      return true;
    } catch (error) {
      console.error('Error saving users to localStorage:', error);
      return false;
    }
  }

  /**
   * Carica gli utenti dal localStorage
   * @returns {Map} Mappa degli utenti caricati
   */
  loadUsers() {
    try {
      const saved = localStorage.getItem(this.USERS_KEY);
      return saved ? new Map(JSON.parse(saved)) : new Map();
    } catch (error) {
      console.error('Error loading users from localStorage:', error);
      return new Map();
    }
  }

  /**
   * Salva il tema nel localStorage
   * @param {string} theme - 'light' o 'dark'
   */
  saveTheme(theme) {
    try {
      localStorage.setItem(this.THEME_KEY, theme);
      return true;
    } catch (error) {
      console.error('Error saving theme to localStorage:', error);
      return false;
    }
  }

  /**
   * Carica il tema dal localStorage
   * @returns {string} - 'light' o 'dark'
   */
  loadTheme() {
    try {
      return localStorage.getItem(this.THEME_KEY) || this.DEFAULT_THEME;
    } catch (error) {
      console.error('Error loading theme from localStorage:', error);
      return this.DEFAULT_THEME;
    }
  }

  /**
   * Esporta i dati in un file JSON
   * @param {Object} data - Dati da esportare
   * @returns {boolean} - true se l'esportazione è riuscita
   */
  exportToFile(data) {
    try {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `curation-data-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      return true;
    } catch (error) {
      console.error('Error exporting data:', error);
      return false;
    }
  }

  /**
   * Importa dati da un file JSON
   * @param {File} file - File da importare
   * @returns {Promise<Object>} - Promise con i dati importati
   */
  async importFromFile(file) {
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      return { success: true, data };
    } catch (error) {
      console.error('Error importing data:', error);
      return { success: false, error };
    }
  }
}

// Esporta un'istanza singleton
const storageService = new StorageService();
export default storageService;