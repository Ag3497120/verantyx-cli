"""
Cross Neural Model - Cross構造のニューラル表現

ノイマン型を排除し、Neural Engineでネイティブ実行可能なモデル
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional
import numpy as np


class StateEncoder(nn.Module):
    """
    状態エンコーダ - ラベルを状態ベクトルに変換

    ノイマン型のプログラムカウンタではなく、
    状態空間での位置として表現
    """

    def __init__(self, num_states: int, embedding_dim: int = 128):
        super().__init__()
        self.num_states = num_states
        self.embedding_dim = embedding_dim

        # 状態埋め込み層
        self.state_embedding = nn.Embedding(num_states, embedding_dim)

    def forward(self, state_id: torch.Tensor) -> torch.Tensor:
        """
        状態IDを埋め込みベクトルに変換

        Args:
            state_id: [batch_size] tensor of state indices

        Returns:
            [batch_size, embedding_dim] state vectors
        """
        return self.state_embedding(state_id)


class TransitionNetwork(nn.Module):
    """
    遷移ネットワーク - 状態遷移を学習可能な重み行列で表現

    ノイマン型の分岐命令ではなく、
    並列的な遷移確率として表現
    """

    def __init__(self, num_states: int, embedding_dim: int = 128):
        super().__init__()
        self.num_states = num_states

        # 遷移判定ネットワーク
        self.transition_net = nn.Sequential(
            nn.Linear(embedding_dim + 64, 256),  # state + stack_top
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, num_states)  # 次状態の確率分布
        )

    def forward(self, state_vector: torch.Tensor,
                stack_summary: torch.Tensor) -> torch.Tensor:
        """
        現在状態とスタック情報から次状態を決定

        Args:
            state_vector: [batch_size, embedding_dim]
            stack_summary: [batch_size, 64] スタックトップの要約

        Returns:
            [batch_size, num_states] 次状態の確率分布
        """
        combined = torch.cat([state_vector, stack_summary], dim=-1)
        logits = self.transition_net(combined)
        return F.softmax(logits, dim=-1)


class StackProcessor(nn.Module):
    """
    スタックプロセッサ - スタック操作をニューラル演算で実装

    ノイマン型のレジスタ操作ではなく、
    テンソル変形操作として実装
    """

    def __init__(self, stack_size: int = 256, feature_dim: int = 64):
        super().__init__()
        self.stack_size = stack_size
        self.feature_dim = feature_dim

        # スタック操作ネットワーク
        self.push_net = nn.Linear(feature_dim, feature_dim)
        self.pop_net = nn.Linear(feature_dim, feature_dim)
        self.dup_net = nn.Linear(feature_dim, feature_dim)

    def forward(self, stack: torch.Tensor,
                operation: str = "noop") -> torch.Tensor:
        """
        スタック操作を実行

        Args:
            stack: [batch_size, stack_size, feature_dim]
            operation: "push", "pop", "dup", "swap", "noop"

        Returns:
            [batch_size, stack_size, feature_dim] 更新されたスタック
        """
        if operation == "push":
            # スタックを1つシフトして新しい値を追加
            shifted = torch.roll(stack, shifts=1, dims=1)
            return shifted

        elif operation == "pop":
            # スタックを1つシフト（最上位を削除）
            shifted = torch.roll(stack, shifts=-1, dims=1)
            return shifted

        elif operation == "dup":
            # 最上位を複製
            top = stack[:, 0:1, :]
            duplicated = self.dup_net(top)
            shifted = torch.roll(stack, shifts=1, dims=1)
            shifted[:, 0:1, :] = duplicated
            return shifted

        elif operation == "swap":
            # 上位2つを交換
            swapped = stack.clone()
            swapped[:, 0, :] = stack[:, 1, :]
            swapped[:, 1, :] = stack[:, 0, :]
            return swapped

        else:  # noop
            return stack

    def get_summary(self, stack: torch.Tensor) -> torch.Tensor:
        """
        スタックの要約ベクトルを取得

        Args:
            stack: [batch_size, stack_size, feature_dim]

        Returns:
            [batch_size, feature_dim] スタックトップの表現
        """
        return stack[:, 0, :]


class MemoryTensor(nn.Module):
    """
    6軸メモリテンソル - Cross構造の6軸メモリを6次元テンソルで表現

    ノイマン型の線形アドレス空間ではなく、
    6次元空間構造として表現
    """

    def __init__(self, dims: Tuple[int, int, int] = (8, 8, 8),
                 feature_dim: int = 64):
        super().__init__()
        self.dims = dims  # (X_size, Y_size, Z_size)
        self.feature_dim = feature_dim

        # 6軸 = 各軸2方向 × 3次元
        # [right, left, up, down, front, back]
        # → [X+, X-, Y+, Y-, Z+, Z-]
        # これを3次元テンソルで表現

        # メモリアクセスネットワーク
        self.read_net = nn.Linear(feature_dim, feature_dim)
        self.write_net = nn.Linear(feature_dim, feature_dim)

    def create_empty(self, batch_size: int) -> torch.Tensor:
        """
        空の6軸メモリテンソルを作成

        Returns:
            [batch_size, X, Y, Z, feature_dim]
        """
        return torch.zeros(
            batch_size,
            self.dims[0],
            self.dims[1],
            self.dims[2],
            self.feature_dim
        )

    def read(self, memory: torch.Tensor,
             position: Tuple[int, int, int]) -> torch.Tensor:
        """
        6軸メモリから読み取り

        Args:
            memory: [batch_size, X, Y, Z, feature_dim]
            position: (x, y, z) 座標

        Returns:
            [batch_size, feature_dim]
        """
        x, y, z = position
        value = memory[:, x, y, z, :]
        return self.read_net(value)

    def write(self, memory: torch.Tensor,
              position: Tuple[int, int, int],
              value: torch.Tensor) -> torch.Tensor:
        """
        6軸メモリに書き込み

        Args:
            memory: [batch_size, X, Y, Z, feature_dim]
            position: (x, y, z) 座標
            value: [batch_size, feature_dim]

        Returns:
            [batch_size, X, Y, Z, feature_dim] 更新されたメモリ
        """
        x, y, z = position
        updated = memory.clone()
        updated[:, x, y, z, :] = self.write_net(value)
        return updated


class CrossNeuralModel(nn.Module):
    """
    Cross Neural Model - Cross構造の完全なニューラル表現

    ノイマン型アーキテクチャを完全に排除:
    - プログラムカウンタ → 状態ベクトル
    - 逐次実行 → 並列遷移
    - レジスタ → スタックテンソル
    - 線形メモリ → 6軸メモリテンソル
    """

    def __init__(self,
                 num_states: int,
                 stack_size: int = 256,
                 memory_dims: Tuple[int, int, int] = (8, 8, 8),
                 embedding_dim: int = 128,
                 feature_dim: int = 64):
        super().__init__()

        self.num_states = num_states
        self.embedding_dim = embedding_dim
        self.feature_dim = feature_dim

        # コンポーネント
        self.state_encoder = StateEncoder(num_states, embedding_dim)
        self.transition_network = TransitionNetwork(num_states, embedding_dim)
        self.stack_processor = StackProcessor(stack_size, feature_dim)
        self.memory_tensor = MemoryTensor(memory_dims, feature_dim)

    def forward(self,
                state_id: torch.Tensor,
                stack: torch.Tensor,
                memory: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Cross構造の1ステップを実行

        ノイマン型の1命令実行ではなく、
        状態空間での遷移として実行

        Args:
            state_id: [batch_size] 現在の状態ID
            stack: [batch_size, stack_size, feature_dim]
            memory: [batch_size, X, Y, Z, feature_dim]

        Returns:
            next_state_id: [batch_size] 次の状態ID
            updated_stack: [batch_size, stack_size, feature_dim]
            updated_memory: [batch_size, X, Y, Z, feature_dim]
        """
        # 状態をエンコード
        state_vector = self.state_encoder(state_id)

        # スタックの要約
        stack_summary = self.stack_processor.get_summary(stack)

        # 次状態を決定（並列遷移）
        state_probs = self.transition_network(state_vector, stack_summary)
        next_state_id = torch.argmax(state_probs, dim=-1)

        # スタックを更新（操作はstate依存で決定される）
        # 簡略化のため、ここではnoopとする
        updated_stack = self.stack_processor(stack, operation="noop")

        # メモリは現在のまま（後で更新ロジックを追加）
        updated_memory = memory

        return next_state_id, updated_stack, updated_memory

    def run_until_halt(self,
                      initial_state: int,
                      max_steps: int = 1000) -> Dict:
        """
        終了状態に達するまで実行

        Args:
            initial_state: 初期状態ID
            max_steps: 最大ステップ数

        Returns:
            実行結果の辞書
        """
        batch_size = 1
        device = next(self.parameters()).device

        # 初期化
        state_id = torch.tensor([initial_state], device=device)
        stack = torch.zeros(batch_size, 256, self.feature_dim, device=device)
        memory = self.memory_tensor.create_empty(batch_size).to(device)

        states_history = [initial_state]

        # 実行ループ（並列可能だが、ここでは逐次実行）
        for step in range(max_steps):
            next_state_id, stack, memory = self.forward(state_id, stack, memory)

            states_history.append(next_state_id.item())

            # 終了状態チェック（state_id == num_states - 1 を終了とする）
            if next_state_id.item() == self.num_states - 1:
                break

            state_id = next_state_id

        return {
            'final_state': state_id.item(),
            'states_history': states_history,
            'steps': len(states_history) - 1,
            'final_stack': stack.cpu().numpy(),
            'final_memory': memory.cpu().numpy()
        }


