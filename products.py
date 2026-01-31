
from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.exceptions import abort

# Dummy data to simulate a database
products_db = {
    1: {'name': 'Whey Protein', 'stock': 20},
    2: {'name': 'Creatine', 'stock': 15},
    3: {'name': 'BCAAs', 'stock': 30},
}

# Create a Blueprint for products
products_bp = Blueprint('products', __name__)

@products_bp.route('/')
def index():
    """Render the list of products."""
    return render_template('products.html', products=products_db)

@products_bp.route('/<int:product_id>/stock', methods=['POST'])
def update_stock(product_id):
    """Update stock for a given product."""
    if product_id not in products_db:
        abort(404)

    try:
        stock_change = int(request.form['stock'])
        
        # Validate stock before updating
        if products_db[product_id]['stock'] + stock_change < 0:
            flash('Ez dago stock nahikorik.', 'danger')
        else:
            products_db[product_id]['stock'] += stock_change
            flash('Stocka eguneratu da.', 'success')
            
    except (ValueError, KeyError):
        flash('Balio okerra sartu da.', 'danger')

    return redirect(url_for('products.index'))
