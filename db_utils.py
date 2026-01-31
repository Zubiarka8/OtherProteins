"""
Database utility functions for user operations, cart management, and orders.
All function names and internal logic in English, but database columns in Basque.
"""

import sqlite3
import logging
import traceback
from database import get_db_connection, hash_password
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# User operations
def create_user(email, password, first_name, last_name, phone=None):
    """Create a new user in the database."""
    # Validate inputs
    if not email or not isinstance(email, str) or len(email.strip()) == 0:
        logger.error("create_user: Invalid email")
        return None
    
    if not password or not isinstance(password, str) or len(password) == 0:
        logger.error("create_user: Invalid password")
        return None
    
    if not first_name or not isinstance(first_name, str) or len(first_name.strip()) == 0:
        logger.error("create_user: Invalid first_name")
        return None
    
    if not last_name or not isinstance(last_name, str) or len(last_name.strip()) == 0:
        logger.error("create_user: Invalid last_name")
        return None
    
    # Sanitize inputs
    email = email.strip()[:255]
    first_name = first_name.strip()[:100]
    last_name = last_name.strip()[:100]
    phone = phone.strip()[:50] if phone and isinstance(phone, str) else None
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("create_user: Failed to get database connection")
            return None
        
        cursor = conn.cursor()
        hashed_pwd = hash_password(password)
        
        cursor.execute('''
            INSERT INTO erabiltzaileak 
            (helbide_elektronikoa, pasahitza, izena, abizenak, tfnoa)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, hashed_pwd, first_name, last_name, phone))
        conn.commit()
        user_id = cursor.lastrowid
        
        if not user_id or user_id <= 0:
            logger.error("create_user: Failed to get user_id after insert")
            return None
        
        return user_id
    except sqlite3.IntegrityError as e:
        logger.warning(f"create_user: Email already exists - {email}")
        return None  # Email already exists
    except sqlite3.Error as e:
        logger.error(f"create_user: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        logger.error(f"create_user: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"create_user: Error closing connection - {str(e)}")

def get_user_by_email(email):
    """Get user by email address."""
    # Validate input
    if not email or not isinstance(email, str) or len(email.strip()) == 0:
        logger.warning("get_user_by_email: Invalid email")
        return None
    
    email = email.strip()[:255]
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("get_user_by_email: Failed to get database connection")
            return None
        
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM erabiltzaileak WHERE helbide_elektronikoa = ?', (email,))
        user = cursor.fetchone()
        
        if user:
            return dict(user)
        return None
    except sqlite3.Error as e:
        logger.error(f"get_user_by_email: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"get_user_by_email: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"get_user_by_email: Error closing connection - {str(e)}")

def verify_password(email, password):
    """Verify user password."""
    # Validate inputs
    if not email or not isinstance(email, str) or len(email.strip()) == 0:
        logger.warning("verify_password: Invalid email")
        return None
    
    if not password or not isinstance(password, str) or len(password) == 0:
        logger.warning("verify_password: Invalid password")
        return None
    
    try:
        user = get_user_by_email(email)
        if not user or not isinstance(user, dict):
            return None
        
        stored_password = user.get('pasahitza')
        if not stored_password:
            logger.warning(f"verify_password: No password stored for user {email}")
            return None
        
        hashed_input = hash_password(password)
        if stored_password == hashed_input:
            return user
        return None
    except Exception as e:
        logger.error(f"verify_password: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return None

# Category operations
def get_all_categories():
    """Get all product categories."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM kategoriak ORDER BY izena')
    categories = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return categories

def get_category_by_id(category_id):
    """Get category by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM kategoriak WHERE kategoria_id = ?', (category_id,))
    category = cursor.fetchone()
    conn.close()
    return dict(category) if category else None

# Product operations
def get_all_products(category_id=None):
    """Get all products, optionally filtered by category."""
    # Validate category_id if provided
    if category_id is not None:
        if not isinstance(category_id, int) or category_id <= 0:
            logger.warning(f"get_all_products: Invalid category_id - {category_id}")
            category_id = None
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("get_all_products: Failed to get database connection")
            return []
        
        cursor = conn.cursor()
        
        if category_id:
            cursor.execute('''
                SELECT p.*, k.izena as kategoria_izena
                FROM produktuak p
                LEFT JOIN kategoriak k ON p.kategoria_id = k.kategoria_id
                WHERE p.kategoria_id = ?
                ORDER BY p.izena
            ''', (category_id,))
        else:
            cursor.execute('''
                SELECT p.*, k.izena as kategoria_izena
                FROM produktuak p
                LEFT JOIN kategoriak k ON p.kategoria_id = k.kategoria_id
                ORDER BY p.izena
            ''')
        
        rows = cursor.fetchall()
        products = []
        for row in rows:
            try:
                products.append(dict(row))
            except Exception as e:
                logger.warning(f"get_all_products: Error converting row to dict - {str(e)}")
                continue
        
        return products
    except sqlite3.Error as e:
        logger.error(f"get_all_products: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        return []
    except Exception as e:
        logger.error(f"get_all_products: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"get_all_products: Error closing connection - {str(e)}")

def get_product_by_id(product_id):
    """Get product by ID."""
    # Validate input
    if not product_id or not isinstance(product_id, int) or product_id <= 0:
        logger.warning(f"get_product_by_id: Invalid product_id - {product_id}")
        return None
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("get_product_by_id: Failed to get database connection")
            return None
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, k.izena as kategoria_izena
            FROM produktuak p
            LEFT JOIN kategoriak k ON p.kategoria_id = k.kategoria_id
            WHERE p.produktu_id = ?
        ''', (product_id,))
        product = cursor.fetchone()
        
        if product:
            return dict(product)
        return None
    except sqlite3.Error as e:
        logger.error(f"get_product_by_id: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"get_product_by_id: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"get_product_by_id: Error closing connection - {str(e)}")

