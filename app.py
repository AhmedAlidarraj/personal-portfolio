import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from flask_migrate import Migrate
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from werkzeug.utils import secure_filename

# تكوين المجلد للملفات المرفقة
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# تكوين التطبيق
app = Flask(__name__)

# تكوين السر
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# تكوين قاعدة البيانات
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# تكوين المجلد للملفات المرفقة
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# تكوين البريد الإلكتروني
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

# تهيئة الإضافات
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
migrate = Migrate(app, db)

# تعريف النماذج
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
    notification_preferences = db.Column(db.String(200), default='1day,3hours,1hour')
    last_notification = db.Column(db.DateTime)

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(100))
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def send_notification(task, time_remaining):
    """إرسال إشعار بريد إلكتروني للمستخدم"""
    try:
        user = User.query.get(task.user_id)
        if not user or not user.email:
            return

        time_text = {
            '1day': 'يوم واحد',
            '3hours': '3 ساعات',
            '1hour': 'ساعة واحدة'
        }.get(time_remaining, time_remaining)

        subject = f"تذكير: المهمة {task.title} تنتهي خلال {time_text}"
        body = f"""
        مرحباً {user.username}،

        هذا تذكير بأن مهمتك "{task.title}" ستنتهي خلال {time_text}.

        تفاصيل المهمة:
        - الوصف: {task.description}
        - الموعد النهائي: {task.deadline.strftime('%Y-%m-%d %H:%M')}

        يرجى إكمال المهمة في الوقت المحدد.
        """

        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=body
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"خطأ في إرسال الإشعار: {e}")
        return False

def check_deadlines():
    """التحقق من المواعيد النهائية وإرسال الإشعارات"""
    try:
        with app.app_context():
            current_time = datetime.now(pytz.UTC)
            tasks = Task.query.filter(
                Task.deadline > current_time,
                Task.notification_preferences.isnot(None)
            ).all()

            for task in tasks:
                if not task.notification_preferences:
                    continue

                preferences = task.notification_preferences.split(',')
                time_until_deadline = task.deadline.replace(tzinfo=pytz.UTC) - current_time

                notification_times = {
                    '1day': timedelta(days=1),
                    '3hours': timedelta(hours=3),
                    '1hour': timedelta(hours=1)
                }

                for pref in preferences:
                    if pref in notification_times:
                        target_delta = notification_times[pref]
                        actual_delta = abs(time_until_deadline - target_delta)

                        if actual_delta <= timedelta(minutes=5):
                            if not task.last_notification or \
                               current_time - task.last_notification.replace(tzinfo=pytz.UTC) > timedelta(hours=1):
                                if send_notification(task, pref):
                                    task.last_notification = current_time
                                    db.session.commit()
    except Exception as e:
        print(f"خطأ في فحص المواعيد النهائية: {e}")

# تكوين المجدول
try:
    scheduler = BackgroundScheduler(timezone=pytz.UTC)
    scheduler.add_job(func=check_deadlines, trigger="interval", minutes=5)
    scheduler.start()
except Exception as e:
    print(f"خطأ في بدء المجدول: {e}")

@app.before_first_request
def create_tables():
    try:
        db.create_all()
        
        # إنشاء مستخدم افتراضي إذا لم يكن موجوداً
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin = User(username='admin', email='admin@example.com')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    except Exception as e:
        print(f"خطأ في إنشاء الجداول: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/tasks')
@login_required
def tasks():
    user_tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('tasks.html', tasks=user_tasks)

@app.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
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
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                attachment = Attachment(
                    filename=filename,
                    file_type=file.content_type,
                    task=task
                )
                db.session.add(attachment)
        
        db.session.add(task)
        db.session.commit()
        flash('تم إنشاء المهمة بنجاح!', 'success')
        return redirect(url_for('tasks'))
    
    return render_template('create_task.html')

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
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                attachment = Attachment(
                    filename=filename,
                    file_type=file.content_type,
                    task=task
                )
                db.session.add(attachment)
        
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

if __name__ == '__main__':
    app.run(debug=True)
