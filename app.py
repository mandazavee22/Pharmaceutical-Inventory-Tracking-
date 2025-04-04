from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import pandas as pd
import io
import time
import webbrowser
import threading
from datetime import datetime
from models import db, User, InventoryItem  # Ensure InventoryItem is imported
from forms import InventoryItemForm  # Import the form for inventory items

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Database URI
db.init_app(app)

# Create the database
with app.app_context():
    db.create_all()
#    db.drop_all()

@app.route('/')
def index():
    return redirect(url_for('login'))  # Redirect to login

#Uncomment this for automatic page openning
def open_browser():
#    # Wait for the server to start
#    import time
    time.sleep(1)  # Adjust sleep time if necessary
    webbrowser.open_new('http://127.0.0.1:5000/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if user exists and password matches
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:  # Use hashed passwords in production
            session['username'] = username
            return redirect(url_for('home'))  # Redirect to home
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Password validation, at least 8 characters, letters and numbers only
        password_pattern = re.compile(r'^[A-Za-z0-9]{8,}$')
        if not password_pattern.match(password):
            flash('Password must be at least 8 characters long and contain only letters and numbers.')
            return render_template('register.html')

        # Check if username or email already exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or Email already exists')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('register.html')

        # Create new user
        new_user = User(email=email, username=username, password=password)  # Hash password in production
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/home')
def home():
    if 'username' in session:
        # Total Active Inventory (not used)
        total_inventory = InventoryItem.query.filter_by(used=False).count()

        # Total Expired Items
        total_expired_items = InventoryItem.query.filter(InventoryItem.expiry_date < datetime.now().date()).count()

        # Stockouts per category
        categories = ['Medical Equipments', 'Medical Drugs', 'Pharmaceuticals']
        stockouts = {category: InventoryItem.query.filter_by(category=category).count() < 50 for category in categories}

        # Inventory Trends Over Time (unused inventory by category)
        inventory_trends = {}
        for category in categories:
            unused_count = InventoryItem.query.filter_by(category=category, used=False).count()
            inventory_trends[category] = unused_count

        # Convert inventory_trends keys and values to lists
        inventory_trend_keys = list(inventory_trends.keys())
        inventory_trend_values = list(inventory_trends.values())

        # Usage Patterns (total used stock against active stock)
        used_inventory = InventoryItem.query.filter_by(used=True).count()

        return render_template('home.html', 
                               total_inventory=total_inventory, 
                               total_expired_items=total_expired_items, 
                               stockouts=stockouts,
                               inventory_trend_keys=inventory_trend_keys,
                               inventory_trend_values=inventory_trend_values,
                               used_inventory=used_inventory,
                               active_inventory=total_inventory)
    return redirect(url_for('login'))  # Redirect to login if not authenticated

@app.route('/inventory-management', methods=['GET', 'POST'])
def inventory_management():
    if 'username' in session:
        form = InventoryItemForm()
        if form.validate_on_submit():
            new_item = InventoryItem(
                category=form.category.data,
                name=form.name.data,
                quantity=form.quantity.data,
                expiry_date=form.expiry_date.data
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item added successfully!', 'success')
            return redirect(url_for('inventory_management'))  # Redirect to the inventory management page

        return render_template('inventory_management.html', form=form)  # Render inventory management page with form
    return redirect(url_for('login'))

@app.route('/add-items', methods=['GET', 'POST'])
def add_items():
    form = InventoryItemForm()  # Initialize the form
    if form.validate_on_submit():
        new_item = InventoryItem(
            category=form.category.data,
            name=form.name.data,
            quantity=form.quantity.data,
            expiry_date=form.expiry_date.data
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Item added successfully!', 'success')
        return redirect(url_for('view_items'))  # Redirect to the view items page

    return render_template('add_items.html', form=form)  # Render the standalone form

@app.route('/view-items', methods=['GET'])
def view_items():
    if 'username' in session:
        search_query = request.args.get('search', '')
        category_filter = request.args.get('category', '')

        # Build the query with filters
        query = InventoryItem.query
        if search_query:
            query = query.filter(InventoryItem.name.ilike(f'%{search_query}%'))  # Case-insensitive search
        if category_filter == 'expired':
            # Filter to get only expired items
            query = query.filter(InventoryItem.expiry_date < datetime.now().date())
        elif category_filter:
            query = query.filter(InventoryItem.category == category_filter)  # Filter by category
        
        inventory_items = query.all()  # Fetch filtered inventory items
        
        # Get unique categories for the filter dropdown
        categories = db.session.query(InventoryItem.category).distinct().all()
        categories = [cat[0] for cat in categories]  # Flatten the list of tuples

        # Add "Expired" option to categories for filtering
        categories.append("Expired")

        # Get the current date
        current_date = datetime.now().date()

        return render_template('view_items.html', inventory_items=inventory_items, categories=categories, current_date=current_date)
    return redirect(url_for('login'))  # Redirect to login if not authenticated

@app.route('/acquire-item/<int:item_id>', methods=['POST'])
def acquire_item(item_id):
    item_to_acquire = InventoryItem.query.get(item_id)
    if item_to_acquire:
        item_to_acquire.used = True  # Mark the item as used
        db.session.commit()
        flash('Item acquired successfully!', 'success')
        return redirect(url_for('view_items'))  # Redirect after acquiring the item
    flash('Item not found!', 'danger')
    return redirect(url_for('view_items'))

@app.route('/delete-item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    item_to_delete = InventoryItem.query.get(item_id)
    if item_to_delete and not item_to_delete.used:  # Ensure the item is not used
        db.session.delete(item_to_delete)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
    else:
        flash('Cannot delete item. It has been used or does not exist.', 'danger')
    return redirect(url_for('view_items'))


@app.route('/reports-analytics', methods=['GET', 'POST'])
def reports_analytics():
    if 'username' in session:
        # Fetch all available categories
        categories = InventoryItem.query.with_entities(InventoryItem.category).distinct().all()
        categories = [category[0] for category in categories]  # Extract category names

        # Start with a base query
        stock_query = InventoryItem.query
        
        # Initialize filter variables
        selected_category = None
        selected_status = None

        if request.method == 'POST':
            # Apply filters based on user input
            selected_category = request.form.get('category')
            selected_status = request.form.get('status')

            if selected_category and selected_category != "All":
                stock_query = stock_query.filter(InventoryItem.category == selected_category)
            if selected_status == 'active':
                stock_query = stock_query.filter_by(used=False)
            elif selected_status == 'used':
                stock_query = stock_query.filter_by(used=True)
            elif selected_status == 'expired':
                stock_query = stock_query.filter(InventoryItem.expiry_date < datetime.now().date())
        
        # Execute the query and convert to a list
        stock_items = stock_query.all()  # This will execute the query and return the results

        # Handle download requests
        if 'download' in request.form:
            format = request.form.get('format')
            if format == 'csv':
                return download_csv(stock_items)
            elif format == 'excel':
                return download_excel(stock_items)
            elif format == 'pdf':
                return download_pdf(stock_items)

        return render_template('reports_analytics.html', stock_items=stock_items, categories=categories, selected_category=selected_category, selected_status=selected_status)
    return redirect(url_for('login'))

def download_csv(stock_items):
    # Convert the stock items to a DataFrame
    data = [{'ID': item.id, 'Name': item.name, 'Category': item.category, 'Status': 'Active' if not item.used else 'Used', 'Expiry Date': item.expiry_date} for item in stock_items]
    df = pd.DataFrame(data)

    # Create a CSV in memory
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='filtered_report.csv'
    )

def download_excel(stock_items):
    # Convert the stock items to a DataFrame
    data = [{'ID': item.id, 'Name': item.name, 'Category': item.category, 'Status': 'Active' if not item.used else 'Used', 'Expiry Date': item.expiry_date} for item in stock_items]
    df = pd.DataFrame(data)

    # Create an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='filtered_report.xlsx'
    )

def download_pdf(stock_items):
    # Convert the stock items to a list of lists
    data = [[item.id, item.name, item.category, 'Active' if not item.used else 'Used', str(item.expiry_date)] for item in stock_items]
    data.insert(0, ['ID', 'Name', 'Category', 'Status', 'Expiry Date'])  # Add headers

    # Create a PDF in memory
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements = [table]
    pdf.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='filtered_report.pdf'
    )

@app.route('/help-support')
def help_support():
    if 'username' in session:
        
        contact_info = {
            'email': 'mandazavimbainashe9@gmail.com',  
            'linkedin': 'https://linkedin.com/in/vimbainashe-mandaza-8402a6324',  
            'whatsapp': 'https://wa.me/+263716700453',  
        }
        return render_template('help_support.html', contact_info=contact_info)  # Pass contact_info to the template
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Start the browser in a separate thread
    #uncomment the below line to initiate the browser automatic redict
    threading.Thread(target=open_browser).start()
    app.run(port='500', debug=True)