def reduce_product_stock(product_id, quantity):
    """Reduce product stock by quantity. Returns True if successful, False if insufficient stock."""
    # Validate inputs
    if not product_id or not isinstance(product_id, int) or product_id <= 0:
        logger.warning(f"reduce_product_stock: Invalid product_id - {product_id}")
        return False
    
    if not quantity or not isinstance(quantity, (int, float)) or quantity <= 0:
        logger.warning(f"reduce_product_stock: Invalid quantity - {quantity}")
        return False
    
    quantity = int(quantity)
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("reduce_product_stock: Failed to get database connection")
            return False
        
        cursor = conn.cursor()
        
        # Check current stock
        cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"reduce_product_stock: Product {product_id} not found")
            return False
        
        current_stock = result['stocka'] if result['stocka'] is not None else 0
        if not isinstance(current_stock, (int, float)):
            current_stock = 0
        current_stock = int(current_stock)
        
        if current_stock < quantity:
            logger.warning(f"reduce_product_stock: Insufficient stock for product {product_id} (current: {current_stock}, requested: {quantity})")
            return False
        
        # Update stock
        new_stock = current_stock - quantity
        if new_stock < 0:
            logger.error(f"reduce_product_stock: Calculated negative stock for product {product_id}")
            return False
        
        cursor.execute('''
            UPDATE produktuak
            SET stocka = ?
            WHERE produktu_id = ?
        ''', (new_stock, product_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"reduce_product_stock: No rows updated for product {product_id}")
            conn.rollback()
            return False
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"reduce_product_stock: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"reduce_product_stock: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"reduce_product_stock: Error closing connection - {str(e)}")

