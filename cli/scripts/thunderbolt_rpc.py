import socket
import struct
import torch
import time

class TensorTransferEngine:
    """
    Ultra-low latency TCP engine designed specifically for Verantyx Pipeline Parallelism.
    Uses Thunderbolt Bridge (10Gbps+) to transfer 8KB fp16 vectors in microseconds.
    """
    def __init__(self, role, host='0.0.0.0', port=5555, peer_ip=None):
        self.role = role
        self.host = host
        self.port = port
        self.peer_ip = peer_ip
        self.conn = None
        self.server_socket = None

    def start(self):
        if self.role == 'worker':
            print(f"  [\033[36mThunderbolt RPC\033[0m] Worker listening on {self.host}:{self.port}...")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow port reuse after crash
            self.server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Disable Nagle's algorithm for low latency
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.conn, addr = self.server_socket.accept()
            print(f"  [\033[36mThunderbolt RPC\033[0m] Connection established with Master at {addr}")
        elif self.role == 'master':
            if not self.peer_ip:
                raise ValueError("Master requires peer_ip (Worker's IP) to connect.")
            print(f"  [\033[36mThunderbolt RPC\033[0m] Master connecting to Worker at {self.peer_ip}:{self.port}...")
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # Retry connection until worker is ready
            self.conn.settimeout(5.0) # Set a 5-second timeout for connection attempts
            while True:
                try:
                    self.conn.connect((self.peer_ip, self.port))
                    self.conn.settimeout(None) # Reset to blocking mode after connection
                    break
                except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
                    print(f"  [\033[33mSystem\033[0m] Connection to {self.peer_ip} timed out or refused. Retrying in 2s...")
                    time.sleep(2.0)
                    
            print(f"  [\033[36mThunderbolt RPC\033[0m] Successfully connected to Worker via Thunderbolt.")

    def send_tensor(self, tensor):
        """Sends a torch tensor over TCP."""
        if self.conn is None:
            raise RuntimeError("Connection not established.")
            
        # Ensure we always send as float16 to match recv_tensor expectations
        tensor_bytes = tensor.detach().cpu().half().numpy().tobytes()
        size_header = struct.pack("!I", len(tensor_bytes))
        
        # Send size followed by payload
        self.conn.sendall(size_header + tensor_bytes)

    def recv_tensor(self, dtype=torch.float16, shape=(1, 4096), device="cpu"):
        """Receives a torch tensor over TCP."""
        if self.conn is None:
            raise RuntimeError("Connection not established.")
            
        # Receive size header (4 bytes)
        header = self._recvall(4)
        if not header:
            return None # Connection closed
            
        size = struct.unpack("!I", header)[0]
        
        # Receive payload
        tensor_bytes = self._recvall(size)
        if not tensor_bytes:
            return None
            
        # Convert back to tensor
        import numpy as np
        np_arr = np.frombuffer(tensor_bytes, dtype=np.float16)
        
        # Make array writable to suppress PyTorch warnings
        np_arr = np_arr.copy()
        
        # If the expected shape doesn't match the incoming data size, fallback to dynamic shape (1, auto)
        expected_size = 1
        for dim in shape:
            expected_size *= dim
            
        if np_arr.size != expected_size:
            actual_shape = (1, np_arr.size)
        else:
            actual_shape = shape
            
        tensor = torch.from_numpy(np_arr).reshape(actual_shape).to(device)
        return tensor

    def _recvall(self, n):
        data = bytearray()
        while len(data) < n:
            packet = self.conn.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

    def close(self):
        if self.conn:
            self.conn.close()
        if self.server_socket:
            self.server_socket.close()
