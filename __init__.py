import random
import time
import os
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = '799ebfb34100b8fc1d7b45d2052c807e'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///main.db'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB максимум
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Создаем папку для аватарок если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
manager = LoginManager(app)
manager.login_view = 'index'
manager.login_message = 'Чтобы использовать данные функции необходимо зарегистрироваться'
manager.login_message_category = 'warning'

app.config['MAIL_SERVER'] = 'smtp.mail.ru'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'jura.n2010a@mail.ru'
app.config['MAIL_DEFAULT_SENDER'] = 'jura.n2010a@mail.ru'
app.config['MAIL_PASSWORD'] = 'ahT6Qk8WOfxKszgjVCdZ'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)


# Фильтр для форматирования времени
@app.template_filter('strftime')
def _jinja2_filter_datetime(timestamp):
    return time.strftime('%d.%m.%Y %H:%M', time.localtime(timestamp))


class User(db.Model, UserMixin):
    """Модель пользователя с логином, паролем и подтверждаемой по почте учётной записью."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    password = db.Column(db.String)
    email = db.Column(db.String, unique=True, nullable=False)
    email_confirmed = db.Column(db.Boolean, default=False)
    admin = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String, default=None)

    def __init__(self, username, password, email=None, email_confirmed=False):
        """Инициализация нового пользователя (пароль и код подтверждения должны быть уже захэшированы)."""
        self.username = username
        self.password = password
        self.email = email
        self.email_confirmed = email_confirmed
    
    def is_banned(self):
        """Проверяет, забанен ли пользователь в данный момент."""
        active_ban = Ban.query.filter(
            Ban.user_id == self.id,
            Ban.expires_at > int(time.time())
        ).first()
        return active_ban is not None
    
    def get_active_ban(self):
        """Возвращает активный бан пользователя, если есть."""
        return Ban.query.filter(
            Ban.user_id == self.id,
            Ban.expires_at > int(time.time())
        ).first()


class ChatMessage(db.Model):
    """Модель сообщения в чате."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String, nullable=False)
    text = db.Column(db.Text, nullable=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('chat_message.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))

    user = db.relationship('User', backref='messages')
    reply_to = db.relationship('ChatMessage', remote_side=[id], backref='replies')


class TeamLobby(db.Model):
    """Модель анкеты для поиска команды."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String, nullable=False)
    lobby_code = db.Column(db.String, nullable=False)
    players_count = db.Column(db.Integer, nullable=False)
    language = db.Column(db.String, nullable=False)
    game_type = db.Column(db.String, nullable=False)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))

    user = db.relationship('User', backref='lobbies')


class MessageLike(db.Model):
    """Модель лайка на сообщение."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=False)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))
    
    user = db.relationship('User', backref='likes_given')
    message = db.relationship('ChatMessage', backref='likes')


class UserReputation(db.Model):
    """Модель оценки пользователя (хороший игрок/собеседник)."""
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))
    
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='reputations_given')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='reputations_received')


class Ban(db.Model):
    """Модель бана пользователя."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String, nullable=False)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))
    expires_at = db.Column(db.Integer, nullable=False)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='bans')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='bans_issued')


class Question(db.Model):
    """Модель вопроса в сообществе."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String, nullable=False)
    title = db.Column(db.String, nullable=False)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))
    
    user = db.relationship('User', backref='questions')


class QuestionMessage(db.Model):
    """Модель сообщения в обсуждении вопроса."""
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Integer, default=lambda: int(time.time()))
    
    question = db.relationship('Question', backref='messages')
    user = db.relationship('User', backref='question_messages')


def _generate_code():
    """Генерирует 6-значный цифровой код подтверждения в виде строки."""
    return f"{random.randint(0, 999999):06d}"


def _send_verification_code(email: str, code: str):
    """Отправляет на указанный email письмо с кодом подтверждения регистрации."""
    subject = "Код подтверждения регистрации"
    body = f"Ваш код подтверждения: {code}\n\nЕсли вы не регистрировались — просто проигнорируйте это письмо."
    with mail.connect() as conn:
        msg = Message(recipients=[email], body=body, subject=subject)
        conn.send(msg)


