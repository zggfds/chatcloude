import os, json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mobile_messenger_2026_key'

# Настройка путей для PythonAnywhere
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['AVATARS_FOLDER'] = os.path.join(basedir, 'static', 'avatars')
JSON_FILE = os.path.join(basedir, 'messages.json')

for f in [app.config['UPLOAD_FOLDER'], app.config['AVATARS_FOLDER']]:
    os.makedirs(f, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

friends_table = db.Table('friends',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('friend_id', db.Integer, db.ForeignKey('user.id'))
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(200), default='/static/avatars/default.png')
    friends = db.relationship('User', secondary=friends_table, 
                               primaryjoin=(friends_table.c.user_id == id), 
                               secondaryjoin=(friends_table.c.friend_id == id))

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def load_json():
    if not os.path.exists(JSON_FILE): return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_json(data):
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    cleaned = [m for m in data if datetime.fromisoformat(m['timestamp']) > cutoff]
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=4)

@app.route('/')
@login_required
def index():
    return render_template('chat.html', friends=current_user.friends)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and check_password_hash(u.password, request.form['password']):
            login_user(u)
            return redirect(url_for('index'))
        flash("Ошибка входа")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash("Ник занят")
            return redirect(url_for('register'))
        u = User(username=request.form['username'], password=generate_password_hash(request.form['password']))
        db.session.add(u)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/add_friend_by_nick', methods=['POST'])
@login_required
def add_friend_by_nick():
    nick = request.form.get('nickname').strip()
    target = User.query.filter_by(username=nick).first()
    if target and target != current_user:
        current_user.friends.append(target)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/get_messages/<int:friend_id>')
@login_required
def get_messages(friend_id):
    all_m = load_json()
    return jsonify([m for m in all_m if (m['sender_id'] == current_user.id and m['recipient_id'] == friend_id) or (m['sender_id'] == friend_id and m['recipient_id'] == current_user.id)])

@app.route('/send_msg', methods=['POST'])
@login_required
def send_msg():
    data = request.json
    all_m = load_json()
    all_m.append({
        'sender_id': current_user.id,
        'recipient_id': int(data['recipient_id']),
        'text': data.get('message'),
        'file_path': data.get('file_path'),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'time': datetime.now().strftime('%H:%M')
    })
    save_json(all_m)
    return jsonify({'status': 'ok'})

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    f = request.files.get('photo')
    if f:
        fname = secure_filename(f"{datetime.now().timestamp()}_{f.filename}")
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        return jsonify({'file_path': 'static/uploads/' + fname})
    return "error", 400

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        f = request.files.get('avatar')
        if f:
            fname = secure_filename(f"av_{current_user.id}_{f.filename}")
            f.save(os.path.join(app.config['AVATARS_FOLDER'], fname))
            current_user.avatar = '/static/avatars/' + fname
            db.session.commit()
    return render_template('profile.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))