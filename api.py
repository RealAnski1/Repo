"""
REST API Blueprint.

Подключается через фабрику create_api_blueprint(db, ...) в __init__.py.

Маршруты:
    GET /api/profile          — список всех пользователей
    GET /api/profile/<id>     — профиль одного пользователя
    GET /api/community        — список всех сообщений чата
    GET /api/community/<id>   — одно сообщение чата
"""

import time
from flask import Blueprint, jsonify


def create_api_blueprint(db, User, ChatMessage, MessageLike, UserReputation, Ban):
    bp = Blueprint('api', __name__, url_prefix='/api')

    # ── Профили ───────────────────────────────────────────────────────────────

    @bp.route('/profile')
    def api_profiles():
        """Список всех пользователей с базовой статистикой."""
        result = []
        for u in User.query.all():
            result.append({
                'id': u.id,
                'username': u.username,
                'admin': u.admin,
                'avatar': u.avatar,
                'messages_count': ChatMessage.query.filter_by(user_id=u.id).count(),
                'reputation': UserReputation.query.filter_by(to_user_id=u.id).count(),
                'is_banned': u.is_banned(),
            })
        return jsonify(result)

    @bp.route('/profile/<int:user_id>')
    def api_profile(user_id):
        """Полный профиль одного пользователя."""
        u = db.session.get(User, user_id)
        if not u:
            return jsonify({'error': 'Пользователь не найден'}), 404

        user_messages = ChatMessage.query.filter_by(user_id=user_id).all()
        likes_received = sum(len(msg.likes) for msg in user_messages)
        active_ban = u.get_active_ban()

        return jsonify({
            'id': u.id,
            'username': u.username,
            'admin': u.admin,
            'avatar': u.avatar,
            'messages_count': len(user_messages),
            'likes_given': MessageLike.query.filter_by(user_id=user_id).count(),
            'likes_received': likes_received,
            'reputation': UserReputation.query.filter_by(to_user_id=user_id).count(),
            'bans_total': Ban.query.filter_by(user_id=user_id).count(),
            'is_banned': u.is_banned(),
            'ban': {
                'reason': active_ban.reason,
                'expires_at': active_ban.expires_at,
                'expires_formatted': time.strftime('%d.%m.%Y %H:%M', time.localtime(active_ban.expires_at)),
            } if active_ban else None,
        })

    # ── Чат ───────────────────────────────────────────────────────────────────

    @bp.route('/community')
    def api_community():
        """Список всех сообщений чата (от новых к старым)."""
        messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).all()
        result = []
        for m in messages:
            result.append({
                'id': m.id,
                'user_id': m.user_id,
                'username': m.username,
                'text': m.text,
                'reply_to_id': m.reply_to_id,
                'likes': len(m.likes),
                'created_at': m.created_at,
                'created_formatted': time.strftime('%d.%m.%Y %H:%M', time.localtime(m.created_at)),
            })
        return jsonify(result)

    @bp.route('/community/<int:message_id>')
    def api_community_message(message_id):
        """Одно сообщение чата вместе с цитируемым сообщением."""
        m = db.session.get(ChatMessage, message_id)
        if not m:
            return jsonify({'error': 'Сообщение не найдено'}), 404

        return jsonify({
            'id': m.id,
            'user_id': m.user_id,
            'username': m.username,
            'text': m.text,
            'reply_to_id': m.reply_to_id,
            'reply_to': {
                'id': m.reply_to.id,
                'username': m.reply_to.username,
                'text': m.reply_to.text,
            } if m.reply_to else None,
            'likes': len(m.likes),
            'created_at': m.created_at,
            'created_formatted': time.strftime('%d.%m.%Y %H:%M', time.localtime(m.created_at)),
        })

    return bp
