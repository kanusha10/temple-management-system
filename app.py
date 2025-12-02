from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import json
import os
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = 'replace_this_with_a_random_secret_key'

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
TEMPLES_FILE = os.path.join(DATA_DIR, 'temples.json')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
TX_FILE = os.path.join(DATA_DIR, 'transactions.json')

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"

# ---------------- JSON UTILS ----------------
def read_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_temple_by_id(tid):
    temples = read_json(TEMPLES_FILE)
    for t in temples:
        if str(t.get("id")) == str(tid):
            return t
    return None

@app.template_filter('format_date')
def format_date(value):
    if not value:
        return ''
    try:
        return datetime.fromisoformat(value).strftime('%Y-%m-%d')
    except:
        return value

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    temples = read_json(TEMPLES_FILE)
    for t in temples:
        t['current_crowd'] = random.randint(0, max(t.get('threshold', 100), 200))
    return render_template('home.html', temples=temples)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/book')
def book_list():
    temples = read_json(TEMPLES_FILE)
    return render_template('book_list.html', temples=temples)

@app.route('/temple/<temple_id>')
def temple_details(temple_id):
    temple = get_temple_by_id(temple_id)
    if not temple:
        return "Temple not found", 404
    return render_template("temple_details.html", temple=temple)

@app.route('/book/<temple_id>')
def book_temple(temple_id):
    if 'user' not in session:
        flash("Please login to book tickets.", "danger")
        return redirect(url_for('login', next=url_for('book_temple', temple_id=temple_id)))

    temple = get_temple_by_id(temple_id)
    return render_template('book_form.html', temple=temple, today=datetime.today().date())


@app.route('/submit_booking', methods=['POST'])
def submit_booking():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 401

    txs = read_json(TX_FILE)
    data = request.form.to_dict()
    user_email = session['user']['email']
    temple_id = data.get('temple_id')
    ticket_type = data.get('ticket_type')
    abhisheka_type = data.get('abhisheka_type') or ""
    selected_date = data.get('date')  # The date the user selects

    # ----------------- Booking Restrictions -----------------
    for t in txs:
        if t['user_email'] == user_email and t['date'] == selected_date:
            if t['temple_id'] == temple_id:
                flash("You already booked this temple on this day.", "danger")
                return redirect(url_for("book_temple", temple_id=temple_id))
            else:
                flash("You cannot book tickets in more than one temple on the same day.", "danger")
                return redirect(url_for("book_list"))

    # ----------------- Add Transaction -----------------
    new_tx = {
        "id": str(random.randint(100000, 999999)),
        "user_email": user_email,
        "temple_id": temple_id,
        "temple_name": get_temple_by_id(temple_id).get("name"),
        "first_name": data.get('first_name'),
        "last_name": data.get('last_name'),
        "gender": data.get('gender'),
        "email": data.get('email'),
        "phone": data.get('phone'),
        "ticket_type": ticket_type,
        "abhisheka_type": abhisheka_type,
        "date": selected_date,
        "amount": float(data.get('amount') or 0),
        "booked_at": datetime.now().isoformat()
    }

    txs.append(new_tx)
    write_json(TX_FILE, txs)

    flash("Booking successful!", "success")
    return redirect(url_for("transactions"))



@app.route('/transactions')
def transactions():
    if 'user' not in session:
        flash("Please login to view transactions.", "danger")
        return redirect(url_for('login'))

    txs = read_json(TX_FILE)
    user_email = session['user']['email']
    user_txs = [t for t in txs if t['user_email'] == user_email]

    return render_template("transactions.html", transactions=user_txs)

@app.route('/crowd')
def crowd():
    temples = read_json(TEMPLES_FILE)
    for t in temples:
        threshold = int(t.get('threshold', 100))
        t['current_crowd'] = random.randint(0, threshold * 2)

        # Compute textual status based on crowd
        if t['current_crowd'] < threshold * 0.5:
            t['status'] = "Low"
            t['status_color'] = "green"
        elif t['current_crowd'] < threshold:
            t['status'] = "Medium"
            t['status_color'] = "yellow"
        else:
            t['status'] = "High"
            t['status_color'] = "red"

    return render_template('crowd.html', temples=temples)


# ---------------- LOGIN / REGISTER ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or url_for("home")

    if request.method == 'POST':
        role = request.form.get('role')

        # ADMIN LOGIN
        if role == 'admin':
            username = request.form.get('username')
            password = request.form.get('password')

            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session['admin'] = {'username': ADMIN_USERNAME, 'email': ADMIN_EMAIL}
                flash("Admin logged in successfully.", "success")
                return redirect(url_for('home'))
            else:
                flash("Invalid admin credentials.", "danger")
                return redirect(url_for('login'))

        # USER LOGIN
        email = request.form.get('email')
        password = request.form.get('password')

        users = read_json(USERS_FILE)
        user = next((u for u in users if u['email'] == email and u.get('password') == password), None)

        if not user:
            flash("Invalid email or password!", "danger")
            return redirect(url_for('login'))

        session['user'] = {"email": user['email'], "first_name": user['first_name']}
        flash("Logged in successfully.", "success")
        return redirect(next_url)

    return render_template('login.html', next_url=next_url)

@app.route('/register_user', methods=['POST'])
def register_user():
    first_name = request.form.get('first_name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm = request.form.get('confirm_password')

    if password != confirm:
        flash("Passwords do not match!", "danger")
        return redirect(url_for('login'))

    users = read_json(USERS_FILE)
    if any(u['email'] == email for u in users):
        flash("Email already registered! Please login.", "warning")
        return redirect(url_for('login'))

    new_user = {"first_name": first_name, "email": email, "password": password}
    users.append(new_user)
    write_json(USERS_FILE, users)

    flash("Registration successful! Please login.", "success")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("home"))

# ---------------- ADMIN ADD TEMPLE ----------------
@app.route('/admin/add_temple', methods=['GET', 'POST'])
def add_temple():
    if 'admin' not in session:
        flash("Admin only.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        temples = read_json(TEMPLES_FILE)
        data = request.form.to_dict()

        abhi_types = [x.strip() for x in data.get('abhisheka_types', '').split(',') if x.strip()]
        abhi_amounts = [float(x) for x in data.get('abhisheka_amounts', '').split(',') if x.strip()]

        abhishekas = []
        for i, name in enumerate(abhi_types):
            amt = abhi_amounts[i] if i < len(abhi_amounts) else random.randint(1500, 5000)
            abhishekas.append({"name": name, "amount": amt})

        new_id = max([int(t['id']) for t in temples] or [0]) + 1
        new_temple = {
            "id": str(new_id),
            "name": data.get("name"),
            "location": data.get("location"),
            "open_time": data.get("open_time"),
            "close_time": data.get("close_time"),
            "threshold": int(data.get("threshold") or 100),
            "darshana_amount": float(data.get("darshana_amount") or 100),
            "abhishekas": abhishekas,
            "image": data.get("image"),
            "history": data.get("history")
        }

        temples.append(new_temple)
        write_json(TEMPLES_FILE, temples)

        flash("Temple added successfully!", "success")
        return redirect(url_for("home"))

    return render_template("add_temple.html")

# ---------------- MAIN ----------------
if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    for file in [TEMPLES_FILE, USERS_FILE, TX_FILE]:
        if not os.path.exists(file):
            write_json(file, [])
    app.run(debug=True)
