from flask import Flask, render_template, abort, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_demo'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# --- EMAIL CONFIGURATION ---
SENDER_EMAIL = os.environ.get('MAIL_USER', 'manavchauhan0442@gmail.com')
APP_PASSWORD = os.environ.get('MAIL_PASS', 'keenxlmdnoobnaat')
# ---------------------------

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Master Dictionary of Indian Dishes for the platform
DISHES = {
    "chole-bhature": {
        "id": "chole-bhature",
        "name": "Chole Bhature",
        "emoji": "🍛",
        "gradient": "from-brand-400 to-orange-600",
        "price": 150,
        "bg_glow": "bg-brand-500/20",
        "svg_icon": "fas fa-utensils"
    },
    "vada-pav": {
        "id": "vada-pav",
        "name": "Vada Pav",
        "emoji": "🍔",
        "gradient": "from-yellow-400 to-red-600",
        "price": 50,
        "bg_glow": "bg-red-500/20",
        "svg_icon": "fas fa-hamburger"
    },
    "biryani": {
        "id": "biryani",
        "name": "Biryani",
        "emoji": "🥘",
        "gradient": "from-amber-600 to-red-800",
        "price": 250,
        "bg_glow": "bg-amber-600/20",
        "svg_icon": "fas fa-bowl-rice"
    },
    "chai": {
        "id": "chai",
        "name": "Chai",
        "emoji": "☕",
        "gradient": "from-orange-400 to-amber-700",
        "price": 20,
        "bg_glow": "bg-orange-500/20",
        "svg_icon": "fas fa-mug-hot"
    },
    "dosa": {
        "id": "dosa",
        "name": "Dosa",
        "emoji": "🥞",
        "gradient": "from-yellow-300 to-yellow-600",
        "price": 100,
        "bg_glow": "bg-yellow-500/20",
        "svg_icon": "fas fa-utensils"
    },
    "samosa": {
        "id": "samosa",
        "name": "Samosa",
        "emoji": "🥟",
        "gradient": "from-yellow-500 to-orange-700",
        "price": 30,
        "bg_glow": "bg-yellow-600/20",
        "svg_icon": "fas fa-play"
    }
}

def get_db_connection():
    conn = sqlite3.connect('pizza.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    dish = DISHES["chole-bhature"]
    username = session.get('username')
    return render_template('index.html', dish=dish, all_dishes=DISHES, username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Default Username/Password behavior
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM creators WHERE username = ? AND password = ?', (username, password)).fetchone()
            conn.close()
            
            if user:
                session['username'] = user['username']
                return redirect(url_for('profile', username=user['username']))
            else:
                return render_template('login.html', error="Invalid username or password")
                
    return render_template('login.html')

# Mock Google Login Endpoint
@app.route('/google-login', methods=['POST'])
def google_login():
    # In a real app we'd redirect to Google OAuth callback. 
    # For mock, simply take first available user in DB to showcase flow
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM creators').fetchone()
    conn.close()
    if user:
        session['username'] = user['username']
        return jsonify({"success": True, "redirect": url_for('profile', username=user['username'])})
    return jsonify({"success": False, "message": "No users in database to mock Google Login with."})

# Send OTP Endpoint (Mock / Real Email)
def send_real_email(receiver, otp, username):
    msg = MIMEMultipart()
    msg['From'] = f"BuyMeCholeBhature <{SENDER_EMAIL}>"
    msg['To'] = receiver
    msg['Subject'] = f"{otp} is your BuyMeCholeBhature secure code"
    
    body = f"Hey {username},\n\nYour 4-digit secure code to log in is: {otp}\n\nDon't share this with anyone."
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

@app.route('/send-otp', methods=['POST'])
def send_otp():
    contact = request.json.get('contact') # can be email or phone
    if not contact:
        return jsonify({"success": False, "message": "Please enter phone or email."})
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM creators WHERE email = ? OR phone = ? OR username = ?', (contact, contact, contact)).fetchone()
    conn.close()
    
    if user:
        mock_otp = str(random.randint(1000, 9999))
        session['pending_otp'] = mock_otp
        session['pending_otp_user'] = user['username']
        
        # Determine if it's an email format
        is_email = '@' in contact
        
        if is_email:
            # If default vars are still set, fallback to Mock behavior and warn terminal
            if '@gmail.com' in SENDER_EMAIL and SENDER_EMAIL == 'your-email@gmail.com':
                print(f"\n[WARNING] Real SMTP not configured! Showing UI mock. OTP for {contact} is {mock_otp}\n")
                return jsonify({"success": True, "message": "OTP sent successfully!", "otp": mock_otp, "mode": "demo"})
            
            # Send Real Email
            success = send_real_email(contact, mock_otp, user['username'])
            if success:
                print(f"[SMTP SERVER] Successfully dispatched {mock_otp} to {contact}")
                return jsonify({"success": True, "message": "Secure code dispatched to your inbox!", "mode": "real"})
            else:
                return jsonify({"success": False, "message": "Server could not send email. Verify your console keys."})
        else:
            # Phone Auth logic requires SMS, dropping to Terminal Mock
            print(f"\n[MOCK OTP SMS] Sending OTP {mock_otp} to {contact}\n")
            return jsonify({"success": True, "message": "Mock SMS sent!", "otp": mock_otp, "mode": "demo"})
    else:
        return jsonify({"success": False, "message": "Account not found with this contact/username."})

# Verify OTP Endpoint
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_otp = request.json.get('otp')
    if 'pending_otp' in session and str(session['pending_otp']) == str(user_otp):
        username = session['pending_otp_user']
        session['username'] = username
        # cleanup
        session.pop('pending_otp', None)
        session.pop('pending_otp_user', None)
        return jsonify({"success": True, "redirect": url_for('profile', username=username)})
    else:
        return jsonify({"success": False, "message": "Invalid or expired OTP."})

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        upi_id = request.form.get('upi_id')
        bio = request.form.get('bio')
        website = request.form.get('website', '')
        github = request.form.get('github', '')
        linkedin = request.form.get('linkedin', '')
        instagram = request.form.get('instagram', '')
        
        pic = request.files.get('profile_pic')
        pic_filename = 'default.png'
        if pic and pic.filename != '':
            pic_filename = secure_filename(pic.filename)
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_filename))
            
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO creators (username, password, name, email, phone, upi_id, bio, pic, website, github, linkedin, instagram) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (username, password, name, email, phone, upi_id, bio, pic_filename, website, github, linkedin, instagram))
            conn.commit()
            session['username'] = username
            return redirect(url_for('profile', username=username))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('setup.html', error="Username already exists")
        
        conn.close()
        
    return render_template('setup.html')

@app.route('/<username>')
def profile(username):
    if username in DISHES:
        return render_template('index.html', dish=DISHES[username], all_dishes=DISHES, username=session.get('username'))
        
    conn = get_db_connection()
    creator = conn.execute('SELECT * FROM creators WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if creator:
        return render_template('profile.html', 
                               username=creator['username'],
                               name=creator['name'], 
                               bio=creator['bio'], 
                               upi_id=creator['upi_id'], 
                               pic=creator['pic'],
                               website=creator['website'],
                               github=creator['github'],
                               linkedin=creator['linkedin'],
                               instagram=creator['instagram'],
                               all_dishes=DISHES)
                               
    abort(404)

if __name__ == '__main__':
    app.run(debug=True, port=8000)