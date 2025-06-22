"""
This module is the main entry point for the FastAPI chat application.

It defines the FastAPI application instance, mounts the static files,
and sets up the primary WebSocket endpoint for real-time chat functionality.
It also manages the WebSocket connections and orchestrates the business logic
by interacting with the database through the `crud` module.
"""

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
    """
    Manages WebSocket connections for chat rooms and the lobby.

    This class handles the logic for connecting users, moving them between
    the lobby and different chat rooms, and broadcasting messages to the
    appropriate clients.
    """
    def __init__(self):
        """Initializes the connection manager with empty lobby and room lists."""
        # A dictionary to hold active connections in rooms: {room_name: {username: websocket}}
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}
        # A dictionary for users connected to the lobby but not in a room: {username: websocket}
        self.lobby: Dict[str, WebSocket] = {}

    async def connect_to_lobby(self, websocket: WebSocket, username: str):
        """Accepts a new WebSocket connection and adds the user to the lobby."""
        await websocket.accept()
        self.lobby[username] = websocket

    def move_to_room(self, websocket: WebSocket, username:str, room_name: str):
        """Moves a user from the lobby to a specific chat room."""
        if username in self.lobby:
            del self.lobby[username]
        
        if room_name not in self.rooms:
            self.rooms[room_name] = {}
        self.rooms[room_name][username] = websocket

    def move_to_lobby(self, username: str, room_name: str):
        """Moves a user from a chat room back to the lobby."""
        if room_name in self.rooms and username in self.rooms[room_name]:
            websocket = self.rooms[room_name][username]
            self.lobby[username] = websocket
            del self.rooms[room_name][username]
            # If the room is now empty, remove it from the active list
            if not self.rooms[room_name]:
                del self.rooms[room_name]
            return True
        return False

    def disconnect_from_lobby(self, username: str):
        """Removes a user from the lobby."""
        if username in self.lobby:
            del self.lobby[username]

    def disconnect_from_room(self, username: str, room_name: str):
        """Removes a user from a room and deletes the room if it becomes empty."""
        if room_name in self.rooms and username in self.rooms[room_name]:
            del self.rooms[room_name][username]
            if not self.rooms[room_name]:
                del self.rooms[room_name]

    async def broadcast_to_room(self, room_name: str, message: str):
        """Sends a message to all users in a specific room."""
        if room_name in self.rooms:
            for connection in self.rooms[room_name].values():
                await connection.send_text(message)

    async def close_room(self, room_name: str):
        """Forcibly closes the connection for all users in a room and removes the room."""
        if room_name in self.rooms:
            for username, connection in self.rooms[room_name].items():
                await connection.close(code=1000)
            del self.rooms[room_name]

    async def broadcast_active_rooms(self):
        """Broadcasts a list of currently active rooms to all users in the lobby."""
        active_room_list = list(self.rooms.keys())
        message = json.dumps({"type": "active_room_list", "rooms": active_room_list})
        
        # We broadcast active rooms to everyone in the lobby
        for connection in self.lobby.values():
            await connection.send_text(message)
    
    async def broadcast_existing_rooms(self, db: Session):
        """
        Broadcasts a list of all existing (not closed) rooms from the database
        to all users in the lobby.
        """
        all_rooms = crud.get_all_rooms(db)
        existing_room_list = [room.name for room in all_rooms]
        message = json.dumps({"type": "existing_room_list", "rooms": existing_room_list})
        
        # We broadcast existing rooms to everyone in the lobby
        for connection in self.lobby.values():
            await connection.send_text(message)

# A single manager instance to handle all connections for the application
manager = RoomConnectionManager()

