from flask import Flask, render_template, abort, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from twilio.rest import Client
import requests
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_demo'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # Allow HTTP for local testing

# --- EMAIL CONFIGURATION ---
SENDER_EMAIL = os.getenv('MAIL_USER')
APP_PASSWORD = os.getenv('MAIL_PASS')

# --- GOOGLE OAUTH CONFIGURATION ---
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# --- TWILIO CONFIGURATION ---
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
# ---------------------------

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

@app.route('/google-login', methods=['POST', 'GET'])
def google_login():
    if not GOOGLE_CLIENT_ID or 'PASTE_YOUR' in GOOGLE_CLIENT_ID:
        return "<h2 style='color:red;font-family:sans-serif;text-align:center;margin-top:50px;'>Google Keys Not Configured!</h2><p style='text-align:center;'>Bhai, `.env` file check karo, wahan <b>GOOGLE_CLIENT_ID</b> missing hai.</p>"
        
    redirect_uri = url_for('google_auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/google-auth')
def google_auth():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        email = user_info['email']
        google_id = user_info['sub']
        name = user_info['name']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM creators WHERE google_id = ? OR email = ?', (google_id, email)).fetchone()
        
        if user:
            session['username'] = user['username']
            # Update google_id if not set
            if not user['google_id']:
                conn.execute('UPDATE creators SET google_id = ? WHERE username = ?', (google_id, user['username']))
                conn.commit()
            conn.close()
            return redirect(url_for('profile', username=user['username']))
        else:
            # New user - redirect to setup with pre-filled info
            conn.close()
            session['pending_google_info'] = {
                'email': email,
                'google_id': google_id,
                'name': name
            }
            return redirect(url_for('setup'))
    return redirect(url_for('login'))

# Send OTP Endpoint (Mock / Real Email)
def send_real_email(receiver, otp, username):
    print(f"[DEBUG] Sending Designed OTP email to {receiver}...")
    try:
        html_content = render_template('otp_email.html', username=username, otp=otp)
        
        msg = MIMEText(html_content, 'html', 'utf-8')
        msg['From'] = f"BuyMeCholeBhature <{SENDER_EMAIL}>"
        msg['To'] = receiver
        msg['Subject'] = f"{otp} is your BuyMeCholeBhature secure code"
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[ERROR] Designed OTP email failed: {e}")
        return False
    

# --- WELCOME EMAIL FUNCTION ---
def send_welcome_email(receiver, username):
    print(f"[DEBUG] Attempting to send welcome email to {receiver}...")
    msg = MIMEMultipart('alternative')
    msg['From'] = f"Buy Me a Chole Bhature <{SENDER_EMAIL}>"
    msg['To'] = receiver
    msg['Subject'] = f"Welcome to Buy Me a Chole Bhature, {username}! 🎉"
    
    # Plaintext fallback
    text_content = f"Hi {username},\n\nWelcome to BuyMeCholeBhature! Your page is live at: https://bymeacholebhature.shop/{username}"
    
    try:
        html_content = render_template('welcome_email.html', username=username)
        
        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver, msg.as_string())
        server.quit()
        print(f"[DEBUG] Welcome email successfully sent to {receiver}")
        return True
    except Exception as e:
        print(f"[ERROR] SMTP Error in welcome email: {e}")
        return False
# ------------------------------