def _start_pending_registration(username: str, password_hash: str, email: str):
    """
    Запускает процесс «ожидающей регистрации»:
    сохраняет данные пользователя и хэш кода в session и отправляет код на почту.
    """
    code = _generate_code()
    session["pending_reg"] = {
        "username": username,
        "password_hash": password_hash,
        "email": email,
        "code_hash": generate_password_hash(code),
        "sent_at": int(time.time()),
        "last_resend_at": int(time.time()),
    }
    _send_verification_code(email, code)


def _clear_pending_registration():
    """Удаляет из session данные о незавершённой регистрации (если они есть)."""
    session.pop("pending_reg", None)


@manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@app.route('/')
def index():
    return render_template("index.html", articles=[])


@app.route('/registration', methods=["POST", "GET"])
def registration():
    if request.method == "GET":
        # Если уже есть незавершённая регистрация в session — сразу показываем модалку ввода кода.
        pending = session.get("pending_reg")
        if pending:
            return render_template(
                "registration.html",
                show_modal=True,
                pending_email=pending.get("email"),
                pending_username=pending.get("username"),
            )
        return render_template("registration.html", show_modal=False)

    # Шаг 2: проверка кода из модалки (если пришло поле verification_code)
    verification_code = (request.form.get("verification_code") or "").strip()
    if verification_code:
        pending = session.get("pending_reg")
        if not pending:
            flash("Сессия подтверждения истекла. Заполните регистрацию заново.", "warning")
            return redirect("/registration")
        if not check_password_hash(pending["code_hash"], verification_code):
            flash("Неверный код подтверждения.", "danger")
            return render_template(
                "registration.html",
                show_modal=True,
                pending_email=pending.get("email"),
                pending_username=pending.get("username"),
            )

        # Код верный — создаём пользователя и авторизуем
        username = pending["username"]
        email = pending["email"]
        password_hash = pending["password_hash"]

        if User.query.filter_by(username=username).first():
            _clear_pending_registration()
            flash("Имя пользователя уже занято. Попробуйте другое.", "danger")
            return redirect("/registration")
        if User.query.filter_by(email=email).first():
            _clear_pending_registration()
            flash("Почта уже используется. Попробуйте другую.", "danger")
            return redirect("/registration")

        new_user = User(username, password_hash, email=email, email_confirmed=True)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        _clear_pending_registration()
        flash("Почта подтверждена. Регистрация завершена!", "success")
        return redirect("/")

    # Шаг 1: старт регистрации (первичная отправка кода на почту)
    username = (request.form.get('username') or "").strip()
    email = (request.form.get('email') or "").strip().lower()
    password = request.form.get('password') or ""
    password2 = request.form.get('password2') or ""

    if not username or not email or not password:
        flash("Заполните логин, почту и пароль.", "danger")
        return redirect("/registration")

    if "@" not in email or "." not in email:
        flash("Введите корректную почту.", "danger")
        return redirect("/registration")

    if User.query.filter_by(username=username).first():
        flash('Имя пользователя занято!', 'danger')
        return redirect("/registration")
    if User.query.filter_by(email=email).first():
        flash('Эта почта уже используется!', 'danger')
        return redirect("/registration")
    if password2 != password:
        flash('Пароли не совпадают!', 'danger')
        return redirect("/registration")

    hash_pwd = generate_password_hash(password)
    _start_pending_registration(username, hash_pwd, email)
    flash("Мы отправили код подтверждения на вашу почту.", "info")
    pending = session.get("pending_reg", {})
    return render_template(
        "registration.html",
        show_modal=True,
        pending_email=pending.get("email"),
        pending_username=pending.get("username"),
    )


@app.route("/registration/resend", methods=["POST"])
def registration_resend():
    # Обрабатывает повторную отправку кода подтверждения, с простым ограничением по времени (cooldown).
    pending = session.get("pending_reg")
    if not pending:
        flash("Сессия подтверждения истекла. Заполните регистрацию заново.", "warning")
        return redirect("/registration")

    now = int(time.time())
    last = int(pending.get("last_resend_at") or 0)
    cooldown = 30
    if now - last < cooldown:
        flash(f"Повторно отправить код можно через {cooldown - (now - last)} сек.", "warning")
        return render_template(
            "registration.html",
            show_modal=True,
            pending_email=pending.get("email"),
            pending_username=pending.get("username"),
        )

    code = _generate_code()
    pending["code_hash"] = generate_password_hash(code)
    pending["last_resend_at"] = now
    pending["sent_at"] = now
    session["pending_reg"] = pending
    _send_verification_code(pending["email"], code)
    flash("Код отправлен повторно.", "info")
    return render_template(
        "registration.html",
        show_modal=True,
        pending_email=pending.get("email"),
        pending_username=pending.get("username"),
    )