# --- Database Dependency ---
def get_db():
    """
    FastAPI dependency that provides a database session for a single request.
    
    This function creates a new SQLAlchemy SessionLocal for each request that needs it,
    and ensures that the session is always closed afterward, even if an error
    occurs. This is a standard pattern for managing database connections in FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- WebSocket Endpoint ---
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str, db: Session = Depends(get_db)):
    """
    The main WebSocket endpoint for the chat application.
    
    This function handles the entire lifecycle of a user's connection.
    - Connects the user and places them in the lobby.
    - Handles auto-rejoining of the last active room.
    - Listens for incoming messages and routes them based on their 'action'.
    - Handles user disconnection gracefully.
    """
    # 1. User Connection and Lobby
    # Get or create the user in the database and connect them to the lobby.
    user = crud.get_or_create_user(db, username=username)
    await manager.connect_to_lobby(websocket, username)
    # Send the initial lists of active and existing rooms.
    await manager.broadcast_active_rooms()
    await manager.broadcast_existing_rooms(db)

    current_room = None

    # 2. Auto-Rejoin Logic
    # If the user has a `last_room_id` and the room still exists, join them automatically.
    if user and user.last_room_id:
        last_room = crud.get_room_by_id(db, user.last_room_id)
        if last_room:
            # Bypassing the lobby, joining room immediately
            current_room = last_room.name
            manager.move_to_room(websocket, username, current_room)

            # Confirm the join and send room history
            await websocket.send_text(json.dumps({"type": "join_confirm", "isAdmin": user.id == last_room.admin_id}))
            history = crud.get_messages_for_room(db, room_name=current_room)
            for msg in history:
                await websocket.send_text(json.dumps({"type": "message", "sender": msg.author.username, "message": msg.text}))
            
            # Notify others in the room of the reconnection.
            await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"User '{username}' has reconnected"}))
        else:
            # If the last room was closed, notify the user.
            await websocket.send_text(json.dumps({"type": "last_room_closed"}))

    # 3. Main Message Loop
    # Listen for incoming messages from the client until they disconnect.
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            # --- ACTION: Join a room ---
            if action == "join":
                room_name = message.get("room")
                current_room = room_name
                # Get or create the room and set the user's last_room for auto-rejoin.
                room = crud.get_or_create_room(db, room_name=room_name, admin_id=user.id)
                crud.update_user_last_room(db, user=user, room=room)
                manager.move_to_room(websocket, username, room_name)

                # Confirm join, send history, and notify others.
                is_admin = user.id == room.admin_id
                await websocket.send_text(json.dumps({"type": "join_confirm", "isAdmin": is_admin}))
                history = crud.get_messages_for_room(db, room_name=room_name)
                for msg in history:
                    await websocket.send_text(json.dumps({"type": "message", "sender": msg.author.username, "message": msg.text}))
                await manager.broadcast_to_room(room_name, json.dumps({"type": "info", "message": f"User '{username}' has joined the room '{room_name}'"}))
                # Update room lists for everyone in the lobby.
                await manager.broadcast_active_rooms()
                await manager.broadcast_existing_rooms(db)

            # --- ACTION: Leave a room ---
            elif action == "leave" and current_room:
                manager.move_to_lobby(username, current_room)
                await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"User '{username}' has left the room"}))
                current_room = None
                # Update room lists for everyone in the lobby.
                await manager.broadcast_active_rooms()
                await manager.broadcast_existing_rooms(db)

            # --- ACTION: Send a message ---
            elif action == "message" and current_room:
                text = message.get("message")
                room = crud.get_room_by_name(db, room_name=current_room)
                # Create the message in the database and broadcast it.
                if user and room:
                    crud.create_message(db, text=text, author_id=user.id, room_id=room.id)
                await manager.broadcast_to_room(current_room, json.dumps({"type": "message", "sender": username, "message": text}))
            
            # --- ACTION: Close a room (Admin only) ---
            elif action == "close" and current_room:
                room = crud.get_room_by_name(db, room_name=current_room)
                if user and room and user.id == room.admin_id:
                    # Notify users, close their connections, and delete the room from the DB.
                    await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"Room '{current_room}' has been closed by the admin."}))
                    await manager.close_room(current_room)
                    
                    # This single function handles the entire transaction atomically.
                    crud.delete_room(db, room_name=current_room)
                    # Expire all objects in the session to force a fresh read from the DB.
                    db.expire_all()
                    
                    # Update room lists for everyone in the lobby.
                    await manager.broadcast_active_rooms()
                    await manager.broadcast_existing_rooms(db)
                    current_room = None

    # 4. Exception Handling
    except WebSocketDisconnect:
        # If the user disconnects, remove them from the lobby or their current room.
        if current_room:
            manager.disconnect_from_room(username, current_room)
            await manager.broadcast_to_room(current_room, json.dumps({"type": "info", "message": f"User '{username}' has left the room"}))
        else:
            manager.disconnect_from_lobby(username)
        
        # Update the room lists for the lobby.
        await manager.broadcast_active_rooms()
        await manager.broadcast_existing_rooms(db)

    except json.JSONDecodeError:
        # Handle cases where the client sends invalid JSON.
        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON format."})) 