@app.route('/send-otp', methods=['POST'])
def send_otp():
    contact = request.json.get('contact') # can be email or phone
    if not contact:
        return jsonify({"success": False, "message": "Please enter your registered email."})
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM creators WHERE email = ? OR phone = ? OR username = ?', (contact, contact, contact)).fetchone()
    conn.close()
    
    if user:
        mock_otp = str(random.randint(1000, 9999))
        session['pending_otp'] = mock_otp
        session['pending_otp_user'] = user['username']
        session.modified = True
        
        # Determine if it's an email format
        is_email = '@' in contact
        
        if is_email:
            # If default vars are still set, fallback to Mock behavior
            if '@gmail.com' in SENDER_EMAIL and SENDER_EMAIL == 'your-email@gmail.com':
                return jsonify({"success": True, "message": "OTP sent successfully!", "otp": mock_otp, "mode": "demo"})
            
            # Send Real Email
            success = send_real_email(contact, mock_otp, user['username'])
            if success:
                return jsonify({"success": True, "message": "Secure code dispatched to your inbox!", "mode": "real"})
            else:
                return jsonify({"success": False, "message": "Email service failed. Check credentials."})
        else:
            # Real SMS via Twilio
            if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
                try:
                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                    message = client.messages.create(
                        body=f"Your BuyMeCholeBhature login code is: {mock_otp}",
                        from_=TWILIO_PHONE_NUMBER,
                        to=contact
                    )
                    return jsonify({"success": True, "message": "Login code sent via SMS!", "mode": "real"})
                except Exception as e:
                    print(f"Twilio Error: {e}")
                    return jsonify({"success": False, "message": "SMS delivery failed. Check your Twilio settings."})
            else:
                # Fallback to Mock
                print(f"\n[MOCK OTP SMS] Sending OTP {mock_otp} to {contact}\n")
                return jsonify({"success": True, "message": "Demo mode: SMS service not configured.", "otp": mock_otp, "mode": "demo"})
    else:
        return jsonify({"success": False, "message": "Authentication failed. Email not recognized."})

# Verify OTP Endpoint
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    user_otp = request.json.get('otp', '').strip()
    pending_otp = session.get('pending_otp')
    
    print(f"--- OTP VERIFICATION ---")
    print(f"User entered: '{user_otp}'")
    print(f"Session OTP: '{pending_otp}'")
    
    if pending_otp and str(pending_otp) == str(user_otp):
        username = session['pending_otp_user']
        session['username'] = username
        # cleanup
        session.pop('pending_otp', None)
        session.pop('pending_otp_user', None)
        session.modified = True
        return jsonify({"success": True, "redirect": url_for('profile', username=username)})
    else:
        return jsonify({"success": False, "message": "Invalid or expired OTP. Please try again."})

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    google_info = session.get('pending_google_info')
    if not google_info:
        return redirect(url_for('login'))
    
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
        google_id = request.form.get('google_id', '')
        
        pic = request.files.get('profile_pic')
        pic_filename = 'default.png'
        if pic and pic.filename != '':
            pic_filename = secure_filename(pic.filename)
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_filename))
            
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO creators (username, password, name, email, phone, upi_id, bio, pic, website, github, linkedin, instagram, google_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         (username, password, name, email, phone, upi_id, bio, pic_filename, website, github, linkedin, instagram, google_id))
            conn.commit()
            
            # ---> WELCOME EMAIL YAHAN TRIGGER HOGA <---
            if email:
                send_welcome_email(email, username)
            # ------------------------------------------
            
            session.pop('pending_google_info', None)
            session['username'] = username
            return redirect(url_for('profile', username=username))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('setup.html', error="Username already exists", prefill=google_info)
        
        conn.close()
        
    return render_template('setup.html', prefill=google_info)

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    username = session['username']
    conn = get_db_connection()
    creator = conn.execute('SELECT * FROM creators WHERE username = ?', (username,)).fetchone()
    
    if request.method == 'POST':
        name = request.form.get('name')
        upi_id = request.form.get('upi_id')
        bio = request.form.get('bio')
        website = request.form.get('website', '')
        github = request.form.get('github', '')
        linkedin = request.form.get('linkedin', '')
        instagram = request.form.get('instagram', '')
        
        pic = request.files.get('profile_pic')
        pic_filename = creator['pic']
        if pic and pic.filename != '':
            pic_filename = secure_filename(pic.filename)
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_filename))
            
        conn.execute('UPDATE creators SET name=?, upi_id=?, bio=?, pic=?, website=?, github=?, linkedin=?, instagram=? WHERE username=?',
                     (name, upi_id, bio, pic_filename, website, github, linkedin, instagram, username))
        conn.commit()
        conn.close()
        return redirect(url_for('profile', username=username))
        
    conn.close()
    return render_template('edit_profile.html', creator=creator)

@app.route('/<username>')
def profile(username):
    if username in DISHES:
        return render_template('index.html', dish=DISHES[username], all_dishes=DISHES, username=session.get('username'))
        
    conn = get_db_connection()
    creator = conn.execute('SELECT * FROM creators WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if creator:
        return render_template('profile.html', 
                               creator_username=creator['username'],
                               session_user=session.get('username'),
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
    app.run(debug=True, port=8001)