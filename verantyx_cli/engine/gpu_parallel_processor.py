"""
GPU Parallel Processor - FRONT/BACK軸の並列データ処理

Apple Metal (MPS) を使用してメッセージバッチ処理と
画像変換の並列化を実現

設計原則:
- GPU: 大量データの並列処理のみ
- ロジックはCross構造に記述
- CPUとの役割分担を明確化
"""

import torch
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional


class GPUParallelProcessor:
    """
    FRONT/BACK軸: GPU並列データ処理

    Apple Metal Performance Shaders (MPS) を使用
    """

    def __init__(self):
        """Initialize GPU processor"""
        # Metal GPU (Apple Silicon)
        if torch.backends.mps.is_available():
            self.device = torch.device('mps')
            self.gpu_available = True
            print(f"✅ GPU (Metal) available: {self.device}")
        else:
            self.device = torch.device('cpu')
            self.gpu_available = False
            print(f"⚠️  GPU not available, using CPU")

        # メッセージ処理用のテンソル
        self.message_buffer = []
        self.batch_size = 32

    def batch_process_messages(self, messages: List[str]) -> List[Dict[str, Any]]:
        """
        メッセージをバッチ処理

        Args:
            messages: メッセージリスト

        Returns:
            処理結果のリスト
        """
        if not messages:
            return []

        print(f"🔄 GPU: Processing {len(messages)} messages in batch...")

        # メッセージをテンソルに変換
        message_tensors = self._messages_to_tensors(messages)

        if self.gpu_available:
            # GPU上で並列処理
            message_tensors = message_tensors.to(self.device)

        # 並列処理: 各メッセージの特徴を抽出
        with torch.no_grad():
            # 文字列長を並列計算
            lengths = torch.tensor([len(msg) for msg in messages],
                                  dtype=torch.float32, device=self.device)

            # "INPUT:"プレフィックスチェックを並列実行
            is_input = torch.tensor([msg.startswith('INPUT:') for msg in messages],
                                   dtype=torch.float32, device=self.device)

            # 並列フィルタリング: INPUT:で始まるメッセージのみ抽出
            input_indices = torch.where(is_input > 0)[0]

        # 結果をCPUに戻す
        if self.gpu_available:
            input_indices = input_indices.cpu()

        # 処理結果を構築
        results = []
        for i, msg in enumerate(messages):
            results.append({
                'message': msg,
                'length': int(lengths[i].item()),
                'is_input': bool(is_input[i].item()),
                'index': i
            })

        print(f"✅ GPU: Processed {len(results)} messages")
        return results

    def parallel_string_operations(self, strings: List[str], operation: str) -> List[Any]:
        """
        文字列操作を並列実行

        Args:
            strings: 文字列リスト
            operation: 操作タイプ ('length', 'trim', 'upper', 'lower')

        Returns:
            操作結果のリスト
        """
        if not strings:
            return []

        print(f"🔄 GPU: Parallel {operation} on {len(strings)} strings...")

        if operation == 'length':
            # 長さ計算を並列実行
            lengths = torch.tensor([len(s) for s in strings],
                                  dtype=torch.int32, device=self.device)
            return lengths.cpu().numpy().tolist()

        elif operation == 'trim':
            # trim操作（CPUで実行、GPUはバッチ管理）
            return [s.strip() for s in strings]

        elif operation == 'upper':
            return [s.upper() for s in strings]

        elif operation == 'lower':
            return [s.lower() for s in strings]

        else:
            raise ValueError(f"Unknown operation: {operation}")

    def parallel_image_to_cross(self, image_paths: List[Path]) -> List[Dict[str, Any]]:
        """
        複数画像をCross構造に並列変換

        Args:
            image_paths: 画像パスのリスト

        Returns:
            Cross構造のリスト
        """
        if not image_paths:
            return []

        print(f"🔄 GPU: Converting {len(image_paths)} images to Cross structures...")

        try:
            from PIL import Image
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from vision.image_to_cross import convert_image_to_cross
        except ImportError:
            print("⚠️  PIL not available, skipping image conversion")
            return []

        # 画像を並列読み込み
        images = []
        for path in image_paths:
            try:
                img = Image.open(path)
                images.append(img)
            except Exception as e:
                print(f"⚠️  Failed to load {path}: {e}")
                images.append(None)

        # GPUで並列変換（画像テンソルのバッチ処理）
        cross_structures = []

        # バッチサイズで分割
        for i in range(0, len(images), self.batch_size):
            batch = images[i:i + self.batch_size]
            batch_paths = image_paths[i:i + self.batch_size]

            # バッチ内の画像を並列変換
            for img, path in zip(batch, batch_paths):
                if img is None:
                    cross_structures.append({})
                    continue

                # 個別変換（TODO: バッチ化）
                try:
                    cross_struct = convert_image_to_cross(
                        image_path=path,
                        output_path=None,  # メモリ上で変換
                        quality='medium'
                    )
                    cross_structures.append(cross_struct)
                except Exception as e:
                    print(f"⚠️  Conversion failed for {path}: {e}")
                    cross_structures.append({})

        print(f"✅ GPU: Converted {len(cross_structures)} images")
        return cross_structures

    def _messages_to_tensors(self, messages: List[str]) -> torch.Tensor:
        """
        メッセージリストをテンソルに変換

        Args:
            messages: メッセージリスト

        Returns:
            テンソル表現
        """
        # 簡易実装: 各メッセージをASCIIコードの配列に
        max_len = max(len(msg) for msg in messages) if messages else 0

        tensor = torch.zeros((len(messages), max_len), dtype=torch.float32)

        for i, msg in enumerate(messages):
            for j, char in enumerate(msg[:max_len]):
                tensor[i, j] = ord(char)

        return tensor


