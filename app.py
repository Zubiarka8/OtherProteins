
from flask import Flask, render_template, request, flash, redirect, url_for, session
from datetime import datetime
from products import products_bp
from database import init_db
from db_utils import (
    get_all_products, 
    get_cart_items, 
    add_to_cart as add_to_cart_db, 
    create_order, 
    reduce_product_stock,
    get_user_by_email,
    get_product_by_id,
    verify_password,
    create_user,
    get_user_orders,
    get_order_details,
    update_cart_item,
    remove_from_cart,
    clear_cart
)

# Initialize database on import
init_db()

# App factory
def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = 'a_very_secret_key'  # Replace in production
    
    # Context processor for template variables (e.g., current year, cart count)
    @app.context_processor
    def inject_template_vars():
        cart_count = 0
        if 'user_id' in session:
            cart_items = get_cart_items(session['user_id'])
            cart_count = sum(item['kantitatea'] for item in cart_items)
        return dict(
            current_year=datetime.now().year,
            cart_count=cart_count
        )

    # Register Blueprints
    app.register_blueprint(products_bp, url_prefix='/products')

    @app.route('/')
    def index():
        """Render the main showcase page."""
        # Get products from database
        products = get_all_products()
        
        # Format products for template
        formatted_products = []
        for p in products:
            formatted_products.append({
                'id': p['produktu_id'],
                'izena': p['izena'],
                'deskribapena': p['deskribapena'],
                'prezioa': p['prezioa'],
                'stocka': p.get('stocka', 0),
                'irudi_urla': p.get('irudi_urla', 'https://via.placeholder.com/250x200')
            })
        
        # Get cart items if user is logged in
        cart_items = []
        if 'user_id' in session:
            cart_items = get_cart_items(session['user_id'])
        
        return render_template('index.html', produktuak=formatted_products, cart_items=cart_items)

    @app.route('/add_to_cart/<int:produktu_id>')
    def add_to_cart(produktu_id):
        """Add product to cart."""
        # For demo purposes, use user_id 1 if not logged in
        # In production, require login
        user_id = session.get('user_id', 1)
        
        # Get product information for flash message
        product = get_product_by_id(produktu_id)
        
        if not product:
            flash('Produktua ez da aurkitu.', 'danger')
            return redirect(url_for('index'))
        
        # Check stock before adding
        available_stock = product.get('stocka', 0)
        if available_stock <= 0:
            flash('Produktua ez dago stockean.', 'warning')
            return redirect(url_for('index'))
        
        # Add product to cart with stock validation
        success, message = add_to_cart_db(user_id, produktu_id, 1)
        if success:
            product_name = product.get('izena', 'Produktua')
            flash(f'{product_name} saskira ondo gehitu da!', 'success')
        else:
            flash(message, 'warning')
        
        return redirect(url_for('index'))

    @app.route('/produktu/<int:id>')
    def produktu_xehetasuna(id):
        """Render product detail page."""
        product = get_product_by_id(id)
        
        if not product:
            flash('Produktua ez da aurkitu.', 'danger')
            return redirect(url_for('index'))
        
        # Format product for template
        formatted_product = {
            'produktu_id': product['produktu_id'],
            'izena': product['izena'],
            'deskribapena': product.get('deskribapena', ''),
            'prezioa': product['prezioa'],
            'stocka': product.get('stocka', 0),
            'irudi_urla': product.get('irudi_urla', 'https://via.placeholder.com/500x500'),
            'kategoria_izena': product.get('kategoria_izena', ''),
            'osagaiak': product.get('osagaiak', ''),
            'balio_nutrizionalak': product.get('balio_nutrizionalak', ''),
            'erabilera_modua': product.get('erabilera_modua', '')
        }
        
        return render_template('product_detail.html', produktua=formatted_product)

    @app.route('/checkout', methods=['POST'])
    def checkout():
        """Process checkout: verify cart, reduce stock, create order, clear cart."""
        # Get user_id from session (default to 1 for demo)
        user_id = session.get('user_id', 1)
        
        # Get cart items
        cart_items = get_cart_items(user_id)
        
        # Verify cart is not empty
        if not cart_items:
            flash('Saskia hutsik dago. Ezin da erosketa burutu.', 'warning')
            return redirect(url_for('index'))
        
        # Verify stock availability and reduce stock
        all_stock_available = True
        insufficient_products = []
        
        for item in cart_items:
            product_id = item['produktu_id']
            quantity = item['kantitatea']
            
            # Check and reduce stock
            if not reduce_product_stock(product_id, quantity):
                all_stock_available = False
                insufficient_products.append(item.get('izena', f'Produktua {product_id}'))
        
        # If any product has insufficient stock, abort checkout
        if not all_stock_available:
            flash(f'Stock nahikorik ez dago produktu hau(et)an: {", ".join(insufficient_products)}', 'danger')
            return redirect(url_for('index'))
        
        # Create order
        order_id = create_order(user_id, status='prozesatzen')
        
        if order_id:
            flash('Erosketa ondo burutu da. Eskerrik asko zure konfiantzagatik!', 'success')
        else:
            flash('Errorea gertatu da erosketa prozesatzean.', 'danger')
        
        return redirect(url_for('index'))

    @app.route('/search')
    def search():
        """Search products by name or description."""
        query = request.args.get('q', '').strip()
        
        if not query:
            return redirect(url_for('index'))
        
        # Get all products and filter by query
        all_products = get_all_products()
        filtered_products = []
        
        query_lower = query.lower()
        for p in all_products:
            if (query_lower in p.get('izena', '').lower() or 
                query_lower in p.get('deskribapena', '').lower()):
                filtered_products.append({
                    'id': p['produktu_id'],
                    'izena': p['izena'],
                    'deskribapena': p['deskribapena'],
                    'prezioa': p['prezioa'],
                    'stocka': p.get('stocka', 0),
                    'irudi_urla': p.get('irudi_urla', 'https://via.placeholder.com/250x200')
                })
        
        return render_template('index.html', produktuak=filtered_products, 
                            search_query=query, cart_items=[])

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login page."""
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            
            if not email or not password:
                flash('Mesedez, bete eremu guztiak.', 'danger')
                return render_template('login.html')
            
            user = verify_password(email, password)
            if user:
                session['user_id'] = user['erabiltzaile_id']
                session['user_email'] = user['helbide_elektronikoa']
                session['user_name'] = f"{user['izena']} {user['abizenak']}"
                flash('Ongi etorri! Saioa ondo hasi da.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Helbide elektronikoa edo pasahitza okerra.', 'danger')
        
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """User registration page."""
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone = request.form.get('phone', '').strip()
            
            # Validation
            if not all([email, password, first_name, last_name]):
                flash('Mesedez, bete eremu beharrezko guztiak.', 'danger')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Pasahitzak ez datoz bat.', 'danger')
                return render_template('register.html')
            
            if len(password) < 6:
                flash('Pasahitzak gutxienez 6 karaktere izan behar ditu.', 'danger')
                return render_template('register.html')
            
            # Create user
            user_id = create_user(email, password, first_name, last_name, phone)
            if user_id:
                flash('Erregistroa ondo burutu da! Mesedez, saioa hasi.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Helbide elektronikoa jada erregistratuta dago.', 'danger')
        
        return render_template('register.html')

    @app.route('/logout')
    def logout():
        """Logout user."""
        session.clear()
        flash('Saioa ondo itxi da. Laster arte!', 'info')
        return redirect(url_for('index'))

    @app.route('/cart')
    def cart():
        """Display shopping cart."""
        user_id = session.get('user_id', 1)
        cart_items = get_cart_items(user_id)
        
        total = sum(item['kantitatea'] * item['prezioa'] for item in cart_items)
        
        return render_template('cart.html', cart_items=cart_items, total=total)

    @app.route('/update_cart', methods=['POST'])
    def update_cart():
        """Update cart item quantity."""
        user_id = session.get('user_id', 1)
        product_id = request.form.get('product_id', type=int)
        quantity = request.form.get('quantity', type=int)
        action = request.form.get('action', '')
        
        if action == 'remove':
            remove_from_cart(user_id, product_id)
            flash('Produktua saskitik kendu da.', 'success')
        elif action == 'increase':
            # Get current quantity and increase by 1
            cart_items = get_cart_items(user_id)
            current_item = next((item for item in cart_items if item['produktu_id'] == product_id), None)
            if current_item:
                new_quantity = current_item['kantitatea'] + 1
                success, message = update_cart_item(user_id, product_id, new_quantity)
                if success:
                    flash(message, 'success')
                else:
                    flash(message, 'warning')
            else:
                flash('Produktua ez da aurkitu saskian.', 'danger')
        elif action == 'decrease':
            # Get current quantity and decrease by 1
            cart_items = get_cart_items(user_id)
            current_item = next((item for item in cart_items if item['produktu_id'] == product_id), None)
            if current_item:
                new_quantity = max(1, current_item['kantitatea'] - 1)
                success, message = update_cart_item(user_id, product_id, new_quantity)
                if success:
                    flash(message, 'success')
                else:
                    flash(message, 'warning')
            else:
                flash('Produktua ez da aurkitu saskian.', 'danger')
        elif quantity and quantity > 0:
            success, message = update_cart_item(user_id, product_id, quantity)
            if success:
                flash(message, 'success')
            else:
                flash(message, 'warning')
        else:
            flash('Kantitate baliogabea.', 'danger')
        
        return redirect(url_for('cart'))

    @app.route('/orders')
    def orders():
        """Display user orders."""
        if 'user_id' not in session:
            flash('Mesedez, saioa hasi zure eskaerak ikusteko.', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        orders = get_user_orders(user_id)
        
        return render_template('orders.html', orders=orders)

    @app.route('/order/<int:order_id>')
    def order_detail(order_id):
        """Display order details."""
        if 'user_id' not in session:
            flash('Mesedez, saioa hasi zure eskaerak ikusteko.', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        
        # Get order details
        order = get_order_details(order_id)
        
        if not order:
            flash('Eskaera ez da aurkitu.', 'danger')
            return redirect(url_for('orders'))
        
        # Verify that the order belongs to the current user
        if order['erabiltzaile_id'] != user_id:
            flash('Eskaera hau zure kontuarena ez da.', 'danger')
            return redirect(url_for('orders'))
        
        # Calculate total
        total = sum(item['kantitatea'] * item['prezioa'] for item in order['elementuak'])
        order['total'] = total
        
        return render_template('order_detail.html', order=order)

    # Generic error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('500.html'), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
