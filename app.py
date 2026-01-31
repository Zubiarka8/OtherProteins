
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
    get_product_by_id
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
        
        # Add product to cart
        if add_to_cart_db(user_id, produktu_id, 1):
            product_name = product.get('izena', 'Produktua')
            flash(f'{product_name} saskira ondo gehitu da!', 'success')
        else:
            flash('Errorea gertatu da produktua gehitzean.', 'danger')
        
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