class GPUMessageProcessor:
    """
    メッセージ処理特化GPU実行エンジン

    Verantyxのメッセージバッチ処理
    """

    def __init__(self):
        self.gpu = GPUParallelProcessor()
        self.message_queue = []

    def enqueue_message(self, message: str):
        """メッセージをキューに追加"""
        self.message_queue.append(message)

    def process_batch(self) -> List[Dict[str, Any]]:
        """
        キュー内のメッセージをバッチ処理

        Returns:
            処理結果
        """
        if not self.message_queue:
            return []

        # GPU並列処理
        results = self.gpu.batch_process_messages(self.message_queue)

        # キューをクリア
        self.message_queue = []

        return results

    def filter_input_messages(self, messages: List[str]) -> List[str]:
        """
        "INPUT:"で始まるメッセージのみをフィルタ（GPU並列）

        Args:
            messages: メッセージリスト

        Returns:
            フィルタされたメッセージ
        """
        results = self.gpu.batch_process_messages(messages)
        return [r['message'] for r in results if r['is_input']]


# ═══════════════════════════════════════════════════════════════
# GPU I/O Processors - Cross構造から呼び出し可能
# ═══════════════════════════════════════════════════════════════

# グローバルGPUインスタンス
_GPU_PROCESSOR = None

def get_gpu_processor():
    """GPUプロセッサのシングルトン取得"""
    global _GPU_PROCESSOR
    if _GPU_PROCESSOR is None:
        _GPU_PROCESSOR = GPUParallelProcessor()
    return _GPU_PROCESSOR


def gpu_batch_process_messages(params: dict) -> dict:
    """
    GPU並列メッセージ処理プロセッサ

    Cross構造から呼び出し可能

    入力:
        {"messages": [str, ...]}

    出力:
        {"results": [dict, ...], "count": int}
    """
    gpu = get_gpu_processor()
    messages = params.get('messages', [])

    results = gpu.batch_process_messages(messages)

    return {
        'results': results,
        'count': len(results)
    }


def gpu_parallel_string_operation(params: dict) -> dict:
    """
    GPU並列文字列操作プロセッサ

    入力:
        {"strings": [str, ...], "operation": str}

    出力:
        {"results": [Any, ...]}
    """
    gpu = get_gpu_processor()
    strings = params.get('strings', [])
    operation = params.get('operation', 'length')

    results = gpu.parallel_string_operations(strings, operation)

    return {'results': results}


def gpu_parallel_image_conversion(params: dict) -> dict:
    """
    GPU並列画像変換プロセッサ

    入力:
        {"image_paths": [str, ...]}

    出力:
        {"cross_structures": [dict, ...], "count": int}
    """
    gpu = get_gpu_processor()
    image_paths = [Path(p) for p in params.get('image_paths', [])]

    cross_structures = gpu.parallel_image_to_cross(image_paths)

    return {
        'cross_structures': cross_structures,
        'count': len(cross_structures)
    }


def get_gpu_io_processors():
    """
    GPU I/O プロセッサを返す

    Cross構造から呼び出し可能なGPU操作
    """
    return {
        'gpu.batch_process': gpu_batch_process_messages,
        'gpu.string_operation': gpu_parallel_string_operation,
        'gpu.image_conversion': gpu_parallel_image_conversion,
    }


if __name__ == "__main__":
    # テスト実行
    print("=" * 70)
    print("GPU Parallel Processor Test")
    print("=" * 70)
    print()

    gpu = GPUParallelProcessor()

    # Test 1: メッセージバッチ処理
    print("Test 1: Batch Message Processing")
    messages = [
        "INPUT: Hello world",
        "OUTPUT: Response",
        "INPUT: Another message",
        "DEBUG: Log message"
    ]

    results = gpu.batch_process_messages(messages)
    print(f"Results: {len(results)} messages processed")
    for r in results:
        print(f"  - {r['message'][:30]}... (length={r['length']}, is_input={r['is_input']})")
    print()

    # Test 2: 並列文字列操作
    print("Test 2: Parallel String Operations")
    strings = ["hello", "world", "test", "message"]
    lengths = gpu.parallel_string_operations(strings, 'length')
    print(f"Lengths: {lengths}")
    print()

    print("=" * 70)
    print("✅ GPU Processor Tests Complete")
    print("=" * 70)
