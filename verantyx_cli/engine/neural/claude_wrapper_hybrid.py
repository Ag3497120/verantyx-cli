"""
Claude Wrapper Hybrid - Neural Engine + I/O Processors

Neural Engineで状態遷移を管理し、
I/O処理はPythonプロセッサで実行するハイブリッドアーキテクチャ
"""

import sys
import os
from pathlib import Path
from typing import Dict, Optional
import numpy as np
import coremltools as ct

# Neural engineコンポーネント
sys.path.insert(0, str(Path(__file__).parent))
from jcross_to_neural import compile_jcross_to_neural
from coreml_converter import CoreMLConverter

# I/O processors - Verantyx specific for Claude communication
sys.path.insert(0, str(Path(__file__).parent.parent))
from processors_verantyx_io import get_verantyx_io_processors

# kofdai_computer
kofdai_dir = Path(__file__).parent.parent.parent.parent.parent / "kofdai_computer"
sys.path.insert(0, str(kofdai_dir))


class ClaudeWrapperHybrid:
    """
    Claude Wrapper Hybrid Architecture

    - Neural Engine: State transition control (non-von Neumann)
    - Python Processors: I/O operations (pure translation)

    Best of both worlds:
    - Parallel state management (Neural Engine)
    - Efficient I/O (Python processors)
    """

    def __init__(self,
                 host: str = "localhost",
                 port: int = 52749,
                 project_path: str = "."):
        self.host = host
        self.port = port
        self.project_path = project_path

        self.neural_model = None
        self.coreml_model = None
        self.processors = {}

        # State
        self.current_state = 0
        self.stack = None
        self.memory = None
        self.variables = {}

        # Neural Engine controls state transitions
        # Processors handle I/O

    def compile_and_setup(self) -> bool:
        """
        Compile Neural Model and setup I/O processors

        Returns:
            True if successful
        """
        print("🔨 Setting up Hybrid Architecture...")
        print("   • Neural Engine: State transitions")
        print("   • Python Processors: I/O operations")
        print()

        # Load JCross source
        jcross_file = Path(__file__).parent.parent / "claude_wrapper_simple.jcross"

        if not jcross_file.exists():
            print(f"❌ JCross wrapper not found: {jcross_file}")
            return False

        with open(jcross_file, 'r', encoding='utf-8') as f:
            jcross_source = f.read()

        try:
            # Compile to Neural Model
            print("─" * 70)
            self.neural_model = compile_jcross_to_neural(jcross_source)

            # Convert to Core ML
            print()
            print("─" * 70)
            print()

            converter = CoreMLConverter()
            model_path = Path(__file__).parent / "claude_wrapper_hybrid.mlpackage"

            self.coreml_model = converter.convert(
                self.neural_model,
                output_path=str(model_path),
                compute_units="CPU_AND_NE"
            )

            # Setup I/O processors
            print()
            print("─" * 70)
            print()
            print("🔧 Loading I/O Processors...")
            self.processors = get_verantyx_io_processors()
            print(f"✅ Loaded {len(self.processors)} processors")

            # Setup variables
            self.variables['host'] = self.host
            self.variables['port'] = self.port
            self.variables['project_path'] = self.project_path

            print()
            print("=" * 70)
            print("✅ Hybrid Architecture Ready!")
            print("=" * 70)

            return True

        except Exception as e:
            print()
            print("=" * 70)
            print(f"❌ Setup failed: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 70)
            return False

    def initialize_state(self):
        """Initialize Neural Engine state"""
        batch_size = 1
        stack_size = 256
        feature_dim = 64
        memory_dims = (8, 8, 8)

        self.current_state = 0
        self.stack = np.zeros((batch_size, stack_size, feature_dim), dtype=np.float32)
        self.memory = np.zeros((batch_size, *memory_dims, feature_dim), dtype=np.float32)

        print(f"✅ Neural Engine state initialized")

    def execute_processor(self, proc_name: str, params: dict = None) -> dict:
        """
        Execute I/O processor

        Args:
            proc_name: Processor name
            params: Parameters dict

        Returns:
            Processor result
        """
        if proc_name not in self.processors:
            print(f"⚠️  Processor not found: {proc_name}")
            return {}

        # Inject VM variables
        if params is None:
            params = {}
        params['__vm_vars__'] = self.variables

        # Execute
        proc_func = self.processors[proc_name]
        result = proc_func(params)

        return result

    def run(self, max_steps: int = 1000):
        """
        Run hybrid execution loop

        Args:
            max_steps: Maximum steps
        """
        print()
        print("🚀 Starting Hybrid Execution...")
        print("   Neural Engine: Managing state transitions")
        print("   Processors: Handling I/O operations")
        print()

        self.initialize_state()

        # Execute initialization: PTY fork and socket connect
        print("─" * 70)
        print()
        print("🔧 Initializing I/O channels...")
        print()

        # Fork Claude process
        print("📦 Forking Claude process...")
        fork_result = self.execute_processor('io.pty_fork', {})
        if fork_result:
            self.variables['claude_fd'] = fork_result.get('pty_fd')
            self.variables['claude_pid'] = fork_result.get('pid')
            print(f"   ✅ Claude PID: {fork_result.get('pid')}")
        else:
            print("   ❌ Failed to fork Claude")
            return

        # Connect to Verantyx socket
        print("🔌 Connecting to Verantyx...")
        socket_result = self.execute_processor('io.socket_connect', {})
        if socket_result:
            self.variables['verantyx_fd'] = socket_result.get('socket_fd')
            print(f"   ✅ Connected (FD: {socket_result.get('socket_fd')})")
        else:
            print("   ❌ Failed to connect to Verantyx")
            return

        print()
        print("─" * 70)
        print()

        # Main loop
        for step in range(max_steps):
            # Neural Engine: Determine next state
            inputs = {
                'state_id': np.array([self.current_state], dtype=np.int32),
                'stack': self.stack,
                'memory': self.memory
            }

            predictions = self.coreml_model.predict(inputs)
            next_state = int(predictions['var_46'][0])

            # Update state
            self.current_state = next_state
            self.stack = predictions['stack']
            self.memory = predictions['memory']

            # Execute I/O based on state
            # Note: State mapping is learned by Neural Engine from JCross program
            # We execute processors based on observed state patterns

            # MAIN_LOOP state: Check for incoming messages
            if step == 0:
                # First step: initialization already done in compile_and_setup
                print(f"State {step}: {self.current_state} (初期化)", flush=True)
            else:
                print(f"State {step}: {self.current_state}", flush=True)

                # Try to receive messages in each iteration
                result = self.execute_processor('io.socket_recv_from_var', {})

                # Encode I/O result into stack for Neural Engine
                # This allows the Neural Engine to condition its next state on I/O results
                has_data = result.get('has_data', 0)
                self.stack[0, 0, 0] = float(has_data)  # Encode has_data flag

                if has_data:
                    message = result.get('data', '')
                    self.variables['message'] = message
                    self.variables['check_msg'] = message
                    print(f"📥 Received: {message[:50]}...", flush=True)

                    # Check if it's an INPUT: message
                    check_result = self.execute_processor('io.check_input_prefix', {})
                    is_input = check_result.get('result', 0)

                    # Encode check result into stack
                    self.stack[0, 1, 0] = float(is_input)

                    if is_input:
                        # Process and send to Claude
                        self.execute_processor('io.process_and_send_to_claude', {})
                        print(f"✅ Sent to Claude", flush=True)

            # Check for end state
            if self.current_state >= self.neural_model.num_states - 1:
                print()
                print(f"✅ Reached end state after {step + 1} steps")
                break

        else:
            print()
            print(f"⚠️  Max steps ({max_steps}) reached")

        print()
        print("─" * 70)
        print(f"Final state: {self.current_state}")
        print("=" * 70)


def run_claude_wrapper_hybrid(host: str, port: int, project_path: str):
    """
    Run Claude Wrapper in Hybrid mode

    Args:
        host: Verantyx host
        port: Verantyx port
        project_path: Project directory
    """
    print()
    print("=" * 70)
    print("Claude Wrapper - Hybrid Architecture")
    print("=" * 70)
    print()
    print(f"🌐 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"📁 Project: {project_path}")
    print()
    print("Architecture:")
    print("  • Neural Engine: Non-von Neumann state control")
    print("  • Python I/O: Pure data translation")
    print()
    print("=" * 70)

    wrapper = ClaudeWrapperHybrid(host, port, project_path)

    if not wrapper.compile_and_setup():
        sys.exit(1)

    wrapper.run(max_steps=100)


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
        project_path = sys.argv[3] if len(sys.argv) > 3 else "."
    else:
        host = "localhost"
        port = 52749
        project_path = "."

    run_claude_wrapper_hybrid(host, port, project_path)