def create_cross_model_from_jcross(jcross_ir_program) -> CrossNeuralModel:
    """
    JCross IRプログラムからCross Neural Modelを生成

    Args:
        jcross_ir_program: CrossIR ProgramIR

    Returns:
        CrossNeuralModel instance
    """
    # ラベル数を数える
    num_states = len(jcross_ir_program.labels) + 1  # +1 for implicit start state

    # モデルを作成
    model = CrossNeuralModel(
        num_states=num_states,
        stack_size=256,
        memory_dims=(8, 8, 8),
        embedding_dim=128,
        feature_dim=64
    )

    return model


if __name__ == "__main__":
    # テスト
    print("Cross Neural Model - Test")
    print("=" * 60)

    # モデルを作成
    model = CrossNeuralModel(
        num_states=5,  # MAIN_LOOP, CHECK, SEND, CLOSED, END
        stack_size=256,
        memory_dims=(8, 8, 8)
    )

    print(f"✅ Model created")
    print(f"   States: {model.num_states}")
    print(f"   Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print()

    # 実行テスト
    print("Running test execution...")
    result = model.run_until_halt(initial_state=0, max_steps=10)

    print(f"✅ Execution complete")
    print(f"   Final state: {result['final_state']}")
    print(f"   Steps: {result['steps']}")
    print(f"   State history: {result['states_history']}")