def restore_product_stock(product_id, quantity):
    """Restore (increase) product stock by quantity. Returns True if successful, False otherwise."""
    # Validate inputs
    if not product_id or not isinstance(product_id, int) or product_id <= 0:
        logger.warning(f"restore_product_stock: Invalid product_id - {product_id}")
        return False
    
    if not quantity or not isinstance(quantity, (int, float)) or quantity <= 0:
        logger.warning(f"restore_product_stock: Invalid quantity - {quantity}")
        return False
    
    quantity = int(quantity)
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("restore_product_stock: Failed to get database connection")
            return False
        
        cursor = conn.cursor()
        
        # Check if product exists
        cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"restore_product_stock: Product {product_id} not found")
            return False
        
        current_stock = result['stocka'] if result['stocka'] is not None else 0
        if not isinstance(current_stock, (int, float)):
            current_stock = 0
        current_stock = int(current_stock)
        
        # Update stock (increase)
        new_stock = current_stock + quantity
        
        cursor.execute('''
            UPDATE produktuak
            SET stocka = ?
            WHERE produktu_id = ?
        ''', (new_stock, product_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"restore_product_stock: No rows updated for product {product_id}")
            conn.rollback()
            return False
        
        conn.commit()
        logger.info(f"restore_product_stock: Restored {quantity} units for product {product_id} (new stock: {new_stock})")
        return True
    except sqlite3.Error as e:
        logger.error(f"restore_product_stock: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"restore_product_stock: Unexpected error - {type(e).__name__}: {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"restore_product_stock: Error closing connection - {str(e)}")

def get_product_stock(product_id):
    """Get current stock for a product."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
    result = cursor.fetchone()
    conn.close()
    return result['stocka'] if result and result['stocka'] is not None else 0

# Cart operations
def get_cart_items(user_id):
    """Get all items in user's cart with stock information."""
    # Validate input
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"get_cart_items: Invalid user_id - {user_id}")
        return []
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("get_cart_items: Failed to get database connection")
            return []
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.*, p.izena, p.prezioa, p.irudi_urla, p.stocka
            FROM saski_elementuak s
            JOIN produktuak p ON s.produktu_id = p.produktu_id
            WHERE s.erabiltzaile_id = ?
        ''', (user_id,))
        
        rows = cursor.fetchall()
        items = []
        for row in rows:
            try:
                items.append(dict(row))
            except Exception as e:
                logger.warning(f"get_cart_items: Error converting row to dict - {str(e)}")
                continue
        
        return items
    except sqlite3.Error as e:
        logger.error(f"get_cart_items: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        return []
    except Exception as e:
        logger.error(f"get_cart_items: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"get_cart_items: Error closing connection - {str(e)}")

def add_to_cart(user_id, product_id, quantity=1):
    """Add or update item in cart. Returns (success: bool, message: str)."""
    # Validate inputs
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"add_to_cart: Invalid user_id - {user_id}")
        return False, 'Erabiltzaile ID baliogabea.'
    
    if not product_id or not isinstance(product_id, int) or product_id <= 0:
        logger.warning(f"add_to_cart: Invalid product_id - {product_id}")
        return False, 'Produktu ID baliogabea.'
    
    if not quantity or not isinstance(quantity, (int, float)) or quantity <= 0:
        logger.warning(f"add_to_cart: Invalid quantity - {quantity}")
        return False, 'Kantitate baliogabea.'
    
    quantity = int(quantity)
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("add_to_cart: Failed to get database connection")
            return False, 'Errorea gertatu da datu-basearekin konektatzean.'
        
        cursor = conn.cursor()
        
        # Get product stock
        cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
        product = cursor.fetchone()
        if not product:
            logger.warning(f"add_to_cart: Product {product_id} not found")
            return False, 'Produktua ez da aurkitu.'
        
        available_stock = product['stocka'] if product['stocka'] is not None else 0
        if not isinstance(available_stock, (int, float)):
            available_stock = 0
        available_stock = int(available_stock)
        
        # Check if item already exists in cart
        cursor.execute('''
            SELECT kantitatea FROM saski_elementuak
            WHERE erabiltzaile_id = ? AND produktu_id = ?
        ''', (user_id, product_id))
        existing = cursor.fetchone()
        
        if existing:
            # Update quantity - check stock
            current_cart_quantity = existing['kantitatea']
            if not isinstance(current_cart_quantity, (int, float)):
                current_cart_quantity = 0
            current_cart_quantity = int(current_cart_quantity)
            new_quantity = current_cart_quantity + quantity
            
            if new_quantity > available_stock:
                return False, f'Stock nahikorik ez dago. Gehienez {available_stock} unitate erabilgarri daude.'
            
            cursor.execute('''
                UPDATE saski_elementuak
                SET kantitatea = ?
                WHERE erabiltzaile_id = ? AND produktu_id = ?
            ''', (new_quantity, user_id, product_id))
            
            if cursor.rowcount == 0:
                logger.warning(f"add_to_cart: No rows updated for user {user_id}, product {product_id}")
                conn.rollback()
                return False, 'Errorea gertatu da saskia eguneratzean.'
        else:
            # Insert new item - check stock
            if quantity > available_stock:
                return False, f'Stock nahikorik ez dago. Gehienez {available_stock} unitate erabilgarri daude.'
            
            # Verify user exists before inserting (to avoid foreign key constraint errors)
            cursor.execute('SELECT erabiltzaile_id FROM erabiltzaileak WHERE erabiltzaile_id = ?', (user_id,))
            user_exists = cursor.fetchone()
            if not user_exists:
                logger.warning(f"add_to_cart: User {user_id} does not exist")
                return False, 'Erabiltzailea ez da aurkitu. Mesedez, saioa hasi.'
            
            try:
                cursor.execute('''
                    INSERT INTO saski_elementuak (erabiltzaile_id, produktu_id, kantitatea)
                    VALUES (?, ?, ?)
                ''', (user_id, product_id, quantity))
            except sqlite3.IntegrityError as e:
                error_msg = str(e).lower()
                if 'foreign key' in error_msg:
                    logger.error(f"add_to_cart: Foreign key constraint failed - user {user_id} or product {product_id} does not exist")
                    return False, 'Erabiltzailea edo produktua ez da aurkitu. Mesedez, saioa hasi.'
                elif 'unique' in error_msg or 'constraint' in error_msg:
                    logger.warning(f"add_to_cart: Constraint violation - {str(e)}")
                    # Item might have been added by another request, try to update instead
                    cursor.execute('''
                        UPDATE saski_elementuak
                        SET kantitatea = kantitatea + ?
                        WHERE erabiltzaile_id = ? AND produktu_id = ?
                    ''', (quantity, user_id, product_id))
                    if cursor.rowcount == 0:
                        conn.rollback()
                        return False, 'Errorea gertatu da produktua saskira gehitzean.'
                else:
                    raise
        
        try:
            conn.commit()
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "locked" in error_msg:
                logger.error(f"add_to_cart: Database locked during commit")
                if conn:
                    conn.rollback()
                return False, 'Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.'
            else:
                raise
        
        return True, 'Produktua saskira gehitu da.'
    except sqlite3.IntegrityError as e:
        error_msg = str(e).lower()
        logger.error(f"add_to_cart: Integrity error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        if 'foreign key' in error_msg:
            return False, 'Erabiltzailea edo produktua ez da aurkitu. Mesedez, saioa hasi.'
        return False, 'Errorea gertatu da datu-basean (integritate arazoa).'
    except sqlite3.OperationalError as e:
        error_msg = str(e).lower()
        logger.error(f"add_to_cart: Database operational error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        if "locked" in error_msg:
            return False, 'Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.'
        elif "no such table" in error_msg:
            return False, 'Datu-basearen taulak ez daude sortuta.'
        else:
            return False, 'Errorea gertatu da datu-basean.'
    except sqlite3.DatabaseError as e:
        logger.error(f"add_to_cart: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False, 'Errorea gertatu da datu-basearekin konektatzean.'
    except sqlite3.Error as e:
        logger.error(f"add_to_cart: General database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False, 'Errorea gertatu da datu-basean.'
    except Exception as e:
        logger.error(f"add_to_cart: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False, 'Errorea gertatu da produktua saskira gehitzean.'
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"add_to_cart: Error closing connection - {str(e)}")

def update_cart_item(user_id, product_id, quantity):
    """Update cart item quantity. Returns (success: bool, message: str)."""
    # Validate inputs
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"update_cart_item: Invalid user_id - {user_id}")
        return False, 'Erabiltzaile ID baliogabea.'
    
    if not product_id or not isinstance(product_id, int) or product_id <= 0:
        logger.warning(f"update_cart_item: Invalid product_id - {product_id}")
        return False, 'Produktu ID baliogabea.'
    
    if not isinstance(quantity, (int, float)):
        logger.warning(f"update_cart_item: Invalid quantity type - {type(quantity)}")
        return False, 'Kantitate baliogabea.'
    
    quantity = int(quantity)
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("update_cart_item: Failed to get database connection")
            return False, 'Errorea gertatu da datu-basearekin konektatzean.'
        
        cursor = conn.cursor()
        
        if quantity <= 0:
            # Remove item if quantity is 0 or less
            cursor.execute('''
                DELETE FROM saski_elementuak
                WHERE erabiltzaile_id = ? AND produktu_id = ?
            ''', (user_id, product_id))
            conn.commit()
            return True, 'Produktua saskitik kendu da.'
        
        # Get product stock
        cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
        product = cursor.fetchone()
        if not product:
            logger.warning(f"update_cart_item: Product {product_id} not found")
            return False, 'Produktua ez da aurkitu.'
        
        available_stock = product['stocka'] if product['stocka'] is not None else 0
        if not isinstance(available_stock, (int, float)):
            available_stock = 0
        available_stock = int(available_stock)
        
        # Check if quantity exceeds stock
        if quantity > available_stock:
            return False, f'Stock nahikorik ez dago. Gehienez {available_stock} unitate erabilgarri daude.'
        
        cursor.execute('''
            UPDATE saski_elementuak
            SET kantitatea = ?
            WHERE erabiltzaile_id = ? AND produktu_id = ?
        ''', (quantity, user_id, product_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"update_cart_item: No rows updated for user {user_id}, product {product_id}")
            conn.rollback()
            return False, 'Produktua ez da aurkitu saskian.'
        
        conn.commit()
        return True, 'Saskia eguneratu da.'
    except sqlite3.Error as e:
        logger.error(f"update_cart_item: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False, 'Errorea gertatu da datu-basean.'
    except Exception as e:
        logger.error(f"update_cart_item: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False, 'Errorea gertatu da saskia eguneratzean.'
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"update_cart_item: Error closing connection - {str(e)}")

def remove_from_cart(user_id, product_id):
    """Remove item from cart."""
    # Validate inputs
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"remove_from_cart: Invalid user_id - {user_id}")
        return False
    
    if not product_id or not isinstance(product_id, int) or product_id <= 0:
        logger.warning(f"remove_from_cart: Invalid product_id - {product_id}")
        return False
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("remove_from_cart: Failed to get database connection")
            return False
        
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM saski_elementuak
            WHERE erabiltzaile_id = ? AND produktu_id = ?
        ''', (user_id, product_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"remove_from_cart: No rows deleted for user {user_id}, product {product_id}")
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"remove_from_cart: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"remove_from_cart: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"remove_from_cart: Error closing connection - {str(e)}")

