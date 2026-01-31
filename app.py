
from flask import Flask, render_template, request, flash, redirect, url_for, session
from datetime import datetime, timedelta
import logging
import traceback
import sqlite3
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound
from products import products_bp
from database import init_db
from db_utils import (
    get_all_products, 
    get_cart_items, 
    add_to_cart as add_to_cart_db, 
    create_order, 
    reduce_product_stock,
    restore_product_stock,
    get_user_by_email,
    get_product_by_id,
    verify_password,
    create_user,
    get_user_orders,
    get_order_details,
    update_cart_item,
    remove_from_cart,
    clear_cart,
    update_order_status,
    is_admin,
    update_product_stock
)

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('error.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize database on import
try:
    init_db()
except sqlite3.OperationalError as e:
    error_msg = str(e).lower()
    if "locked" in error_msg:
        logger.error("Database initialization failed: Database is locked. Another process may be using it.")
    elif "no such table" in error_msg or "no such column" in error_msg:
        logger.error(f"Database initialization failed: Schema error - {str(e)}")
    else:
        logger.error(f"Database initialization failed: Operational error - {str(e)}")
    logger.error(traceback.format_exc())
    raise
except sqlite3.DatabaseError as e:
    logger.error(f"Database initialization failed: Database error - {str(e)}")
    logger.error(traceback.format_exc())
    raise
except PermissionError as e:
    logger.error(f"Database initialization failed: Permission denied - {str(e)}")
    logger.error(traceback.format_exc())
    raise
except Exception as e:
    logger.error(f"Database initialization failed: Unexpected error - {type(e).__name__}: {str(e)}")
    logger.error(traceback.format_exc())
    raise

# App factory
def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = 'a_very_secret_key'  # Replace in production
    
    # Template filter to translate order status to Basque
    @app.template_filter('egoera_izena')
    def egoera_izena_filter(egoera):
        """Translate order status to Basque."""
        translations = {
            'prozesatzen': 'Prozesatzen',
            'pagado': 'Ordainduta',
            'bidalita': 'Bidalita',
            'bukatuta': 'Bukatuta',
            'bertan_behera': 'Bertan behera utzita',
            'pendiente': 'Zain'
        }
        return translations.get(egoera.lower() if egoera else '', egoera.title() if egoera else '')
    
    # Context processor for template variables (e.g., current year, cart count)
    @app.context_processor
    def inject_template_vars():
        try:
            cart_count = 0
            if 'user_id' in session:
                user_id = session.get('user_id')
                if user_id and isinstance(user_id, int) and user_id > 0:
                    try:
                        cart_items = get_cart_items(user_id)
                        if cart_items and isinstance(cart_items, list):
                            cart_count = sum(
                                item.get('kantitatea', 0) 
                                for item in cart_items 
                                if isinstance(item, dict) and isinstance(item.get('kantitatea', 0), (int, float))
                            )
                    except sqlite3.OperationalError as e:
                        error_msg = str(e).lower()
                        if "locked" in error_msg:
                            logger.error(f"Context processor: Database locked when getting cart for user {user_id}")
                        elif "no such table" in error_msg:
                            logger.error(f"Context processor: Table saski_elementuak does not exist")
                        else:
                            logger.error(f"Context processor: Database operational error - {str(e)}")
                        logger.error(traceback.format_exc())
                    except sqlite3.DatabaseError as e:
                        logger.error(f"Context processor: Database error getting cart for user {user_id} - {str(e)}")
                        logger.error(traceback.format_exc())
                    except AttributeError as e:
                        logger.error(f"Context processor: Attribute error getting cart - {str(e)}")
                        logger.error(traceback.format_exc())
                    except TypeError as e:
                        logger.error(f"Context processor: Type error getting cart - {str(e)}")
                        logger.error(traceback.format_exc())
                    except Exception as e:
                        logger.error(f"Context processor: Unexpected error getting cart for user {user_id} - {type(e).__name__}: {str(e)}")
                        logger.error(traceback.format_exc())
            return dict(
                current_year=datetime.now().year,
                cart_count=int(cart_count) if cart_count >= 0 else 0
            )
        except KeyError as e:
            logger.error(f"Context processor: Missing key in session - {str(e)}")
            logger.error(traceback.format_exc())
            return dict(current_year=datetime.now().year, cart_count=0)
        except ValueError as e:
            logger.error(f"Context processor: Value error - {str(e)}")
            logger.error(traceback.format_exc())
            return dict(current_year=datetime.now().year, cart_count=0)
        except Exception as e:
            logger.error(f"Context processor: Unexpected error - {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            return dict(current_year=datetime.now().year, cart_count=0)

    # Register Blueprints
    app.register_blueprint(products_bp, url_prefix='/products')

    @app.route('/')
    def index():
        """Render the main showcase page."""
        try:
            # Get products from database
            try:
                products = get_all_products()
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    logger.error("Index route: Database locked when getting products")
                    flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                elif "no such table" in error_msg:
                    logger.error("Index route: Table produktuak does not exist")
                    flash('Datu-basearen taulak ez daude sortuta. Mesedez, kontaktatu administratzailearekin.', 'danger')
                else:
                    logger.error(f"Index route: Database operational error - {str(e)}")
                    flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
                logger.error(traceback.format_exc())
                products = []
            except sqlite3.DatabaseError as e:
                logger.error(f"Index route: Database error getting products - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                products = []
            except Exception as e:
                logger.error(f"Index route: Unexpected error getting products - {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
                products = []
            
            if not products:
                products = []
                logger.warning("No products found in database")
            
            # Format products for template with validation
            formatted_products = []
            for p in products:
                if not isinstance(p, dict):
                    logger.warning(f"Invalid product format: {type(p)}")
                    continue
                
                try:
                    product_id = p.get('produktu_id')
                    if not product_id or not isinstance(product_id, int):
                        logger.warning(f"Invalid product ID: {product_id}")
                        continue
                    
                    formatted_products.append({
                        'id': product_id,
                        'izena': str(p.get('izena', 'Produktu ezezaguna')) if p.get('izena') else 'Produktu ezezaguna',
                        'deskribapena': str(p.get('deskribapena', '')) if p.get('deskribapena') else '',
                        'prezioa': float(p.get('prezioa', 0.0)) if isinstance(p.get('prezioa'), (int, float)) else 0.0,
                        'stocka': int(p.get('stocka', 0)) if isinstance(p.get('stocka'), (int, float)) else 0,
                        'irudi_urla': str(p.get('irudi_urla', 'https://via.placeholder.com/250x200')) if p.get('irudi_urla') else 'https://via.placeholder.com/250x200'
                    })
                except ValueError as e:
                    logger.error(f"Index route: ValueError formatting product - {str(e)}")
                    logger.error(f"Product data: {p}")
                    continue
                except TypeError as e:
                    logger.error(f"Index route: TypeError formatting product - {str(e)}")
                    logger.error(f"Product data: {p}")
                    continue
                except KeyError as e:
                    logger.error(f"Index route: KeyError formatting product - Missing key: {str(e)}")
                    logger.error(f"Product data: {p}")
                    continue
                except Exception as e:
                    logger.error(f"Index route: Unexpected error formatting product - {type(e).__name__}: {str(e)}")
                    logger.error(f"Product data: {p}")
                    continue
            
            # Get cart items if user is logged in
            cart_items = []
            if 'user_id' in session:
                user_id = session.get('user_id')
                if user_id and isinstance(user_id, int) and user_id > 0:
                    try:
                        cart_items = get_cart_items(user_id)
                        if not isinstance(cart_items, list):
                            cart_items = []
                            logger.warning(f"Invalid cart items format for user {user_id}")
                    except sqlite3.OperationalError as e:
                        error_msg = str(e).lower()
                        if "locked" in error_msg:
                            logger.error(f"Index route: Database locked when getting cart for user {user_id}")
                        else:
                            logger.error(f"Index route: Database operational error getting cart - {str(e)}")
                        logger.error(traceback.format_exc())
                        cart_items = []
                    except sqlite3.DatabaseError as e:
                        logger.error(f"Index route: Database error getting cart for user {user_id} - {str(e)}")
                        logger.error(traceback.format_exc())
                        cart_items = []
                    except Exception as e:
                        logger.error(f"Index route: Unexpected error getting cart - {type(e).__name__}: {str(e)}")
                        logger.error(traceback.format_exc())
                        cart_items = []
            
            return render_template('index.html', produktuak=formatted_products, cart_items=cart_items)
        except BadRequest as e:
            logger.error(f"Index route: Bad request - {str(e)}")
            logger.error(traceback.format_exc())
            flash('Eskaera baliogabea.', 'danger')
            return render_template('index.html', produktuak=[], cart_items=[]), 400
        except InternalServerError as e:
            logger.error(f"Index route: Internal server error - {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return render_template('index.html', produktuak=[], cart_items=[]), 500
        except Exception as e:
            logger.error(f"Index route: Unexpected error - {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errorea gertatu da orria kargatzean. Mesedez, saiatu berriro.', 'danger')
            return render_template('index.html', produktuak=[], cart_items=[]), 500

    @app.route('/add_to_cart/<int:produktu_id>')
    def add_to_cart(produktu_id):
        """Add product to cart."""
        try:
            # Validate product_id
            if not isinstance(produktu_id, int) or produktu_id <= 0:
                logger.warning(f"Invalid product_id: {produktu_id}")
                flash('Produktu ID baliogabea.', 'danger')
                return redirect(url_for('index'))
            
            # For demo purposes, use user_id 1 if not logged in
            # In production, require login
            user_id = session.get('user_id')
            
            # If not logged in, require login (don't use default user_id)
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"User not logged in, redirecting to login")
                flash('Mesedez, saioa hasi produktua saskira gehitzeko.', 'warning')
                return redirect(url_for('login'))
            
            # Get product information for flash message
            try:
                product = get_product_by_id(produktu_id)
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    logger.error(f"Add to cart: Database locked when getting product {produktu_id}")
                    flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                elif "no such table" in error_msg:
                    logger.error(f"Add to cart: Table produktuak does not exist")
                    flash('Datu-basearen taulak ez daude sortuta.', 'danger')
                else:
                    logger.error(f"Add to cart: Database operational error getting product {produktu_id} - {str(e)}")
                    flash('Errorea gertatu da produktua eskuratzean.', 'danger')
                logger.error(traceback.format_exc())
                return redirect(url_for('index'))
            except sqlite3.DatabaseError as e:
                logger.error(f"Add to cart: Database error getting product {produktu_id} - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                return redirect(url_for('index'))
            except AttributeError as e:
                logger.error(f"Add to cart: Attribute error getting product {produktu_id} - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuaren datuak prozesatzean.', 'danger')
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Add to cart: Unexpected error getting product {produktu_id} - {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktua eskuratzean.', 'danger')
                return redirect(url_for('index'))
            
            if not product or not isinstance(product, dict):
                logger.warning(f"Product {produktu_id} not found")
                flash('Produktua ez da aurkitu.', 'danger')
                return redirect(url_for('index'))
            
            # Check stock before adding
            try:
                available_stock = product.get('stocka', 0)
                if not isinstance(available_stock, (int, float)):
                    available_stock = 0
                available_stock = int(available_stock)
            except ValueError as e:
                logger.error(f"Add to cart: ValueError parsing stock for product {produktu_id} - {str(e)}")
                logger.error(f"Stock value: {product.get('stocka')}")
                available_stock = 0
            except TypeError as e:
                logger.error(f"Add to cart: TypeError parsing stock for product {produktu_id} - {str(e)}")
                logger.error(f"Stock value: {product.get('stocka')}")
                available_stock = 0
            except Exception as e:
                logger.error(f"Add to cart: Unexpected error parsing stock - {type(e).__name__}: {str(e)}")
                available_stock = 0
            
            if available_stock <= 0:
                flash('Produktua ez dago stockean.', 'warning')
                return redirect(url_for('index'))
            
            # Add product to cart with stock validation
            try:
                success, message = add_to_cart_db(user_id, produktu_id, 1)
                if not isinstance(success, bool):
                    logger.warning(f"Add to cart: Invalid return from add_to_cart_db: success={success}, type={type(success)}")
                    success = False
                    message = 'Errorea gertatu da produktua saskira gehitzean.'
            except sqlite3.IntegrityError as e:
                error_msg = str(e).lower()
                if "foreign key" in error_msg:
                    logger.error(f"Add to cart: Foreign key constraint failed - user {user_id} or product {produktu_id} does not exist")
                    success = False
                    message = 'Erabiltzailea edo produktua ez da aurkitu. Mesedez, saioa hasi berriro.'
                elif "unique" in error_msg or "constraint" in error_msg:
                    logger.error(f"Add to cart: Constraint violation - {str(e)}")
                    success = False
                    message = 'Produktua jada saskian dago.'
                else:
                    logger.error(f"Add to cart: Integrity error - {str(e)}")
                    success = False
                    message = 'Errorea gertatu da produktua saskira gehitzean (integritate arazoa).'
                logger.error(traceback.format_exc())
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    logger.error(f"Add to cart: Database locked when adding product {produktu_id} to cart")
                    success = False
                    message = 'Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.'
                elif "no such table" in error_msg:
                    logger.error(f"Add to cart: Table saski_elementuak does not exist")
                    success = False
                    message = 'Datu-basearen taulak ez daude sortuta.'
                else:
                    logger.error(f"Add to cart: Database operational error - {str(e)}")
                    success = False
                    message = 'Errorea gertatu da datu-basean.'
                logger.error(traceback.format_exc())
            except sqlite3.DatabaseError as e:
                logger.error(f"Add to cart: Database error - {str(e)}")
                logger.error(traceback.format_exc())
                success = False
                message = 'Errorea gertatu da datu-basearekin konektatzean.'
            except ValueError as e:
                logger.error(f"Add to cart: ValueError - {str(e)}")
                logger.error(traceback.format_exc())
                success = False
                message = 'Balio baliogabea sartu da.'
            except TypeError as e:
                logger.error(f"Add to cart: TypeError - {str(e)}")
                logger.error(traceback.format_exc())
                success = False
                message = 'Mota baliogabeko datuak.'
            except Exception as e:
                logger.error(f"Add to cart: Unexpected error - {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                success = False
                message = 'Errorea gertatu da produktua saskira gehitzean.'
            
            if success:
                product_name = product.get('izena', 'Produktua')
                if not product_name:
                    product_name = 'Produktua'
                flash(f'{product_name} saskira ondo gehitu da!', 'success')
            else:
                flash(message if message else 'Errorea gertatu da produktua saskira gehitzean.', 'warning')
            
            return redirect(url_for('index'))
        except BadRequest as e:
            logger.error(f"Add to cart: Bad request - {str(e)}")
            logger.error(traceback.format_exc())
            flash('Eskaera baliogabea.', 'danger')
            return redirect(url_for('index'))
        except NotFound as e:
            logger.error(f"Add to cart: Not found - {str(e)}")
            logger.error(traceback.format_exc())
            flash('Produktua ez da aurkitu.', 'danger')
            return redirect(url_for('index'))
        except InternalServerError as e:
            logger.error(f"Add to cart: Internal server error - {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da zerbitzarian.', 'danger')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Add to cart: Unexpected error - {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('index'))

    @app.route('/produktu/<int:id>')
    def produktu_xehetasuna(id):
        """Render product detail page."""
        try:
            # Validate product ID
            if not isinstance(id, int) or id <= 0:
                logger.warning(f"Invalid product ID: {id}")
                flash('Produktu ID baliogabea.', 'danger')
                return redirect(url_for('index'))
            
            # Get product with error handling
            try:
                product = get_product_by_id(id)
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    logger.error(f"Product detail: Database locked when getting product {id}")
                    flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                elif "no such table" in error_msg:
                    logger.error(f"Product detail: Table produktuak does not exist")
                    flash('Datu-basearen taulak ez daude sortuta.', 'danger')
                else:
                    logger.error(f"Product detail: Database operational error getting product {id} - {str(e)}")
                    flash('Errorea gertatu da produktua eskuratzean.', 'danger')
                logger.error(traceback.format_exc())
                return redirect(url_for('index'))
            except sqlite3.DatabaseError as e:
                logger.error(f"Product detail: Database error getting product {id} - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                return redirect(url_for('index'))
            except AttributeError as e:
                logger.error(f"Product detail: Attribute error getting product {id} - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuaren datuak prozesatzean.', 'danger')
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Product detail: Unexpected error getting product {id} - {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktua eskuratzean.', 'danger')
                return redirect(url_for('index'))
            
            if not product or not isinstance(product, dict):
                logger.warning(f"Product {id} not found")
                flash('Produktua ez da aurkitu.', 'danger')
                return redirect(url_for('index'))
            
            # Format product for template with validation
            try:
                formatted_product = {
                    'produktu_id': int(product.get('produktu_id', 0)) if product.get('produktu_id') else 0,
                    'izena': str(product.get('izena', 'Produktu ezezaguna')) if product.get('izena') else 'Produktu ezezaguna',
                    'deskribapena': str(product.get('deskribapena', '')) if product.get('deskribapena') else '',
                    'prezioa': float(product.get('prezioa', 0.0)) if isinstance(product.get('prezioa'), (int, float)) else 0.0,
                    'stocka': int(product.get('stocka', 0)) if isinstance(product.get('stocka'), (int, float)) else 0,
                    'irudi_urla': str(product.get('irudi_urla', 'https://via.placeholder.com/500x500')) if product.get('irudi_urla') else 'https://via.placeholder.com/500x500',
                    'kategoria_izena': str(product.get('kategoria_izena', '')) if product.get('kategoria_izena') else '',
                    'osagaiak': str(product.get('osagaiak', '')) if product.get('osagaiak') else '',
                    'balio_nutrizionalak': str(product.get('balio_nutrizionalak', '')) if product.get('balio_nutrizionalak') else '',
                    'erabilera_modua': str(product.get('erabilera_modua', '')) if product.get('erabilera_modua') else ''
                }
                
                # Validate required fields
                if not formatted_product['produktu_id']:
                    logger.warning(f"Product {id} has invalid produktu_id")
                    flash('Produktuaren datuak baliogabeak dira.', 'danger')
                    return redirect(url_for('index'))
            except ValueError as e:
                logger.error(f"Product detail: ValueError formatting product {id} - {str(e)}")
                logger.error(f"Product data: {product}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuaren datuak prozesatzean (balio baliogabea).', 'danger')
                return redirect(url_for('index'))
            except TypeError as e:
                logger.error(f"Product detail: TypeError formatting product {id} - {str(e)}")
                logger.error(f"Product data: {product}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuaren datuak prozesatzean (mota baliogabea).', 'danger')
                return redirect(url_for('index'))
            except KeyError as e:
                logger.error(f"Product detail: KeyError formatting product {id} - Missing key: {str(e)}")
                logger.error(f"Product data: {product}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuaren datuak prozesatzean (gako falta).', 'danger')
                return redirect(url_for('index'))
            
            return render_template('product_detail.html', produktua=formatted_product)
        except Exception as e:
            logger.error(f"Unexpected error in produktu_xehetasuna: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('index'))

    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        """Display checkout form (GET) or process checkout (POST): verify cart, reduce stock, create order, clear cart."""
        try:
            # Get user_id from session - require login
            user_id = session.get('user_id')
            
            # Validate user_id - require login
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"User not logged in, redirecting to login")
                flash('Mesedez, saioa hasi erosketa burutzeko.', 'warning')
                return redirect(url_for('login'))
            
            # Get cart items with error handling
            try:
                cart_items = get_cart_items(user_id)
            except Exception as e:
                logger.error(f"Error getting cart items for checkout: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da saskia eskuratzean.', 'danger')
                return redirect(url_for('cart'))
            
            # Verify cart is not empty
            if not cart_items or not isinstance(cart_items, list) or len(cart_items) == 0:
                flash('Saskia hutsik dago. Ezin da erosketa burutu.', 'warning')
                return redirect(url_for('index'))
            
            # Handle GET request - show checkout form
            if request.method == 'GET':
                # Calculate totals for display
                subtotal = 0.0
                try:
                    for item in cart_items:
                        if isinstance(item, dict):
                            quantity = item.get('kantitatea', 0)
                            price = item.get('prezioa', 0.0)
                            if isinstance(quantity, (int, float)) and isinstance(price, (int, float)):
                                subtotal += float(quantity) * float(price)
                except Exception as e:
                    logger.error(f"Error calculating subtotal: {str(e)}")
                    subtotal = 0.0
                
                subtotal = round(subtotal, 2)
                entrega_kostua = 5.0 if subtotal < 50 else 0.0
                total = subtotal + entrega_kostua
                
                return render_template('checkout.html', 
                                     cart_items=cart_items,
                                     subtotal=subtotal,
                                     entrega_kostua=entrega_kostua,
                                     total=total)
            
            # Handle POST request - process checkout
            
            # Verify stock availability and reduce stock
            all_stock_available = True
            insufficient_products = []
            
            for item in cart_items:
                if not isinstance(item, dict):
                    logger.warning(f"Invalid cart item format: {type(item)}")
                    continue
                
                try:
                    product_id = item.get('produktu_id')
                    quantity = item.get('kantitatea', 0)
                    
                    # Validate product_id and quantity
                    if not isinstance(product_id, int) or product_id <= 0:
                        logger.warning(f"Invalid product_id in cart item: {product_id}")
                        all_stock_available = False
                        insufficient_products.append(item.get('izena', 'Produktu ezezaguna'))
                        continue
                    
                    if not isinstance(quantity, (int, float)) or quantity <= 0:
                        logger.warning(f"Invalid quantity in cart item: {quantity}")
                        all_stock_available = False
                        insufficient_products.append(item.get('izena', f'Produktua {product_id}'))
                        continue
                    
                    quantity = int(quantity)
                    
                    # Check and reduce stock
                    try:
                        stock_reduced = reduce_product_stock(product_id, quantity)
                        if not stock_reduced:
                            all_stock_available = False
                            product_name = item.get('izena', f'Produktua {product_id}')
                            if not product_name:
                                product_name = f'Produktua {product_id}'
                            insufficient_products.append(product_name)
                    except sqlite3.OperationalError as e:
                        error_msg = str(e).lower()
                        if "locked" in error_msg:
                            logger.error(f"Checkout: Database locked when reducing stock for product {product_id}")
                        else:
                            logger.error(f"Checkout: Database operational error reducing stock - {str(e)}")
                        logger.error(traceback.format_exc())
                        all_stock_available = False
                        insufficient_products.append(item.get('izena', f'Produktua {product_id}'))
                    except sqlite3.DatabaseError as e:
                        logger.error(f"Checkout: Database error reducing stock for product {product_id} - {str(e)}")
                        logger.error(traceback.format_exc())
                        all_stock_available = False
                        insufficient_products.append(item.get('izena', f'Produktua {product_id}'))
                    except ValueError as e:
                        logger.error(f"Checkout: ValueError reducing stock for product {product_id} - {str(e)}")
                        logger.error(traceback.format_exc())
                        all_stock_available = False
                        insufficient_products.append(item.get('izena', f'Produktua {product_id}'))
                    except Exception as e:
                        logger.error(f"Checkout: Unexpected error reducing stock for product {product_id} - {type(e).__name__}: {str(e)}")
                        logger.error(traceback.format_exc())
                        all_stock_available = False
                        insufficient_products.append(item.get('izena', f'Produktua {product_id}'))
                except KeyError as e:
                    logger.error(f"Checkout: KeyError processing cart item - Missing key: {str(e)}")
                    logger.error(f"Item data: {item}")
                    all_stock_available = False
                    insufficient_products.append(item.get('izena', 'Produktu ezezaguna'))
                except ValueError as e:
                    logger.error(f"Checkout: ValueError processing cart item - {str(e)}")
                    logger.error(f"Item data: {item}")
                    all_stock_available = False
                    insufficient_products.append(item.get('izena', 'Produktu ezezaguna'))
                except TypeError as e:
                    logger.error(f"Checkout: TypeError processing cart item - {str(e)}")
                    logger.error(f"Item data: {item}")
                    all_stock_available = False
                    insufficient_products.append(item.get('izena', 'Produktu ezezaguna'))
            
            # If any product has insufficient stock, abort checkout
            if not all_stock_available:
                error_msg = f'Stock nahikorik ez dago produktu hau(et)an: {", ".join(insufficient_products)}'
                flash(error_msg, 'danger')
                return redirect(url_for('cart'))
            
            # Create order with error handling
            # If user is admin@gmail.com, set status to 'pagado' automatically
            user_email = session.get('user_email', '')
            order_status = 'pagado' if user_email == 'admin@gmail.com' else 'prozesatzen'
            
            try:
                order_id = create_order(user_id, status=order_status)
            except sqlite3.IntegrityError as e:
                error_msg = str(e).lower()
                if "foreign key" in error_msg:
                    logger.error(f"Checkout: Foreign key constraint failed when creating order for user {user_id}")
                    flash('Errorea gertatu da eskaera sortzean. Erabiltzailea edo produktua ez da aurkitu.', 'danger')
                elif "unique" in error_msg or "constraint" in error_msg:
                    logger.error(f"Checkout: Constraint violation when creating order - {str(e)}")
                    flash('Errorea gertatu da eskaera sortzean (integritate arazoa).', 'danger')
                else:
                    logger.error(f"Checkout: Integrity error creating order - {str(e)}")
                    flash('Errorea gertatu da eskaera sortzean (integritate arazoa).', 'danger')
                logger.error(traceback.format_exc())
                return redirect(url_for('cart'))
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    logger.error(f"Checkout: Database locked when creating order for user {user_id}")
                    flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                elif "no such table" in error_msg:
                    logger.error(f"Checkout: Required table does not exist")
                    flash('Datu-basearen taulak ez daude sortuta.', 'danger')
                else:
                    logger.error(f"Checkout: Database operational error creating order - {str(e)}")
                    flash('Errorea gertatu da datu-basean.', 'danger')
                logger.error(traceback.format_exc())
                return redirect(url_for('cart'))
            except sqlite3.DatabaseError as e:
                logger.error(f"Checkout: Database error creating order - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                return redirect(url_for('cart'))
            except ValueError as e:
                logger.error(f"Checkout: ValueError creating order - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaeraren datuak prozesatzean.', 'danger')
                return redirect(url_for('cart'))
            except Exception as e:
                logger.error(f"Checkout: Unexpected error creating order - {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaera sortzean. Mesedez, saiatu berriro.', 'danger')
                return redirect(url_for('cart'))
            
            if order_id and isinstance(order_id, int) and order_id > 0:
                flash('Erosketa ondo burutu da. Eskerrik asko zure konfiantzagatik!', 'success')
                return redirect(url_for('index'))
            else:
                logger.error(f"Checkout: Order creation returned invalid ID: {order_id}")
                flash('Errorea gertatu da erosketa prozesatzean. Mesedez, saiatu berriro.', 'danger')
                return redirect(url_for('cart'))
        except KeyError as e:
            logger.error(f"Checkout: KeyError - Missing key: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errorea gertatu da saskia prozesatzean.', 'danger')
            return redirect(url_for('cart'))
        except AttributeError as e:
            logger.error(f"Checkout: AttributeError - {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errorea gertatu da datuak prozesatzean.', 'danger')
            return redirect(url_for('cart'))
        except Exception as e:
            logger.error(f"Checkout: Unexpected error - {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('cart'))

    @app.route('/search')
    def search():
        """Search products by name or description."""
        try:
            query = request.args.get('q', '').strip()
            
            # Validate query
            if not query or len(query) == 0:
                return redirect(url_for('index'))
            
            if len(query) > 200:  # Prevent extremely long queries
                query = query[:200]
                logger.warning(f"Query truncated to 200 characters")
            
            # Get all products and filter by query
            try:
                all_products = get_all_products()
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    logger.error("Search: Database locked when getting products")
                    flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                elif "no such table" in error_msg:
                    logger.error("Search: Table produktuak does not exist")
                    flash('Datu-basearen taulak ez daude sortuta.', 'danger')
                else:
                    logger.error(f"Search: Database operational error - {str(e)}")
                    flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
                logger.error(traceback.format_exc())
                return redirect(url_for('index'))
            except sqlite3.DatabaseError as e:
                logger.error(f"Search: Database error getting products - {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Search: Unexpected error getting products - {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
                return redirect(url_for('index'))
            
            if not isinstance(all_products, list):
                all_products = []
                logger.warning("get_all_products returned non-list")
            
            filtered_products = []
            query_lower = query.lower()
            
            for p in all_products:
                if not isinstance(p, dict):
                    continue
                
                try:
                    product_name = str(p.get('izena', '')).lower()
                    product_desc = str(p.get('deskribapena', '')).lower()
                    
                    if query_lower in product_name or query_lower in product_desc:
                        product_id = p.get('produktu_id')
                        if not product_id or not isinstance(product_id, int):
                            continue
                        
                        filtered_products.append({
                            'id': product_id,
                            'izena': str(p.get('izena', 'Produktu ezezaguna')) if p.get('izena') else 'Produktu ezezaguna',
                            'deskribapena': str(p.get('deskribapena', '')) if p.get('deskribapena') else '',
                            'prezioa': float(p.get('prezioa', 0.0)) if isinstance(p.get('prezioa'), (int, float)) else 0.0,
                            'stocka': int(p.get('stocka', 0)) if isinstance(p.get('stocka'), (int, float)) else 0,
                            'irudi_urla': str(p.get('irudi_urla', 'https://via.placeholder.com/250x200')) if p.get('irudi_urla') else 'https://via.placeholder.com/250x200'
                        })
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error processing product in search: {str(e)}")
                    continue
            
            # Get cart items if user is logged in
            cart_items = []
            if 'user_id' in session:
                user_id = session.get('user_id')
                if user_id and isinstance(user_id, int) and user_id > 0:
                    try:
                        cart_items = get_cart_items(user_id)
                        if not isinstance(cart_items, list):
                            cart_items = []
                    except Exception as e:
                        logger.error(f"Error getting cart items in search: {str(e)}")
                        cart_items = []
            
            return render_template('index.html', produktuak=filtered_products, 
                                search_query=query, cart_items=cart_items)
        except Exception as e:
            logger.error(f"Unexpected error in search: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errorea gertatu da bilaketan. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('index'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login page."""
        try:
            if request.method == 'POST':
                email = request.form.get('email', '').strip()
                password = request.form.get('password', '')
                
                # Validate inputs
                if not email or not password:
                    flash('Mesedez, bete eremu guztiak.', 'danger')
                    return render_template('login.html')
                
                # Validate email format (basic validation)
                if len(email) > 255 or '@' not in email or len(email) < 3:
                    flash('Helbide elektroniko formatua baliogabea da.', 'danger')
                    return render_template('login.html')
                
                # Validate password length
                if len(password) < 1 or len(password) > 500:
                    flash('Pasahitzaren luzera baliogabea da.', 'danger')
                    return render_template('login.html')
                
                # Verify password with error handling
                try:
                    user = verify_password(email, password)
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if "locked" in error_msg:
                        logger.error(f"Login: Database locked when verifying password for {email}")
                        flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                    elif "no such table" in error_msg:
                        logger.error(f"Login: Table erabiltzaileak does not exist")
                        flash('Datu-basearen taulak ez daude sortuta.', 'danger')
                    else:
                        logger.error(f"Login: Database operational error verifying password - {str(e)}")
                        flash('Errorea gertatu da saioa egiaztatzean.', 'danger')
                    logger.error(traceback.format_exc())
                    return render_template('login.html')
                except sqlite3.DatabaseError as e:
                    logger.error(f"Login: Database error verifying password for {email} - {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                    return render_template('login.html')
                except AttributeError as e:
                    logger.error(f"Login: Attribute error verifying password - {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da saioa egiaztatzean.', 'danger')
                    return render_template('login.html')
                except Exception as e:
                    logger.error(f"Login: Unexpected error verifying password - {type(e).__name__}: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da saioa egiaztatzean. Mesedez, saiatu berriro.', 'danger')
                    return render_template('login.html')
                
                if user and isinstance(user, dict):
                    try:
                        user_id = user.get('erabiltzaile_id')
                        if not user_id or not isinstance(user_id, int) or user_id <= 0:
                            logger.warning(f"Invalid user_id from verify_password: {user_id}")
                            flash('Errorea gertatu da saioa hasieratzean.', 'danger')
                            return render_template('login.html')
                        
                        session['user_id'] = user_id
                        session['user_email'] = str(user.get('helbide_elektronikoa', email))
                        
                        first_name = str(user.get('izena', '')) if user.get('izena') else ''
                        last_name = str(user.get('abizenak', '')) if user.get('abizenak') else ''
                        session['user_name'] = f"{first_name} {last_name}".strip()
                        
                        if not session['user_name']:
                            session['user_name'] = email
                        
                        # Check if user is admin
                        user_is_admin = user.get('admin', 0) == 1
                        session['is_admin'] = user_is_admin
                        
                        flash('Ongi etorri! Saioa ondo hasi da.', 'success')
                        return redirect(url_for('index'))
                    except (KeyError, ValueError, TypeError) as e:
                        logger.error(f"Error setting session data: {str(e)}")
                        logger.error(traceback.format_exc())
                        flash('Errorea gertatu da saioa hasieratzean.', 'danger')
                        return render_template('login.html')
                else:
                    flash('Helbide elektronikoa edo pasahitza okerra.', 'danger')
            
            return render_template('login.html')
        except Exception as e:
            logger.error(f"Unexpected error in login: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return render_template('login.html'), 500

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """User registration page."""
        try:
            if request.method == 'POST':
                email = request.form.get('email', '').strip()
                password = request.form.get('password', '')
                confirm_password = request.form.get('confirm_password', '')
                first_name = request.form.get('first_name', '').strip()
                last_name = request.form.get('last_name', '').strip()
                phone = request.form.get('phone', '').strip()
                
                # Validation - check required fields
                if not all([email, password, first_name, last_name]):
                    flash('Mesedez, bete eremu beharrezko guztiak.', 'danger')
                    return render_template('register.html')
                
                # Validate email format
                if len(email) > 255 or '@' not in email or len(email) < 3:
                    flash('Helbide elektroniko formatua baliogabea da.', 'danger')
                    return render_template('register.html')
                
                # Validate password length
                if len(password) < 6:
                    flash('Pasahitzak gutxienez 6 karaktere izan behar ditu.', 'danger')
                    return render_template('register.html')
                
                if len(password) > 500:
                    flash('Pasahitza luzeegia da (gehienez 500 karaktere).', 'danger')
                    return render_template('register.html')
                
                # Validate password confirmation
                if password != confirm_password:
                    flash('Pasahitzak ez datoz bat.', 'danger')
                    return render_template('register.html')
                
                # Validate name fields
                if len(first_name) > 100 or len(last_name) > 100:
                    flash('Izenak luzeegiak dira (gehienez 100 karaktere bakoitzeko).', 'danger')
                    return render_template('register.html')
                
                if len(first_name) < 1 or len(last_name) < 1:
                    flash('Izenak ezin dira hutsik egon.', 'danger')
                    return render_template('register.html')
                
                # Validate phone if provided
                if phone and len(phone) > 50:
                    flash('Telefono zenbakia luzeegia da.', 'danger')
                    return render_template('register.html')
                
                # Create user with error handling
                try:
                    user_id = create_user(email, password, first_name, last_name, phone if phone else None)
                except sqlite3.IntegrityError as e:
                    error_msg = str(e).lower()
                    if "unique" in error_msg or "constraint" in error_msg:
                        logger.warning(f"Register: Email {email} already exists")
                        flash('Helbide elektronikoa jada erregistratuta dago.', 'danger')
                    else:
                        logger.error(f"Register: Integrity error creating user - {str(e)}")
                        flash('Errorea gertatu da erabiltzailea sortzean (integritate arazoa).', 'danger')
                    logger.error(traceback.format_exc())
                    return render_template('register.html')
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if "locked" in error_msg:
                        logger.error(f"Register: Database locked when creating user {email}")
                        flash('Datu-basea erabilgarri ez dago. Mesedez, saiatu berriro.', 'danger')
                    elif "no such table" in error_msg:
                        logger.error(f"Register: Table erabiltzaileak does not exist")
                        flash('Datu-basearen taulak ez daude sortuta.', 'danger')
                    else:
                        logger.error(f"Register: Database operational error creating user - {str(e)}")
                        flash('Errorea gertatu da datu-basean.', 'danger')
                    logger.error(traceback.format_exc())
                    return render_template('register.html')
                except sqlite3.DatabaseError as e:
                    logger.error(f"Register: Database error creating user - {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da datu-basearekin konektatzean.', 'danger')
                    return render_template('register.html')
                except ValueError as e:
                    logger.error(f"Register: ValueError creating user - {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da erabiltzailearen datuak prozesatzean.', 'danger')
                    return render_template('register.html')
                except Exception as e:
                    logger.error(f"Register: Unexpected error creating user - {type(e).__name__}: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da erabiltzailea sortzean. Mesedez, saiatu berriro.', 'danger')
                    return render_template('register.html')
                
                if user_id and isinstance(user_id, int) and user_id > 0:
                    flash('Erregistroa ondo burutu da! Mesedez, saioa hasi.', 'success')
                    return redirect(url_for('login'))
                else:
                    flash('Helbide elektronikoa jada erregistratuta dago.', 'danger')
            
            return render_template('register.html')
        except Exception as e:
            logger.error(f"Unexpected error in register: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return render_template('register.html'), 500

    @app.route('/logout')
    def logout():
        """Logout user."""
        session.clear()
        flash('Saioa ondo itxi da. Laster arte!', 'info')
        return redirect(url_for('index'))

    @app.route('/cart')
    def cart():
        """Display shopping cart."""
        try:
            user_id = session.get('user_id')
            
            # Validate user_id - require login
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"User not logged in, redirecting to login")
                flash('Mesedez, saioa hasi saskia ikusteko.', 'warning')
                return redirect(url_for('login'))
            
            # Get cart items with error handling
            try:
                cart_items = get_cart_items(user_id)
            except Exception as e:
                logger.error(f"Error getting cart items: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da saskia eskuratzean.', 'danger')
                cart_items = []
            
            if not isinstance(cart_items, list):
                logger.warning(f"Invalid cart_items format: {type(cart_items)}")
                cart_items = []
            
            # Calculate total with validation
            total = 0.0
            try:
                for item in cart_items:
                    if not isinstance(item, dict):
                        continue
                    try:
                        quantity = item.get('kantitatea', 0)
                        price = item.get('prezioa', 0.0)
                        
                        if isinstance(quantity, (int, float)) and isinstance(price, (int, float)):
                            quantity = float(quantity)
                            price = float(price)
                            if quantity >= 0 and price >= 0:
                                total += quantity * price
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error calculating total for item: {str(e)}")
                        continue
            except Exception as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                total = 0.0
            
            total = round(total, 2)
            
            return render_template('cart.html', cart_items=cart_items, total=total)
        except Exception as e:
            logger.error(f"Unexpected error in cart: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da saskia kargatzean.', 'danger')
            return render_template('cart.html', cart_items=[], total=0.0), 500

    @app.route('/update_cart', methods=['POST'])
    def update_cart():
        """Update cart item quantity."""
        try:
            user_id = session.get('user_id')
            
            # Validate user_id - require login
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"User not logged in, redirecting to login")
                flash('Mesedez, saioa hasi saskia eguneratzeko.', 'warning')
                return redirect(url_for('login'))
            
            # Get and validate form data
            try:
                product_id = request.form.get('product_id', type=int)
                quantity = request.form.get('quantity', type=int)
                action = request.form.get('action', '').strip()
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing form data: {str(e)}")
                flash('Datu baliogabeak.', 'danger')
                return redirect(url_for('cart'))
            
            # Validate product_id
            if not product_id or not isinstance(product_id, int) or product_id <= 0:
                logger.warning(f"Invalid product_id in update_cart: {product_id}")
                flash('Produktu ID baliogabea.', 'danger')
                return redirect(url_for('cart'))
            
            if action == 'remove':
                try:
                    remove_from_cart(user_id, product_id)
                    flash('Produktua saskitik kendu da.', 'success')
                except Exception as e:
                    logger.error(f"Error removing from cart: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da produktua saskitik kentzean.', 'danger')
            elif action == 'increase':
                try:
                    cart_items = get_cart_items(user_id)
                    if not isinstance(cart_items, list):
                        flash('Errorea gertatu da saskia eskuratzean.', 'danger')
                        return redirect(url_for('cart'))
                    
                    current_item = next((item for item in cart_items if isinstance(item, dict) and item.get('produktu_id') == product_id), None)
                    if current_item:
                        current_quantity = current_item.get('kantitatea', 0)
                        if not isinstance(current_quantity, (int, float)) or current_quantity < 0:
                            current_quantity = 0
                        new_quantity = int(current_quantity) + 1
                        success, message = update_cart_item(user_id, product_id, new_quantity)
                        if success:
                            flash(message if message else 'Kantitatea eguneratu da.', 'success')
                        else:
                            flash(message if message else 'Errorea gertatu da kantitatea eguneratzean.', 'warning')
                    else:
                        flash('Produktua ez da aurkitu saskian.', 'danger')
                except Exception as e:
                    logger.error(f"Error increasing cart quantity: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da kantitatea handitzean.', 'danger')
            elif action == 'decrease':
                try:
                    cart_items = get_cart_items(user_id)
                    if not isinstance(cart_items, list):
                        flash('Errorea gertatu da saskia eskuratzean.', 'danger')
                        return redirect(url_for('cart'))
                    
                    current_item = next((item for item in cart_items if isinstance(item, dict) and item.get('produktu_id') == product_id), None)
                    if current_item:
                        current_quantity = current_item.get('kantitatea', 0)
                        if not isinstance(current_quantity, (int, float)) or current_quantity < 0:
                            current_quantity = 0
                        new_quantity = max(1, int(current_quantity) - 1)
                        success, message = update_cart_item(user_id, product_id, new_quantity)
                        if success:
                            flash(message if message else 'Kantitatea eguneratu da.', 'success')
                        else:
                            flash(message if message else 'Errorea gertatu da kantitatea eguneratzean.', 'warning')
                    else:
                        flash('Produktua ez da aurkitu saskian.', 'danger')
                except Exception as e:
                    logger.error(f"Error decreasing cart quantity: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da kantitatea gutxitzean.', 'danger')
            elif quantity and isinstance(quantity, int) and quantity > 0:
                try:
                    success, message = update_cart_item(user_id, product_id, quantity)
                    if success:
                        flash(message if message else 'Kantitatea eguneratu da.', 'success')
                    else:
                        flash(message if message else 'Errorea gertatu da kantitatea eguneratzean.', 'warning')
                except Exception as e:
                    logger.error(f"Error updating cart quantity: {str(e)}")
                    logger.error(traceback.format_exc())
                    flash('Errorea gertatu da kantitatea eguneratzean.', 'danger')
            else:
                flash('Kantitate baliogabea.', 'danger')
            
            return redirect(url_for('cart'))
        except Exception as e:
            logger.error(f"Unexpected error in update_cart: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('cart'))

    @app.route('/orders')
    def orders():
        """Display user orders."""
        try:
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi zure eskaerak ikusteko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            
            # Validate user_id
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"Invalid user_id in orders: {user_id}")
                flash('Erabiltzaile ID baliogabea. Mesedez, saioa hasi berriro.', 'warning')
                session.clear()
                return redirect(url_for('login'))
            
            # Get user orders with error handling
            try:
                orders = get_user_orders(user_id)
            except Exception as e:
                logger.error(f"Error getting user orders: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaerak eskuratzean.', 'danger')
                orders = []
            
            if not isinstance(orders, list):
                logger.warning(f"Invalid orders format: {type(orders)}")
                orders = []
            
            return render_template('orders.html', orders=orders)
        except Exception as e:
            logger.error(f"Unexpected error in orders: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return render_template('orders.html', orders=[]), 500

    @app.route('/order/<int:order_id>')
    def order_detail(order_id):
        """Display order details."""
        try:
            # Validate order_id
            if not isinstance(order_id, int) or order_id <= 0:
                logger.warning(f"Invalid order_id: {order_id}")
                flash('Eskaera ID baliogabea.', 'danger')
                return redirect(url_for('orders'))
            
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi zure eskaerak ikusteko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            
            # Validate user_id
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"Invalid user_id in order_detail: {user_id}")
                flash('Erabiltzaile ID baliogabea. Mesedez, saioa hasi berriro.', 'warning')
                session.clear()
                return redirect(url_for('login'))
            
            # Get order details with error handling
            try:
                order = get_order_details(order_id)
            except Exception as e:
                logger.error(f"Error getting order details: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaeraren xehetasunak eskuratzean.', 'danger')
                return redirect(url_for('orders'))
            
            if not order or not isinstance(order, dict):
                flash('Eskaera ez da aurkitu.', 'danger')
                return redirect(url_for('orders'))
            
            # Verify that the order belongs to the current user
            order_user_id = order.get('erabiltzaile_id')
            if not order_user_id or not isinstance(order_user_id, int):
                logger.warning(f"Invalid erabiltzaile_id in order: {order_user_id}")
                flash('Eskaeraren datuak baliogabeak dira.', 'danger')
                return redirect(url_for('orders'))
            
            if order_user_id != user_id:
                logger.warning(f"User {user_id} tried to access order {order_id} belonging to user {order_user_id}")
                flash('Eskaera hau zure kontuarena ez da.', 'danger')
                return redirect(url_for('orders'))
            
            # Calculate total with validation
            total = 0.0
            order_items = order.get('elementuak', [])
            if not isinstance(order_items, list):
                logger.warning(f"Invalid order items format: {type(order_items)}")
                order_items = []
            
            try:
                for item in order_items:
                    if not isinstance(item, dict):
                        continue
                    try:
                        quantity = item.get('kantitatea', 0)
                        price = item.get('prezioa', 0.0)
                        
                        if isinstance(quantity, (int, float)) and isinstance(price, (int, float)):
                            quantity = float(quantity)
                            price = float(price)
                            if quantity >= 0 and price >= 0:
                                total += quantity * price
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error calculating total for order item: {str(e)}")
                        continue
            except Exception as e:
                logger.error(f"Error calculating order total: {str(e)}")
                total = 0.0
            
            order['total'] = round(total, 2)
            
            # Add cancel logic: can cancel if order is less than 24 hours old and not already cancelled
            can_cancel = False
            cancel_message = ''
            
            try:
                order_status = order.get('egoera', '')
                if order_status != 'bertan_behera':
                    # Check if order is less than 24 hours old
                    creation_date_str = order.get('sormen_data', '')
                    if creation_date_str:
                        try:
                            # Parse the creation date
                            if 'T' in creation_date_str:
                                creation_date = datetime.strptime(creation_date_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                creation_date = datetime.strptime(creation_date_str[:19], '%Y-%m-%d %H:%M:%S')
                            
                            time_diff = datetime.now() - creation_date
                            if time_diff < timedelta(hours=24):
                                can_cancel = True
                            else:
                                cancel_message = 'Eskaera ezin da bertan behera utzi 24 ordu baino gehiago igaro direlako.'
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing order date: {str(e)}")
                            cancel_message = 'Ezin da eskaeraren data egiaztatu.'
                    else:
                        cancel_message = 'Eskaeraren data ez da aurkitu.'
                else:
                    cancel_message = 'Eskaera jada bertan behera utzi da.'
            except Exception as e:
                logger.error(f"Error calculating cancel logic: {str(e)}")
                cancel_message = 'Errorea gertatu da eskaeraren egoera egiaztatzean.'
            
            order['can_cancel'] = can_cancel
            order['cancel_message'] = cancel_message
            
            return render_template('order_detail.html', order=order)
        except Exception as e:
            logger.error(f"Unexpected error in order_detail: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('orders'))

    @app.route('/order/<int:order_id>/confirm', methods=['POST'])
    def confirm_order_route(order_id):
        """Confirm order receipt (change status to 'bukatuta')."""
        try:
            # Validate order_id
            if not isinstance(order_id, int) or order_id <= 0:
                logger.warning(f"Invalid order_id in confirm_order: {order_id}")
                flash('Eskaera ID baliogabea.', 'danger')
                return redirect(url_for('orders'))
            
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi zure eskaerak kudeatzeko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"Invalid user_id in confirm_order: {user_id}")
                flash('Erabiltzaile ID baliogabea.', 'warning')
                return redirect(url_for('login'))
            
            # Get order details to verify ownership
            try:
                order = get_order_details(order_id)
            except Exception as e:
                logger.error(f"Error getting order details in confirm_order: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaera eskuratzean.', 'danger')
                return redirect(url_for('orders'))
            
            if not order or not isinstance(order, dict):
                flash('Eskaera ez da aurkitu.', 'danger')
                return redirect(url_for('orders'))
            
            # Verify ownership
            order_user_id = order.get('erabiltzaile_id')
            if not order_user_id or order_user_id != user_id:
                logger.warning(f"User {user_id} tried to confirm order {order_id} belonging to user {order_user_id}")
                flash('Eskaera hau zure kontuarena ez da.', 'danger')
                return redirect(url_for('orders'))
            
            # Verify order status is 'prozesatzen' or 'bidalita'
            current_status = order.get('egoera', '')
            if current_status not in ['prozesatzen', 'bidalita']:
                if current_status == 'bukatuta':
                    flash('Eskaera hau jada iritsi da.', 'info')
                elif current_status == 'bertan_behera':
                    flash('Eskaera hau bertan behera utzi da.', 'warning')
                else:
                    flash('Eskaera hau ezin da iritsi egoera honetan.', 'warning')
                return redirect(url_for('order_detail', order_id=order_id))
            
            # Update order status to 'bukatuta'
            try:
                update_order_status(order_id, 'bukatuta')
                flash('Eskaera ondo iritsi da. Eskerrik asko zure erosketagatik!', 'success')
            except Exception as e:
                logger.error(f"Error updating order status in confirm_order: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaeraren egoera eguneratzean.', 'danger')
            
            return redirect(url_for('order_detail', order_id=order_id))
        except Exception as e:
            logger.error(f"Unexpected error in confirm_order: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('orders'))

    @app.route('/order/<int:order_id>/cancel', methods=['POST'])
    def cancel_order_route(order_id):
        """Cancel order (change status to 'bertan_behera')."""
        try:
            # Validate order_id
            if not isinstance(order_id, int) or order_id <= 0:
                logger.warning(f"Invalid order_id in cancel_order: {order_id}")
                flash('Eskaera ID baliogabea.', 'danger')
                return redirect(url_for('orders'))
            
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi zure eskaerak kudeatzeko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"Invalid user_id in cancel_order: {user_id}")
                flash('Erabiltzaile ID baliogabea.', 'warning')
                return redirect(url_for('login'))
            
            # Get order details to verify ownership and check if can cancel
            try:
                order = get_order_details(order_id)
            except Exception as e:
                logger.error(f"Error getting order details in cancel_order: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaera eskuratzean.', 'danger')
                return redirect(url_for('orders'))
            
            if not order or not isinstance(order, dict):
                flash('Eskaera ez da aurkitu.', 'danger')
                return redirect(url_for('orders'))
            
            # Verify ownership
            order_user_id = order.get('erabiltzaile_id')
            if not order_user_id or order_user_id != user_id:
                logger.warning(f"User {user_id} tried to cancel order {order_id} belonging to user {order_user_id}")
                flash('Eskaera hau zure kontuarena ez da.', 'danger')
                return redirect(url_for('orders'))
            
            # Check if order can be cancelled
            current_status = order.get('egoera', '')
            if current_status == 'bertan_behera':
                flash('Eskaera hau jada bertan behera utzi da.', 'info')
                return redirect(url_for('order_detail', order_id=order_id))
            
            # Check if order is less than 24 hours old
            can_cancel = False
            creation_date_str = order.get('sormen_data', '')
            if creation_date_str:
                try:
                    if 'T' in creation_date_str:
                        creation_date = datetime.strptime(creation_date_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        creation_date = datetime.strptime(creation_date_str[:19], '%Y-%m-%d %H:%M:%S')
                    time_diff = datetime.now() - creation_date
                    can_cancel = time_diff < timedelta(hours=24)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing order date in cancel_order: {str(e)}")
                    can_cancel = False
            
            if not can_cancel:
                flash('Eskaera ezin da bertan behera utzi 24 ordu baino gehiago igaro direlako.', 'warning')
                return redirect(url_for('order_detail', order_id=order_id))
            
            # Restore stock for all products in the order before canceling
            order_items = order.get('elementuak', [])
            if not isinstance(order_items, list):
                order_items = []
            
            stock_restored = True
            restored_products = []
            failed_products = []
            
            for item in order_items:
                if not isinstance(item, dict):
                    continue
                
                try:
                    product_id = item.get('produktu_id')
                    quantity = item.get('kantitatea', 0)
                    
                    # Validate product_id and quantity
                    if not isinstance(product_id, int) or product_id <= 0:
                        logger.warning(f"cancel_order: Invalid product_id in order item: {product_id}")
                        failed_products.append(item.get('izena', 'Produktu ezezaguna'))
                        continue
                    
                    if not isinstance(quantity, (int, float)) or quantity <= 0:
                        logger.warning(f"cancel_order: Invalid quantity in order item: {quantity}")
                        failed_products.append(item.get('izena', f'Produktua {product_id}'))
                        continue
                    
                    quantity = int(quantity)
                    
                    # Restore stock
                    try:
                        restored = restore_product_stock(product_id, quantity)
                        if restored:
                            product_name = item.get('izena', f'Produktua {product_id}')
                            if not product_name:
                                product_name = f'Produktua {product_id}'
                            restored_products.append(product_name)
                            logger.info(f"cancel_order: Restored {quantity} units for product {product_id}")
                        else:
                            stock_restored = False
                            product_name = item.get('izena', f'Produktua {product_id}')
                            if not product_name:
                                product_name = f'Produktua {product_id}'
                            failed_products.append(product_name)
                            logger.error(f"cancel_order: Failed to restore stock for product {product_id}")
                    except Exception as e:
                        logger.error(f"cancel_order: Error restoring stock for product {product_id} - {str(e)}")
                        logger.error(traceback.format_exc())
                        stock_restored = False
                        failed_products.append(item.get('izena', f'Produktua {product_id}'))
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"cancel_order: Error processing order item - {str(e)}")
                    logger.error(f"Item data: {item}")
                    failed_products.append(item.get('izena', 'Produktu ezezaguna'))
            
            # Update order status to 'bertan_behera'
            try:
                update_order_status(order_id, 'bertan_behera')
                
                if stock_restored and len(restored_products) > 0:
                    flash(f'Eskaera bertan behera utzi da. Stocka berreskuratu da produktu hau(et)an: {", ".join(restored_products)}', 'success')
                elif len(failed_products) > 0:
                    flash(f'Eskaera bertan behera utzi da, baina errorea gertatu da stocka berreskuratzean produktu hau(et)an: {", ".join(failed_products)}', 'warning')
                else:
                    flash('Eskaera bertan behera utzi da.', 'success')
            except Exception as e:
                logger.error(f"Error updating order status in cancel_order: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaeraren egoera eguneratzean.', 'danger')
            
            return redirect(url_for('order_detail', order_id=order_id))
        except Exception as e:
            logger.error(f"Unexpected error in cancel_order: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('orders'))

    @app.route('/admin/stock')
    def admin_stock():
        """Admin panel for managing product stock."""
        try:
            # Check if user is logged in
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi administratzaile panela erabiltzeko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                flash('Erabiltzaile ID baliogabea.', 'warning')
                return redirect(url_for('login'))
            
            # Check if user is admin
            if not session.get('is_admin', False):
                if not is_admin(user_id):
                    flash('Ez duzu baimenik administratzaile panela erabiltzeko.', 'danger')
                    return redirect(url_for('index'))
                session['is_admin'] = True
            
            # Get all products
            try:
                products = get_all_products()
            except Exception as e:
                logger.error(f"Error getting products in admin_stock: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
                products = []
            
            if not isinstance(products, list):
                products = []
            
            return render_template('admin_stock.html', products=products)
        except Exception as e:
            logger.error(f"Unexpected error in admin_stock: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('index'))

    @app.route('/admin/stock/update', methods=['POST'])
    def admin_update_stock():
        """Update product stock from admin panel."""
        try:
            # Check if user is logged in
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi administratzaile panela erabiltzeko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                flash('Erabiltzaile ID baliogabea.', 'warning')
                return redirect(url_for('login'))
            
            # Check if user is admin
            if not session.get('is_admin', False):
                if not is_admin(user_id):
                    flash('Ez duzu baimenik stock-a aldatzeko.', 'danger')
                    return redirect(url_for('index'))
                session['is_admin'] = True
            
            # Get all product IDs and their stock changes from form
            updated_count = 0
            failed_count = 0
            failed_products = []
            
            # Process all stock updates from the form
            for key, value in request.form.items():
                if key.startswith('stock_change_'):
                    try:
                        product_id = int(key.replace('stock_change_', ''))
                        stock_change = int(value) if value else 0
                        
                        # Get current stock
                        current_stock_key = f'current_stock_{product_id}'
                        current_stock = request.form.get(current_stock_key, type=int)
                        if current_stock is None:
                            # If not in form, get from database
                            try:
                                product = get_product_by_id(product_id)
                                if product:
                                    current_stock = product.get('stocka', 0)
                                    if not isinstance(current_stock, (int, float)):
                                        current_stock = 0
                                    current_stock = int(current_stock)
                                else:
                                    logger.warning(f"Product {product_id} not found")
                                    failed_count += 1
                                    continue
                            except Exception as e:
                                logger.error(f"Error getting current stock for product {product_id}: {str(e)}")
                                failed_count += 1
                                continue
                        
                        # Calculate new stock (current + change)
                        new_stock = current_stock + stock_change
                        
                        # Validate: new stock cannot be negative
                        if new_stock < 0:
                            product = get_product_by_id(product_id)
                            product_name = product.get('izena', f'Produktua {product_id}') if product else f'Produktua {product_id}'
                            flash(f'{product_name} produktuaren stock-a ezin da {new_stock} unitatera jaitsi (gutxienez 0 izan behar du). Uneko stocka: {current_stock}, aldaketa: {stock_change}', 'warning')
                            failed_count += 1
                            failed_products.append(product_name)
                            continue
                        
                        # Update stock
                        try:
                            success = update_product_stock(product_id, new_stock)
                            if success:
                                updated_count += 1
                            else:
                                failed_count += 1
                                product = get_product_by_id(product_id)
                                if product:
                                    failed_products.append(product.get('izena', f'Produktua {product_id}'))
                        except Exception as e:
                            logger.error(f"Error updating stock for product {product_id}: {str(e)}")
                            logger.error(traceback.format_exc())
                            failed_count += 1
                            try:
                                product = get_product_by_id(product_id)
                                if product:
                                    failed_products.append(product.get('izena', f'Produktua {product_id}'))
                            except:
                                pass
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing stock data: {key} = {value}, error: {str(e)}")
                        failed_count += 1
                        continue
            
            # Show appropriate message
            if updated_count > 0 and failed_count == 0:
                flash(f'{updated_count} produkturen stock-a ondo eguneratu da.', 'success')
            elif updated_count > 0 and failed_count > 0:
                flash(f'{updated_count} produkturen stock-a eguneratu da, baina {failed_count} produktutan errorea gertatu da.', 'warning')
                if failed_products:
                    flash(f'Errorea gertatu da produktu hau(et)an: {", ".join(failed_products)}', 'warning')
            elif failed_count > 0:
                flash(f'Errorea gertatu da stock-a eguneratzean.', 'danger')
                if failed_products:
                    flash(f'Errorea gertatu da produktu hau(et)an: {", ".join(failed_products)}', 'danger')
            else:
                flash('Ez da eguneratzerik egin.', 'info')
            
            return redirect(url_for('admin_stock'))
        except Exception as e:
            logger.error(f"Unexpected error in admin_update_stock: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('admin_stock'))

    # Generic error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {request.url}")
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {str(error)}")
        logger.error(traceback.format_exc())
        return render_template('500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle all unhandled exceptions."""
        logger.error(f"Unhandled exception: {str(error)}")
        logger.error(traceback.format_exc())
        flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
        return render_template('500.html'), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
