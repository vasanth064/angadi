from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import datetime

# Initialize Flask App
app = Flask(__name__, template_folder="templates")
app.secret_key = "supersecretkey"

# Set the URI for PostgreSQL Database
# Update with your credentials
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://myuser:mypassword@db:5432/mydatabase'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database and Flask-Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# User Model (Stores and Admins)


class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Admin Flag

# Product Model


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    hidden = db.Column(db.Boolean, default=False)  # Hide Product Option

# Helper Function for Timestamp


def current_timestamp():
    return datetime.datetime.now()

# Sales Model


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Keep for uniqueness
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    # Store-specific sale number
    sale_number = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    timestamp = db.Column(db.DateTime, default=current_timestamp)
    customer_name = db.Column(
        db.String(100), nullable=False, default="Unknown")
    customer_phone = db.Column(
        db.String(20), nullable=False, default="Not Provided")

    # Ensure uniqueness of sale_number per store
    __table_args__ = (db.UniqueConstraint(
        'store_id', 'sale_number', name='unique_store_sale_number'),)

# Sale Items Model


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey(
        'product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    # Relationship with Product model
    product = db.relationship('Product', backref='sale_items', lazy=True)

# Log Model


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=current_timestamp)

# Routes and Views


@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = Store.query.filter_by(username=username, password=password).first()

    if user:
        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    # If login fails, return to login page with error flag
    return render_template('login.html', error=True)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect(url_for('home'))
    store = Store.query.get(session['user_id'])
    products = Product.query.filter_by(store_id=session['user_id']).all()
    return render_template('dashboard.html', products=products, store_name=store.name)


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('home'))
    stores = Store.query.all()
    sales = Sale.query.all()
    return render_template('admin_dashboard.html', stores=stores, sales=sales)


@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    hidden = 'hidden' in request.form  # Checkbox for hiding product
    new_product = Product(
        store_id=session['user_id'], name=name, price=price, stock=stock, hidden=hidden)
    db.session.add(new_product)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/pos')
def pos():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    store = Store.query.get(session['user_id'])
    products = Product.query.filter_by(
        # Exclude hidden products
        store_id=session['user_id'], hidden=False).all()
    return render_template('pos.html', products=products, store_name=store.name)


@app.route('/process_sale', methods=['POST'])
def process_sale():
    if 'user_id' not in session:
        return redirect(url_for('home'))

    data = request.json
    store_id = session['user_id']
    items = data.get('items', [])
    customer_name = data.get('customer_name', "Unknown")
    customer_phone = data.get('customer_phone', "Not Provided")
    discount = data.get('discount', 0)

    total_amount = sum(float(item['price']) * int(item['quantity'])
                       for item in items) - float(discount)

    # Get the latest sale number for the store
    last_sale = Sale.query.filter_by(store_id=store_id).order_by(
        Sale.sale_number.desc()).first()
    # Start from 1 if no previous sale
    new_sale_number = (last_sale.sale_number + 1) if last_sale else 1

    # Create a new sale entry
    sale = Sale(store_id=store_id, sale_number=new_sale_number, total_amount=total_amount,
                customer_name=customer_name, customer_phone=customer_phone, discount=discount, timestamp=datetime.datetime.now())
    db.session.add(sale)
    db.session.commit()

    # Process sale items and update stock
    for item in items:
        product = Product.query.get(item['id'])
        if product and product.stock >= int(item['quantity']):
            product.stock -= int(item['quantity'])
            sale_item = SaleItem(sale_id=sale.id, product_id=product.id, quantity=int(
                item['quantity']), price=float(product.price))
            db.session.add(sale_item)

    db.session.commit()
    return jsonify({"message": "Sale completed!", "total": total_amount, "sale_number": new_sale_number})


@app.route('/sales_report')
def sales_report():
    if 'user_id' not in session:
        return redirect(url_for('home'))

    store = Store.query.get(session['user_id'])

    # Fetch sales with their associated SaleItems and Product names
    sales = Sale.query.filter_by(store_id=session['user_id']).all()

    for sale in sales:
        # Include related products when fetching sale items
        sale.items = SaleItem.query.filter_by(
            sale_id=sale.id).all()  # Sale items with related product

    return render_template('sales_report.html', sales=sales, store_name=store.name)


@app.route('/edit_product/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))

    product = Product.query.get_or_404(product_id)

    # Update the product details
    product.name = request.form['name']
    product.price = float(request.form['price'])
    product.stock = int(request.form['stock'])

    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/toggle_product_visibility', methods=['POST'])
def toggle_product_visibility():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    product_id = request.form['product_id']
    product = Product.query.get(product_id)
    if product:
        product.hidden = not product.hidden  # Toggle visibility
        db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clear the session data
    return redirect(url_for('home'))  # Redirect to the login page


# Start the Application with Migrations
if __name__ == '__main__':
    app.run(debug=True)
