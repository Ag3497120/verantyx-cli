"""
JCross Enhanced Vocabulary - 強化された語彙システム

LLMの確率的理解ではなく、Cross構造への決定的マッピング

設計思想:
- 日本語 → Cross構造の6軸への明確なマッピング
- 曖昧性のない操作コマンド
- 自然言語の構造的分解
- 意味の幾何学的表現

例:
  "りんごを右に動かす"
  → RIGHT軸: +1移動
  → 対象: りんご (UP軸のエンティティ)
  → 動作: 移動 (FRONT軸の操作)
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class CrossAxis(Enum):
    """Cross構造の6軸"""
    RIGHT = "RIGHT"
    LEFT = "LEFT"
    UP = "UP"
    DOWN = "DOWN"
    FRONT = "FRONT"
    BACK = "BACK"


class SemanticCategory(Enum):
    """意味カテゴリ"""
    ENTITY = "entity"        # 実体 (りんご、人、物)
    ACTION = "action"        # 動作 (取る、置く、動かす)
    DIRECTION = "direction"  # 方向 (右、左、上、下)
    PROPERTY = "property"    # 属性 (赤い、大きい、重い)
    RELATION = "relation"    # 関係 (の上に、の隣に)
    QUANTITY = "quantity"    # 数量 (3個、全部、半分)
    STATE = "state"         # 状態 (開いた、閉じた)
    TEMPORAL = "temporal"   # 時間 (今、後で、前に)


@dataclass
class CrossMapping:
    """日本語→Cross構造のマッピング"""
    word: str              # 日本語単語
    category: SemanticCategory
    axis: CrossAxis        # 主要軸
    vector: Tuple[float, float, float, float, float, float]  # 6軸ベクトル
    operations: List[str]  # 実行可能な操作


class EnhancedVocabulary:
    """
    強化された語彙システム

    日本語の各単語をCross構造の6軸にマッピング
    """

    def __init__(self):
        self.vocabulary = {}
        self._initialize_core_vocabulary()

    def _initialize_core_vocabulary(self):
        """コア語彙の初期化"""

        # ═══════════════════════════════════════════════════════════
        # 1. 方向・移動語彙 (RIGHT/LEFT軸)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # RIGHT方向 (正の値)
            "右": CrossMapping("右", SemanticCategory.DIRECTION, CrossAxis.RIGHT,
                             (1, 0, 0, 0, 0, 0), ["移動", "向く", "見る"]),
            "右へ": CrossMapping("右へ", SemanticCategory.DIRECTION, CrossAxis.RIGHT,
                               (1, 0, 0, 0, 0, 0), ["移動"]),
            "右に": CrossMapping("右に", SemanticCategory.DIRECTION, CrossAxis.RIGHT,
                               (1, 0, 0, 0, 0, 0), ["移動", "配置"]),

            # LEFT方向 (負の値)
            "左": CrossMapping("左", SemanticCategory.DIRECTION, CrossAxis.LEFT,
                             (-1, 0, 0, 0, 0, 0), ["移動", "向く", "見る"]),
            "左へ": CrossMapping("左へ", SemanticCategory.DIRECTION, CrossAxis.LEFT,
                               (-1, 0, 0, 0, 0, 0), ["移動"]),
            "左に": CrossMapping("左に", SemanticCategory.DIRECTION, CrossAxis.LEFT,
                               (-1, 0, 0, 0, 0, 0), ["移動", "配置"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 2. 高さ・階層語彙 (UP/DOWN軸)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # UP方向 (抽象化、上位概念)
            "上": CrossMapping("上", SemanticCategory.DIRECTION, CrossAxis.UP,
                             (0, 0, 1, 0, 0, 0), ["移動", "持ち上げる", "昇る"]),
            "上に": CrossMapping("上に", SemanticCategory.DIRECTION, CrossAxis.UP,
                               (0, 0, 1, 0, 0, 0), ["配置", "積む"]),
            "高く": CrossMapping("高く", SemanticCategory.DIRECTION, CrossAxis.UP,
                               (0, 0, 1, 0, 0, 0), ["移動", "上げる"]),

            # DOWN方向 (具体化、下位概念)
            "下": CrossMapping("下", SemanticCategory.DIRECTION, CrossAxis.DOWN,
                             (0, 0, -1, 0, 0, 0), ["移動", "下げる", "降りる"]),
            "下に": CrossMapping("下に", SemanticCategory.DIRECTION, CrossAxis.DOWN,
                               (0, 0, -1, 0, 0, 0), ["配置", "置く"]),
            "低く": CrossMapping("低く", SemanticCategory.DIRECTION, CrossAxis.DOWN,
                               (0, 0, -1, 0, 0, 0), ["移動", "下げる"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 3. 時間・順序語彙 (FRONT/BACK軸)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # FRONT方向 (未来、次、前方)
            "前": CrossMapping("前", SemanticCategory.DIRECTION, CrossAxis.FRONT,
                             (0, 0, 0, 0, 1, 0), ["移動", "進む", "予測"]),
            "前に": CrossMapping("前に", SemanticCategory.DIRECTION, CrossAxis.FRONT,
                               (0, 0, 0, 0, 1, 0), ["配置", "挿入"]),
            "次": CrossMapping("次", SemanticCategory.TEMPORAL, CrossAxis.FRONT,
                             (0, 0, 0, 0, 1, 0), ["選択", "移動"]),
            "後で": CrossMapping("後で", SemanticCategory.TEMPORAL, CrossAxis.FRONT,
                               (0, 0, 0, 0, 1, 0), ["延期", "予約"]),

            # BACK方向 (過去、前、後方)
            "後ろ": CrossMapping("後ろ", SemanticCategory.DIRECTION, CrossAxis.BACK,
                               (0, 0, 0, 0, -1, 0), ["移動", "戻る", "記憶"]),
            "後ろに": CrossMapping("後ろに", SemanticCategory.DIRECTION, CrossAxis.BACK,
                                 (0, 0, 0, 0, -1, 0), ["配置", "追加"]),
            "前の": CrossMapping("前の", SemanticCategory.TEMPORAL, CrossAxis.BACK,
                               (0, 0, 0, 0, -1, 0), ["参照", "記憶から取得"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 4. 実体・対象語彙 (エンティティ)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # 物理的実体
            "りんご": CrossMapping("りんご", SemanticCategory.ENTITY, CrossAxis.UP,
                                 (0, 0, 0.3, 0, 0, 0), ["取る", "置く", "食べる"]),
            "本": CrossMapping("本", SemanticCategory.ENTITY, CrossAxis.UP,
                             (0, 0, 0.2, 0, 0, 0), ["読む", "開く", "閉じる"]),
            "箱": CrossMapping("箱", SemanticCategory.ENTITY, CrossAxis.UP,
                             (0, 0, 0.4, 0, 0, 0), ["開ける", "閉める", "入れる"]),

            # 抽象的実体
            "考え": CrossMapping("考え", SemanticCategory.ENTITY, CrossAxis.UP,
                               (0, 0, 0.8, 0, 0, 0), ["思考", "整理", "共有"]),
            "記憶": CrossMapping("記憶", SemanticCategory.ENTITY, CrossAxis.BACK,
                               (0, 0, 0, 0, -0.9, 0), ["思い出す", "保存", "忘れる"]),
            "計画": CrossMapping("計画", SemanticCategory.ENTITY, CrossAxis.FRONT,
                               (0, 0, 0, 0, 0.9, 0), ["立てる", "実行", "変更"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 5. 動作語彙 (アクション)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # 基本動作
            "取る": CrossMapping("取る", SemanticCategory.ACTION, CrossAxis.UP,
                               (0, 0, 0.5, 0, 0, 0), ["実行"]),
            "置く": CrossMapping("置く", SemanticCategory.ACTION, CrossAxis.DOWN,
                               (0, 0, -0.5, 0, 0, 0), ["実行"]),
            "動かす": CrossMapping("動かす", SemanticCategory.ACTION, CrossAxis.RIGHT,
                                 (0.5, 0, 0, 0, 0, 0), ["実行"]),

            # 移動動作
            "移動する": CrossMapping("移動する", SemanticCategory.ACTION, CrossAxis.RIGHT,
                                   (0.3, 0, 0, 0, 0, 0), ["実行"]),
            "進む": CrossMapping("進む", SemanticCategory.ACTION, CrossAxis.FRONT,
                               (0, 0, 0, 0, 0.6, 0), ["実行"]),
            "戻る": CrossMapping("戻る", SemanticCategory.ACTION, CrossAxis.BACK,
                               (0, 0, 0, 0, -0.6, 0), ["実行"]),

            # 認知動作
            "見る": CrossMapping("見る", SemanticCategory.ACTION, CrossAxis.FRONT,
                               (0, 0, 0, 0, 0.4, 0), ["実行", "観察"]),
            "聞く": CrossMapping("聞く", SemanticCategory.ACTION, CrossAxis.RIGHT,
                               (0.3, 0, 0, 0, 0, 0), ["実行", "受信"]),
            "考える": CrossMapping("考える", SemanticCategory.ACTION, CrossAxis.UP,
                                 (0, 0, 0.7, 0, 0, 0), ["実行", "推論"]),

            # 変換動作
            "開ける": CrossMapping("開ける", SemanticCategory.ACTION, CrossAxis.FRONT,
                                 (0, 0, 0, 0, 0.5, 0), ["実行", "展開"]),
            "閉じる": CrossMapping("閉じる", SemanticCategory.ACTION, CrossAxis.BACK,
                                 (0, 0, 0, 0, -0.5, 0), ["実行", "収束"]),
            "変える": CrossMapping("変える", SemanticCategory.ACTION, CrossAxis.RIGHT,
                                 (0.6, 0, 0, 0, 0, 0), ["実行", "変換"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 6. 属性語彙 (プロパティ)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # 色
            "赤い": CrossMapping("赤い", SemanticCategory.PROPERTY, CrossAxis.RIGHT,
                               (0.8, 0, 0, 0, 0, 0), ["判定", "フィルタ"]),
            "青い": CrossMapping("青い", SemanticCategory.PROPERTY, CrossAxis.LEFT,
                               (-0.8, 0, 0, 0, 0, 0), ["判定", "フィルタ"]),

            # サイズ
            "大きい": CrossMapping("大きい", SemanticCategory.PROPERTY, CrossAxis.UP,
                                 (0, 0, 0.7, 0, 0, 0), ["判定", "比較"]),
            "小さい": CrossMapping("小さい", SemanticCategory.PROPERTY, CrossAxis.DOWN,
                                 (0, 0, -0.7, 0, 0, 0), ["判定", "比較"]),

            # 状態
            "新しい": CrossMapping("新しい", SemanticCategory.PROPERTY, CrossAxis.FRONT,
                                 (0, 0, 0, 0, 0.8, 0), ["判定", "フィルタ"]),
            "古い": CrossMapping("古い", SemanticCategory.PROPERTY, CrossAxis.BACK,
                               (0, 0, 0, 0, -0.8, 0), ["判定", "フィルタ"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 7. 関係語彙 (リレーション)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            "の上に": CrossMapping("の上に", SemanticCategory.RELATION, CrossAxis.UP,
                                 (0, 0, 0.6, 0, 0, 0), ["配置", "判定"]),
            "の下に": CrossMapping("の下に", SemanticCategory.RELATION, CrossAxis.DOWN,
                                 (0, 0, -0.6, 0, 0, 0), ["配置", "判定"]),
            "の右に": CrossMapping("の右に", SemanticCategory.RELATION, CrossAxis.RIGHT,
                                 (0.6, 0, 0, 0, 0, 0), ["配置", "判定"]),
            "の左に": CrossMapping("の左に", SemanticCategory.RELATION, CrossAxis.LEFT,
                                 (-0.6, 0, 0, 0, 0, 0), ["配置", "判定"]),
            "の前に": CrossMapping("の前に", SemanticCategory.RELATION, CrossAxis.FRONT,
                                 (0, 0, 0, 0, 0.6, 0), ["配置", "判定"]),
            "の後ろに": CrossMapping("の後ろに", SemanticCategory.RELATION, CrossAxis.BACK,
                                   (0, 0, 0, 0, -0.6, 0), ["配置", "判定"]),

            # 包含関係
            "の中に": CrossMapping("の中に", SemanticCategory.RELATION, CrossAxis.DOWN,
                                 (0, 0, -0.5, 0, 0, 0), ["配置", "含む"]),
            "の外に": CrossMapping("の外に", SemanticCategory.RELATION, CrossAxis.UP,
                                 (0, 0, 0.5, 0, 0, 0), ["配置", "除外"]),
        })

        # ═══════════════════════════════════════════════════════════
        # 8. 数量語彙 (クオンティティ)
        # ═══════════════════════════════════════════════════════════

        self.vocabulary.update({
            # 基本数
            "1個": CrossMapping("1個", SemanticCategory.QUANTITY, CrossAxis.UP,
                              (0, 0, 0.1, 0, 0, 0), ["数える", "選択"]),
            "2個": CrossMapping("2個", SemanticCategory.QUANTITY, CrossAxis.UP,
                              (0, 0, 0.2, 0, 0, 0), ["数える", "選択"]),
            "3個": CrossMapping("3個", SemanticCategory.QUANTITY, CrossAxis.UP,
                              (0, 0, 0.3, 0, 0, 0), ["数える", "選択"]),

            # 相対数
            "全部": CrossMapping("全部", SemanticCategory.QUANTITY, CrossAxis.UP,
                               (0, 0, 1.0, 0, 0, 0), ["選択", "全選択"]),
            "半分": CrossMapping("半分", SemanticCategory.QUANTITY, CrossAxis.UP,
                               (0, 0, 0.5, 0, 0, 0), ["分割", "選択"]),
            "いくつか": CrossMapping("いくつか", SemanticCategory.QUANTITY, CrossAxis.UP,
                                   (0, 0, 0.4, 0, 0, 0), ["選択"]),
        })

    def map_to_cross(self, word: str) -> Optional[CrossMapping]:
        """
        日本語単語をCross構造にマッピング

        Args:
            word: 日本語単語

        Returns:
            CrossMapping または None
        """
        return self.vocabulary.get(word)

    def parse_sentence(self, sentence: str) -> List[CrossMapping]:
        """
        文をCross構造のシーケンスに分解

        Args:
            sentence: 日本語文

        Returns:
            CrossMappingのリスト
        """
        # 簡易分割（実際は形態素解析を使用）
        words = sentence.replace("を", " ").replace("に", " ").split()

        mappings = []
        for word in words:
            mapping = self.map_to_cross(word)
            if mapping:
                mappings.append(mapping)

        return mappings

    def sentence_to_vector(self, sentence: str) -> Tuple[float, float, float, float, float, float]:
        """
        文を6軸ベクトルに変換

        Args:
            sentence: 日本語文

        Returns:
            6次元ベクトル (RIGHT, LEFT, UP, DOWN, FRONT, BACK)
        """
        mappings = self.parse_sentence(sentence)

        # 各軸の合計
        total_vector = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        for mapping in mappings:
            for i in range(6):
                total_vector[i] += mapping.vector[i]

        return tuple(total_vector)

    def get_semantic_field(self, category: SemanticCategory) -> List[CrossMapping]:
        """
        意味カテゴリに属する全単語を取得

        Args:
            category: 意味カテゴリ

        Returns:
            CrossMappingのリスト
        """
        return [
            mapping for mapping in self.vocabulary.values()
            if mapping.category == category
        ]

    def add_word(self, word: str, category: SemanticCategory,
                 axis: CrossAxis, vector: Tuple[float, float, float, float, float, float],
                 operations: List[str]):
        """
        新しい語彙を追加

        Args:
            word: 単語
            category: カテゴリ
            axis: 主軸
            vector: 6軸ベクトル
            operations: 操作リスト
        """
        self.vocabulary[word] = CrossMapping(word, category, axis, vector, operations)


class StructuralUnderstanding:
    """
    構造的理解エンジン

    LLMの確率的理解ではなく、幾何学的・構造的理解
    """

    def __init__(self):
        self.vocab = EnhancedVocabulary()

    def understand(self, japanese_text: str) -> Dict[str, Any]:
        """
        日本語を構造的に理解

        Args:
            japanese_text: 日本語テキスト

        Returns:
            構造的理解結果
        """
        # 文をCross構造にマッピング
        mappings = self.vocab.parse_sentence(japanese_text)

        # 6軸ベクトルに変換
        vector = self.vocab.sentence_to_vector(japanese_text)

        # 主要軸を決定
        abs_vector = [abs(v) for v in vector]
        max_idx = abs_vector.index(max(abs_vector))
        axis_names = ["RIGHT", "LEFT", "UP", "DOWN", "FRONT", "BACK"]
        primary_axis = axis_names[max_idx]

        # 意味カテゴリを分析
        categories = {}
        for mapping in mappings:
            cat = mapping.category.value
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(mapping.word)

        return {
            "text": japanese_text,
            "vector": vector,
            "primary_axis": primary_axis,
            "categories": categories,
            "mappings": [
                {
                    "word": m.word,
                    "category": m.category.value,
                    "axis": m.axis.value,
                    "vector": m.vector
                }
                for m in mappings
            ],
            "understanding_type": "structural"  # NOT probabilistic
        }


if __name__ == "__main__":
    print("=" * 70)
    print("JCross Enhanced Vocabulary - 構造的理解デモ")
    print("=" * 70)
    print()

    engine = StructuralUnderstanding()

    # Test 1: 基本的な文
    print("Test 1: 基本的な動作")
    result = engine.understand("りんごを右に動かす")
    print(f"入力: {result['text']}")
    print(f"6軸ベクトル: {result['vector']}")
    print(f"主要軸: {result['primary_axis']}")
    print(f"カテゴリ: {result['categories']}")
    print()

    # Test 2: 複雑な文
    print("Test 2: 複雑な関係")
    result = engine.understand("赤い箱の上に本を置く")
    print(f"入力: {result['text']}")
    print(f"6軸ベクトル: {result['vector']}")
    print(f"主要軸: {result['primary_axis']}")
    print(f"カテゴリ: {result['categories']}")
    print()

    # Test 3: 時間的表現
    print("Test 3: 時間的表現")
    result = engine.understand("前の記憶を思い出す")
    print(f"入力: {result['text']}")
    print(f"6軸ベクトル: {result['vector']}")
    print(f"主要軸: {result['primary_axis']}")
    print(f"カテゴリ: {result['categories']}")
    print()

    # Test 4: 抽象概念
    print("Test 4: 抽象概念")
    result = engine.understand("考えを整理する")
    print(f"入力: {result['text']}")
    print(f"6軸ベクトル: {result['vector']}")
    print(f"主要軸: {result['primary_axis']}")
    print(f"カテゴリ: {result['categories']}")
    print()

    print("=" * 70)
    print("✅ 構造的理解 (Structural Understanding)")
    print("❌ 確率的理解 (Probabilistic Understanding)")
    print("=" * 70)
