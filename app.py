import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

# تكوين السر
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')

# تكوين قاعدة البيانات
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# تكوين المجلد للملفات المرفقة
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# تهيئة الإضافات
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True)

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('tasks'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('tasks'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/tasks')
@login_required
def tasks():
    user_tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('tasks.html', tasks=user_tasks)

@app.route('/add_task', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        task_type = request.form.get('task_type')
        deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%dT%H:%M')
        
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            deadline=deadline,
            user_id=current_user.id
        )
        
        files = request.files.getlist('attachments')
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                attachment = Attachment(filename=filename, file_type=file.content_type)
                task.attachments.append(attachment)
        
        db.session.add(task)
        db.session.commit()
        flash('Task added successfully!')
        return redirect(url_for('tasks'))
    
    return render_template('add_task.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('لا يمكنك حذف هذه المهمة', 'error')
        return redirect(url_for('tasks'))
    
    # حذف الملفات المرفقة من المجلد
    for attachment in task.attachments:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(task)
    db.session.commit()
    flash('تم حذف المهمة بنجاح', 'success')
    return redirect(url_for('tasks'))

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
        
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.description = request.form.get('description')
        task.task_type = request.form.get('task_type')
        task.deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%dT%H:%M')
        
        files = request.files.getlist('attachments')
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                attachment = Attachment(filename=filename, file_type=file.content_type)
                task.attachments.append(attachment)
        
        db.session.commit()
        flash('تم تحديث المهمة بنجاح!', 'success')
        return redirect(url_for('tasks'))
        
    return render_template('edit_task.html', task=task)

@app.route('/delete_attachment/<int:attachment_id>', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    if attachment.task.user_id != current_user.id:
        flash('لا يمكنك حذف هذا الملف', 'error')
        return redirect(url_for('tasks'))
    
    # حذف الملف من المجلد
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.session.delete(attachment)
    db.session.commit()
    flash('تم حذف الملف بنجاح', 'success')
    return redirect(url_for('edit_task', task_id=attachment.task_id))

@app.before_first_request
def create_tables():
    db.create_all()
    # إنشاء مستخدم افتراضي إذا لم يكن موجوداً
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=False)
