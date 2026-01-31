"""
Database utility functions for user operations, cart management, and orders.
All function names and internal logic in English, but database columns in Basque.
"""

import sqlite3
from database import get_db_connection, hash_password
from datetime import datetime

# User operations
def create_user(email, password, first_name, last_name, phone=None):
    """Create a new user in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        hashed_pwd = hash_password(password)
        cursor.execute('''
            INSERT INTO erabiltzaileak 
            (helbide_elektronikoa, pasahitza, izena, abizenak, tfnoa)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, hashed_pwd, first_name, last_name, phone))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None  # Email already exists
    finally:
        conn.close()

def get_user_by_email(email):
    """Get user by email address."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM erabiltzaileak WHERE helbide_elektronikoa = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def verify_password(email, password):
    """Verify user password."""
    user = get_user_by_email(email)
    if user and user['pasahitza'] == hash_password(password):
        return user
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
    conn = get_db_connection()
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
    
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return products

def get_product_by_id(product_id):
    """Get product by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, k.izena as kategoria_izena
        FROM produktuak p
        LEFT JOIN kategoriak k ON p.kategoria_id = k.kategoria_id
        WHERE p.produktu_id = ?
    ''', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return dict(product) if product else None

def reduce_product_stock(product_id, quantity):
    """Reduce product stock by quantity. Returns True if successful, False if insufficient stock."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check current stock
        cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
        result = cursor.fetchone()
        
        if not result:
            return False
        
        current_stock = result['stocka'] if result['stocka'] is not None else 0
        
        if current_stock < quantity:
            return False
        
        # Update stock
        new_stock = current_stock - quantity
        cursor.execute('''
            UPDATE produktuak
            SET stocka = ?
            WHERE produktu_id = ?
        ''', (new_stock, product_id))
        
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.*, p.izena, p.prezioa, p.irudi_urla, p.stocka
        FROM saski_elementuak s
        JOIN produktuak p ON s.produktu_id = p.produktu_id
        WHERE s.erabiltzaile_id = ?
    ''', (user_id,))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def add_to_cart(user_id, product_id, quantity=1):
    """Add or update item in cart. Returns (success: bool, message: str)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get product stock
        cursor.execute('SELECT stocka FROM produktuak WHERE produktu_id = ?', (product_id,))
        product = cursor.fetchone()
        if not product:
            return False, 'Produktua ez da aurkitu.'
        
        available_stock = product['stocka'] if product['stocka'] is not None else 0
        
        # Check if item already exists in cart
        cursor.execute('''
            SELECT kantitatea FROM saski_elementuak
            WHERE erabiltzaile_id = ? AND produktu_id = ?
        ''', (user_id, product_id))
        existing = cursor.fetchone()
        
        if existing:
            # Update quantity - check stock
            current_cart_quantity = existing['kantitatea']
            new_quantity = current_cart_quantity + quantity
            
            if new_quantity > available_stock:
                return False, f'Stock nahikorik ez dago. Gehienez {available_stock} unitate erabilgarri daude.'
            
            cursor.execute('''
                UPDATE saski_elementuak
                SET kantitatea = ?
                WHERE erabiltzaile_id = ? AND produktu_id = ?
            ''', (new_quantity, user_id, product_id))
        else:
            # Insert new item - check stock
            if quantity > available_stock:
                return False, f'Stock nahikorik ez dago. Gehienez {available_stock} unitate erabilgarri daude.'
            
            cursor.execute('''
                INSERT INTO saski_elementuak (erabiltzaile_id, produktu_id, kantitatea)
                VALUES (?, ?, ?)
            ''', (user_id, product_id, quantity))
        
        conn.commit()
        return True, 'Produktua saskira gehitu da.'
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def update_cart_item(user_id, product_id, quantity):
    """Update cart item quantity. Returns (success: bool, message: str)."""
    conn = None
    try:
        conn = get_db_connection()
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
            return False, 'Produktua ez da aurkitu.'
        
        available_stock = product['stocka'] if product['stocka'] is not None else 0
        
        # Check if quantity exceeds stock
        if quantity > available_stock:
            return False, f'Stock nahikorik ez dago. Gehienez {available_stock} unitate erabilgarri daude.'
        
        cursor.execute('''
            UPDATE saski_elementuak
            SET kantitatea = ?
            WHERE erabiltzaile_id = ? AND produktu_id = ?
        ''', (quantity, user_id, product_id))
        
        conn.commit()
        return True, 'Saskia eguneratu da.'
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def remove_from_cart(user_id, product_id):
    """Remove item from cart."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM saski_elementuak
            WHERE erabiltzaile_id = ? AND produktu_id = ?
        ''', (user_id, product_id))
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def clear_cart(user_id):
    """Clear all items from user's cart."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM saski_elementuak WHERE erabiltzaile_id = ?', (user_id,))
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# Order operations
def create_order(user_id, status='pendiente', entrega_mota='tienda', helbidea=None, entrega_kostua=0.0):
    """Create a new order from user's cart."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get cart items (using separate connection to avoid locking)
        cart_items = get_cart_items(user_id)
        if not cart_items:
            return None
        
        # Create order header
        cursor.execute('''
            INSERT INTO eskaerak (erabiltzaile_id, egoera, entrega_mota, helbidea, entrega_kostua)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, status, entrega_mota, helbidea, entrega_kostua))
        order_id = cursor.lastrowid
        
        # Create order items from cart
        for item in cart_items:
            cursor.execute('''
                INSERT INTO eskaera_elementuak (eskaera_id, produktu_id, kantitatea, prezioa)
                VALUES (?, ?, ?, ?)
            ''', (order_id, item['produktu_id'], item['kantitatea'], item['prezioa']))
        
        # Clear cart after creating order (within same transaction)
        cursor.execute('DELETE FROM saski_elementuak WHERE erabiltzaile_id = ?', (user_id,))
        
        conn.commit()
        return order_id
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def get_user_orders(user_id):
    """Get all orders for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM eskaerak
        WHERE erabiltzaile_id = ?
        ORDER BY sormen_data DESC
    ''', (user_id,))
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return orders

def get_order_details(order_id):
    """Get order details with items."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get order header
        cursor.execute('SELECT * FROM eskaerak WHERE eskaera_id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            return None
        
        # Get order items
        cursor.execute('''
            SELECT e.*, p.izena, p.irudi_urla
            FROM eskaera_elementuak e
            JOIN produktuak p ON e.produktu_id = p.produktu_id
            WHERE e.eskaera_id = ?
            ORDER BY e.eskaera_elementu_id
        ''', (order_id,))
        items = [dict(row) for row in cursor.fetchall()]
        
        result = dict(order)
        result['elementuak'] = items
        return result
    except Exception as e:
        raise
    finally:
        if conn:
            conn.close()

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

