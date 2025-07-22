from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import asyncio
from datetime import datetime


class WebSocketManager:
    """Manages WebSocket connections for real-time task progress updates"""
    
    _instance = None
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):
            # Dictionary: task_id -> list of WebSocket connections
            self.connections: Dict[str, List[WebSocket]] = {}
            self._initialized = True
            print(f"[WebSocketManager] Singleton instance created with ID: {id(self)}")
        else:
            print(f"[WebSocketManager] Reusing existing singleton instance with ID: {id(self)}")
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept a WebSocket connection and add it to the task's connection list"""
        await websocket.accept()
        
        if task_id not in self.connections:
            self.connections[task_id] = []
        
        self.connections[task_id].append(websocket)
        print(f"[WebSocket] Client connected to task {task_id}. Total connections: {len(self.connections[task_id])}")
        print(f"[WebSocket] Manager instance ID: {id(self)}")
        print(f"[WebSocket] All tracked tasks: {list(self.connections.keys())}")
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove a WebSocket connection from the task's connection list"""
        if task_id in self.connections:
            try:
                self.connections[task_id].remove(websocket)
                print(f"[WebSocket] Client disconnected from task {task_id}. Remaining connections: {len(self.connections[task_id])}")
                
                # Clean up empty connection lists
                if not self.connections[task_id]:
                    del self.connections[task_id]
                    print(f"[WebSocket] Removed empty connection list for task {task_id}")
                    
            except ValueError:
                print(f"[WebSocket] WebSocket not found in connection list for task {task_id}")
        else:
            print(f"[WebSocket] No connection list found for task {task_id}")
    
    async def send_progress_update(self, task_id: str, progress_data: dict):
        """Send progress update to all connected clients for a task"""
        print(f"[WebSocketManager] Attempting to send progress update for task: {task_id}")
        print(f"[WebSocketManager] Manager instance ID: {id(self)}")
        print(f"[WebSocketManager] Current connections: {list(self.connections.keys())}")
        print(f"[WebSocketManager] Total connections across all tasks: {sum(len(conns) for conns in self.connections.values())}")
        
        if task_id not in self.connections:
            print(f"[WebSocketManager] No connections found for task: {task_id}")
            print(f"[WebSocketManager] Available tasks: {list(self.connections.keys())}")
            return
        
        connection_count = len(self.connections[task_id])
        print(f"[WebSocketManager] Sending to {connection_count} connections for task: {task_id}")
        
        # Add timestamp to progress data
        message_data = {
            **progress_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        message = json.dumps(message_data)
        print(f"[WebSocketManager] Sending message: {message}")
        
        # Send to all connections for this task
        connections_to_remove = []
        successful_sends = 0
        
        for i, websocket in enumerate(self.connections[task_id]):
            try:
                await websocket.send_text(message)
                successful_sends += 1
                print(f"[WebSocketManager] Successfully sent message to connection {i+1}/{connection_count}")
            except Exception as e:
                print(f"[WebSocket] Failed to send message to connection {i+1}: {e}")
                connections_to_remove.append(websocket)
        
        print(f"[WebSocketManager] Successfully sent to {successful_sends}/{connection_count} connections")
        
        # Remove dead connections
        for websocket in connections_to_remove:
            self.disconnect(websocket, task_id)
    
    def get_connection_count(self, task_id: str) -> int:
        """Get number of active connections for a task"""
        return len(self.connections.get(task_id, []))
    
    def get_all_connections_count(self) -> int:
        """Get total number of active connections across all tasks"""
        return sum(len(connections) for connections in self.connections.values())
    
    def debug_connections(self) -> dict:
        """Debug method to inspect current connections"""
        return {
            "instance_id": id(self),
            "total_tasks": len(self.connections),
            "task_connections": {
                task_id: len(connections) 
                for task_id, connections in self.connections.items()
            },
            "total_connections": self.get_all_connections_count()
        }
    
    async def broadcast_system_message(self, message: str):
        """Send a system message to all connected clients"""
        system_message = json.dumps({
            "type": "system",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        all_connections = []
        for connections_list in self.connections.values():
            all_connections.extend(connections_list)
        
        connections_to_remove = []
        
        for websocket in all_connections:
            try:
                await websocket.send_text(system_message)
            except Exception:
                connections_to_remove.append(websocket)
        
        # Clean up dead connections (this is a bit more complex since we need to find which task they belong to)
        for websocket in connections_to_remove:
            for task_id, connections_list in self.connections.items():
                if websocket in connections_list:
                    self.disconnect(websocket, task_id)
                    break


# Create the singleton instance
websocket_manager = WebSocketManager() 