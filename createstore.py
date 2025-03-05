from app import db, Store, app  # Import app from main Flask file

with app.app_context():  # ✅ FIX: Create an application context
    # Create a new store
    new_store = Store(name="Test Store 2", username="store2", password="password123", is_admin=False)

    # Add to database
    db.session.add(new_store)
    db.session.commit()

    # Confirm store added
    print("Store 'Test Store' created successfully!")