@app.route('/login', methods=["POST", "GET"])
def login():
    if request.method == "GET":
        if current_user.is_authenticated:
            flash("Вы уже авторизованы", 'warning')
            return redirect("/")
        return render_template("login.html")
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Такого пользователя не существует', 'danger')
        return redirect("/login")
    if check_password_hash(user.password, password):
        login_user(user)
        return redirect('/')
    flash("Неверный логин или пароль!", 'danger')
    return render_template("login.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect("/")


@app.route('/community', methods=["GET", "POST"])
@login_required
def community():
    # Проверяем бан
    if current_user.is_banned():
        ban = current_user.get_active_ban()
        flash(f"Вы забанены до {time.strftime('%d.%m.%Y %H:%M', time.localtime(ban.expires_at))}. Причина: {ban.reason}", "danger")
        return redirect("/")
    
    if request.method == "POST":
        text = (request.form.get('message') or "").strip()
        reply_to_id = request.form.get('reply_to_id')
        
        if not text:
            flash("Сообщение не может быть пустым", "warning")
            return redirect("/community")

        new_message = ChatMessage(
            user_id=current_user.id,
            username=current_user.username,
            text=text,
            reply_to_id=int(reply_to_id) if reply_to_id else None
        )
        db.session.add(new_message)
        db.session.commit()
        flash("Сообщение отправлено", "success")
        return redirect("/community")

    messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).all()
    
    # Получаем информацию о лайках текущего пользователя
    user_likes = {}
    if current_user.is_authenticated:
        likes = MessageLike.query.filter_by(user_id=current_user.id).all()
        user_likes = {like.message_id: True for like in likes}
    
    return render_template("community.html", messages=messages, user_likes=user_likes)


@app.route('/community/delete/<int:message_id>', methods=["POST"])
@login_required
def delete_message(message_id):
    message = db.session.get(ChatMessage, message_id)
    if not message:
        flash("Сообщение не найдено", "danger")
        return redirect("/community")

    # Проверка прав: либо автор сообщения, либо админ
    if message.user_id != current_user.id and not current_user.admin:
        flash("У вас нет прав для удаления этого сообщения", "danger")
        return redirect("/community")

    db.session.delete(message)
    db.session.commit()
    flash("Сообщение удалено", "success")
    return redirect("/community")

@app.route('/community/like/<int:message_id>', methods=["POST"])
@login_required
def like_message(message_id):
    message = db.session.get(ChatMessage, message_id)
    if not message:
        flash("Сообщение не найдено", "danger")
        return redirect("/community")
    
    # Нельзя лайкать свои сообщения
    if message.user_id == current_user.id:
        flash("Нельзя лайкать свои сообщения", "warning")
        return redirect("/community")
    
    # Проверяем, не поставлен ли уже лайк
    existing_like = MessageLike.query.filter_by(
        user_id=current_user.id,
        message_id=message_id
    ).first()
    
    if existing_like:
        # Убираем лайк
        db.session.delete(existing_like)
        db.session.commit()
        flash("Лайк убран", "info")
    else:
        # Ставим лайк
        new_like = MessageLike(user_id=current_user.id, message_id=message_id)
        db.session.add(new_like)
        db.session.commit()
        flash("Лайк поставлен", "success")
    
    return redirect("/community")