def clear_cart(user_id):
    """Clear all items from user's cart."""
    # Validate input
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"clear_cart: Invalid user_id - {user_id}")
        return False
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("clear_cart: Failed to get database connection")
            return False
        
        cursor = conn.cursor()
        cursor.execute('DELETE FROM saski_elementuak WHERE erabiltzaile_id = ?', (user_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"clear_cart: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"clear_cart: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"clear_cart: Error closing connection - {str(e)}")

# Order operations
def create_order(user_id, status='pendiente'):
    """Create a new order from user's cart."""
    # Validate inputs
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"create_order: Invalid user_id - {user_id}")
        return None
    
    if not status or not isinstance(status, str):
        status = 'pendiente'
    status = status.strip()[:50]
    
    conn = None
    try:
        # Get cart items (using separate connection to avoid locking)
        cart_items = get_cart_items(user_id)
        if not cart_items or not isinstance(cart_items, list) or len(cart_items) == 0:
            logger.warning(f"create_order: Empty cart for user {user_id}")
            return None
        
        conn = get_db_connection()
        if not conn:
            logger.error("create_order: Failed to get database connection")
            return None
        
        cursor = conn.cursor()
        
        # Create order header
        cursor.execute('''
            INSERT INTO eskaerak (erabiltzaile_id, egoera)
            VALUES (?, ?)
        ''', (user_id, status))
        order_id = cursor.lastrowid
        
        if not order_id or order_id <= 0:
            logger.error(f"create_order: Failed to create order for user {user_id}")
            conn.rollback()
            return None
        
        # Create order items from cart with validation
        for item in cart_items:
            if not isinstance(item, dict):
                logger.warning(f"create_order: Invalid cart item format")
                continue
            
            try:
                product_id = item.get('produktu_id')
                quantity = item.get('kantitatea', 0)
                price = item.get('prezioa', 0.0)
                
                if not product_id or not isinstance(product_id, int) or product_id <= 0:
                    logger.warning(f"create_order: Invalid product_id in cart item")
                    continue
                
                if not isinstance(quantity, (int, float)) or quantity <= 0:
                    logger.warning(f"create_order: Invalid quantity in cart item")
                    continue
                
                if not isinstance(price, (int, float)) or price < 0:
                    logger.warning(f"create_order: Invalid price in cart item")
                    continue
                
                cursor.execute('''
                    INSERT INTO eskaera_elementuak (eskaera_id, produktu_id, kantitatea, prezioa)
                    VALUES (?, ?, ?, ?)
                ''', (order_id, product_id, int(quantity), float(price)))
            except sqlite3.IntegrityError as e:
                error_msg = str(e).lower()
                if "foreign key" in error_msg:
                    logger.error(f"create_order: Foreign key constraint failed for product {product_id} or order {order_id}")
                else:
                    logger.error(f"create_order: Integrity error inserting order item - {str(e)}")
                logger.error(f"Item data: {item}")
                conn.rollback()
                return None
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                logger.error(f"create_order: Operational error inserting order item - {str(e)}")
                logger.error(f"Item data: {item}")
                if "locked" in error_msg:
                    conn.rollback()
                    return None
                raise
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"create_order: Error processing cart item - {str(e)}")
                logger.error(f"Item data: {item}")
                continue
            except Exception as e:
                logger.error(f"create_order: Unexpected error processing cart item - {type(e).__name__}: {str(e)}")
                logger.error(f"Item data: {item}")
                logger.error(traceback.format_exc())
                continue
        
        # Clear cart after creating order (within same transaction)
        try:
            cursor.execute('DELETE FROM saski_elementuak WHERE erabiltzaile_id = ?', (user_id,))
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            logger.error(f"create_order: Error clearing cart - {str(e)}")
            if "locked" in error_msg:
                conn.rollback()
                return None
            raise
        
        try:
            conn.commit()
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            logger.error(f"create_order: Error committing order - {str(e)}")
            conn.rollback()
            if "locked" in error_msg:
                return None
            raise
        
        return order_id
    except sqlite3.IntegrityError as e:
        error_msg = str(e).lower()
        logger.error(f"create_order: Integrity error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        if "foreign key" in error_msg:
            logger.error(f"create_order: Foreign key constraint failed - user {user_id} or product does not exist")
        return None
    except sqlite3.OperationalError as e:
        error_msg = str(e).lower()
        logger.error(f"create_order: Operational error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        if "locked" in error_msg:
            logger.error(f"create_order: Database locked when creating order")
        elif "no such table" in error_msg:
            logger.error(f"create_order: Required table does not exist")
        return None
    except sqlite3.DatabaseError as e:
        logger.error(f"create_order: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
    except sqlite3.Error as e:
        logger.error(f"create_order: General database error - {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        logger.error(f"create_order: Unexpected error - {type(e).__name__}: {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"create_order: Error closing connection - {str(e)}")

def get_user_orders(user_id):
    """Get all orders for a user."""
    # Validate input
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        logger.warning(f"get_user_orders: Invalid user_id - {user_id}")
        return []
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("get_user_orders: Failed to get database connection")
            return []
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM eskaerak
            WHERE erabiltzaile_id = ?
            ORDER BY sormen_data DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        orders = []
        for row in rows:
            try:
                orders.append(dict(row))
            except Exception as e:
                logger.warning(f"get_user_orders: Error converting row to dict - {str(e)}")
                continue
        
        return orders
    except sqlite3.Error as e:
        logger.error(f"get_user_orders: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        return []
    except Exception as e:
        logger.error(f"get_user_orders: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"get_user_orders: Error closing connection - {str(e)}")

def get_order_details(order_id):
    """Get order details with items."""
    # Validate input
    if not order_id or not isinstance(order_id, int) or order_id <= 0:
        logger.warning(f"get_order_details: Invalid order_id - {order_id}")
        return None
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("get_order_details: Failed to get database connection")
            return None
        
        cursor = conn.cursor()
        
        # Get order header
        cursor.execute('SELECT * FROM eskaerak WHERE eskaera_id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            logger.warning(f"get_order_details: Order {order_id} not found")
            return None
        
        # Get order items
        cursor.execute('''
            SELECT e.*, p.izena, p.irudi_urla
            FROM eskaera_elementuak e
            JOIN produktuak p ON e.produktu_id = p.produktu_id
            WHERE e.eskaera_id = ?
            ORDER BY e.eskaera_elementu_id
        ''', (order_id,))
        
        rows = cursor.fetchall()
        items = []
        for row in rows:
            try:
                items.append(dict(row))
            except Exception as e:
                logger.warning(f"get_order_details: Error converting row to dict - {str(e)}")
                continue
        
        result = dict(order)
        result['elementuak'] = items
        return result
    except sqlite3.Error as e:
        logger.error(f"get_order_details: Database error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"get_order_details: Unexpected error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"get_order_details: Error closing connection - {str(e)}")

def update_order_status(order_id, status):
    """Update order status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE eskaerak
        SET egoera = ?
        WHERE eskaera_id = ?
    ''', (status, order_id))
    conn.commit()
    conn.close()
    return True

