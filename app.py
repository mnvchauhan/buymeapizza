from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_db():
    conn = sqlite3.connect('pizza.db')
    c = conn.cursor()
    # Naye columns: instagram aur website add kiye hain
    c.execute('''CREATE TABLE IF NOT EXISTS creators 
                 (username TEXT PRIMARY KEY, name TEXT, upi_id TEXT, 
                  bio TEXT, pic TEXT, github TEXT, instagram TEXT, linkedin TEXT, website TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        username = request.form.get('username').lower().replace(" ", "")
        name = request.form.get('name')
        upi_id = request.form.get('upi_id')
        bio = request.form.get('bio')
        github = request.form.get('github', '')
        instagram = request.form.get('instagram', '')
        linkedin = request.form.get('linkedin', '')
        website = request.form.get('website', '')
        
        pic_filename = "default.png"
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(f"{username}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                pic_filename = filename

        conn = sqlite3.connect('pizza.db')
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO creators 
                         (username, name, upi_id, bio, pic, github, instagram, linkedin, website) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (username, name, upi_id, bio, pic_filename, github, instagram, linkedin, website))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Bhai ye Username pehle se taken hai! Back jaakar doosra try karo."
        finally:
            conn.close()

        return redirect(url_for('show_profile', username=username))

    return render_template('setup.html')

@app.route('/<username>')
def show_profile(username):
    conn = sqlite3.connect('pizza.db')
    c = conn.cursor()
    c.execute("SELECT name, upi_id, bio, pic, github, instagram, linkedin, website FROM creators WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()

    if user:
        return render_template('profile.html', 
                               username=username, name=user[0], upi_id=user[1], 
                               bio=user[2], pic=user[3], github=user[4], 
                               instagram=user[5], linkedin=user[6], website=user[7])
    else:
        return "Profile nahi mili! Pehle setup karo.", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)