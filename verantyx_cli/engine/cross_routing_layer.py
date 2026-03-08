"""
Cross Routing Layer - Top-level information control layer

This is the highest layer that controls all information flow between:
- User input
- Master agent (Agent 0)
- Sub-agents (Agent 1, 2, 3, ...)
- Cross structures

Architecture:
┌─────────────────────────────────────────────┐
│         Cross Routing Layer                 │
│  - Parse user input                         │
│  - Detect agent references (e.g., "2番")    │
│  - Route information to correct agent       │
│  - Aggregate progress from all agents       │
│  - Control what info goes to master agent   │
└─────────────────────────────────────────────┘
        ↓                    ↓
┌──────────────┐    ┌────────────────────┐
│ Master Agent │    │ Sub-Agents         │
│ (Agent 0)    │───→│ Agent 1, 2, 3, ... │
│              │    │                    │
│ - Controls   │    │ - Execute tasks    │
│ - Commands   │    │ - Report progress  │
└──────────────┘    └────────────────────┘
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class CrossRoutingLayer:
    """
    Cross Routing Layer - Highest level information controller

    Responsibilities:
    1. Parse user input for agent references
    2. Route messages to appropriate agents
    3. Aggregate Cross structures from all agents
    4. Provide master agent with sub-agent progress
    5. Control information flow to Claude
    """

    def __init__(self, verantyx_dir: Path):
        self.verantyx_dir = verantyx_dir
        self.routing_cross_file = verantyx_dir / "cross_routing.json"

        # Agent reference patterns
        self.agent_patterns = [
            r'(\d+)番(?:の)?(?:エージェント|agent)',  # "2番のエージェント"
            r'(?:エージェント|agent)\s*(\d+)',         # "エージェント2"
            r'agent\s*#?(\d+)',                        # "agent #2"
            r'#(\d+)',                                 # "#2"
        ]

        # Routing history
        self.routing_history: List[Dict[str, Any]] = []

    def parse_input(self, user_input: str) -> Dict[str, Any]:
        """
        Parse user input to detect agent references

        Returns:
            {
                'original_input': str,
                'target_agent': int or None (None = master),
                'command_type': str,  # 'query', 'command', 'broadcast'
                'extracted_agent_refs': List[int],
                'processed_input': str  # Input with agent refs removed
            }
        """
        result = {
            'original_input': user_input,
            'target_agent': None,
            'command_type': 'query',
            'extracted_agent_refs': [],
            'processed_input': user_input
        }

        # Detect agent references
        for pattern in self.agent_patterns:
            matches = re.finditer(pattern, user_input, re.IGNORECASE)
            for match in matches:
                agent_num = int(match.group(1))
                result['extracted_agent_refs'].append(agent_num)

        # If specific agent(s) mentioned, route to those agents
        if result['extracted_agent_refs']:
            # Route to first mentioned agent
            result['target_agent'] = result['extracted_agent_refs'][0]
            result['command_type'] = 'query'  # Query about specific agent

        # Detect command keywords
        command_keywords = {
            'query': ['進捗', '状態', 'status', 'progress', '確認'],
            'command': ['やって', '実行', 'execute', '命令', 'do'],
            'broadcast': ['全員', 'みんな', 'all', 'everyone', '全て']
        }

        for cmd_type, keywords in command_keywords.items():
            if any(keyword in user_input.lower() for keyword in keywords):
                result['command_type'] = cmd_type
                break

        # Log routing decision
        logger.info(f"Routing decision: {result}")

        return result

    def get_agent_progress(self, agent_id: int, agent_cross_file: Path) -> Dict[str, Any]:
        """
        Get progress information for specific agent

        Returns Cross structure with progress info
        """
        if not agent_cross_file.exists():
            return {
                'agent_id': agent_id,
                'status': 'not_available',
                'progress': None
            }

        try:
            with open(agent_cross_file, 'r', encoding='utf-8') as f:
                agent_cross = json.load(f)

            # Extract progress info from Cross structure
            axes = agent_cross.get('axes', {})
            down = axes.get('down', {})
            front = axes.get('front', {})
            right = axes.get('right', {})

            progress = {
                'agent_id': agent_id,
                'status': 'active',
                'total_messages': down.get('total_user_messages', 0),
                'current_activity': front.get('current_activity', 'unknown'),
                'recent_messages': front.get('recent_user_messages', [])[-3:],
                'learned_patterns': right.get('learned_patterns', []),
                'topics': right.get('conversation_topics', []),
                'last_update': agent_cross.get('timestamp', 'unknown')
            }

            return progress

        except Exception as e:
            logger.error(f"Error reading agent {agent_id} progress: {e}")
            return {
                'agent_id': agent_id,
                'status': 'error',
                'error': str(e)
            }

    def aggregate_all_progress(self, agent_cross_files: Dict[int, Path]) -> Dict[str, Any]:
        """
        Aggregate progress from all agents

        Returns comprehensive progress report
        """
        all_progress = {
            'timestamp': datetime.now().isoformat(),
            'num_agents': len(agent_cross_files),
            'agents': {}
        }

        for agent_id, cross_file in agent_cross_files.items():
            progress = self.get_agent_progress(agent_id, cross_file)
            all_progress['agents'][agent_id] = progress

        return all_progress

    def create_master_context(
        self,
        user_input: str,
        routing_info: Dict[str, Any],
        agent_cross_files: Dict[int, Path]
    ) -> str:
        """
        Create context for master agent (Agent 0)

        This context includes:
        - Original user input
        - Referenced agent progress (if any)
        - All sub-agents' current status
        """
        context_parts = []

        # Original input
        context_parts.append(f"User Input: {user_input}")
        context_parts.append("")

        # If user referenced specific agent(s), provide their progress
        if routing_info['extracted_agent_refs']:
            context_parts.append("=== Referenced Agent Progress ===")
            for agent_id in routing_info['extracted_agent_refs']:
                if agent_id in agent_cross_files:
                    progress = self.get_agent_progress(agent_id, agent_cross_files[agent_id])
                    context_parts.append(f"\nAgent {agent_id}:")
                    context_parts.append(f"  Status: {progress.get('status', 'unknown')}")
                    context_parts.append(f"  Activity: {progress.get('current_activity', 'unknown')}")
                    context_parts.append(f"  Messages: {progress.get('total_messages', 0)}")
                    context_parts.append(f"  Topics: {', '.join(progress.get('topics', []))}")

                    # Include recent messages
                    recent = progress.get('recent_messages', [])
                    if recent:
                        context_parts.append(f"  Recent activity:")
                        for msg in recent[-3:]:
                            context_parts.append(f"    - {msg[:100]}...")
                else:
                    context_parts.append(f"\nAgent {agent_id}: Not found")

            context_parts.append("")

        # Provide summary of all sub-agents (excluding master itself)
        context_parts.append("=== All Sub-Agents Status ===")
        sub_agent_files = {k: v for k, v in agent_cross_files.items() if k > 0}

        if sub_agent_files:
            for agent_id, cross_file in sorted(sub_agent_files.items()):
                progress = self.get_agent_progress(agent_id, cross_file)
                status_icon = "✅" if progress['status'] == 'active' else "❌"
                context_parts.append(
                    f"Agent {agent_id}: {status_icon} "
                    f"{progress.get('current_activity', 'unknown')} "
                    f"({progress.get('total_messages', 0)} msgs)"
                )
        else:
            context_parts.append("No sub-agents available")

        context_parts.append("")
        context_parts.append("You are the master agent (Agent 0). You can:")
        context_parts.append("- Answer questions about any sub-agent's progress")
        context_parts.append("- Command sub-agents to perform tasks")
        context_parts.append("- Coordinate work between sub-agents")
        context_parts.append("")

        return "\n".join(context_parts)

    def route_message(
        self,
        user_input: str,
        agent_cross_files: Dict[int, Path]
    ) -> Dict[str, Any]:
        """
        Main routing function

        Returns:
            {
                'routing_decision': Dict,
                'master_context': str,  # What to send to master agent
                'target_agents': List[int],  # Which agents to send to
                'message_for_agents': str  # What to send to target agents
            }
        """
        # Parse input
        routing_info = self.parse_input(user_input)

        # Create context for master agent
        master_context = self.create_master_context(
            user_input,
            routing_info,
            agent_cross_files
        )

        # Determine target agents
        target_agents = []
        message_for_agents = user_input

        if routing_info['command_type'] == 'broadcast':
            # Send to all agents
            target_agents = list(agent_cross_files.keys())
        elif routing_info['target_agent'] is not None:
            # Send to specific agent(s)
            target_agents = routing_info['extracted_agent_refs']
        else:
            # Default: only master agent
            target_agents = [0]

        # Record routing
        routing_record = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'routing_info': routing_info,
            'target_agents': target_agents
        }
        self.routing_history.append(routing_record)

        # Save routing state
        self._save_routing_state()

        result = {
            'routing_decision': routing_info,
            'master_context': master_context,
            'target_agents': target_agents,
            'message_for_agents': message_for_agents
        }

        logger.info(f"Routing result: targets={target_agents}, type={routing_info['command_type']}")

        return result

    def _save_routing_state(self):
        """Save routing state to Cross structure"""
        routing_state = {
            'type': 'verantyx_cross_routing',
            'timestamp': datetime.now().isoformat(),
            'routing_history': self.routing_history[-50:],  # Keep last 50
            'statistics': {
                'total_routes': len(self.routing_history),
                'command_types': self._count_command_types(),
                'agent_references': self._count_agent_references()
            }
        }

        with open(self.routing_cross_file, 'w', encoding='utf-8') as f:
            json.dump(routing_state, f, ensure_ascii=False, indent=2)

    def _count_command_types(self) -> Dict[str, int]:
        """Count command types in routing history"""
        counts = {}
        for record in self.routing_history:
            cmd_type = record['routing_info']['command_type']
            counts[cmd_type] = counts.get(cmd_type, 0) + 1
        return counts

    def _count_agent_references(self) -> Dict[int, int]:
        """Count how many times each agent was referenced"""
        counts = {}
        for record in self.routing_history:
            for agent_id in record['routing_info']['extracted_agent_refs']:
                counts[agent_id] = counts.get(agent_id, 0) + 1
        return counts

    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get routing statistics"""
        return {
            'total_routes': len(self.routing_history),
            'command_types': self._count_command_types(),
            'agent_references': self._count_agent_references(),
            'recent_routes': self.routing_history[-10:]
        }
