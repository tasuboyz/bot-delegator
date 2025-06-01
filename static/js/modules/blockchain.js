/**
 * Blockchain Module - Gestisce l'interazione con le blockchain Steem e Hive
 */

class BlockchainService {
  constructor() {
    this.nodes = {
      steem: [
        'https://api.steemit.com',
        'https://api.justyy.com',
        'https://api.moecki.online'
      ],
      hive: [
        'https://api.deathwing.me',
        'https://api.hive.blog',
        'https://api.openhive.network'
      ]
    };
    
    this.currentNodes = { steem: 0, hive: 0 };
    this.steemClient = null;
    this.hiveClient = null;
    
    // Inizializzazione quando il browser carica steem e dhive
    this.initializeClientsWhenReady();
  }

  /**
   * Controlla se i client blockchain sono disponibili e li inizializza
   */
  initializeClientsWhenReady() {
    // Controlla se steem e dhive sono già caricati
    if (typeof steem !== 'undefined' && typeof dhive !== 'undefined') {
      this.initializeClients();
    } else {
      // Riprova dopo un breve timeout
      setTimeout(() => this.initializeClientsWhenReady(), 200);
    }
  }

  /**
   * Inizializza i client blockchain
   */
  initializeClients() {
    this.steemClient = steem;
    this.steemClient.api.setOptions({ url: this.nodes.steem[0] });
    this.hiveClient = new dhive.Client(this.nodes.hive);
    console.log("Blockchain clients initialized");
  }

  /**
   * Passa al nodo successivo per la blockchain specificata
   * @param {string} platform - 'steem' o 'hive'
   * @returns {Promise<void>}
   */
  async switchNode(platform) {
    this.currentNodes[platform] = (this.currentNodes[platform] + 1) % this.nodes[platform].length;
    const newNode = this.nodes[platform][this.currentNodes[platform]];
    
    if (platform === 'steem') {
      this.steemClient.api.setOptions({ url: newNode });
    } else {
      this.hiveClient = new dhive.Client([newNode]);
    }
    
    console.log(`Switched ${platform} node to: ${newNode}`);
  }

  /**
   * Verifica la connessione al nodo corrente
   * @param {string} platform - 'steem' o 'hive'
   * @returns {Promise<boolean>} - true se la connessione è ok
   */
  async verifyNodeConnection(platform) {
    try {
      if (platform === 'steem') {
        await new Promise((resolve, reject) => {
          this.steemClient.api.getDynamicGlobalProperties((err, result) => {
            if (err) reject(err);
            else resolve(result);
          });
        });
      } else {
        await this.hiveClient.database.getDynamicGlobalProperties();
      }
      return true;
    } catch (error) {
      console.error(`Node connection failed for ${platform}, switching...`, error);
      await this.switchNode(platform);
      return false;
    }
  }

  /**
   * Ottiene le informazioni di un account
   * @param {string} username - Nome utente
   * @param {string} platform - 'steem' o 'hive'
   * @returns {Promise<Object>} - Informazioni dell'account
   */
  async getAccountInfo(username, platform) {
    let attempts = 0;
    const maxAttempts = 3;

    while (attempts < maxAttempts) {
      try {
        if (platform === 'steem') {
          const result = await new Promise((resolve, reject) => {
            this.steemClient.api.getAccounts([username], (err, result) => {
              if (err) reject(err);
              else resolve(result);
            });
          });
          return result;
        } else {
          return await this.hiveClient.database.getAccounts([username]);
        }
      } catch (error) {
        attempts++;
        console.error(`Attempt ${attempts} failed for ${username}:`, error);
        if (attempts === maxAttempts) throw error;
        await this.switchNode(platform);
      }
    }
  }

  /**
   * Ottiene i post più recenti di un utente
   * @param {string} username - Nome utente
   * @param {string} platform - 'steem' o 'hive'
   * @returns {Promise<Array>} - Lista di post
   */
  async getLatestPosts(username, platform) {
    let attempts = 0;
    const maxAttempts = 3;

    while (attempts < maxAttempts) {
      try {
        const query = {
          tag: username,
          limit: 1
        };

        if (platform === 'steem') {
          return await new Promise((resolve, reject) => {
            this.steemClient.api.getDiscussionsByBlog(query, (err, result) => {
              if (err) reject(err);
              else resolve(result);
            });
          });
        } else {
          return await this.hiveClient.database.getDiscussions('blog', query);
        }
      } catch (error) {
        attempts++;
        console.error(`Attempt ${attempts} failed for getting posts:`, error);
        if (attempts === maxAttempts) throw error;
        await this.switchNode(platform);
      }
    }
  }

  /**
   * Ottiene il dominio corretto per una piattaforma
   * @param {string} platform - 'steem' o 'hive'
   * @returns {string} - URL del dominio
   */
  getDomainForPlatform(platform) {
    return platform === 'steem' ? 'https://steemit.com' : 'https://peakd.com';
  }
}

// Esporta un'istanza singleton
const blockchainService = new BlockchainService();
export default blockchainService;