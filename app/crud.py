from sqlalchemy.orm import Session
from . import models

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, username: str):
    db_user = models.User(username=username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_or_create_user(db: Session, username: str):
    db_user = get_user_by_username(db, username=username)
    if db_user:
        return db_user
    return create_user(db, username=username)

def get_room_by_name(db: Session, room_name: str):
    return db.query(models.ChatRoom).filter(models.ChatRoom.name == room_name).first()

def get_room_by_id(db: Session, room_id: int):
    return db.query(models.ChatRoom).filter(models.ChatRoom.id == room_id).first()

def get_all_rooms(db: Session):
    return db.query(models.ChatRoom).all()

def create_room(db: Session, room_name: str, admin_id: int):
    db_room = models.ChatRoom(name=room_name, admin_id=admin_id)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

def get_or_create_room(db: Session, room_name: str, admin_id: int):
    db_room = get_room_by_name(db, room_name)
    if db_room:
        return db_room
    return create_room(db, room_name=room_name, admin_id=admin_id)

def get_messages_for_room(db: Session, room_name: str, skip: int = 0, limit: int = 100):
    room = get_room_by_name(db, room_name)
    if not room:
        return []
    return db.query(models.Message).filter(models.Message.room_id == room.id).order_by(models.Message.timestamp.asc()).offset(skip).limit(limit).all()

def create_message(db: Session, text: str, author_id: int, room_id: int):
    db_message = models.Message(text=text, author_id=author_id, room_id=room_id)
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def update_user_last_room(db: Session, user: models.User, room: models.ChatRoom):
    user.last_room_id = room.id
    db.commit()
    return user

def delete_messages_for_room(db: Session, room_name: str):
    room = get_room_by_name(db, room_name)
    if room:
        db.query(models.Message).filter(models.Message.room_id == room.id).delete(synchronize_session=False)

def delete_room(db: Session, room_name: str):
    room = get_room_by_name(db, room_name)
    if room:
        # First, delete all messages in the room
        delete_messages_for_room(db, room_name)
        # Clear last_room_id for any users in this room
        db.query(models.User).filter(models.User.last_room_id == room.id).update({"last_room_id": None})
        
        # Delete the room itself
        db.delete(room)
        
        # Commit all changes as a single transaction
        db.commit()

def delete_room_and_messages(db: Session, room_name: str):
    room = get_room_by_name(db, room_name)
    if room:
        # 1. Delete associated messages
        db.query(models.Message).filter(models.Message.room_id == room.id).delete(synchronize_session=False)
        # 2. Clear last_room_id for any users that were in this room
        db.query(models.User).filter(models.User.last_room_id == room.id).update({"last_room_id": None})
        # 3. Delete the room itself
        db.delete(room)
        # 4. Commit all changes as a single transaction
        db.commit() 