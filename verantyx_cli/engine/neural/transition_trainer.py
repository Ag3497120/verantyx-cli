"""
Transition Trainer - 遷移パターン学習

JCrossプログラムから実際の遷移パターンを学習し、
Neural Engineで正確な状態遷移を実現
"""

import torch
import torch.nn as nn
import torch.optim as optim
from typing import List, Tuple, Dict
import sys
from pathlib import Path

# Cross Neural Modelをインポート
sys.path.insert(0, str(Path(__file__).parent))
from cross_neural_model import CrossNeuralModel

# kofdai_computer
kofdai_dir = Path(__file__).parent.parent.parent.parent.parent / "kofdai_computer"
sys.path.insert(0, str(kofdai_dir))

from cross_ir import ProgramIR, Op


class TransitionTrainer:
    """
    遷移パターンを学習

    ノイマン型の逐次実行トレースから、
    Neural Networkの重みとして遷移パターンを学習
    """

    def __init__(self, model: CrossNeuralModel):
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=0.01)
        self.loss_fn = nn.CrossEntropyLoss()

    def extract_execution_traces(self,
                                 ir_program: ProgramIR,
                                 labels_to_ids: Dict[str, int]) -> List[Tuple[int, int]]:
        """
        CrossIR実行トレースから状態遷移を抽出

        Args:
            ir_program: CrossIR program
            labels_to_ids: ラベル→状態IDマッピング

        Returns:
            List of (from_state, to_state) transitions
        """
        traces = []

        # PC→ラベルマッピング（逆引き）
        pc_to_label = {pc: label for label, pc in ir_program.labels.items()}

        # 現在の状態を追跡
        current_state = labels_to_ids.get("__START__", 0)
        instructions = ir_program.instructions

        for i, instr in enumerate(instructions):
            op = instr.op

            # PCがラベル位置なら状態更新
            if i in pc_to_label:
                label = pc_to_label[i]
                current_state = labels_to_ids.get(label, current_state)

            # ジャンプ命令 → 遷移を記録
            if op == Op.JMP:
                target_label = str(instr.arg)
                if target_label in labels_to_ids:
                    target_state = labels_to_ids[target_label]
                    traces.append((current_state, target_state))
                    current_state = target_state

            elif op == Op.JZ:
                # 条件ジャンプ - 両方の遷移を記録
                target_label = str(instr.arg)
                if target_label in labels_to_ids:
                    target_state = labels_to_ids[target_label]

                    # ゼロなら遷移
                    traces.append((current_state, target_state))

                    # ゼロでなければ次の状態へ
                    next_state = current_state
                    for j in range(i + 1, len(instructions)):
                        if j in pc_to_label:
                            next_label = pc_to_label[j]
                            next_state = labels_to_ids[next_label]
                            break
                    traces.append((current_state, next_state))

            elif op == Op.JNZ:
                # 非ゼロなら遷移
                target_label = str(instr.arg)
                if target_label in labels_to_ids:
                    target_state = labels_to_ids[target_label]
                    traces.append((current_state, target_state))

                    # ゼロなら次の状態へ
                    next_state = current_state
                    for j in range(i + 1, len(instructions)):
                        if j in pc_to_label:
                            next_label = pc_to_label[j]
                            next_state = labels_to_ids[next_label]
                            break
                    traces.append((current_state, next_state))

            elif op == Op.HALT:
                # 終了状態へ
                end_state = labels_to_ids.get("__END__", self.model.num_states - 1)
                traces.append((current_state, end_state))

        return traces

    def train(self,
             transitions: List[Tuple[int, int]],
             num_epochs: int = 500,
             verbose: bool = True) -> Dict:
        """
        遷移パターンを学習

        Args:
            transitions: List of (from_state, to_state) tuples
            num_epochs: 学習エポック数
            verbose: ログ表示

        Returns:
            Training history
        """
        if verbose:
            print()
            print("🎓 Training transition patterns...")
            print(f"   Transitions: {len(transitions)}")
            print(f"   Epochs: {num_epochs}")
            print()

        history = {
            'loss': [],
            'accuracy': []
        }

        device = next(self.model.parameters()).device

        for epoch in range(num_epochs):
            total_loss = 0.0
            correct = 0
            total = 0

            for from_state, to_state in transitions:
                # 入力準備
                state_id = torch.tensor([from_state], device=device)
                stack = torch.randn(1, 256, 64, device=device)
                memory = self.model.memory_tensor.create_empty(1).to(device)

                # 予測
                self.optimizer.zero_grad()

                # Transition networkから確率分布を取得
                state_vector = self.model.state_encoder(state_id)
                stack_summary = self.model.stack_processor.get_summary(stack)
                state_probs = self.model.transition_network(state_vector, stack_summary)

                # 損失計算（クロスエントロピー）
                target = torch.tensor([to_state], device=device, dtype=torch.long)
                loss = self.loss_fn(state_probs, target)

                # 誤差逆伝播
                loss.backward()
                self.optimizer.step()

                total_loss += loss.item()

                # 精度計算
                predicted = torch.argmax(state_probs, dim=-1).item()
                if predicted == to_state:
                    correct += 1
                total += 1

            # エポック終了
            avg_loss = total_loss / len(transitions) if transitions else 0
            accuracy = correct / total if total > 0 else 0

            history['loss'].append(avg_loss)
            history['accuracy'].append(accuracy)

            if verbose and (epoch + 1) % 50 == 0:
                print(f"   Epoch {epoch + 1}/{num_epochs}: Loss={avg_loss:.4f}, Accuracy={accuracy:.2%}")

        if verbose:
            print()
            print(f"✅ Training complete!")
            print(f"   Final Loss: {history['loss'][-1]:.4f}")
            print(f"   Final Accuracy: {history['accuracy'][-1]:.2%}")

        return history