@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("Пользователь не найден", "danger")
        return redirect("/")
    
    # Подсчитываем статистику
    messages_count = ChatMessage.query.filter_by(user_id=user_id).count()
    
    # Лайки, поставленные пользователем
    likes_given = MessageLike.query.filter_by(user_id=user_id).count()
    
    # Лайки, полученные пользователем (на его сообщения)
    user_messages = ChatMessage.query.filter_by(user_id=user_id).all()
    likes_received = sum(len(msg.likes) for msg in user_messages)
    
    # Репутация (сколько людей считают его хорошим игроком)
    reputation_count = UserReputation.query.filter_by(to_user_id=user_id).count()
    
    # Проверяем, поставил ли текущий пользователь репутацию этому пользователю
    has_given_reputation = False
    if current_user.is_authenticated:
        has_given_reputation = UserReputation.query.filter_by(
            from_user_id=current_user.id,
            to_user_id=user_id
        ).first() is not None
    
    return render_template(
        "profile.html",
        profile_user=user,
        messages_count=messages_count,
        likes_given=likes_given,
        likes_received=likes_received,
        reputation_count=reputation_count,
        has_given_reputation=has_given_reputation
    )

@app.route('/profile/<int:user_id>/reputation', methods=["POST"])
@login_required
def give_reputation(user_id):
    if user_id == current_user.id:
        flash("Нельзя давать репутацию самому себе", "warning")
        return redirect(f"/profile/{user_id}")
    
    user = db.session.get(User, user_id)
    if not user:
        flash("Пользователь не найден", "danger")
        return redirect("/")
    
    # Проверяем, не дана ли уже репутация
    existing_rep = UserReputation.query.filter_by(
        from_user_id=current_user.id,
        to_user_id=user_id
    ).first()
    
    if existing_rep:
        # Убираем репутацию
        db.session.delete(existing_rep)
        db.session.commit()
        flash("Вы отменили оценку пользователя", "info")
    else:
        # Даем репутацию
        new_rep = UserReputation(from_user_id=current_user.id, to_user_id=user_id)
        db.session.add(new_rep)
        db.session.commit()
        flash("Вы отметили пользователя как хорошего игрока!", "success")
    
    return redirect(f"/profile/{user_id}")


