from flask import Flask, request, render_template, redirect, url_for, session,flash,send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from db import db
from models import User, Note
import secrets
import sqlite3
import os

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'  # Directory to store uploaded files
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Secret key for sessions
app.secret_key = secrets.token_hex(16)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notesapp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the app
db.init_app(app)
def get_db_connection():
    # Connect to the SQLite database
    conn = sqlite3.connect('instance/notesapp.db')
    conn.row_factory = sqlite3.Row  # To return rows as dictionaries
    return conn
# Routes

@app.route('/Admin')
def index():
    # Fetch all table names from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    return render_template('index.html', tables=tables)

@app.route('/AdminLogin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin')  # Not needed in login; remove if unused

        # Debugging
        print(f"Login attempt: email={email}, is_admin={is_admin}")

        user = User.query.filter_by(email=email).first()

        if user:
            print(f"User found: username={user.username}, is_admin={user.is_admin}")
        else:
            print("No user found with this email.")

        if user and user.check_password(password):
            if not user.is_admin:
                print("User is not an admin.")
                return render_template('admin_login.html', error="You are not authorized as an admin.")
            
            # Set session and redirect
            session['user_email'] = user.email
            print(f"Admin login successful: {user.email}")
            return redirect(url_for('index'))
        else:
            print("Invalid email or password.")
            return render_template('admin_login.html', error="Invalid email or password")

    return render_template('admin_login.html')


@app.route('/AdminRegister', methods=['GET', 'POST'])
def Admin_register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin') == 'True'  # Convert to boolean

        # Debugging: Log form data
        print(f"username: {username}, email: {email}, is_admin: {is_admin}")

        # Check for existing user
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            print(f"Existing user found: {existing_user}")
            return render_template('admin_login.html', message="Username or email already exists.")

        # Create new user
        new_user = User(username=username, email=email, is_admin=is_admin)
        new_user.set_password(password)

        # Try committing to the database
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            print(f"Error adding new user: {e}")
            return render_template('admin_register.html', message="Error creating account.")

        return redirect(url_for('admin_login'))

    return render_template('admin_register.html')


@app.route('/table/<table_name>')
def view_table(table_name):
    # Fetch data from the specified table
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    conn.close()
    return render_template('table.html', rows=rows, column_names=column_names, table_name=table_name)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/profile')
def profile():
    # Check if the user is logged in
    user_email = session.get('user_email')
    if not user_email:
        flash("You need to log in to access your profile.", "error")
        return redirect(url_for('login'))

    # Fetch the logged-in user
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return "User not found", 404

    # Retrieve user-specific files (assuming files are stored in subfolders for each user)
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
    os.makedirs(user_folder, exist_ok=True)  # Ensure the user folder exists
    uploaded_files = os.listdir(user_folder)

    # Fetch the notes associated with the logged-in user
    notes = user.notes

    # Render the profile template with user data, notes, and files
    return render_template(
        'profile.html',
        username=user.username,
        notes=notes,
        files=uploaded_files
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_email'] = user.email  # Store the user's email in the session
            return redirect(url_for('profile'))
        else:
            return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_email', None)  
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            return render_template('register.html', message="Username or email already exists.")

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/add_note', methods=['GET', 'POST'])
def add_note():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_email = session.get('user_email')

        if not user_email:
            return redirect(url_for('login'))

        user = User.query.filter_by(email=user_email).first()
        if not user:
            return "User not found", 404

        new_note = Note(title=title, content=content, user_id=user.id)
        db.session.add(new_note)
        db.session.commit()

        flash("Note added successfully!")
        return redirect(url_for('profile'))

    return render_template('add_note.html')

@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if request.method == 'POST':
        note.title = request.form['title']
        note.content = request.form['content']
        db.session.commit()

        flash("Note updated successfully!")
        return redirect(url_for('profile'))

    return render_template('edit_note.html', note=note)

# Delete Note View
@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()

    flash("Note deleted successfully!")
    return redirect(url_for('profile'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('profile'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('profile'))

    # Check if the user is logged in
    user_email = session.get('user_email')
    if not user_email:
        flash('Please log in to upload files')
        return redirect(url_for('login'))

    # Retrieve the user's username
    user = User.query.filter_by(email=user_email).first()
    if not user:
        flash('User not found')
        return redirect(url_for('profile'))

    # Create a user-specific folder if it doesn't exist
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
    os.makedirs(user_folder, exist_ok=True)

    # Save the file in the user's folder
    if file:
        filename = secure_filename(file.filename)  # Sanitize the filename
        file_path = os.path.join(user_folder, filename)
        file.save(file_path)
        flash('File uploaded successfully')
        return redirect(url_for('profile'))

@app.route('/delete_file/<filename>', methods=['POST'])
def delete_file(filename):
    # Check if the user is logged in
    user_email = session.get('user_email')
    if not user_email:
        flash('Please log in to delete files')
        return redirect(url_for('login'))

    # Retrieve the user's username
    user = User.query.filter_by(email=user_email).first()
    if not user:
        flash('User not found')
        return redirect(url_for('profile'))

    # Construct the file path for the user's uploaded files
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user.username)
    file_path = os.path.join(user_folder, filename)

    # Check if the file exists
    if not os.path.exists(file_path):
        flash('File not found')
        return redirect(url_for('profile'))

    # Delete the file
    try:
        os.remove(file_path)
        flash('File deleted successfully')
    except Exception as e:
        flash(f'Error deleting file: {e}')

    return redirect(url_for('profile'))


# Serve uploaded files
@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables
    app.run(debug=True)
