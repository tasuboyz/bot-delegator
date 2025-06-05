FROM python:3.10.12

# Aggiorna i pacchetti e installa tzdata
RUN apt-get update && apt-get install -y tzdata

# Configura il fuso orario
ENV TZ=Europe/Rome
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Configura OpenSSL per abilitare algoritmi legacy come RIPEMD160
RUN openssl version -d && \
    OPENSSL_CONF_DIR=$(openssl version -d | cut -d '"' -f 2) && \
    echo "openssl_conf = openssl_init" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "[openssl_init]" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "providers = provider_sect" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "[provider_sect]" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "default = default_sect" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "legacy = legacy_sect" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "[default_sect]" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "activate = 1" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "[legacy_sect]" >> $OPENSSL_CONF_DIR/openssl.cnf && \
    echo "activate = 1" >> $OPENSSL_CONF_DIR/openssl.cnf

# Imposta la variabile d'ambiente per OpenSSL
ENV OPENSSL_CONF=/etc/ssl/openssl.cnf

# Imposta la directory di lavoro
WORKDIR /home/khadas/Edge2/bot-delegator

# Copia il file requirements.txt e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto dei file dell'applicazione
COPY . .

# Espone la porta 8089
EXPOSE 8089

# Comando per eseguire l'applicazione
CMD ["python3", "app.py"]