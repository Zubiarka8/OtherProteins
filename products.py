
from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.exceptions import abort
import logging
import traceback

# Configure logging
logger = logging.getLogger(__name__)

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
    try:
        if not products_db or not isinstance(products_db, dict):
            logger.error("products_db is invalid")
            flash('Errorea gertatu da produktuak eskuratzean.', 'danger')
            return render_template('products.html', products={})
        
        return render_template('products.html', products=products_db)
    except Exception as e:
        logger.error(f"Error in products index: {str(e)}")
        logger.error(traceback.format_exc())
        flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')
        return render_template('products.html', products={}), 500

@products_bp.route('/<int:product_id>/stock', methods=['POST'])
def update_stock(product_id):
    """Update stock for a given product."""
    try:
        # Validate product_id
        if not isinstance(product_id, int) or product_id <= 0:
            logger.warning(f"Invalid product_id: {product_id}")
            flash('Produktu ID baliogabea.', 'danger')
            return redirect(url_for('products.index'))
        
        if product_id not in products_db:
            logger.warning(f"Product {product_id} not found")
            abort(404)
        
        # Validate product data
        product = products_db.get(product_id)
        if not product or not isinstance(product, dict):
            logger.error(f"Invalid product data for ID {product_id}")
            flash('Produktuaren datuak baliogabeak dira.', 'danger')
            return redirect(url_for('products.index'))
        
        # Get and validate stock change
        try:
            stock_value = request.form.get('stock', '')
            if not stock_value or len(stock_value.strip()) == 0:
                flash('Stock balioa ezin da hutsik egon.', 'danger')
                return redirect(url_for('products.index'))
            
            stock_change = int(stock_value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid stock value: {request.form.get('stock')}")
            flash('Stock balioa zenbaki osoa izan behar da.', 'danger')
            return redirect(url_for('products.index'))
        
        # Validate current stock
        current_stock = product.get('stock', 0)
        if not isinstance(current_stock, (int, float)):
            logger.warning(f"Invalid current stock for product {product_id}: {current_stock}")
            current_stock = 0
        
        current_stock = int(current_stock)
        
        # Validate stock before updating
        new_stock = current_stock + stock_change
        if new_stock < 0:
            flash('Ez dago stock nahikorik. Ezin da stock negatiboa izan.', 'danger')
            return redirect(url_for('products.index'))
        
        # Prevent extremely large stock values
        if new_stock > 1000000:
            flash('Stock balioa handiegia da (gehienez 1.000.000).', 'danger')
            return redirect(url_for('products.index'))
        
        # Update stock
        try:
            products_db[product_id]['stock'] = new_stock
            flash('Stocka eguneratu da.', 'success')
        except (KeyError, TypeError) as e:
            logger.error(f"Error updating stock for product {product_id}: {str(e)}")
            logger.error(traceback.format_exc())
            flash('Errorea gertatu da stocka eguneratzean.', 'danger')
            
    except Exception as e:
        logger.error(f"Unexpected error in update_stock: {str(e)}")
        logger.error(traceback.format_exc())
        flash('Errore larria gertatu da. Mesedez, saiatu berriro.', 'danger')

    return redirect(url_for('products.index'))
