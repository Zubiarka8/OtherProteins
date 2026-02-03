"""
Database schema and initialization for OtherProteins e-commerce platform.
All table and column names are in Basque as per requirements.

SQLite path: set SQLITE_PATH env var for production (e.g. Render persistent disk).
Example: SQLITE_PATH=/data/otherproteins.db
"""

import os
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

# Configurable for Render: use persistent disk path via SQLITE_PATH
DATABASE_PATH = Path(os.environ.get('SQLITE_PATH', 'otherproteins.db'))

def get_db_connection():
    """Get a database connection with timeout and WAL mode for better concurrency."""
    import time
    import logging
    import os
    max_retries = 5
    retry_delay = 0.2
    logger = logging.getLogger(__name__)
    
    # Ensure database parent directory exists (skip for cwd-relative paths like 'otherproteins.db')
    parent = DATABASE_PATH.parent
    if parent != Path('.'):
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating database directory: {str(e)}")
    
    for attempt in range(max_retries):
        conn = None
        try:
            # Increase timeout and use check_same_thread=False for better concurrency
            conn = sqlite3.connect(
                str(DATABASE_PATH), 
                timeout=60.0,  # Increased timeout to 60 seconds
                check_same_thread=False  # Allow connections from different threads
            )
            conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrency (allows multiple readers)
            # This is safe to call multiple times - it will return the current mode if already set
            try:
                conn.execute('PRAGMA journal_mode=WAL')
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not set WAL mode: {str(e)}")
            
            # Set busy timeout to handle concurrent access better (60 seconds)
            try:
                conn.execute('PRAGMA busy_timeout=60000')
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not set busy timeout: {str(e)}")
            
            # Enable foreign keys
            try:
                conn.execute('PRAGMA foreign_keys=ON')
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not enable foreign keys: {str(e)}")
            
            # Test the connection
            conn.execute('SELECT 1')
            return conn
            
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if conn:
                try:
                    conn.close()
                except:
                    pass
                conn = None
            
            if "database is locked" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Database locked, retrying in {wait_time:.2f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Database locked after {max_retries} attempts")
                    raise sqlite3.OperationalError(f"Database is locked and could not be accessed after {max_retries} attempts")
            elif "unable to open database file" in error_msg:
                logger.error(f"Unable to open database file: {DATABASE_PATH}")
                raise
            elif "no such file or directory" in error_msg:
                logger.error(f"Database directory does not exist: {DATABASE_PATH.parent}")
                raise
            else:
                logger.error(f"Database operational error: {str(e)}")
                raise
        except PermissionError as e:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            logger.error(f"Permission denied accessing database: {DATABASE_PATH}")
            raise
        except sqlite3.DatabaseError as e:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            logger.error(f"Unexpected error connecting to database: {type(e).__name__}: {str(e)}")
            raise

def init_db():
    """Initialize the database with all required tables."""
    import logging
    logger = logging.getLogger(__name__)
    conn = None
    try:
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
        
        # Migration: Add admin column to users table
        try:
            cursor.execute('ALTER TABLE erabiltzaileak ADD COLUMN admin INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create admin user if it doesn't exist
        import logging
        logger = logging.getLogger(__name__)
        try:
            admin_email = 'admin@gmail.com'
            cursor.execute('SELECT erabiltzaile_id FROM erabiltzaileak WHERE helbide_elektronikoa = ?', (admin_email,))
            admin_user = cursor.fetchone()
            if not admin_user:
                admin_password = hash_password('admin123')
                cursor.execute('''
                    INSERT INTO erabiltzaileak (helbide_elektronikoa, pasahitza, izena, abizenak, admin)
                    VALUES (?, ?, ?, ?, ?)
                ''', (admin_email, admin_password, 'Admin', 'Erabiltzailea', 1))
                logger.info("Admin user created successfully")
            else:
                # Update existing admin user to ensure it has admin privileges
                cursor.execute('UPDATE erabiltzaileak SET admin = 1 WHERE helbide_elektronikoa = ?', (admin_email,))
        except sqlite3.OperationalError as e:
            logger.warning(f"Could not create/update admin user: {str(e)}")
        except Exception as e:
            logger.warning(f"Error creating admin user: {str(e)}")

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
            kalea TEXT,
            zenbakia TEXT,
            hiria TEXT,
            probintzia TEXT,
            posta_kodea TEXT,
            FOREIGN KEY (erabiltzaile_id) REFERENCES erabiltzaileak(erabiltzaile_id)
        )
        ''')
        
        # Migration: Add new columns if they don't exist
        new_order_columns = [
        ('entrega_mota', 'TEXT DEFAULT "tienda"'),
        ('helbidea', 'TEXT'),
        ('entrega_kostua', 'REAL DEFAULT 0'),
        ('kalea', 'TEXT'),
        ('zenbakia', 'TEXT'),
        ('hiria', 'TEXT'),
        ('probintzia', 'TEXT'),
        ('posta_kodea', 'TEXT')
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
        
        try:
            conn.commit()
            logger.info("Database initialized successfully at %s", DATABASE_PATH)
        except Exception as e:
            logger.error(f"Error committing database initialization: {str(e)}")
            conn.rollback()
            raise
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing connection in init_db: {str(e)}")

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
    
    # Product insertion disabled - products should be added manually through admin panel
    
    # Insert sample user (password: 'admin123')
    hashed_password = hash_password('admin123')
    cursor.execute('''
        INSERT OR IGNORE INTO erabiltzaileak 
        (helbide_elektronikoa, pasahitza, izena, abizenak, tfnoa)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin@otherproteins.com', hashed_password, 'Admin', 'Erabiltzaile', '+34 600 000 000'))
    
    conn.commit()
    conn.close()
    import logging
    logging.getLogger(__name__).info("Sample data seeded successfully")

if __name__ == '__main__':
    init_db()
    seed_sample_data()

