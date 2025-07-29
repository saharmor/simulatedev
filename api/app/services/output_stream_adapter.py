#!/usr/bin/env python3
"""
Output Stream Adapter for CLI Agents
====================================
Bridges tmux output buffers to WebSocket streaming for real-time updates to the 
Tauri frontend. Converts tmux output format to frontend-expected JSON structure
and handles incremental updates efficiently.

This module handles:
- Real-time output capture from tmux sessions
- Format conversion from tmux to WebSocket JSON
- Incremental update streaming
- Output buffering and throttling
- Integration with existing WebSocket manager
"""

import asyncio
import json
import time
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum

from .tmux_service import TmuxService, SessionInfo, SessionStatus
from .websocket_manager import WebSocketManager


class OutputType(Enum):
    """Types of output messages"""
    PROGRESS = "progress"
    OUTPUT = "output" 
    ERROR = "error"
    STATUS = "status"
    COMPLETION = "completion"
    
    def __str__(self):
        return self.value


@dataclass
class StreamConfig:
    """Configuration for output streaming"""
    buffer_size: int = 1000
    throttle_interval: float = 0.1  # 100ms throttling
    max_output_chunk: int = 5000
    heartbeat_interval: float = 30.0  # 30s heartbeat
    enable_compression: bool = False
    
    
@dataclass
class StreamSession:
    """Tracks streaming state for a task session"""
    task_id: str
    session_id: str
    started_at: float
    last_update: float
    output_buffer: List[str] = field(default_factory=list)
    total_lines_sent: int = 0
    last_status: Optional[SessionStatus] = None
    throttle_pending: bool = False
    last_captured_output: str = ""  # Track last output to detect changes
    
    def get_age(self) -> float:
        """Get session age in seconds"""
        return time.time() - self.started_at