def allowed_file(filename):
    """Проверяет, разрешено ли расширение файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/profile/<int:user_id>/upload_avatar', methods=["POST"])
@login_required
def upload_avatar(user_id):
    if user_id != current_user.id:
        flash("Вы можете загружать аватарку только для своего профиля", "danger")
        return redirect(f"/profile/{user_id}")
    
    if 'avatar' not in request.files:
        flash("Файл не выбран", "danger")
        return redirect(f"/profile/{user_id}")
    
    file = request.files['avatar']
    if file.filename == '':
        flash("Файл не выбран", "danger")
        return redirect(f"/profile/{user_id}")
    
    if file and allowed_file(file.filename):
        # Удаляем старую аватарку если есть
        if current_user.avatar:
            old_avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.avatar)
            if os.path.exists(old_avatar_path):
                os.remove(old_avatar_path)
        
        # Сохраняем новую аватарку
        filename = secure_filename(f"user_{user_id}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        current_user.avatar = filename
        db.session.commit()
        flash("Аватарка загружена успешно!", "success")
    else:
        flash("Недопустимый формат файла. Разрешены: png, jpg, jpeg, gif, webp", "danger")
    
    return redirect(f"/profile/{user_id}")


@app.route('/ban/<int:user_id>', methods=["POST"])
@login_required
def ban_user(user_id):
    if not current_user.admin:
        flash("У вас нет прав для бана пользователей", "danger")
        return redirect("/community")
    
    if user_id == current_user.id:
        flash("Нельзя забанить самого себя", "warning")
        return redirect("/community")
    
    user = db.session.get(User, user_id)
    if not user:
        flash("Пользователь не найден", "danger")
        return redirect("/community")
    
    if user.admin:
        flash("Нельзя забанить администратора", "warning")
        return redirect("/community")
    
    duration = request.form.get('duration')
    reason = request.form.get('reason')
    
    if not duration or not reason:
        flash("Укажите срок и причину бана", "danger")
        return redirect("/community")
    
    # Вычисляем время окончания бана
    duration_map = {
        'day': 86400,      # 1 день
        'week': 604800,    # 7 дней
        'month': 2592000   # 30 дней
    }
    
    if duration not in duration_map:
        flash("Неверный срок бана", "danger")
        return redirect("/community")
    
    expires_at = int(time.time()) + duration_map[duration]
    
    # Создаем бан
    new_ban = Ban(
        user_id=user_id,
        admin_id=current_user.id,
        reason=reason,
        expires_at=expires_at
    )
    db.session.add(new_ban)
    db.session.commit()
    
    duration_text = {'day': 'день', 'week': 'неделю', 'month': 'месяц'}
    flash(f"Пользователь {user.username} забанен на {duration_text[duration]}", "success")
    return redirect("/community")


@app.route('/team')
def team():
    # Удаляем анкеты старше 30 минут
    thirty_minutes_ago = int(time.time()) - 1800
    TeamLobby.query.filter(TeamLobby.created_at < thirty_minutes_ago).delete()
    db.session.commit()

    lobbies = TeamLobby.query.order_by(TeamLobby.created_at.desc()).all()
    return render_template("team.html", lobbies=lobbies)


@app.route('/team/create', methods=["POST"])
@login_required
def create_lobby():
    # Проверяем бан
    if current_user.is_banned():
        ban = current_user.get_active_ban()
        flash(f"Вы забанены до {time.strftime('%d.%m.%Y %H:%M', time.localtime(ban.expires_at))}. Причина: {ban.reason}", "danger")
        return redirect("/team")
    
    lobby_code = (request.form.get('lobby_code') or "").strip()
    players_count = request.form.get('players_count')
    language = request.form.get('language')
    game_type = request.form.get('game_type')

    if not lobby_code:
        flash("Введите код команды или название лобби", "danger")
        return redirect("/team")

    if not players_count or not players_count.isdigit():
        flash("Выберите количество игроков", "danger")
        return redirect("/team")

    players_count = int(players_count)
    if players_count < 2 or players_count > 6:
        flash("Количество игроков должно быть от 2 до 6", "danger")
        return redirect("/team")

    if language not in ['Русский', 'Английский']:
        flash("Выберите язык команды", "danger")
        return redirect("/team")

    if game_type not in ['Развлечение', 'Прохождение']:
        flash("Выберите тип игры", "danger")
        return redirect("/team")

    new_lobby = TeamLobby(
        user_id=current_user.id,
        username=current_user.username,
        lobby_code=lobby_code,
        players_count=players_count,
        language=language,
        game_type=game_type
    )
    db.session.add(new_lobby)
    db.session.commit()
    flash("Анкета создана успешно!", "success")
    return redirect("/team")


@app.route('/team/delete/<int:lobby_id>', methods=["POST"])
@login_required
def delete_lobby(lobby_id):
    lobby = db.session.get(TeamLobby, lobby_id)
    if not lobby:
        flash("Анкета не найдена", "danger")
        return redirect("/team")

    # Проверка прав: только админ может удалять
    if not current_user.admin:
        flash("У вас нет прав для удаления анкет", "danger")
        return redirect("/team")

    db.session.delete(lobby)
    db.session.commit()
    flash("Анкета удалена", "success")
    return redirect("/team")

@app.route('/questions')
def questions():
    all_questions = Question.query.order_by(Question.created_at.desc()).all()
    # Подсчитываем количество ответов для каждого вопроса
    questions_with_counts = []
    for q in all_questions:
        count = QuestionMessage.query.filter_by(question_id=q.id).count()
        questions_with_counts.append({'question': q, 'replies_count': count})
    return render_template("questions.html", questions=questions_with_counts)

@app.route('/questions/create', methods=["POST"])
@login_required
def create_question():
    # Проверяем бан
    if current_user.is_banned():
        ban = current_user.get_active_ban()
        flash(f"Вы забанены до {time.strftime('%d.%m.%Y %H:%M', time.localtime(ban.expires_at))}. Причина: {ban.reason}", "danger")
        return redirect("/questions")
    
    title = (request.form.get('title') or "").strip()
    if not title:
        flash("Введите вопрос", "danger")
        return redirect("/questions")
    
    new_question = Question(
        user_id=current_user.id,
        username=current_user.username,
        title=title
    )
    db.session.add(new_question)
    db.session.commit()
    flash("Вопрос опубликован!", "success")
    return redirect("/questions")

@app.route('/questions/<int:question_id>')
def question_detail(question_id):
    question = db.session.get(Question, question_id)
    if not question:
        flash("Вопрос не найден", "danger")
        return redirect("/questions")
    
    messages = QuestionMessage.query.filter_by(question_id=question_id).order_by(QuestionMessage.created_at.asc()).all()
    return render_template("question_detail.html", question=question, messages=messages)

@app.route('/questions/<int:question_id>/reply', methods=["POST"])
@login_required
def reply_to_question(question_id):
    # Проверяем бан
    if current_user.is_banned():
        ban = current_user.get_active_ban()
        flash(f"Вы забанены до {time.strftime('%d.%m.%Y %H:%M', time.localtime(ban.expires_at))}. Причина: {ban.reason}", "danger")
        return redirect(f"/questions/{question_id}")
    
    question = db.session.get(Question, question_id)
    if not question:
        flash("Вопрос не найден", "danger")
        return redirect("/questions")
    
    text = (request.form.get('message') or "").strip()
    if not text:
        flash("Сообщение не может быть пустым", "warning")
        return redirect(f"/questions/{question_id}")
    
    new_message = QuestionMessage(
        question_id=question_id,
        user_id=current_user.id,
        username=current_user.username,
        text=text
    )
    db.session.add(new_message)
    db.session.commit()
    flash("Ответ отправлен", "success")
    return redirect(f"/questions/{question_id}")

@app.route('/questions/<int:question_id>/delete', methods=["POST"])
@login_required
def delete_question(question_id):
    question = db.session.get(Question, question_id)
    if not question:
        flash("Вопрос не найден", "danger")
        return redirect("/questions")
    
    # Проверка прав: либо автор вопроса, либо админ
    if question.user_id != current_user.id and not current_user.admin:
        flash("У вас нет прав для удаления этого вопроса", "danger")
        return redirect("/questions")
    
    # Удаляем все сообщения в вопросе
    QuestionMessage.query.filter_by(question_id=question_id).delete()
    db.session.delete(question)
    db.session.commit()
    flash("Вопрос удален", "success")
    return redirect("/questions")

@app.route('/questions/<int:question_id>/message/<int:message_id>/delete', methods=["POST"])
@login_required
def delete_question_message(question_id, message_id):
    message = db.session.get(QuestionMessage, message_id)
    if not message:
        flash("Сообщение не найдено", "danger")
        return redirect(f"/questions/{question_id}")
    
    # Проверка прав: либо автор сообщения, либо админ
    if message.user_id != current_user.id and not current_user.admin:
        flash("У вас нет прав для удаления этого сообщения", "danger")
        return redirect(f"/questions/{question_id}")
    
    db.session.delete(message)
    db.session.commit()
    flash("Сообщение удалено", "success")
    return redirect(f"/questions/{question_id}")


@app.route('/admin/bans')
@login_required
def admin_bans():
    if not current_user.admin:
        flash("У вас нет прав для доступа к этой странице", "danger")
        return redirect("/")
    
    # Получаем все активные баны
    current_time = int(time.time())
    active_bans = Ban.query.filter(Ban.expires_at > current_time).order_by(Ban.created_at.desc()).all()
    
    # Получаем все истекшие баны
    expired_bans = Ban.query.filter(Ban.expires_at <= current_time).order_by(Ban.created_at.desc()).all()
    
    return render_template("admin_bans.html", active_bans=active_bans, expired_bans=expired_bans)


@app.route('/admin/unban/<int:ban_id>', methods=["POST"])
@login_required
def unban_user(ban_id):
    if not current_user.admin:
        flash("У вас нет прав для выполнения этого действия", "danger")
        return redirect("/")
    
    ban = db.session.get(Ban, ban_id)
    if not ban:
        flash("Бан не найден", "danger")
        return redirect("/admin/bans")
    
    # Устанавливаем время окончания бана на текущее время (разбан)
    ban.expires_at = int(time.time())
    db.session.commit()
    
    flash(f"Пользователь {ban.user.username} разбанен", "success")
    return redirect("/admin/bans")



from api import create_api_blueprint
app.register_blueprint(create_api_blueprint(db, User, ChatMessage, MessageLike, UserReputation, Ban))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()
