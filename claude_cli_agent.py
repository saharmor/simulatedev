import json
from typing import List
from .base_cli_agent import BaseCliAgent
from .models import AgentConfig

class ClaudeCliAgent(BaseCliAgent):
    """Claude CLI agent implementation"""
    
    def parse_output(self, text: str) -> str:
        """Parse Claude's JSON streaming output"""
        if not text:
            return ""
        
        cleaned = self.clean_terminal_output(text)
        output_lines = []
        
        for line in cleaned.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            try:
                json_obj = json.loads(line)
                
                # Handle different message types
                if json_obj.get('type') == 'system':
                    if json_obj.get('subtype') == 'init':
                        output_lines.append(f"[Claude] Initializing session...")
                        model = json_obj.get('model', 'unknown')
                        output_lines.append(f"[Claude] Model: {model}")
                
                elif json_obj.get('type') == 'assistant':
                    message = json_obj.get('message', {})
                    content = message.get('content', [])
                    
                    for content_item in content:
                        if content_item.get('type') == 'text':
                            text_content = content_item.get('text', '')
                            if text_content.strip():
                                output_lines.append(text_content)
                        
                        elif content_item.get('type') == 'tool_use':
                            tool_name = content_item.get('name', 'unknown')
                            output_lines.append(f"\n[Tool] Using: {tool_name}")
                            
                            # Show tool details
                            input_data = content_item.get('input', {})
                            if tool_name == 'Write':
                                file_path = input_data.get('file_path', '')
                                if file_path:
                                    output_lines.append(f"   Creating file: {file_path}")
                            elif tool_name == 'Edit':
                                file_path = input_data.get('file_path', '')
                                if file_path:
                                    output_lines.append(f"   Editing file: {file_path}")
                            elif tool_name == 'Read':
                                file_path = input_data.get('file_path', '')
                                if file_path:
                                    output_lines.append(f"   Reading file: {file_path}")
                            elif tool_name == 'Bash':
                                command = input_data.get('command', '')
                                if command:
                                    output_lines.append(f"   Running: {command}")
                
                elif json_obj.get('type') == 'user':
                    message = json_obj.get('message', {})
                    content = message.get('content', [])
                    
                    for content_item in content:
                        if content_item.get('type') == 'tool_result':
                            result_content = content_item.get('content', '')
                            if result_content:
                                # Truncate long results
                                if len(result_content) > 200:
                                    result_content = result_content[:200] + "..."
                                output_lines.append(f"   Result: {result_content}")
                
                elif json_obj.get('type') == 'result':
                    if json_obj.get('subtype') == 'success':
                        output_lines.append("\n[Claude] Task completed successfully!")
                        result = json_obj.get('result', '')
                        if result:
                            output_lines.append(f"   Result: {result}")
                        cost = json_obj.get('cost_usd', 0)
                        duration = json_obj.get('duration_ms', 0)
                        output_lines.append(f"   Duration: {duration/1000:.1f}s, Cost: ${cost:.4f}")
                    else:
                        error = json_obj.get('error', 'Unknown error')
                        output_lines.append(f"\n[Claude] Task failed: {error}")
                        
            except json.JSONDecodeError:
                # Not JSON, treat as regular output
                if line:
                    output_lines.append(line)
            except Exception as e:
                self.logger.debug(f"Error parsing Claude JSON: {e}")
                output_lines.append(line)
        
        return '\n'.join(output_lines)
    
    def get_yolo_command_modification(self, base_command: List[str]) -> List[str]:
        """Modify Claude command for YOLO mode"""
        modified = base_command.copy()
        
        # Replace acceptEdits with bypassPermissions for YOLO
        if "--permission-mode" in modified and "acceptEdits" in modified:
            accept_idx = modified.index("acceptEdits")
            modified[accept_idx] = "bypassPermissions"
        
        return modified
    
    async def apply_yolo_mode(self, pane: str, run_command_func) -> bool:
        """Claude YOLO is handled via command modification, no post-startup action needed"""
        return True 