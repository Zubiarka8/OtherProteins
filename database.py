"""
Database schema and initialization for OtherProteins e-commerce platform.
All table and column names are in Basque as per requirements.
"""

import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

DATABASE_PATH = Path('otherproteins.db')

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with all required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create erabiltzaileak (users) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS erabiltzaileak (
            erabiltzaile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            helbide_elektronikoa TEXT UNIQUE NOT NULL,
            pasahitza TEXT NOT NULL,
            izena TEXT NOT NULL,
            abizenak TEXT NOT NULL,
            tfnoa TEXT,
            sormen_data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create kategoriak (categories) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kategoriak (
            kategoria_id INTEGER PRIMARY KEY AUTOINCREMENT,
            izena TEXT NOT NULL UNIQUE,
            deskribapena TEXT
        )
    ''')
    
    # Create produktuak (products) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produktuak (
            produktu_id INTEGER PRIMARY KEY AUTOINCREMENT,
            izena TEXT NOT NULL,
            deskribapena TEXT,
            prezioa REAL NOT NULL,
            irudi_urla TEXT,
            kategoria_id INTEGER,
            stocka INTEGER DEFAULT 0,
            FOREIGN KEY (kategoria_id) REFERENCES kategoriak(kategoria_id)
        )
    ''')
    
    # Add stocka column if it doesn't exist (migration for existing databases)
    try:
        cursor.execute('ALTER TABLE produktuak ADD COLUMN stocka INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create saski_elementuak (cart items) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saski_elementuak (
            erabiltzaile_id INTEGER NOT NULL,
            produktu_id INTEGER NOT NULL,
            kantitatea INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (erabiltzaile_id, produktu_id),
            FOREIGN KEY (erabiltzaile_id) REFERENCES erabiltzaileak(erabiltzaile_id),
            FOREIGN KEY (produktu_id) REFERENCES produktuak(produktu_id)
        )
    ''')
    
    # Create eskaerak (orders) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eskaerak (
            eskaera_id INTEGER PRIMARY KEY AUTOINCREMENT,
            erabiltzaile_id INTEGER NOT NULL,
            sormen_data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            egoera TEXT NOT NULL DEFAULT 'pendiente',
            FOREIGN KEY (erabiltzaile_id) REFERENCES erabiltzaileak(erabiltzaile_id)
        )
    ''')
    
    # Create eskaera_elementuak (order items) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eskaera_elementuak (
            eskaera_elementu_id INTEGER PRIMARY KEY AUTOINCREMENT,
            eskaera_id INTEGER NOT NULL,
            produktu_id INTEGER NOT NULL,
            kantitatea INTEGER NOT NULL,
            prezioa REAL NOT NULL,
            FOREIGN KEY (eskaera_id) REFERENCES eskaerak(eskaera_id),
            FOREIGN KEY (produktu_id) REFERENCES produktuak(produktu_id)
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_erabiltzaile_email ON erabiltzaileak(helbide_elektronikoa)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_produktu_kategoria ON produktuak(kategoria_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_saski_erabiltzaile ON saski_elementuak(erabiltzaile_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_eskaera_erabiltzaile ON eskaerak(erabiltzaile_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_eskaera_elementu_eskaera ON eskaera_elementuak(eskaera_id)')
    
    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {DATABASE_PATH}")

def hash_password(password):
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def seed_sample_data():
    """Add sample data to the database for testing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert sample categories
    kategoriak = [
        ('Proteina', 'Proteina suplementuak'),
        ('Kreatina', 'Kreatina produktuak'),
        ('Pre-entrenamendua', 'Pre-entrenamendu suplementuak'),
        ('Barritak', 'Barritak eta snackak'),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO kategoriak (izena, deskribapena)
        VALUES (?, ?)
    ''', kategoriak)
    
    # Insert sample products
    produktuak = [
        ('Whey Protein Isolate', 'Kalitate handiko proteina isolatua', 55.00, '/images/whey.jpg', 1, 15),
        ('Caseina Nocturna', 'Proteina motel askatzea gauean', 45.50, '/images/caseina.jpg', 1, 10),
        ('Barritas Energéticas', 'Barritak entrenamenduarentzat', 25.00, '/images/barritas.jpg', 4, 30),
        ('Creatina Monohidratada', 'Kreatina purua', 22.99, '/images/creatina.jpg', 2, 25),
        ('Pre-entreno Intenso', 'Pre-entrenamendu formula indartsua', 38.75, '/images/preentreno.jpg', 3, 0),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO produktuak (izena, deskribapena, prezioa, irudi_urla, kategoria_id, stocka)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', produktuak)
    
    # Update stock for existing products if they don't have it
    cursor.execute('UPDATE produktuak SET stocka = 15 WHERE izena = "Whey Protein Isolate" AND stocka IS NULL')
    cursor.execute('UPDATE produktuak SET stocka = 10 WHERE izena = "Caseina Nocturna" AND stocka IS NULL')
    cursor.execute('UPDATE produktuak SET stocka = 30 WHERE izena = "Barritas Energéticas" AND stocka IS NULL')
    cursor.execute('UPDATE produktuak SET stocka = 25 WHERE izena = "Creatina Monohidratada" AND stocka IS NULL')
    cursor.execute('UPDATE produktuak SET stocka = 0 WHERE izena = "Pre-entreno Intenso" AND stocka IS NULL')
    
    # Insert sample user (password: 'admin123')
    hashed_password = hash_password('admin123')
    cursor.execute('''
        INSERT OR IGNORE INTO erabiltzaileak 
        (helbide_elektronikoa, pasahitza, izena, abizenak, tfnoa)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin@otherproteins.com', hashed_password, 'Admin', 'Erabiltzaile', '+34 600 000 000'))
    
    conn.commit()
    conn.close()
    print("Sample data seeded successfully")

if __name__ == '__main__':
    init_db()
    seed_sample_data()
    print("\nDatabase setup complete!")

