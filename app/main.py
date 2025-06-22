import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Dict, List

from . import models, crud
from .database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get(request: Request):
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

class RoomConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}
        self.lobby: Dict[str, WebSocket] = {}

    async def connect_to_lobby(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.lobby[username] = websocket

    def move_to_room(self, websocket: WebSocket, username: str, room_name: str):
        if username in self.lobby:
            del self.lobby[username]
        
        if room_name not in self.rooms:
            self.rooms[room_name] = {}
        self.rooms[room_name][username] = websocket

    def move_to_lobby(self, username: str, room_name: str):
        if room_name in self.rooms and username in self.rooms[room_name]:
            websocket = self.rooms[room_name][username]
            self.lobby[username] = websocket
            del self.rooms[room_name][username]
            if not self.rooms[room_name]:
                del self.rooms[room_name]
            return True
        return False

    def disconnect_from_lobby(self, username: str):
        if username in self.lobby:
            del self.lobby[username]

    def disconnect_from_room(self, username: str, room_name: str):
        if room_name in self.rooms and username in self.rooms[room_name]:
            del self.rooms[room_name][username]
            if not self.rooms[room_name]:
                del self.rooms[room_name]

    async def broadcast_to_room(self, room_name: str, message: str):
        if room_name in self.rooms:
            for connection in self.rooms[room_name].values():
                await connection.send_text(message)

    async def close_room(self, room_name: str):
        if room_name in self.rooms:
            for username, connection in self.rooms[room_name].items():
                await connection.close(code=1000)
            del self.rooms[room_name]

    async def broadcast_active_rooms(self):
        active_room_list = list(self.rooms.keys())
        message = json.dumps({"type": "active_room_list", "rooms": active_room_list})
        
        # We broadcast active rooms to everyone in the lobby
        for connection in self.lobby.values():
            await connection.send_text(message)
    
    async def broadcast_existing_rooms(self, db: Session):
        all_rooms = crud.get_all_rooms(db)
        existing_room_list = [room.name for room in all_rooms]
        message = json.dumps({"type": "existing_room_list", "rooms": existing_room_list})
        
        # We broadcast existing rooms to everyone in the lobby
        for connection in self.lobby.values():
            await connection.send_text(message)

manager = RoomConnectionManager()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str, db: Session = Depends(get_db)):
    user = crud.get_or_create_user(db, username=username)
    await manager.connect_to_lobby(websocket, username)
    await manager.broadcast_active_rooms()
    await manager.broadcast_existing_rooms(db)

    current_room = None
    # Auto-rejoin logic
    if user and user.last_room_id:
        last_room = crud.get_room_by_id(db, user.last_room_id)
        if last_room:
            # Bypassing the lobby, joining room immediately
            current_room = last_room.name
            manager.move_to_room(websocket, username, current_room)

            await websocket.send_text(json.dumps({"type": "join_confirm", "isAdmin": user.id == last_room.admin_id}))
            
            history = crud.get_messages_for_room(db, room_name=current_room)
            for msg in history:
                await websocket.send_text(json.dumps({"type": "message", "sender": msg.author.username, "message": msg.text}))
            
            await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"User '{username}' has reconnected"}))
        else:
            await websocket.send_text(json.dumps({"type": "last_room_closed"}))
    else:
        current_room = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "join":
                room_name = message.get("room")
                current_room = room_name
                room = crud.get_or_create_room(db, room_name=room_name, admin_id=user.id)
                crud.update_user_last_room(db, user=user, room=room)
                manager.move_to_room(websocket, username, room_name)

                is_admin = user.id == room.admin_id
                await websocket.send_text(json.dumps({"type": "join_confirm", "isAdmin": is_admin}))

                history = crud.get_messages_for_room(db, room_name=room_name)
                for msg in history:
                    await websocket.send_text(json.dumps({"type": "message", "sender": msg.author.username, "message": msg.text}))

                await manager.broadcast_to_room(room_name, json.dumps({"type": "info", "message": f"User '{username}' has joined the room '{room_name}'"}))
                await manager.broadcast_active_rooms()
                await manager.broadcast_existing_rooms(db)

            elif action == "leave" and current_room:
                manager.move_to_lobby(username, current_room)
                await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"User '{username}' has left the room"}))
                current_room = None
                await manager.broadcast_active_rooms()
                await manager.broadcast_existing_rooms(db)

            elif action == "message" and current_room:
                text = message.get("message")
                room = crud.get_room_by_name(db, room_name=current_room)
                if user and room:
                    crud.create_message(db, text=text, author_id=user.id, room_id=room.id)
                
                await manager.broadcast_to_room(current_room, json.dumps({"type": "message", "sender": username, "message": text}))
            
            elif action == "close" and current_room:
                room = crud.get_room_by_name(db, room_name=current_room)
                if user and room and user.id == room.admin_id:
                    await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"Room '{current_room}' has been closed by the admin."}))
                    await manager.close_room(current_room)
                    
                    # This single function handles the entire transaction atomically.
                    crud.delete_room(db, room_name=current_room)
                    # Expire all objects in the session to force a fresh read from the DB.
                    db.expire_all()
                    
                    await manager.broadcast_active_rooms()
                    await manager.broadcast_existing_rooms(db)
                    current_room = None

    except WebSocketDisconnect:
        if current_room:
            manager.disconnect_from_room(username, current_room)
            await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"User '{username}' has left the room"}))
        else:
            manager.disconnect_from_lobby(username)
        
        await manager.broadcast_active_rooms()
        await manager.broadcast_existing_rooms(db)

    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON format."})) 