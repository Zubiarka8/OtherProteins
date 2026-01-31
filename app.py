
from flask import Flask, render_template, request, flash, redirect, url_for, session, make_response
from datetime import datetime, timedelta
import logging
import traceback
import sqlite3
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound
from io import BytesIO
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
    get_user_by_id,
    get_product_by_id,
    verify_password,
    create_user,
    get_user_orders,
    get_all_orders,
    get_order_details,
    update_cart_item,
    remove_from_cart,
    clear_cart,
    update_order_status,
    is_admin,
    update_product_stock,
    update_product_name,
    update_product_price,
    update_product_image,
    update_product_description,
    delete_product,
    update_user_info
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
            
            # Get and store delivery information
            entrega_mota = request.form.get('entrega_mota', 'tienda')
            session['entrega_mota'] = entrega_mota
            
            # Calculate shipping cost
            subtotal = 0.0
            try:
                for item in cart_items:
                    if isinstance(item, dict):
                        quantity = item.get('kantitatea', 0)
                        price = item.get('prezioa', 0.0)
                        if isinstance(quantity, (int, float)) and isinstance(price, (int, float)):
                            subtotal += float(quantity) * float(price)
            except Exception as e:
                logger.error(f"Error calculating subtotal in POST: {str(e)}")
                subtotal = 0.0
            
            subtotal = round(subtotal, 2)
            entrega_kostua = 5.0 if (entrega_mota == 'etxera' and subtotal < 50) else 0.0
            
            # Get address information
            helbidea = None
            kalea = None
            zenbakia = None
            hiria = None
            probintzia = None
            posta_kodea = None
            
            if entrega_mota == 'etxera':
                # Get address from form
                kalea = request.form.get('kalea', '').strip() or None
                zenbakia = request.form.get('zenbakia', '').strip() or None
                hiria = request.form.get('hiria', '').strip() or None
                probintzia = request.form.get('probintzia', '').strip() or None
                posta_kodea = request.form.get('posta_kodea', '').strip() or None
                
                # Build full address string
                address_parts = [kalea, zenbakia, posta_kodea, hiria, probintzia]
                address_parts = [part for part in address_parts if part]
                helbidea = ', '.join(address_parts) if address_parts else None
                
                # Store in session
                session['kalea'] = kalea or ''
                session['zenbakia'] = zenbakia or ''
                session['hiria'] = hiria or ''
                session['probintzia'] = probintzia or ''
                session['posta_kodea'] = posta_kodea or ''
            else:
                # Clear delivery address if picking up in store
                session.pop('kalea', None)
                session.pop('zenbakia', None)
                session.pop('hiria', None)
                session.pop('probintzia', None)
                session.pop('posta_kodea', None)
            
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
                order_id = create_order(
                    user_id, 
                    status=order_status,
                    entrega_mota=entrega_mota,
                    entrega_kostua=entrega_kostua,
                    helbidea=helbidea,
                    kalea=kalea,
                    zenbakia=zenbakia,
                    hiria=hiria,
                    probintzia=probintzia,
                    posta_kodea=posta_kodea
                )
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

    @app.route('/payment', methods=['GET', 'POST'])
    def payment():
        """Display payment form (GET) or process payment (POST)."""
        try:
            # Get user_id from session - require login
            user_id = session.get('user_id')
            
            # Validate user_id - require login
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"User not logged in, redirecting to login")
                flash('Mesedez, saioa hasi ordainketa burutzeko.', 'warning')
                return redirect(url_for('login'))
            
            # Get cart items with error handling
            try:
                cart_items = get_cart_items(user_id)
            except Exception as e:
                logger.error(f"Error getting cart items for payment: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da saskia eskuratzean.', 'danger')
                return redirect(url_for('cart'))
            
            # Verify cart is not empty
            if not cart_items or not isinstance(cart_items, list) or len(cart_items) == 0:
                flash('Saskia hutsik dago. Ezin da ordainketa burutu.', 'warning')
                return redirect(url_for('index'))
            
            # Handle GET request - show payment form
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
                
                # Get delivery info from session if available
                entrega_mota = session.get('entrega_mota', 'tienda')
                hiria = session.get('hiria', '')
                probintzia = session.get('probintzia', '')
                
                return render_template('payment.html', 
                                     cart_items=cart_items,
                                     subtotal=subtotal,
                                     entrega_kostua=entrega_kostua,
                                     total=total,
                                     entrega_mota=entrega_mota,
                                     hiria=hiria,
                                     probintzia=probintzia)
            
            # Handle POST request - process payment (redirect to checkout to create order)
            # Payment is processed in checkout, this is just a form step
            return redirect(url_for('checkout'))
            
        except Exception as e:
            logger.error(f"Unexpected error in payment: {type(e).__name__}: {str(e)}")
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
            
            # Check if user is admin
            user_email = session.get('user_email', '')
            is_user_admin = session.get('is_admin', False)
            
            # Get orders - all orders if admin, user orders otherwise
            try:
                if is_user_admin and user_email == 'admin@gmail.com':
                    # Admin sees all orders from all users
                    orders = get_all_orders()
                    is_admin_view = True
                else:
                    # Regular user sees only their orders
                    orders = get_user_orders(user_id)
                    is_admin_view = False
            except Exception as e:
                logger.error(f"Error getting orders: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaerak eskuratzean.', 'danger')
                orders = []
                is_admin_view = False
            
            if not isinstance(orders, list):
                logger.warning(f"Invalid orders format: {type(orders)}")
                orders = []
            
            return render_template('orders.html', orders=orders, is_admin_view=is_admin_view)
        except Exception as e:
            logger.error(f"Unexpected error in orders: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return render_template('orders.html', orders=[], is_admin_view=False), 500

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
            
            # Verify that the order belongs to the current user (unless admin)
            user_email = session.get('user_email', '')
            is_user_admin = session.get('is_admin', False)
            
            order_user_id = order.get('erabiltzaile_id')
            if not order_user_id or not isinstance(order_user_id, int):
                logger.warning(f"Invalid erabiltzaile_id in order: {order_user_id}")
                flash('Eskaeraren datuak baliogabeak dira.', 'danger')
                return redirect(url_for('orders'))
            
            # Admin can access any order, regular users can only access their own
            if not (is_user_admin and user_email == 'admin@gmail.com') and order_user_id != user_id:
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
            
            # Verify ownership (unless admin)
            user_email = session.get('user_email', '')
            is_user_admin = session.get('is_admin', False)
            
            order_user_id = order.get('erabiltzaile_id')
            # Admin can confirm any order, regular users can only confirm their own
            if not (is_user_admin and user_email == 'admin@gmail.com') and (not order_user_id or order_user_id != user_id):
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
            
            # Verify ownership (unless admin)
            user_email = session.get('user_email', '')
            is_user_admin = session.get('is_admin', False)
            
            order_user_id = order.get('erabiltzaile_id')
            # Admin can cancel any order, regular users can only cancel their own
            if not (is_user_admin and user_email == 'admin@gmail.com') and (not order_user_id or order_user_id != user_id):
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

    def generate_invoice_pdf(order_data, invoice_user_data=None):
        """Generate a PDF invoice/ticket for an order.
        
        Args:
            order_data: Order data from database
            invoice_user_data: Optional dict with user data for invoice (izena, abizenak, helbide_elektronikoa, telefonoa)
                              If provided, these values will be used instead of database values.
        """
        try:
            # Import reportlab only when needed
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import mm, inch
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
            except ImportError:
                logger.error("reportlab library is not installed. Please install it with: pip install reportlab")
                return None
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, 
                                    rightMargin=30*mm, leftMargin=30*mm,
                                    topMargin=30*mm, bottomMargin=30*mm)
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            
            # Company header style
            company_title_style = ParagraphStyle(
                'CompanyTitle',
                parent=styles['Heading1'],
                fontSize=28,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=5,
                alignment=1,  # Center
                fontName='Helvetica-Bold'
            )
            
            # Invoice title style
            invoice_title_style = ParagraphStyle(
                'InvoiceTitle',
                parent=styles['Normal'],
                fontSize=18,
                textColor=colors.HexColor('#34495e'),
                spaceAfter=20,
                alignment=1,  # Center
                fontName='Helvetica-Bold'
            )
            
            # Section heading style
            heading_style = ParagraphStyle(
                'SectionHeading',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=10,
                spaceBefore=15,
                fontName='Helvetica-Bold'
            )
            
            # Normal text style
            normal_style = ParagraphStyle(
                'NormalText',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#34495e'),
                leading=12
            )
            
            # Company info style
            company_info_style = ParagraphStyle(
                'CompanyInfo',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#7f8c8d'),
                alignment=1,  # Center
                leading=11
            )
            
            # Header with company info
            header_data = [
                [Paragraph("<b>OtherProteins</b>", company_title_style)],
                [Paragraph("Proteina eta Nutrizio Produktuak", company_info_style)],
                [Paragraph("www.otherproteins.com | info@otherproteins.com", company_info_style)],
                [Spacer(1, 15)],
                [Paragraph("<b>FAKTURA</b>", invoice_title_style)]
            ]
            
            header_table = Table(header_data, colWidths=[180*mm])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 25))
            
            # Order info
            order_id = order_data.get('eskaera_id', 'N/A')
            order_date = order_data.get('sormen_data', '')
            order_date_formatted = 'N/A'
            if order_date and len(order_date) >= 10:
                try:
                    # Format date nicely
                    date_obj = datetime.strptime(order_date[:10], '%Y-%m-%d')
                    order_date_formatted = date_obj.strftime('%Y-%m-%d')
                except:
                    order_date_formatted = order_date[:10] if len(order_date) >= 10 else 'N/A'
            
            # Get user info - use invoice_user_data if provided, otherwise from database
            if invoice_user_data:
                # Use data from form (for admin)
                customer_name = f"{invoice_user_data.get('izena', '')} {invoice_user_data.get('abizenak', '')}".strip()
                customer_email = invoice_user_data.get('helbide_elektronikoa', '')
                customer_phone = invoice_user_data.get('telefonoa', 'N/A') if invoice_user_data.get('telefonoa') else 'N/A'
            else:
                # Get user info from database
                user_id = order_data.get('erabiltzaile_id')
                user_info = None
                if user_id:
                    try:
                        user_info = get_user_by_id(user_id)
                    except Exception as e:
                        logger.warning(f"Error getting user info for PDF: {str(e)}")
                        pass
                
                # Customer info
                if user_info:
                    customer_name = f"{user_info.get('izena', '')} {user_info.get('abizenak', '')}".strip()
                    customer_email = user_info.get('helbide_elektronikoa', '')
                    customer_phone = user_info.get('telefonoa', 'N/A') if user_info.get('telefonoa') else 'N/A'
                else:
                    customer_name = "Bezero ezezaguna"
                    customer_email = "N/A"
                    customer_phone = "N/A"
            
            # Translate order status
            status_translations = {
                'prozesatzen': 'Prozesatzen',
                'pagado': 'Ordainduta',
                'bidalita': 'Bidalita',
                'bukatuta': 'Bukatuta',
                'bertan_behera': 'Bertan behera utzita'
            }
            order_status = status_translations.get(order_data.get("egoera", "N/A"), order_data.get("egoera", "N/A"))
            
            # Information table with better styling - Date at the top
            info_data = [
                [Paragraph("<b>ESKAERA INFORMAZIOA</b>", ParagraphStyle('InfoHeader', parent=normal_style, fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#2c3e50'))),
                 Paragraph("<b>BEZEROAREN INFORMAZIOA</b>", ParagraphStyle('InfoHeader', parent=normal_style, fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#2c3e50')))],
                [Paragraph(f"<b>Data:</b> {order_date_formatted}", ParagraphStyle('DateRow', parent=normal_style, fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#2c3e50'))),
                 Paragraph(f"<b>Izena:</b> {customer_name}", normal_style)],
                [Paragraph(f"<b>Eskaera #:</b> {order_id}", normal_style),
                 Paragraph(f"<b>Email:</b> {customer_email}", normal_style)],
                [Paragraph(f"<b>Egoera:</b> {order_status}", normal_style),
                 Paragraph(f"<b>Telefonoa:</b> {customer_phone}", normal_style)]
            ]
            
            info_table = Table(info_data, colWidths=[90*mm, 90*mm])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 25))
            
            # Order items section with improved design
            elements.append(Spacer(1, 5))
            section_title = Paragraph(
                "<b>PRODUKTUAK</b>", 
                ParagraphStyle(
                    'SectionTitle',
                    parent=normal_style,
                    fontSize=16,
                    textColor=colors.HexColor('#2c3e50'),
                    spaceAfter=15,
                    fontName='Helvetica-Bold'
                )
            )
            elements.append(section_title)
            
            items = order_data.get('elementuak', [])
            if items and isinstance(items, list) and len(items) > 0:
                # Table header with better formatting
                header_style = ParagraphStyle(
                    'TableHeader',
                    parent=normal_style,
                    fontSize=11,
                    fontName='Helvetica-Bold',
                    textColor=colors.white,
                    alignment=1
                )
                
                table_data = [
                    [
                        Paragraph("<b>PRODUKTUA</b>", header_style),
                        Paragraph("<b>KANTITATEA</b>", header_style),
                        Paragraph("<b>PREZIOA UNITATEA</b>", header_style),
                        Paragraph("<b>GUZTIRA</b>", header_style)
                    ]
                ]
                
                # Table rows with improved formatting
                subtotal = 0.0
                items_added = 0
                row_style = ParagraphStyle('TableRow', parent=normal_style, fontSize=10)
                price_style = ParagraphStyle('PriceRow', parent=normal_style, fontSize=10, alignment=2)  # Right align
                
                for item in items:
                    if isinstance(item, dict):
                        try:
                            product_name = str(item.get('izena', 'Produktu ezezaguna'))
                            quantity = item.get('kantitatea', 0)
                            price = item.get('prezioa', 0.0)
                            
                            # Convert to float safely
                            try:
                                quantity = float(quantity) if quantity else 0.0
                                price = float(price) if price else 0.0
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Error converting quantity/price to float: {str(e)}")
                                continue
                            
                            if quantity <= 0 or price < 0:
                                logger.warning(f"Invalid quantity or price: quantity={quantity}, price={price}")
                                continue
                            
                            item_total = quantity * price
                            subtotal += item_total
                            
                            # Format numbers with proper spacing
                            quantity_str = f"{int(quantity):,}".replace(',', '.')
                            price_str = f"{price:.2f} €"
                            total_str = f"{item_total:.2f} €"
                            
                            table_data.append([
                                Paragraph(product_name, row_style),
                                Paragraph(quantity_str, ParagraphStyle('QuantityRow', parent=normal_style, fontSize=10, alignment=1)),  # Center
                                Paragraph(price_str, price_style),
                                Paragraph(total_str, price_style)
                            ])
                            items_added += 1
                        except Exception as e:
                            logger.warning(f"Error processing order item: {str(e)}")
                            continue
                
                # Check if we have any items
                if items_added == 0:
                    logger.warning("No valid items found in order for PDF generation")
                    elements.append(Paragraph("Ez da produkturik aurkitu eskaera honetan.", normal_style))
                else:
                    # Totals section with improved formatting
                    entrega_kostua = 5.0 if subtotal < 50 else 0.0
                    total = subtotal + entrega_kostua
                    
                    # Separator row
                    table_data.append(['', '', '', ''])
                    
                    # Totals rows with better styling
                    total_label_style = ParagraphStyle(
                        'TotalLabel',
                        parent=normal_style,
                        fontSize=11,
                        fontName='Helvetica-Bold',
                        alignment=2,  # Right align
                        textColor=colors.HexColor('#2c3e50')
                    )
                    total_value_style = ParagraphStyle(
                        'TotalValue',
                        parent=normal_style,
                        fontSize=11,
                        fontName='Helvetica-Bold',
                        alignment=2,  # Right align
                        textColor=colors.HexColor('#2c3e50')
                    )
                    
                    table_data.append([
                        '',
                        '',
                        Paragraph('<b>Azpitotala:</b>', total_label_style),
                        Paragraph(f'<b>{subtotal:.2f} €</b>', total_value_style)
                    ])
                    
                    if entrega_kostua > 0:
                        table_data.append([
                            '',
                            '',
                            Paragraph('<b>Bidalketa:</b>', total_label_style),
                            Paragraph(f'<b>{entrega_kostua:.2f} €</b>', total_value_style)
                        ])
                    else:
                        table_data.append([
                            '',
                            '',
                            Paragraph('Bidalketa:', ParagraphStyle('ShippingLabel', parent=normal_style, fontSize=10, alignment=2, textColor=colors.HexColor('#7f8c8d'))),
                            Paragraph('Doan', ParagraphStyle('ShippingValue', parent=normal_style, fontSize=10, alignment=2, textColor=colors.HexColor('#27ae60'), fontName='Helvetica-Bold'))
                        ])
                    
                    # Grand total row
                    grand_total_style = ParagraphStyle(
                        'GrandTotal',
                        parent=normal_style,
                        fontSize=13,
                        fontName='Helvetica-Bold',
                        alignment=2,
                        textColor=colors.white
                    )
                    
                    table_data.append([
                        '',
                        '',
                        Paragraph('<b>GUZTIRA:</b>', grand_total_style),
                        Paragraph(f'<b>{total:.2f} €</b>', grand_total_style)
                    ])
                    
                    # Create table with enhanced styling
                    items_table = Table(table_data, colWidths=[105*mm, 22*mm, 28*mm, 25*mm])
                    items_table.setStyle(TableStyle([
                        # Header row - Dark blue background
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 14),
                        ('TOPPADDING', (0, 0), (-1, 0), 14),
                        # Product rows - alternating colors
                        ('ALIGN', (0, 1), (0, -5), 'LEFT'),
                        ('ALIGN', (1, 1), (1, -5), 'CENTER'),
                        ('ALIGN', (2, 1), (2, -5), 'RIGHT'),
                        ('ALIGN', (3, 1), (3, -5), 'RIGHT'),
                        ('VALIGN', (0, 1), (-1, -5), 'MIDDLE'),
                        ('FONTNAME', (0, 1), (-1, -5), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -5), 10),
                        ('TOPPADDING', (0, 1), (-1, -5), 10),
                        ('BOTTOMPADDING', (0, 1), (-1, -5), 10),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -5), [colors.white, colors.HexColor('#f8f9fa')]),
                        # Separator row (empty row before totals)
                        ('BACKGROUND', (0, -4), (-1, -4), colors.white),
                        ('TOPPADDING', (0, -4), (-1, -4), 5),
                        ('BOTTOMPADDING', (0, -4), (-1, -4), 5),
                        # Totals section - Light gray background
                        ('BACKGROUND', (0, -3), (-1, -2), colors.HexColor('#ecf0f1')),
                        ('VALIGN', (0, -3), (-1, -2), 'MIDDLE'),
                        ('TOPPADDING', (0, -3), (-1, -2), 12),
                        ('BOTTOMPADDING', (0, -3), (-1, -2), 12),
                        # Grand total row - Blue background
                        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#3498db')),
                        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
                        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, -1), (-1, -1), 14),
                        ('BOTTOMPADDING', (0, -1), (-1, -1), 14),
                        ('FONTSIZE', (0, -1), (-1, -1), 13),
                        # Borders
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1a252f')),  # Thicker line below header
                        ('LINEBELOW', (0, -5), (-1, -5), 1.5, colors.HexColor('#95a5a6')),  # Line before totals
                        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#2980b9')),  # Line above grand total
                        # Padding
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ]))
                    elements.append(KeepTogether(items_table))
            else:
                logger.warning(f"No items found in order_data for PDF. Items: {items}")
                elements.append(Paragraph("Ez da produkturik aurkitu eskaera honetan.", normal_style))
            
            elements.append(Spacer(1, 30))
            
            # Additional info section
            info_section = [
                [Paragraph("<b>Oharrak:</b>", ParagraphStyle('InfoLabel', parent=normal_style, fontSize=10, fontName='Helvetica-Bold'))],
                [Paragraph("• Faktura hau zure erosketaren erregistro ofiziala da.", normal_style)],
                [Paragraph("• Galderak edo zalantzak badituzu, gure bezeroen arreta zerbitzuarekin harremanetan jarri.", normal_style)],
                [Paragraph("• Produktuak jasotzean, mesedez egiaztatu dena ondo dagoela.", normal_style)],
            ]
            
            info_section_table = Table(info_section, colWidths=[180*mm])
            info_section_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(info_section_table)
            elements.append(Spacer(1, 20))
            
            # Footer with company info
            footer_data = [
                [Spacer(1, 10)],
                [Paragraph("<b>Eskerrik asko zure erosketagatik!</b>", ParagraphStyle(
                    'FooterThanks',
                    parent=normal_style,
                    fontSize=12,
                    textColor=colors.HexColor('#2c3e50'),
                    alignment=1,
                    fontName='Helvetica-Bold'
                ))],
                [Spacer(1, 5)],
                [Paragraph("OtherProteins - Zure osasunaren bazkidea", ParagraphStyle(
                    'FooterCompany',
                    parent=normal_style,
                    fontSize=9,
                    textColor=colors.HexColor('#7f8c8d'),
                    alignment=1
                ))],
                [Paragraph(f"Faktura sortze data: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ParagraphStyle(
                    'FooterDate',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.HexColor('#95a5a6'),
                    alignment=1
                ))]
            ]
            
            footer_table = Table(footer_data, colWidths=[180*mm])
            footer_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(footer_table)
            
            # Build PDF
            doc.build(elements)
            buffer.seek(0)
            return buffer
        except ImportError as e:
            logger.error(f"reportlab library is not installed: {str(e)}")
            logger.error("Please install reportlab with: pip install reportlab")
            return None
        except Exception as e:
            logger.error(f"Error generating PDF invoice: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            # Log order data for debugging (without sensitive info)
            logger.error(f"Order data keys: {list(order_data.keys()) if isinstance(order_data, dict) else 'Not a dict'}")
            if isinstance(order_data, dict):
                logger.error(f"Order ID: {order_data.get('eskaera_id', 'N/A')}")
                logger.error(f"Order items count: {len(order_data.get('elementuak', [])) if isinstance(order_data.get('elementuak'), list) else 'N/A'}")
            return None

    @app.route('/order/<int:order_id>/invoice')
    def download_invoice(order_id):
        """Download PDF invoice/ticket for an order."""
        try:
            # Validate order_id
            if not isinstance(order_id, int) or order_id <= 0:
                logger.warning(f"Invalid order_id in download_invoice: {order_id}")
                flash('Eskaera ID baliogabea.', 'danger')
                return redirect(url_for('orders'))
            
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi faktura deskargatzeko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.warning(f"Invalid user_id in download_invoice: {user_id}")
                flash('Erabiltzaile ID baliogabea.', 'warning')
                return redirect(url_for('login'))
            
            # Get order details
            try:
                order = get_order_details(order_id)
            except Exception as e:
                logger.error(f"Error getting order details in download_invoice: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da eskaera eskuratzean.', 'danger')
                return redirect(url_for('orders'))
            
            if not order or not isinstance(order, dict):
                flash('Eskaera ez da aurkitu.', 'danger')
                return redirect(url_for('orders'))
            
            # Verify ownership (unless admin)
            order_user_id = order.get('erabiltzaile_id')
            user_email = session.get('user_email', '')
            is_user_admin = session.get('is_admin', False)
            if not is_user_admin and (not order_user_id or order_user_id != user_id):
                logger.warning(f"User {user_id} tried to download invoice for order {order_id} belonging to user {order_user_id}")
                flash('Eskaera hau zure kontuarena ez da.', 'danger')
                return redirect(url_for('orders'))
            
            # Check if order belongs to admin - if so, require invoice data
            order_user_id = order.get('erabiltzaile_id')
            order_user_info = None
            if order_user_id:
                try:
                    order_user_info = get_user_by_id(order_user_id)
                except Exception as e:
                    logger.warning(f"Error getting order user info: {str(e)}")
            
            # Check if order was made by admin@gmail.com
            order_user_email = None
            if order_user_info:
                order_user_email = order_user_info.get('helbide_elektronikoa', '')
            
            # If order belongs to admin, require invoice data (client data for physical store)
            if order_user_email == 'admin@gmail.com':
                # Check if invoice data is in session (from form)
                invoice_data = session.get('invoice_user_data', None)
                if not invoice_data:
                    # Store order_id in session to redirect back after providing data
                    session['pending_invoice_order_id'] = order_id
                    flash('Mesedez, sartu bezeroaren datuak faktura sortu aurretik.', 'warning')
                    return redirect(url_for('admin_complete_profile'))
            
            # Generate PDF
            try:
                # Get invoice data from session if order belongs to admin (client data for physical store)
                invoice_user_data = None
                if order_user_email == 'admin@gmail.com':
                    # Get invoice data from session (already verified above)
                    invoice_user_data = session.get('invoice_user_data', None)
                    # Clear session data after use
                    if invoice_user_data:
                        session.pop('invoice_user_data', None)
                # For regular users, invoice_user_data will be None, so PDF will use database data
                
                pdf_buffer = generate_invoice_pdf(order, invoice_user_data=invoice_user_data)
                if not pdf_buffer:
                    logger.error(f"generate_invoice_pdf returned None for order {order_id}")
                    flash('Errorea gertatu da faktura sortzean. Mesedez, saiatu berriro edo jarri harremanetan laguntza teknikorekin.', 'danger')
                    return redirect(url_for('order_detail', order_id=order_id))
            except Exception as e:
                logger.error(f"Exception calling generate_invoice_pdf: {type(e).__name__}: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da faktura sortzean. Mesedez, saiatu berriro.', 'danger')
                return redirect(url_for('order_detail', order_id=order_id))
            
            # Create response
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename=faktura_{order_id}.pdf'
            return response
        except Exception as e:
            logger.error(f"Unexpected error in download_invoice: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('orders'))

    @app.route('/admin/complete-profile', methods=['GET', 'POST'])
    def admin_complete_profile():
        """Form for admin to complete profile before generating invoice."""
        try:
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            user_email = session.get('user_email', '')
            
            # Only allow admin@gmail.com
            if user_email != 'admin@gmail.com':
                flash('Bakarrik administratzaileak erabil dezakete orri hau.', 'danger')
                return redirect(url_for('index'))
            
            # Get current user info
            user_info = get_user_by_id(user_id)
            if not user_info:
                flash('Erabiltzailea ez da aurkitu.', 'danger')
                return redirect(url_for('index'))
            
            # For admin, form should be empty (admin enters client data, not their own)
            # If there's invoice data in session, use it (admin might have started filling it)
            form_data = {
                'izena': '',
                'abizenak': '',
                'helbide_elektronikoa': '',
                'telefonoa': ''
            }
            
            session_invoice_data = session.get('invoice_user_data', None)
            if session_invoice_data:
                form_data.update(session_invoice_data)
            
            if request.method == 'POST':
                # Get form data
                first_name = request.form.get('izena', '').strip()
                last_name = request.form.get('abizenak', '').strip()
                email = request.form.get('helbide_elektronikoa', '').strip()
                phone = request.form.get('telefonoa', '').strip()
                
                # Validate required fields
                errors = []
                if not first_name:
                    errors.append('Izena beharrezkoa da.')
                if not last_name:
                    errors.append('Abizenak beharrezkoak dira.')
                if not email:
                    errors.append('Email beharrezkoa da.')
                elif '@' not in email:
                    errors.append('Email baliogabea.')
                if not phone:
                    errors.append('Telefono zenbakia beharrezkoa da.')
                
                if errors:
                    for error in errors:
                        flash(error, 'danger')
                    # Return form with submitted data
                    form_data = {
                        'izena': first_name,
                        'abizenak': last_name,
                        'helbide_elektronikoa': email,
                        'telefonoa': phone
                    }
                    return render_template('admin_complete_profile.html', user=user_info, form_data=form_data)
                
                # Store invoice data in session (don't update database)
                # These data will only be used for the invoice PDF
                invoice_data = {
                    'izena': first_name,
                    'abizenak': last_name,
                    'helbide_elektronikoa': email,
                    'telefonoa': phone
                }
                session['invoice_user_data'] = invoice_data
                
                flash('Fakturako datuak gorde dira.', 'success')
                
                # Redirect to invoice if there was a pending invoice
                pending_order_id = session.pop('pending_invoice_order_id', None)
                if pending_order_id:
                    return redirect(url_for('download_invoice', order_id=pending_order_id))
                else:
                    return redirect(url_for('orders'))
            
            return render_template('admin_complete_profile.html', user=user_info, form_data=form_data)
        except Exception as e:
            logger.error(f"Unexpected error in admin_complete_profile: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
            return redirect(url_for('index'))

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
            
            # Get sorting parameters
            order_by = request.args.get('order_by', 'produktu_id')
            direction = request.args.get('direction', 'asc')
            
            # Validate order_by column (security: prevent SQL injection)
            allowed_columns = {
                'produktu_id': 'produktu_id',
                'izena': 'izena',
                'prezioa': 'prezioa',
                'stocka': 'stocka',
                'irudi_urla': 'irudi_urla'
            }
            order_by = allowed_columns.get(order_by, 'produktu_id')
            
            # Validate direction
            if direction not in ['asc', 'desc']:
                direction = 'asc'
            
            # Get all products with sorting
            try:
                products = get_all_products(order_by=order_by, direction=direction)
            except Exception as e:
                logger.error(f"Error getting products in admin_stock: {str(e)}")
                logger.error(traceback.format_exc())
                flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
                products = []
            
            if not isinstance(products, list):
                products = []
            
            return render_template('admin_stock.html', products=products, order_by=order_by, direction=direction)
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
            name_updated_count = 0
            price_updated_count = 0
            image_updated_count = 0
            description_updated_count = 0
            failed_count = 0
            failed_products = []
            
            # Track unique products that were updated (by field type)
            products_with_stock_update = set()
            products_with_name_update = set()
            products_with_price_update = set()
            products_with_image_update = set()
            products_with_description_update = set()
            
            # Process all product updates from the form
            processed_products = set()  # Track which products we've processed
            
            # First, process stock updates
            for key, value in request.form.items():
                if key.startswith('stock_change_'):
                    try:
                        product_id = int(key.replace('stock_change_', ''))
                        if product_id in processed_products:
                            continue
                        processed_products.add(product_id)
                        
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
                            flash(f'⚠️ {product_name} produktuaren stock-a ezin da {new_stock} unitatera jaitsi. Gutxienez 0 unitate izan behar du. Uneko stocka: {current_stock} unitate, aldaketa: {stock_change} unitate.', 'warning')
                            failed_count += 1
                            failed_products.append(product_name)
                            continue
                        
                        # Update stock
                        try:
                            success = update_product_stock(product_id, new_stock)
                            if success:
                                updated_count += 1
                                products_with_stock_update.add(product_id)
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
            
            # Process product name updates
            for key, value in request.form.items():
                if key.startswith('product_name_'):
                    try:
                        product_id = int(key.replace('product_name_', ''))
                        new_name = value.strip() if value else None
                        
                        if not new_name or len(new_name) == 0:
                            continue  # Skip empty names
                        
                        # Get current product to compare
                        try:
                            product = get_product_by_id(product_id)
                            if not product:
                                logger.warning(f"Product {product_id} not found for name update")
                                continue
                            
                            current_name = product.get('izena', '').strip()
                            if current_name == new_name:
                                continue  # No change needed
                            
                            # Update product name
                            success = update_product_name(product_id, new_name)
                            if success:
                                name_updated_count += 1
                                products_with_name_update.add(product_id)
                            else:
                                logger.warning(f"Failed to update name for product {product_id}")
                        except Exception as e:
                            logger.error(f"Error updating name for product {product_id}: {str(e)}")
                            logger.error(traceback.format_exc())
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing name data: {key} = {value}, error: {str(e)}")
                        continue
            
            # Process product price updates
            for key, value in request.form.items():
                if key.startswith('product_price_'):
                    try:
                        product_id = int(key.replace('product_price_', ''))
                        try:
                            new_price = float(value) if value else None
                            if new_price is None or new_price < 0:
                                continue  # Skip invalid prices
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid price value for product {product_id}: {value}")
                            continue
                        
                        # Get current product to compare
                        try:
                            product = get_product_by_id(product_id)
                            if not product:
                                logger.warning(f"Product {product_id} not found for price update")
                                continue
                            
                            current_price = product.get('prezioa', 0)
                            try:
                                current_price = float(current_price) if current_price else 0.0
                            except (ValueError, TypeError):
                                current_price = 0.0
                            
                            # Round to 2 decimal places for comparison
                            new_price = round(new_price, 2)
                            current_price = round(current_price, 2)
                            
                            if current_price == new_price:
                                continue  # No change needed
                            
                            # Update product price
                            success = update_product_price(product_id, new_price)
                            if success:
                                price_updated_count += 1
                                products_with_price_update.add(product_id)
                            else:
                                logger.warning(f"Failed to update price for product {product_id}")
                        except Exception as e:
                            logger.error(f"Error updating price for product {product_id}: {str(e)}")
                            logger.error(traceback.format_exc())
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing price data: {key} = {value}, error: {str(e)}")
                        continue
            
            # Process product image URL updates
            for key, value in request.form.items():
                if key.startswith('product_image_'):
                    try:
                        product_id = int(key.replace('product_image_', ''))
                        new_image_url = value.strip() if value else ''
                        
                        # Get current product to compare
                        try:
                            product = get_product_by_id(product_id)
                            if not product:
                                logger.warning(f"Product {product_id} not found for image update")
                                continue
                            
                            current_image_url = product.get('irudi_urla', '') or ''
                            current_image_url = current_image_url.strip()
                            
                            if current_image_url == new_image_url:
                                continue  # No change needed
                            
                            # Update product image URL
                            success = update_product_image(product_id, new_image_url)
                            if success:
                                image_updated_count += 1
                                products_with_image_update.add(product_id)
                            else:
                                logger.warning(f"Failed to update image URL for product {product_id}")
                        except Exception as e:
                            logger.error(f"Error updating image URL for product {product_id}: {str(e)}")
                            logger.error(traceback.format_exc())
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing image data: {key} = {value}, error: {str(e)}")
                        continue
            
            # Process product description updates
            for key, value in request.form.items():
                if key.startswith('product_description_'):
                    try:
                        product_id = int(key.replace('product_description_', ''))
                        new_description = value.strip() if value else ''
                        
                        # Get current product to compare
                        try:
                            product = get_product_by_id(product_id)
                            if not product:
                                logger.warning(f"Product {product_id} not found for description update")
                                continue
                            
                            current_description = product.get('deskribapena', '') or ''
                            current_description = current_description.strip()
                            
                            if current_description == new_description:
                                continue  # No change needed
                            
                            # Update product description
                            success = update_product_description(product_id, new_description)
                            if success:
                                description_updated_count += 1
                                products_with_description_update.add(product_id)
                            else:
                                logger.warning(f"Failed to update description for product {product_id}")
                        except Exception as e:
                            logger.error(f"Error updating description for product {product_id}: {str(e)}")
                            logger.error(traceback.format_exc())
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing description data: {key} = {value}, error: {str(e)}")
                        continue
            
            # Show appropriate message in Basque
            # Count unique products updated (not individual field updates)
            all_updated_products = (products_with_stock_update | products_with_name_update | 
                                  products_with_price_update | products_with_image_update | 
                                  products_with_description_update)
            unique_products_count = len(all_updated_products)
            
            # Build update details list (what fields were updated)
            update_details = []
            if len(products_with_stock_update) > 0:
                update_details.append('stock-a')
            if len(products_with_name_update) > 0:
                update_details.append('izena')
            if len(products_with_price_update) > 0:
                update_details.append('prezioa')
            if len(products_with_image_update) > 0:
                update_details.append('irudia')
            if len(products_with_description_update) > 0:
                update_details.append('deskribapena')
            
            if unique_products_count > 0 and failed_count == 0:
                # All updates successful
                if unique_products_count == 1:
                    if len(update_details) == 1:
                        flash(f'✅ Produktu baten {update_details[0]} ondo eguneratu da.', 'success')
                    else:
                        flash(f'✅ Produktu baten {", ".join(update_details[:-1])} eta {update_details[-1]} ondo eguneratu dira.', 'success')
                else:
                    if len(update_details) == 1:
                        flash(f'✅ {unique_products_count} produkturen {update_details[0]} ondo eguneratu da.', 'success')
                    else:
                        flash(f'✅ {unique_products_count} produkturen {", ".join(update_details[:-1])} eta {update_details[-1]} ondo eguneratu dira.', 'success')
                    
            elif unique_products_count > 0 and failed_count > 0:
                # Some updates successful, some failed
                if unique_products_count == 1:
                    if len(update_details) == 1:
                        flash(f'⚠️ Produktu baten {update_details[0]} eguneratu da, baina {failed_count} produktutan errorea gertatu da.', 'warning')
                    else:
                        flash(f'⚠️ Produktu baten {", ".join(update_details[:-1])} eta {update_details[-1]} eguneratu dira, baina {failed_count} produktutan errorea gertatu da.', 'warning')
                else:
                    if len(update_details) == 1:
                        flash(f'⚠️ {unique_products_count} produkturen {update_details[0]} eguneratu da, baina {failed_count} produktutan errorea gertatu da.', 'warning')
                    else:
                        flash(f'⚠️ {unique_products_count} produkturen {", ".join(update_details[:-1])} eta {update_details[-1]} eguneratu dira, baina {failed_count} produktutan errorea gertatu da.', 'warning')
                
                if failed_products:
                    if len(failed_products) == 1:
                        flash(f'❌ Errorea gertatu da produktu honetan: {failed_products[0]}', 'warning')
                    else:
                        flash(f'❌ Errorea gertatu da produktu hauetan: {", ".join(failed_products[:5])}{"..." if len(failed_products) > 5 else ""}', 'warning')
                        
            elif failed_count > 0:
                # All updates failed
                flash('❌ Errorea gertatu da produktuen datuak eguneratzean.', 'danger')
                if failed_products:
                    if len(failed_products) == 1:
                        flash(f'Produktu honetan errorea: {failed_products[0]}', 'danger')
                    else:
                        flash(f'Produktu hauetan errorea: {", ".join(failed_products[:5])}{"..." if len(failed_products) > 5 else ""}', 'danger')
            else:
                # No changes made
                flash('ℹ️ Ez da aldaketarik egin. Produktuen datuak berdinak dira.', 'info')
            
            # Preserve sorting parameters when redirecting
            # Get from URL args (form action includes them) or default
            order_by = request.args.get('order_by') or request.form.get('order_by') or 'produktu_id'
            direction = request.args.get('direction') or request.form.get('direction') or 'asc'
            return redirect(url_for('admin_stock', order_by=order_by, direction=direction))
        except Exception as e:
            logger.error(f"Unexpected error in admin_update_stock: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('❌ Errore larria gertatu da produktuen datuak eguneratzean. Mesedez, saiatu berriro.', 'danger')
            # Preserve sorting parameters when redirecting
            order_by = request.args.get('order_by') or request.form.get('order_by') or 'produktu_id'
            direction = request.args.get('direction') or request.form.get('direction') or 'asc'
            return redirect(url_for('admin_stock', order_by=order_by, direction=direction))

    @app.route('/admin/stock/delete/<int:product_id>', methods=['POST'])
    def admin_delete_product(product_id):
        """Delete a product from the database."""
        try:
            # Check if user is logged in
            if 'user_id' not in session:
                flash('Mesedez, saioa hasi produktua ezabatzeko.', 'warning')
                return redirect(url_for('login'))
            
            user_id = session.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                flash('Erabiltzaile ID baliogabea.', 'warning')
                return redirect(url_for('login'))
            
            # Check if user is admin
            if not session.get('is_admin', False):
                if not is_admin(user_id):
                    flash('Ez duzu baimenik produktua ezabatzeko.', 'danger')
                    return redirect(url_for('index'))
                session['is_admin'] = True
            
            # Get product info before deletion for flash message
            product = get_product_by_id(product_id)
            product_name = product.get('izena', f'Produktua {product_id}') if product else f'Produktua {product_id}'
            
            # Delete the product
            success = delete_product(product_id)
            
            if success:
                flash(f'✅ {product_name} produktua ondo ezabatu da.', 'success')
            else:
                flash(f'❌ Errorea gertatu da {product_name} produktua ezabatzean.', 'danger')
            
            # Preserve sorting parameters when redirecting
            order_by = request.args.get('order_by', 'produktu_id')
            direction = request.args.get('direction', 'asc')
            return redirect(url_for('admin_stock', order_by=order_by, direction=direction))
            
        except Exception as e:
            logger.error(f"Unexpected error in admin_delete_product: {type(e).__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('❌ Errore larria gertatu da produktua ezabatzean. Mesedez, saiatu berriro.', 'danger')
            # Preserve sorting parameters when redirecting
            order_by = request.args.get('order_by', 'produktu_id')
            direction = request.args.get('direction', 'asc')
            return redirect(url_for('admin_stock', order_by=order_by, direction=direction))

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
