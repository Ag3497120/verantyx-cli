"""
Cross Structure Generator - Generate Cross memory from chat interactions

Converts conversation history into Cross 6-axis structure.
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CrossGenerator:
    """
    Generate Cross structure from conversation data

    Axes:
    - UP: Goals/Intent (what user wants to achieve)
    - DOWN: Facts/Foundation (concrete data, message counts)
    - FRONT: Current Focus (recent messages)
    - BACK: History (past messages)
    - RIGHT: Expansion (learned patterns, possibilities)
    - LEFT: Constraints (system limits, rules)
    """

    def __init__(
        self,
        output_file: Path,
        update_interval: float = 3.0,
        agent_id: Optional[int] = None,
        agent_role: Optional[str] = None
    ):
        """
        Initialize Cross generator

        Args:
            output_file: Path to save Cross structure
            update_interval: Update interval in seconds
            agent_id: Agent ID (for multi-agent mode)
            agent_role: Agent role (for multi-agent mode)
        """
        self.output_file = output_file
        self.update_interval = update_interval
        self.agent_id = agent_id
        self.agent_role = agent_role

        # Conversation data
        self.user_messages: List[Dict] = []
        self.assistant_messages: List[Dict] = []
        self.session_start = datetime.now()

        # Progress tracking (for multi-agent)
        self.current_task: Optional[str] = None
        self.task_status: str = "idle"  # idle, working, completed, failed
        self.task_progress_percent: int = 0
        self.subtasks: List[Dict[str, Any]] = []

        # Update thread
        self._running = False
        self._update_thread: threading.Thread = None

    def start(self):
        """Start Cross structure updates"""
        self._running = True
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True
        )
        self._update_thread.start()
        logger.info(f"Cross generator started (updates every {self.update_interval}s)")

    def stop(self):
        """Stop Cross structure updates"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=2.0)
        logger.info("Cross generator stopped")

    def add_user_message(self, content: str):
        """Add user message to conversation history"""
        self.user_messages.append({
            'timestamp': datetime.now().isoformat(),
            'content': content
        })

    def add_assistant_message(self, content: str):
        """Add assistant message to conversation history"""
        self.assistant_messages.append({
            'timestamp': datetime.now().isoformat(),
            'content': content
        })

    def _update_loop(self):
        """Update Cross structure periodically"""
        while self._running:
            try:
                self._generate_and_save()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error updating Cross structure: {e}")
                time.sleep(self.update_interval)

    def _generate_and_save(self):
        """Generate Cross structure and save to file"""
        cross_structure = self._generate_cross_structure()

        # Write atomically
        temp_file = self.output_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cross_structure, f, ensure_ascii=False, indent=2)
        temp_file.replace(self.output_file)

        logger.debug(f"Cross structure updated: {self.output_file}")

    def _generate_cross_structure(self) -> Dict[str, Any]:
        """Generate Cross structure from conversation data"""
        now = datetime.now()
        session_duration = (now - self.session_start).total_seconds()

        # Extract recent messages
        recent_user = [msg['content'] for msg in self.user_messages[-5:]]
        recent_assistant = [msg['content'] for msg in self.assistant_messages[-3:]]

        # Infer current activity
        current_activity = self._infer_activity()

        # Extract learned patterns
        patterns = self._extract_patterns()

        # Build Cross structure
        cross_structure = {
            "type": "verantyx_conversation_cross",
            "timestamp": now.isoformat(),
            "session_start": self.session_start.isoformat(),
            "session_duration_seconds": session_duration,
            "axes": {
                "up": {  # Goals/Intent
                    "goal": "Interactive conversation with Claude",
                    "user_intent": self._infer_user_intent(),
                    "mode": "chat_interaction"
                },
                "down": {  # Facts/Foundation
                    "total_user_messages": len(self.user_messages),
                    "total_assistant_messages": len(self.assistant_messages),
                    "session_duration_seconds": session_duration,
                    "average_message_length": self._calculate_avg_message_length()
                },
                "front": {  # Current Focus
                    "recent_user_messages": recent_user,
                    "recent_assistant_messages": recent_assistant,
                    "current_activity": current_activity,
                    "last_interaction": self.user_messages[-1]['timestamp'] if self.user_messages else None
                },
                "back": {  # History
                    "all_user_messages": [msg['content'] for msg in self.user_messages[-50:]],
                    "all_assistant_messages": [msg['content'] for msg in self.assistant_messages[-50:]],
                    "session_history": {
                        "start": self.session_start.isoformat(),
                        "duration_seconds": session_duration
                    }
                },
                "right": {  # Expansion/Possibilities
                    "learned_patterns": patterns,
                    "conversation_topics": self._extract_topics(),
                    "interaction_style": self._analyze_interaction_style()
                },
                "left": {  # Constraints/Limitations
                    "constraints": [
                        "socket_based_communication",
                        "text_only_interface",
                        "local_processing"
                    ],
                    "system_info": {
                        "update_interval_seconds": self.update_interval,
                        "max_history_messages": 50
                    }
                }
            },
            "progress": {  # NEW: Progress tracking for multi-agent
                "agent_id": self.agent_id,
                "agent_role": self.agent_role,
                "current_task": self.current_task,
                "task_status": self.task_status,
                "task_progress_percent": self.task_progress_percent,
                "subtasks": self.subtasks,
                "last_update": now.isoformat()
            },
            "metadata": {
                "format_version": "1.1",  # Updated version
                "cross_native": True,
                "auto_generated": True,
                "generator": "verantyx_cross_generator",
                "verantyx_cli_version": "1.0.0",
                "multi_agent_enabled": self.agent_id is not None
            }
        }

        return cross_structure

    def _infer_activity(self) -> str:
        """Infer current activity from recent messages"""
        if not self.user_messages:
            return "waiting_for_input"

        if not self.assistant_messages:
            return "processing_first_message"

        # Check time since last message
        last_msg_time = datetime.fromisoformat(self.user_messages[-1]['timestamp'])
        time_since_last = (datetime.now() - last_msg_time).total_seconds()

        if time_since_last < 5:
            return "active_conversation"
        elif time_since_last < 30:
            return "recent_interaction"
        else:
            return "idle"

    def _infer_user_intent(self) -> str:
        """Infer user's intent from messages"""
        if not self.user_messages:
            return "unknown"

        recent_messages = ' '.join([msg['content'] for msg in self.user_messages[-3:]])
        lower = recent_messages.lower()

        # Simple keyword-based inference
        if any(word in lower for word in ['fix', 'bug', 'error', '問題', 'エラー']):
            return "debugging"
        elif any(word in lower for word in ['implement', 'add', '実装', '追加']):
            return "feature_development"
        elif any(word in lower for word in ['explain', 'how', 'what', '説明', 'どう']):
            return "learning"
        elif any(word in lower for word in ['hello', 'hi', 'こんにちは', 'はじめ']):
            return "greeting"
        else:
            return "general_conversation"

    def _extract_patterns(self) -> List[str]:
        """Extract patterns from conversation"""
        patterns = []

        if len(self.user_messages) > 3:
            patterns.append("multi_turn_conversation")

        # Check for common topics
        all_text = ' '.join([msg['content'] for msg in self.user_messages])

        if 'code' in all_text.lower() or 'コード' in all_text:
            patterns.append("code_discussion")

        if len(self.user_messages) > 10:
            patterns.append("extended_session")

        return patterns

    def _extract_topics(self) -> List[str]:
        """Extract conversation topics"""
        topics = []

        all_text = ' '.join([msg['content'] for msg in self.user_messages])
        lower = all_text.lower()

        # Simple keyword extraction
        topic_keywords = {
            'programming': ['code', 'function', 'class', 'コード', '関数'],
            'debugging': ['bug', 'error', 'fix', 'バグ', 'エラー'],
            'design': ['design', 'architecture', '設計', 'アーキテクチャ'],
            'testing': ['test', 'テスト'],
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in lower for keyword in keywords):
                topics.append(topic)

        return topics if topics else ['general']

    def _analyze_interaction_style(self) -> str:
        """Analyze user's interaction style"""
        if not self.user_messages:
            return "unknown"

        avg_length = self._calculate_avg_message_length()

        if avg_length < 20:
            return "concise"
        elif avg_length < 100:
            return "moderate"
        else:
            return "detailed"

    def _calculate_avg_message_length(self) -> float:
        """Calculate average message length"""
        if not self.user_messages:
            return 0.0

        total_length = sum(len(msg['content']) for msg in self.user_messages)
        return total_length / len(self.user_messages)

    # ===== Progress tracking methods (for multi-agent) =====

    def set_task(self, task_description: str):
        """Set current task"""
        self.current_task = task_description
        self.task_status = "working"
        self.task_progress_percent = 0
        logger.info(f"Agent {self.agent_id}: Task set - {task_description}")

    def update_progress(self, progress_percent: int, status: Optional[str] = None):
        """Update task progress"""
        self.task_progress_percent = min(100, max(0, progress_percent))
        if status:
            self.task_status = status
        logger.info(f"Agent {self.agent_id}: Progress {self.task_progress_percent}% - {self.task_status}")

    def add_subtask(self, subtask_name: str, subtask_status: str = "pending"):
        """Add subtask"""
        subtask = {
            'name': subtask_name,
            'status': subtask_status,
            'created_at': datetime.now().isoformat()
        }
        self.subtasks.append(subtask)
        logger.info(f"Agent {self.agent_id}: Subtask added - {subtask_name}")

    def update_subtask(self, subtask_index: int, status: str):
        """Update subtask status"""
        if 0 <= subtask_index < len(self.subtasks):
            self.subtasks[subtask_index]['status'] = status
            self.subtasks[subtask_index]['updated_at'] = datetime.now().isoformat()
            logger.info(f"Agent {self.agent_id}: Subtask {subtask_index} - {status}")

    def complete_task(self):
        """Mark task as completed"""
        self.task_status = "completed"
        self.task_progress_percent = 100
        logger.info(f"Agent {self.agent_id}: Task completed - {self.current_task}")

    def fail_task(self, reason: str = "Unknown error"):
        """Mark task as failed"""
        self.task_status = "failed"
        logger.error(f"Agent {self.agent_id}: Task failed - {reason}")
