from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Mail, Message
import os
import pytz
from werkzeug.utils import secure_filename
import time
from flask_bcrypt import Bcrypt, generate_password_hash, check_password_hash

# تكوين المجلد للملفات المرفقة
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

# تكوين قاعدة البيانات
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///portfolio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# تكوين البريد الإلكتروني
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# تعريف النماذج
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    tasks = db.relationship('Task', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    task_type = db.Column(db.String(50))
    deadline = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attachments = db.relationship('Attachment', backref='task', lazy=True, cascade='all, delete-orphan')

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(100))
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def send_reminder_email(task):
    msg = Message('Task Reminder',
                 sender=app.config['MAIL_USERNAME'],
                 recipients=[task.user.email])
    msg.body = f'Reminder: Your task "{task.title}" is due in one week on {task.deadline}'
    mail.send(msg)

def check_upcoming_deadlines():
    tasks = Task.query.all()
    for task in tasks:
        if datetime.utcnow() + timedelta(days=7) >= task.deadline >= datetime.utcnow():
            send_reminder_email(task)

scheduler = BackgroundScheduler(timezone=pytz.UTC)
scheduler.add_job(func=check_upcoming_deadlines, trigger="interval", hours=24)
scheduler.start()

def init_db():
    with app.app_context():
        # إنشاء جميع الجداول
        db.create_all()
        
        # التحقق من وجود مستخدم افتراضي
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin = User(username='admin', email='admin@example.com')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

# تهيئة قاعدة البيانات عند بدء التطبيق
init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/tasks')
@login_required
def tasks():
    user_tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('tasks.html', tasks=user_tasks)

@app.route('/task/new', methods=['GET', 'POST'])
@login_required
def new_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        task_type = request.form['task_type']
        deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%dT%H:%M')
        
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            deadline=deadline,
            user_id=current_user.id
        )
        
        # حفظ المهمة أولاً للحصول على task.id
        db.session.add(task)
        db.session.commit()
        
        # معالجة الملفات المرفقة
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and file.filename:
                    # تأمين اسم الملف
                    filename = secure_filename(file.filename)
                    # إضافة الوقت لتجنب تكرار الأسماء
                    unique_filename = f"{int(time.time())}_{filename}"
                    
                    # حفظ الملف
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    
                    # إنشاء مرفق جديد
                    attachment = Attachment(
                        filename=unique_filename,
                        file_type=file.content_type,  # حفظ نوع الملف
                        task_id=task.id
                    )
                    db.session.add(attachment)
        
        try:
            db.session.commit()
            flash('تم إضافة المهمة بنجاح!', 'success')
            return redirect(url_for('tasks'))
        except Exception as e:
            db.session.rollback()
            flash('حدث خطأ أثناء حفظ المهمة', 'error')
            return redirect(url_for('new_task'))
    
    return render_template('new_task.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):  
            login_user(user)
            return redirect(url_for('tasks'))
        
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # التحقق من اسم المستخدم
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً، الرجاء اختيار اسم آخر', 'error')
            return redirect(url_for('register'))
        
        # التحقق من البريد الإلكتروني
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مستخدم مسبقاً، الرجاء استخدام بريد آخر', 'error')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.commit()
            flash('تم التسجيل بنجاح!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('حدث خطأ أثناء التسجيل، الرجاء المحاولة مرة أخرى', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
