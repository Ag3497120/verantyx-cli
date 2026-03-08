"""
Multi-Agent Controller - Control multiple Claude agents simultaneously

Manages multiple Claude instances, each with its own Cross structure.
User's personality and characteristics are considered for agent coordination.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .claude_socket_server import ClaudeSocketServer
from .claude_tab_launcher import launch_claude_in_new_tab
from .cross_generator import CrossGenerator

logger = logging.getLogger(__name__)


class AgentInstance:
    """Single agent instance"""

    def __init__(
        self,
        agent_id: int,
        agent_name: str,
        project_path: Path,
        verantyx_dir: Path,
        llm_command: str
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.project_path = project_path
        self.verantyx_dir = verantyx_dir
        self.llm_command = llm_command

        # Socket server for this agent
        self.socket_server: Optional[ClaudeSocketServer] = None

        # Cross generator for this agent
        self.cross_generator: Optional[CrossGenerator] = None
        self.cross_file = verantyx_dir / f"agent_{agent_id}_{agent_name}.cross.json"

        # State
        self.running = False
        self.connected = False

        # Message history
        self.messages: List[Dict[str, str]] = []

    def start(self) -> bool:
        """Start this agent instance"""
        logger.info(f"Starting agent {self.agent_id}: {self.agent_name}")

        # Create socket server
        self.socket_server = ClaudeSocketServer()
        host, port = self.socket_server.start()
        logger.info(f"Agent {self.agent_id} socket server: {host}:{port}")

        # Launch in new tab
        if not launch_claude_in_new_tab(self.project_path, self.llm_command, host, port):
            logger.error(f"Failed to launch agent {self.agent_id}")
            self.socket_server.stop()
            return False

        # Wait for connection
        wait_start = time.time()
        while not self.socket_server.is_connected() and (time.time() - wait_start) < 30:
            time.sleep(0.5)

        if not self.socket_server.is_connected():
            logger.error(f"Agent {self.agent_id} did not connect in time")
            self.socket_server.stop()
            return False

        self.connected = True

        # Start Cross generator with agent info
        self.cross_generator = CrossGenerator(
            output_file=self.cross_file,
            update_interval=3.0,
            agent_id=self.agent_id,
            agent_role=self.agent_name
        )
        self.cross_generator.start()
        logger.info(f"Agent {self.agent_id} Cross generator started: {self.cross_file}")

        self.running = True
        return True

    def stop(self):
        """Stop this agent instance"""
        logger.info(f"Stopping agent {self.agent_id}: {self.agent_name}")
        self.running = False

        if self.cross_generator:
            self.cross_generator.stop()

        if self.socket_server:
            self.socket_server.stop()

    def send_input(self, text: str):
        """Send input to this agent"""
        if self.socket_server and self.connected:
            self.socket_server.send_input(text)

            # Record in Cross
            if self.cross_generator:
                self.cross_generator.add_user_message(text)

            # Record in message history
            self.messages.append({
                'timestamp': datetime.now().isoformat(),
                'role': 'user',
                'content': text
            })

    def get_outputs(self) -> List[str]:
        """Get outputs from this agent"""
        if self.socket_server:
            return self.socket_server.outputs
        return []

    def add_assistant_message(self, content: str):
        """Record assistant message"""
        if self.cross_generator:
            self.cross_generator.add_assistant_message(content)

        self.messages.append({
            'timestamp': datetime.now().isoformat(),
            'role': 'assistant',
            'content': content
        })


class MultiAgentController:
    """
    Controls multiple Claude agents

    Features:
    - Launch multiple agents simultaneously
    - Each agent has its own Cross structure
    - Coordinate agents based on user personality
    - Aggregate Cross structures for meta-analysis
    """

    def __init__(
        self,
        project_path: Path,
        verantyx_dir: Path,
        llm_command: str = "claude"
    ):
        self.project_path = project_path
        self.verantyx_dir = verantyx_dir
        self.llm_command = llm_command

        # Agent instances
        self.agents: List[AgentInstance] = []

        # User personality profile (loaded from Cross or inferred)
        self.user_profile: Dict[str, Any] = {}

        # Cross routing layer (NEW)
        from .cross_routing_layer import CrossRoutingLayer
        self.routing_layer = CrossRoutingLayer(verantyx_dir)

    def create_agents(self, agent_configs: List[Dict[str, str]]) -> bool:
        """
        Create multiple agents

        Args:
            agent_configs: List of agent configurations
                          Each config: {'name': 'agent_name', 'role': 'description'}

        Returns:
            True if all agents started successfully
        """
        logger.info(f"Creating {len(agent_configs)} agents...")

        for i, config in enumerate(agent_configs):
            agent_name = config.get('name', f'agent_{i}')

            agent = AgentInstance(
                agent_id=i,
                agent_name=agent_name,
                project_path=self.project_path,
                verantyx_dir=self.verantyx_dir,
                llm_command=self.llm_command
            )

            if not agent.start():
                logger.error(f"Failed to start agent {i}: {agent_name}")
                # Stop already started agents
                for started_agent in self.agents:
                    started_agent.stop()
                return False

            self.agents.append(agent)
            logger.info(f"✅ Agent {i} ({agent_name}) started successfully")

        logger.info(f"All {len(self.agents)} agents started successfully")
        return True

    def stop_all_agents(self):
        """Stop all agents"""
        logger.info("Stopping all agents...")
        for agent in self.agents:
            agent.stop()
        self.agents = []

    def broadcast_input(self, text: str):
        """Send input to all agents"""
        logger.info(f"Broadcasting to {len(self.agents)} agents: {text}")
        for agent in self.agents:
            agent.send_input(text)

    def send_to_agent(self, agent_id: int, text: str):
        """Send input to specific agent"""
        if 0 <= agent_id < len(self.agents):
            self.agents[agent_id].send_input(text)
        else:
            logger.warning(f"Agent {agent_id} not found")

    def send_with_routing(self, user_input: str) -> Dict[str, Any]:
        """
        Send input with Cross routing intelligence

        This uses the routing layer to:
        1. Parse input for agent references ("2番のエージェント")
        2. Route to appropriate agent(s)
        3. Send master agent (Agent 0) context about sub-agents if needed

        Returns:
            Routing result with targets and contexts
        """
        # Get agent Cross files
        agent_cross_files = {
            agent.agent_id: agent.cross_file
            for agent in self.agents
        }

        # Route message through routing layer
        routing_result = self.routing_layer.route_message(user_input, agent_cross_files)

        # Send to master agent (Agent 0) with full context
        if 0 in routing_result['target_agents']:
            master_context = routing_result['master_context']
            self.agents[0].send_input(master_context)

        # Send to sub-agents (Agent 1+) with original message
        for agent_id in routing_result['target_agents']:
            if agent_id > 0 and agent_id < len(self.agents):
                self.agents[agent_id].send_input(routing_result['message_for_agents'])

        return routing_result

    def get_agent_outputs(self, agent_id: int) -> List[str]:
        """Get outputs from specific agent"""
        if 0 <= agent_id < len(self.agents):
            return self.agents[agent_id].get_outputs()
        return []

    def get_all_outputs(self) -> Dict[int, List[str]]:
        """Get outputs from all agents"""
        return {
            agent.agent_id: agent.get_outputs()
            for agent in self.agents
        }

    def aggregate_cross_structures(self) -> Dict[str, Any]:
        """
        Aggregate Cross structures from all agents

        Creates meta-Cross structure combining insights from all agents
        """
        aggregate = {
            'type': 'verantyx_multi_agent_cross',
            'timestamp': datetime.now().isoformat(),
            'num_agents': len(self.agents),
            'agents': [],
            'meta_axes': {
                'up': {},      # Aggregated goals
                'down': {},    # Aggregated facts
                'front': {},   # Current state
                'back': {},    # History
                'right': {},   # Learned patterns across all agents
                'left': {}     # Constraints
            }
        }

        # Collect from each agent
        for agent in self.agents:
            if agent.cross_file.exists():
                try:
                    with open(agent.cross_file, 'r', encoding='utf-8') as f:
                        agent_cross = json.load(f)

                    aggregate['agents'].append({
                        'agent_id': agent.agent_id,
                        'agent_name': agent.agent_name,
                        'cross_structure': agent_cross
                    })
                except Exception as e:
                    logger.error(f"Error reading Cross for agent {agent.agent_id}: {e}")

        # Aggregate patterns
        all_patterns = []
        all_topics = []
        total_messages = 0

        for agent_data in aggregate['agents']:
            cross = agent_data['cross_structure']
            axes = cross.get('axes', {})

            # Collect patterns
            right = axes.get('right', {})
            all_patterns.extend(right.get('learned_patterns', []))
            all_topics.extend(right.get('conversation_topics', []))

            # Count messages
            down = axes.get('down', {})
            total_messages += down.get('total_user_messages', 0)

        # Build meta-axes
        aggregate['meta_axes']['up'] = {
            'goal': 'Multi-agent collaboration',
            'coordination_mode': 'parallel_processing'
        }

        aggregate['meta_axes']['down'] = {
            'total_agents': len(self.agents),
            'total_messages': total_messages,
            'active_agents': sum(1 for a in self.agents if a.running)
        }

        aggregate['meta_axes']['right'] = {
            'learned_patterns': list(set(all_patterns)),  # Unique patterns
            'topics': list(set(all_topics))               # Unique topics
        }

        return aggregate

    def save_aggregate_cross(self, output_file: Optional[Path] = None):
        """Save aggregated Cross structure"""
        if output_file is None:
            output_file = self.verantyx_dir / 'multi_agent_aggregate.cross.json'

        aggregate = self.aggregate_cross_structures()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(aggregate, f, ensure_ascii=False, indent=2)

        logger.info(f"Aggregate Cross structure saved to: {output_file}")
        return output_file

    def load_user_profile(self, profile_file: Optional[Path] = None):
        """
        Load user personality profile from Cross structure

        This allows agents to be coordinated based on user characteristics
        """
        if profile_file is None:
            # Try to find existing conversation Cross
            profile_file = self.verantyx_dir / 'conversation.cross.json'

        if profile_file.exists():
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    cross = json.load(f)

                # Extract user characteristics from Cross
                axes = cross.get('axes', {})
                right = axes.get('right', {})

                self.user_profile = {
                    'interaction_style': right.get('interaction_style', 'unknown'),
                    'learned_patterns': right.get('learned_patterns', []),
                    'topics': right.get('conversation_topics', [])
                }

                logger.info(f"User profile loaded: {self.user_profile}")
            except Exception as e:
                logger.error(f"Error loading user profile: {e}")

    def coordinate_agents(self, task: str) -> Dict[int, str]:
        """
        Coordinate agents based on task and user profile

        Returns personalized instructions for each agent
        """
        instructions = {}

        # Simple coordination strategy
        # More sophisticated strategies can be added based on user_profile

        if len(self.agents) == 2:
            instructions[0] = f"Agent 0 (Research): Research and analyze this task: {task}"
            instructions[1] = f"Agent 1 (Implementation): Implement solutions for: {task}"

        elif len(self.agents) == 3:
            instructions[0] = f"Agent 0 (Analysis): Analyze requirements for: {task}"
            instructions[1] = f"Agent 1 (Design): Design solution for: {task}"
            instructions[2] = f"Agent 2 (Implementation): Implement: {task}"

        else:
            # Default: all agents get the same task
            for agent in self.agents:
                instructions[agent.agent_id] = f"Agent {agent.agent_id}: {task}"

        return instructions