class OutputStreamAdapter:
    """Bridges tmux output to WebSocket streaming"""
    
    def __init__(self, tmux_service: TmuxService, 
                 websocket_manager: Optional[WebSocketManager] = None,
                 config: Optional[StreamConfig] = None):
        self.tmux_service = tmux_service
        self.websocket_manager = websocket_manager or WebSocketManager.get_instance()
        self.config = config or StreamConfig()
        
        # Streaming state
        self._streaming_sessions: Dict[str, StreamSession] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Performance tracking
        self._stats = {
            'messages_sent': 0,
            'bytes_sent': 0,
            'sessions_monitored': 0,
            'throttled_updates': 0
        }
        
        self.logger = logging.getLogger(__name__)
        
    async def start(self):
        """Start the output stream adapter"""
        if self._running:
            return
            
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.logger.info("Output stream adapter started")
        
    async def stop(self):
        """Stop the output stream adapter and cleanup"""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel all monitoring tasks
        for task in list(self._monitoring_tasks.values()):
            task.cancel()
            
        await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)
        self._monitoring_tasks.clear()
        
        # Cancel heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
                
        self._streaming_sessions.clear()
        self.logger.info("Output stream adapter stopped")
    
    async def start_streaming(self, task_id: str, session_id: str) -> bool:
        """Start streaming output for a task session"""
        if task_id in self._streaming_sessions:
            self.logger.warning(f"Already streaming for task {task_id}")
            return False
            
        # Verify session exists
        session_info = await self.tmux_service.get_session_status(session_id)
        if not session_info:
            self.logger.error(f"Session {session_id} not found for task {task_id}")
            return False
            
        # Create stream session
        stream_session = StreamSession(
            task_id=task_id,
            session_id=session_id,
            started_at=time.time(),
            last_update=time.time()
        )
        
        self._streaming_sessions[task_id] = stream_session
        
        # Start monitoring task
        monitor_task = asyncio.create_task(
            self._monitor_session_output(task_id)
        )
        self._monitoring_tasks[task_id] = monitor_task
        
        # Send initial status
        await self._send_progress_update(
            task_id,
            OutputType.STATUS,
            {"message": "Output streaming started", "session_id": session_id}
        )
        
        self._stats['sessions_monitored'] += 1
        self.logger.info(f"Started streaming for task {task_id}, session {session_id}")
        return True
        
    async def stop_streaming(self, task_id: str, final_status: Optional[str] = None):
        """Stop streaming for a task"""
        if task_id not in self._streaming_sessions:
            return
            
        # Cancel monitoring task
        if task_id in self._monitoring_tasks:
            self._monitoring_tasks[task_id].cancel()
            try:
                await self._monitoring_tasks[task_id]
            except asyncio.CancelledError:
                pass
            del self._monitoring_tasks[task_id]
            
        # Send final status if provided
        if final_status:
            await self._send_progress_update(
                task_id,
                OutputType.COMPLETION,
                {"status": final_status, "message": "Task completed"}
            )
            
        # Cleanup
        stream_session = self._streaming_sessions.pop(task_id, None)
        if stream_session:
            duration = time.time() - stream_session.started_at
            self.logger.info(
                f"Stopped streaming for task {task_id} after {duration:.2f}s, "
                f"sent {stream_session.total_lines_sent} lines"
            )
    
    async def _monitor_session_output(self, task_id: str):
        """Monitor tmux session output and stream changes"""
        stream_session = self._streaming_sessions.get(task_id)
        if not stream_session:
            return
            
        session_id = stream_session.session_id
        last_throttle_time = 0
        
        try:
            while self._running:
                try:
                    # Check session status
                    session_info = await self.tmux_service.get_session_status(session_id)
                    if not session_info:
                        self.logger.warning(f"Session {session_id} no longer exists")
                        break
                        
                    # Handle status changes
                    if session_info.status != stream_session.last_status:
                        await self._handle_status_change(task_id, stream_session, session_info)
                        stream_session.last_status = session_info.status
                        
                    # Capture new output
                    new_output = await self.tmux_service.capture_session_output(session_id)
                    
                    # Only process if output has actually changed
                    last_output_key = f"last_output_{session_id}"
                    last_output = getattr(stream_session, 'last_captured_output', '')
                    
                    if new_output and new_output != last_output:
                        # Store current output for next comparison
                        stream_session.last_captured_output = new_output
                        
                        # Add to buffer only the new parts
                        output_lines = new_output.split('\n')
                        stream_session.output_buffer.extend(output_lines)
                        self.logger.debug(f"Output changed for {session_id}, added {len(output_lines)} lines")
                    elif new_output == last_output:
                        self.logger.debug(f"No output changes for {session_id}, skipping processing")
                        
                        # Apply buffer size limits
                        if len(stream_session.output_buffer) > self.config.buffer_size:
                            overflow = len(stream_session.output_buffer) - self.config.buffer_size
                            stream_session.output_buffer = stream_session.output_buffer[overflow:]
                        
                        # Throttle output sending
                        current_time = time.time()
                        if current_time - last_throttle_time >= self.config.throttle_interval:
                            await self._send_buffered_output(task_id, stream_session)
                            last_throttle_time = current_time
                        else:
                            stream_session.throttle_pending = True
                            self._stats['throttled_updates'] += 1
                    
                    # Send throttled updates if needed
                    elif stream_session.throttle_pending:
                        current_time = time.time()
                        if current_time - last_throttle_time >= self.config.throttle_interval:
                            await self._send_buffered_output(task_id, stream_session)
                            last_throttle_time = current_time
                            stream_session.throttle_pending = False
                    
                    # Check if session is done
                    if session_info.status in [SessionStatus.DONE, SessionStatus.STOPPED]:
                        # Send final output
                        if stream_session.output_buffer:
                            await self._send_buffered_output(task_id, stream_session)
                        break
                        
                    # Sleep before next check - reduced frequency to minimize console spam
                    await asyncio.sleep(2.0)  # Increased from 0.5s to 2s
                    
                except Exception as e:
                    self.logger.error(f"Error monitoring session {session_id}: {e}")
                    await asyncio.sleep(3.0)  # Increased backoff to reduce spam on errors
                    
        except asyncio.CancelledError:
            self.logger.debug(f"Monitoring cancelled for task {task_id}")
        except Exception as e:
            self.logger.error(f"Unexpected error monitoring task {task_id}: {e}")
            
    async def _handle_status_change(self, task_id: str, stream_session: StreamSession, 
                                   session_info: SessionInfo):
        """Handle session status changes"""
        status_message = {
            "session_id": session_info.session_id,
            "status": session_info.status.value,
            "agent_type": session_info.agent.__class__.__name__,
            "yolo_mode": session_info.yolo_mode
        }
        
        if session_info.status == SessionStatus.RUNNING:
            status_message["message"] = "Agent is running"
            await self._send_progress_update(task_id, OutputType.PROGRESS, status_message)
        elif session_info.status == SessionStatus.REQUIRES_USER_INPUT:
            status_message["message"] = "Agent requires user input"
            await self._send_progress_update(task_id, OutputType.STATUS, status_message)
        elif session_info.status == SessionStatus.DONE:
            status_message["message"] = "Agent completed successfully"
            await self._send_progress_update(task_id, OutputType.COMPLETION, status_message)
        elif session_info.status == SessionStatus.STOPPED:
            status_message["message"] = "Agent stopped"
            await self._send_progress_update(task_id, OutputType.ERROR, status_message)
            
    async def _send_buffered_output(self, task_id: str, stream_session: StreamSession):
        """Send buffered output to WebSocket"""
        if not stream_session.output_buffer:
            return
            
        # Prepare output chunk
        output_lines = stream_session.output_buffer.copy()
        stream_session.output_buffer.clear()
        
        # Limit chunk size
        if len(output_lines) > self.config.max_output_chunk:
            # Keep most recent lines
            output_lines = output_lines[-self.config.max_output_chunk:]
            
        output_text = '\n'.join(output_lines)
        
        # Send output
        await self._send_progress_update(
            task_id,
            OutputType.OUTPUT,
            {
                "output": output_text,
                "line_count": len(output_lines),
                "total_lines_sent": stream_session.total_lines_sent + len(output_lines)
            }
        )
        
        stream_session.total_lines_sent += len(output_lines)
        stream_session.last_update = time.time()
        
    async def _send_progress_update(self, task_id: str, output_type: OutputType, 
                                   data: Dict[str, Any]):
        """Send progress update via WebSocket manager"""
        try:
            message_data = {
                "type": output_type.value,
                "task_id": task_id,
                **data
            }
            
            await self.websocket_manager.send_progress_update(task_id, message_data)
            
            # Update stats
            self._stats['messages_sent'] += 1
            message_size = len(json.dumps(message_data, default=str))
            self._stats['bytes_sent'] += message_size
            
        except Exception as e:
            self.logger.error(f"Failed to send progress update for task {task_id}: {e}")
            
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to active sessions"""
        try:
            while self._running:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                current_time = time.time()
                for task_id, stream_session in list(self._streaming_sessions.items()):
                    # Send heartbeat if no recent activity
                    if current_time - stream_session.last_update > self.config.heartbeat_interval:
                        await self._send_progress_update(
                            task_id,
                            OutputType.STATUS,
                            {
                                "message": "heartbeat",
                                "session_age": stream_session.get_age(),
                                "lines_sent": stream_session.total_lines_sent
                            }
                        )
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error in heartbeat loop: {e}")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get streaming statistics"""
        return {
            **self._stats,
            'active_sessions': len(self._streaming_sessions),
            'monitoring_tasks': len(self._monitoring_tasks),
            'running': self._running
        }
        
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get information about active streaming sessions"""
        current_time = time.time()
        return [
            {
                "task_id": stream_session.task_id,
                "session_id": stream_session.session_id,
                "age": current_time - stream_session.started_at,
                "lines_sent": stream_session.total_lines_sent,
                "last_status": stream_session.last_status.value if stream_session.last_status else None,
                "throttle_pending": stream_session.throttle_pending
            }
            for stream_session in self._streaming_sessions.values()
        ] 