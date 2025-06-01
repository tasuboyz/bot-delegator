# db.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Configure the SQLite database
DATABASE_URI = 'sqlite:///site.db'  # Path to the SQLite database file
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    data = db.Column(db.JSON, nullable=False)  # Ensure the correct data type

    def __repr__(self):
        return f'<User  {self.username}>'

class Delegator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    vesting_shares = db.Column(db.String(20), nullable=False)  # Memorizza l'ultimo importo
    last_operation_id = db.Column(db.String(50), unique=True)  # Previene duplicati
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Delegator  {self.username}>'

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(20), nullable=True)  # steem, hive o null per impostazioni globali
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Settings {self.key}={self.value} ({self.platform or "global"})>'