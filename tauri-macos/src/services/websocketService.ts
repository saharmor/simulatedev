import { WebSocketProgressMessage } from '../types/progress';

// WebSocketMessage is now imported from types/progress as WebSocketProgressMessage

export interface WebSocketCallbacks {
  onProgress?: (data: WebSocketProgressMessage) => void;
  onError?: (error: string) => void;
  onClose?: () => void;
  onOpen?: () => void;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private taskId: string | null = null;
  private callbacks: WebSocketCallbacks = {};
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private isConnecting = false;

  constructor() {
    console.log("[WebSocketService] WebSocket service initialized");
  }

  connect(taskId: string, callbacks: WebSocketCallbacks): void {
    console.log(`[WebSocketService] Connecting to WebSocket for task: ${taskId}`);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log("[WebSocketService] WebSocket already connected, closing existing connection");
      this.ws.close();
    }

    this.taskId = taskId;
    this.callbacks = callbacks;
    this.isConnecting = true;

    try {
      const wsUrl = `ws://localhost:8000/ws/tasks/${taskId}`;
      console.log(`[WebSocketService] Connecting to: ${wsUrl}`);
      
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        console.log(`[WebSocketService] WebSocket connected for task: ${taskId}`);
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        
        if (this.callbacks.onOpen) {
          this.callbacks.onOpen();
        }
      };

      this.ws.onmessage = (event) => {
        try {
          console.log(`[WebSocketService] Raw message received: ${event.data}`);
          const data: WebSocketProgressMessage = JSON.parse(event.data);
          console.log(`[WebSocketService] Parsed message data:`, data);
          console.log(`[WebSocketService] Message type: ${data.type}`);
          console.log(`[WebSocketService] Task ID: ${data.task_id}`);
          console.log(`[WebSocketService] Step ID: ${data.step_id}`);
          console.log(`[WebSocketService] Status: ${data.status}`);
          console.log(`[WebSocketService] Phase: ${data.phase}`);
          console.log(`[WebSocketService] Step: ${data.step}`);
          console.log(`[WebSocketService] Agent context:`, data.agent_context);
          console.log(`[WebSocketService] Timestamp: ${data.timestamp}`);
          console.log(`[WebSocketService] Full message object:`, JSON.stringify(data, null, 2));
          
          if (data.type === "progress" && this.callbacks.onProgress) {
            console.log(`[WebSocketService] Calling progress callback with data:`, data);
            this.callbacks.onProgress(data);
          } else if (data.type === "error" && this.callbacks.onError) {
            console.log(`[WebSocketService] Calling error callback with message: ${data.error_message}`);
            this.callbacks.onError(data.error_message || "Unknown error");
          } else {
            console.log(`[WebSocketService] No callback found for message type: ${data.type}`);
          }
        } catch (error) {
          console.error("[WebSocketService] Error parsing WebSocket message:", error);
          console.error("[WebSocketService] Raw message that failed to parse:", event.data);
        }
      };

      this.ws.onerror = (error) => {
        console.error(`[WebSocketService] WebSocket error for task ${taskId}:`, error);
        this.isConnecting = false;
        
        if (this.callbacks.onError) {
          this.callbacks.onError("WebSocket connection error");
        }
      };

      this.ws.onclose = (event) => {
        console.log(`[WebSocketService] WebSocket closed for task ${taskId}. Code: ${event.code}, Reason: ${event.reason}`);
        this.isConnecting = false;
        
        if (this.callbacks.onClose) {
          this.callbacks.onClose();
        }

        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        }
      };

    } catch (error) {
      console.error("[WebSocketService] Error creating WebSocket connection:", error);
      this.isConnecting = false;
      
      if (this.callbacks.onError) {
        this.callbacks.onError("Failed to create WebSocket connection");
      }
    }
  }

  private attemptReconnect(): void {
    if (this.isConnecting || !this.taskId) {
      return;
    }

    this.reconnectAttempts++;
    console.log(`[WebSocketService] Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      if (this.taskId) {
        this.connect(this.taskId, this.callbacks);
      }
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
  }

  disconnect(): void {
    console.log(`[WebSocketService] Disconnecting WebSocket for task: ${this.taskId}`);
    
    if (this.ws) {
      this.ws.close(1000, "Client disconnecting");
      this.ws = null;
    }
    
    this.taskId = null;
    this.callbacks = {};
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    this.isConnecting = false;
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  sendMessage(message: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log(`[WebSocketService] Sending message: ${message}`);
      this.ws.send(message);
    } else {
      console.warn("[WebSocketService] Cannot send message - WebSocket not connected");
    }
  }
}

export const websocketService = new WebSocketService(); 