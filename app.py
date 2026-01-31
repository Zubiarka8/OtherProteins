
from flask import Flask, render_template
from products import products_bp

# Sample product data for the showcase
showcase_products = [
    {'name': 'Whey Protein Isolate', 'price': 55.00, 'stock': 15},
    {'name': 'Caseina Nocturna', 'price': 45.50, 'stock': 10},
    {'name': 'Barritas Energéticas', 'price': 25.00, 'stock': 30},
    {'name': 'Creatina Monohidratada', 'price': 22.99, 'stock': 25},
    {'name': 'Pre-entreno Intenso', 'price': 38.75, 'stock': 0}, 
]


# App factory
def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = 'a_very_secret_key'  # Replace in production

    # Register Blueprints
    app.register_blueprint(products_bp, url_prefix='/products')

    @app.route('/')
    def index():
        """Render the main showcase page."""
        return render_template('index.html', products=showcase_products)

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
