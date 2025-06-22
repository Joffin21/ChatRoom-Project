import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    last_room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=True)

    messages = relationship("Message", back_populates="author")
    last_room = relationship("ChatRoom", foreign_keys=[last_room_id])


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    messages = relationship("Message", back_populates="room", cascade="all, delete-orphan")
    admin = relationship("User", foreign_keys=[admin_id])


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    author_id = Column(Integer, ForeignKey("users.id"))
    room_id = Column(Integer, ForeignKey("chat_rooms.id"))

    author = relationship("User", back_populates="messages")
    room = relationship("ChatRoom", back_populates="messages") 