from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import SessionLocal, ChatMessage, User, Student
from core.auth_bp import require_role
from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import joinedload # Добавил для чистоты импортов

chat_bp = Blueprint("chat_bp", __name__)

TECH_NAME = "Техническая Поддержка" 

@chat_bp.route("/chat")
def chat_page():
    user = session.get("user")
    if not user: return redirect("/login")
    
    my_fio = user["fio"]
    role = user["role"]

    session_db = SessionLocal()
    try:
        # 1. ТЕХПОДДЕРЖКА (Tech) - Видит список чатов
        if role == "tech":
            selected_user = request.args.get("u")
            
            users_list = []
            
            # Логика загрузки пользователей для sidebar
            users_list = []
            staff = session_db.query(User).filter(User.role != "tech").all()
            for u in staff:
                users_list.append({"fio": u.fio, "role": u.role, "type": "staff"})
                
            active_participants = session_db.query(ChatMessage.sender_fio).filter(
                ChatMessage.recipient_fio == TECH_NAME
            ).distinct().all()
            
            active_names = {r[0] for r in active_participants}
            
            # Добавляем активных студентов
            for name in active_names:
                if not any(u['fio'] == name for u in users_list):
                    student_info = session_db.query(Student.group_code).filter(Student.full_name == name).first()
                    role_str = student_info[0] if student_info and student_info[0] else "Студент"
                    users_list.append({"fio": name, "role": role_str, "type": "student"})


            messages = []
            if selected_user:
                messages = session_db.query(ChatMessage).filter(
                    or_(
                        and_(ChatMessage.sender_fio == TECH_NAME, ChatMessage.recipient_fio == selected_user),
                        and_(ChatMessage.sender_fio == selected_user, ChatMessage.recipient_fio == TECH_NAME)
                    )
                ).order_by(ChatMessage.created_at).all()
                
                # Помечаем прочитанными входящие для Tech
                session_db.query(ChatMessage).filter(
                    ChatMessage.sender_fio == selected_user,
                    ChatMessage.recipient_fio == TECH_NAME,
                    ChatMessage.is_read == False
                ).update({"is_read": True}, synchronize_session=False)
                session_db.commit()

            return render_template("tech_chat.html", 
                                   users=users_list, 
                                   selected_user=selected_user, 
                                   messages=messages,
                                   my_fio=my_fio,
                                   is_tech=True)

        # 2. ОБЫЧНЫЙ ПОЛЬЗОВАТЕЛЬ (Student/Curator/Head)
        else:
            messages = session_db.query(ChatMessage).filter(
                or_(
                    and_(ChatMessage.sender_fio == my_fio, ChatMessage.recipient_fio == TECH_NAME),
                    and_(ChatMessage.sender_fio == TECH_NAME, ChatMessage.recipient_fio == my_fio)
                )
            ).order_by(ChatMessage.created_at).all()
            
            # Помечаем прочитанными сообщения от Техподдержки
            session_db.query(ChatMessage).filter(
                ChatMessage.sender_fio == TECH_NAME,
                ChatMessage.recipient_fio == my_fio,
                ChatMessage.is_read == False
            ).update({"is_read": True}, synchronize_session=False)
            session_db.commit()
            
            return render_template("tech_chat.html", 
                                   selected_user=TECH_NAME, 
                                   messages=messages, 
                                   my_fio=my_fio,
                                   is_tech=False)
    finally:
        session_db.close()


@chat_bp.route("/api/chat/send", methods=["POST"])
def send_message():
    user = session.get("user")
    if not user: return jsonify({"ok": False}), 403
    
    data = request.json
    text = data.get("text")
    recipient = data.get("recipient") 

    if not text or not recipient:
        return jsonify({"ok": False}), 400

    sender = user["fio"]
    
    if user["role"] != "tech":
        recipient = TECH_NAME
    
    msg = ChatMessage(sender_fio=sender, recipient_fio=recipient, message=text)
    
    session_db = SessionLocal()
    session_db.add(msg)
    session_db.commit()
    session_db.close()
    
    return jsonify({"ok": True})


@chat_bp.route("/api/chat/updates")
def get_updates():
    """API для получения новых сообщений (Polling)"""
    user = session.get("user")
    if not user: return jsonify({"messages": []})
    
    my_fio = user["fio"]
    target_user = request.args.get("u")
    last_id = int(request.args.get("last_id", 0))

    if not target_user:
        return jsonify({"messages": []})

    session_db = SessionLocal()
    try:
        new_msgs = session_db.query(ChatMessage).filter(
            ChatMessage.id > last_id,
            or_(
                and_(ChatMessage.sender_fio == my_fio, ChatMessage.recipient_fio == target_user),
                and_(ChatMessage.sender_fio == target_user, ChatMessage.recipient_fio == my_fio)
            )
        ).order_by(ChatMessage.created_at).all()

        if new_msgs:
            # Помечаем прочитанными только те сообщения, которые мы только что получили
            session_db.query(ChatMessage).filter(
                ChatMessage.id.in_([m.id for m in new_msgs]),
                ChatMessage.recipient_fio == my_fio,
                ChatMessage.is_read == False
            ).update({"is_read": True}, synchronize_session=False)
            session_db.commit()

        data = [m.to_dict() for m in new_msgs]
        return jsonify({"messages": data})
    finally:
        session_db.close()


@chat_bp.route("/api/chat/unread_count")
def unread_count():
    """Возвращает количество непрочитанных сообщений для текущего пользователя."""
    user = session.get("user")
    if not user: return jsonify({"count": 0})
    
    my_fio = user["fio"]
    
    session_db = SessionLocal()
    try:
        count = session_db.query(ChatMessage).filter(
            ChatMessage.recipient_fio == my_fio,
            ChatMessage.is_read == False
        ).count()
        return jsonify({"count": count})
    finally:
        session_db.close()