def train_from_jcross(jcross_source: str,
                     model: CrossNeuralModel,
                     labels_to_ids: Dict[str, int],
                     ir_program: ProgramIR,
                     num_epochs: int = 500) -> Dict:
    """
    JCrossプログラムから遷移を学習

    Args:
        jcross_source: JCross source
        model: CrossNeuralModel
        labels_to_ids: Label to state ID mapping
        ir_program: CrossIR program
        num_epochs: Training epochs

    Returns:
        Training history
    """
    trainer = TransitionTrainer(model)

    # 実行トレースから遷移を抽出
    transitions = trainer.extract_execution_traces(ir_program, labels_to_ids)

    print(f"📊 Extracted {len(transitions)} transitions from program")

    # 学習
    history = trainer.train(transitions, num_epochs=num_epochs, verbose=True)

    return history


if __name__ == "__main__":
    # テスト
    from jcross_to_neural import JCrossNeuralCompiler
    from jcross_ir_compiler import compile_jcross_to_ir

    test_program = """
"開始"
表示する

ラベル LOOP
  "ループ中"
  表示する
  ジャンプ CHECK

ラベル CHECK
  "チェック"
  表示する
  ジャンプ END

ラベル END
"終了"
表示する

終わる
"""

    print("=" * 70)
    print("Transition Trainer - Test")
    print("=" * 70)
    print()

    # コンパイル
    compiler = JCrossNeuralCompiler()
    compile_result = compile_jcross_to_ir(test_program)
    ir_program = compile_result.program

    compiler._extract_state_graph(ir_program)
    model = compiler._build_neural_model()

    print(f"Model states: {model.num_states}")
    print(f"Labels: {list(compiler.labels_to_ids.keys())}")
    print()

    # 学習
    history = train_from_jcross(
        test_program,
        model,
        compiler.labels_to_ids,
        ir_program,
        num_epochs=200
    )

    print()
    print("=" * 70)
    print("✅ Training test complete!")
    print("=" * 70)
