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
    """Get a database connection with timeout and WAL mode for better concurrency."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency (allows multiple readers)
    conn.execute('PRAGMA journal_mode=WAL')
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
            osagaiak TEXT,
            balio_nutrizionalak TEXT,
            erabilera_modua TEXT,
            FOREIGN KEY (kategoria_id) REFERENCES kategoriak(kategoria_id)
        )
    ''')
    
    # Migration: Add new columns if they don't exist (for existing databases)
    new_columns = [
        ('stocka', 'INTEGER DEFAULT 0'),
        ('osagaiak', 'TEXT'),
        ('balio_nutrizionalak', 'TEXT'),
        ('erabilera_modua', 'TEXT')
    ]
    
    for column_name, column_type in new_columns:
        try:
            cursor.execute(f'ALTER TABLE produktuak ADD COLUMN {column_name} {column_type}')
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
            entrega_mota TEXT DEFAULT 'tienda',
            helbidea TEXT,
            entrega_kostua REAL DEFAULT 0,
            FOREIGN KEY (erabiltzaile_id) REFERENCES erabiltzaileak(erabiltzaile_id)
        )
    ''')
    
    # Migration: Add new columns if they don't exist
    new_order_columns = [
        ('entrega_mota', 'TEXT DEFAULT "tienda"'),
        ('helbidea', 'TEXT'),
        ('entrega_kostua', 'REAL DEFAULT 0')
    ]
    
    for column_name, column_type in new_order_columns:
        try:
            cursor.execute(f'ALTER TABLE eskaerak ADD COLUMN {column_name} {column_type}')
        except sqlite3.OperationalError:
            pass  # Column already exists
    
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
    
    # Insert sample products with complete information
    produktuak = [
        (
            'Whey Protein Isolate',
            'Kalitate handiko proteina isolatua, %90 baino gehiagoko proteina purutasuna duena. Muskuluen berreskuratzea azkartzen du entrenamenduaren ondoren.',
            55.00,
            '/images/whey.jpg',
            1,
            15,
            'Proteina isolatua (Whey Protein Isolate), zapore naturalak (txokolate, banilla, marrubi), lezitina (soja), acesulfame K, sukralosa.',
            'Zerbitzu bakoitzeko (30g): Energia: 110 kcal, Proteina: 25g, Karbohidratoak: 2g (horietatik azukreak: 1g), Gantzak: 0.5g, Gatzak: 0.1g.',
            'Nahastu 30g produktua 250ml ur edo esnearekin. Erabili entrenamenduaren ondoren edo gosariaren ordez. Nahasketa ondo irabiatu eta berehala hartu.'
        ),
        (
            'Caseina Nocturna',
            'Proteina motel askatzea gauean. Muskuluen mantenua bermatzen du lo egiten duzun bitartean.',
            45.50,
            '/images/caseina.jpg',
            1,
            10,
            'Mikrokapsulatutako kaseina, zapore naturalak, lezitina, acesulfame K.',
            'Zerbitzu bakoitzeko (40g): Energia: 140 kcal, Proteina: 30g, Karbohidratoak: 3g, Gantzak: 1g, Gatzak: 0.2g.',
            'Nahastu 40g produktua 300ml ur edo esnearekin. Gauean lo egin baino 30 minutura hartu. Nahasketa ondo irabiatu.'
        ),
        (
            'Barritas Energéticas',
            'Barritak entrenamenduarentzat. Energia azkarra eta proteina ugaria eskaintzen dute.',
            25.00,
            '/images/barritas.jpg',
            4,
            30,
            'Oloa, proteina isolatua, eztia, kakaoa, fruitu lehorrak, intxaurrak, bitamina eta mineralak.',
            'Barrita bakoitzeko (60g): Energia: 250 kcal, Proteina: 20g, Karbohidratoak: 25g, Gantzak: 8g, Zuntz dietetikoa: 5g.',
            'Erabili entrenamendu baino 30-60 minutura edo entrenamenduaren ondoren. Barrita zabaldu eta jan.'
        ),
        (
            'Creatina Monohidratada',
            'Kreatina purua, muskuluen indarra eta errendimendua hobetzen duena.',
            22.99,
            '/images/creatina.jpg',
            2,
            25,
            'Kreatina monohidratada %100 purua, ez du gehigarririk.',
            'Zerbitzu bakoitzeko (5g): Kreatina: 5g, Kaloriak: 0 kcal, Gantzak: 0g, Karbohidratoak: 0g.',
            'Erabili eguneko 3-5g entrenamendu baino 30 minutura edo entrenamenduaren ondoren. Nahastu 200-300ml ur edo zukuarekin. Nahasketa ondo irabiatu eta berehala hartu.'
        ),
        (
            'Pre-entreno Intenso',
            'Pre-entrenamendu formula indartsua. Energia, fokua eta errendimendua hobetzen ditu.',
            38.75,
            '/images/preentreno.jpg',
            3,
            0,
            'Kafeina anhidroa, beta-alanina, L-arginina, taurina, bitamina B taldea, mineralak, zapore naturalak.',
            'Zerbitzu bakoitzeko (15g): Energia: 50 kcal, Kafeina: 200mg, Beta-alanina: 2g, L-arginina: 1g, Taurina: 1g, Bitamina B6: 2mg.',
            'Nahastu 15g produktua 300-400ml ur hotzarekin. Erabili entrenamendu baino 20-30 minutura. Ez hartu eguneko 17:00etatik aurrera lo egiteko arazoak ekiditeko.'
        ),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO produktuak 
        (izena, deskribapena, prezioa, irudi_urla, kategoria_id, stocka, osagaiak, balio_nutrizionalak, erabilera_modua)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', produktuak)
    
    # Update existing products with new fields if they don't have them
    updates = [
        ('Whey Protein Isolate', 15, 'Proteina isolatua (Whey Protein Isolate), zapore naturalak (txokolate, banilla, marrubi), lezitina (soja), acesulfame K, sukralosa.', 'Zerbitzu bakoitzeko (30g): Energia: 110 kcal, Proteina: 25g, Karbohidratoak: 2g (horietatik azukreak: 1g), Gantzak: 0.5g, Gatzak: 0.1g.', 'Nahastu 30g produktua 250ml ur edo esnearekin. Erabili entrenamenduaren ondoren edo gosariaren ordez. Nahasketa ondo irabiatu eta berehala hartu.'),
        ('Caseina Nocturna', 10, 'Mikrokapsulatutako kaseina, zapore naturalak, lezitina, acesulfame K.', 'Zerbitzu bakoitzeko (40g): Energia: 140 kcal, Proteina: 30g, Karbohidratoak: 3g, Gantzak: 1g, Gatzak: 0.2g.', 'Nahastu 40g produktua 300ml ur edo esnearekin. Gauean lo egin baino 30 minutura hartu. Nahasketa ondo irabiatu.'),
        ('Barritas Energéticas', 30, 'Oloa, proteina isolatua, eztia, kakaoa, fruitu lehorrak, intxaurrak, bitamina eta mineralak.', 'Barrita bakoitzeko (60g): Energia: 250 kcal, Proteina: 20g, Karbohidratoak: 25g, Gantzak: 8g, Zuntz dietetikoa: 5g.', 'Erabili entrenamendu baino 30-60 minutura edo entrenamenduaren ondoren. Barrita zabaldu eta jan.'),
        ('Creatina Monohidratada', 25, 'Kreatina monohidratada %100 purua, ez du gehigarririk.', 'Zerbitzu bakoitzeko (5g): Kreatina: 5g, Kaloriak: 0 kcal, Gantzak: 0g, Karbohidratoak: 0g.', 'Erabili eguneko 3-5g entrenamendu baino 30 minutura edo entrenamenduaren ondoren. Nahastu 200-300ml ur edo zukuarekin. Nahasketa ondo irabiatu eta berehala hartu.'),
        ('Pre-entreno Intenso', 0, 'Kafeina anhidroa, beta-alanina, L-arginina, taurina, bitamina B taldea, mineralak, zapore naturalak.', 'Zerbitzu bakoitzeko (15g): Energia: 50 kcal, Kafeina: 200mg, Beta-alanina: 2g, L-arginina: 1g, Taurina: 1g, Bitamina B6: 2mg.', 'Nahastu 15g produktua 300-400ml ur hotzarekin. Erabili entrenamendu baino 20-30 minutura. Ez hartu eguneko 17:00etatik aurrera lo egiteko arazoak ekiditeko.')
    ]
    
    for izena, stocka, osagaiak, balio_nutrizionalak, erabilera_modua in updates:
        cursor.execute('''
            UPDATE produktuak 
            SET stocka = COALESCE(stocka, ?),
                osagaiak = COALESCE(osagaiak, ?),
                balio_nutrizionalak = COALESCE(balio_nutrizionalak, ?),
                erabilera_modua = COALESCE(erabilera_modua, ?)
            WHERE izena = ?
        ''', (stocka, osagaiak, balio_nutrizionalak, erabilera_modua, izena))
    
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

