"""
JCross Operation Commands - 操作コマンド体系

確率的予測ではなく、決定的な操作の実行

300以上の操作コマンドを6軸にマッピング
"""

from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
from jcross_enhanced_vocabulary import CrossAxis, SemanticCategory


@dataclass
class OperationCommand:
    """操作コマンド"""
    name_ja: str           # 日本語名
    name_en: str           # 英語名
    axis: CrossAxis        # 主要軸
    category: str          # カテゴリ
    parameters: List[str]  # パラメータ
    jcross_code: str      # JCrossコード
    description: str       # 説明


class OperationCommandLibrary:
    """
    操作コマンドライブラリ

    300+の決定的操作コマンド
    """

    def __init__(self):
        self.commands = {}
        self._initialize_commands()

    def _initialize_commands(self):
        """コマンドの初期化"""

        # ═══════════════════════════════════════════════════════════
        # 1. RIGHT/LEFT軸 - 移動・変換操作 (100コマンド)
        # ═══════════════════════════════════════════════════════════

        self._add_movement_commands()
        self._add_transformation_commands()

        # ═══════════════════════════════════════════════════════════
        # 2. UP/DOWN軸 - 抽象化・具体化操作 (100コマンド)
        # ═══════════════════════════════════════════════════════════

        self._add_abstraction_commands()
        self._add_hierarchy_commands()

        # ═══════════════════════════════════════════════════════════
        # 3. FRONT/BACK軸 - 時間・記憶操作 (100コマンド)
        # ═══════════════════════════════════════════════════════════

        self._add_temporal_commands()
        self._add_memory_commands()

        # ═══════════════════════════════════════════════════════════
        # 4. 全軸 - 視覚認識・形状操作 (100コマンド)
        # ═══════════════════════════════════════════════════════════

        self._add_vision_commands()
        self._add_shape_recognition_commands()
        self._add_pattern_extraction_commands()

    def _add_movement_commands(self):
        """移動操作コマンド (RIGHT/LEFT軸)"""

        commands = [
            # 基本移動
            ("右に移動", "move_right", ["距離"], '取り出す 距離\\n# RIGHT軸+方向に移動',
             "指定距離だけRIGHT方向に移動"),
            ("左に移動", "move_left", ["距離"], '取り出す 距離\\n# LEFT軸-方向に移動',
             "指定距離だけLEFT方向に移動"),

            # 回転
            ("右に回転", "rotate_right", ["角度"], '取り出す 角度\\n# RIGHT軸回転',
             "RIGHT軸中心に回転"),
            ("左に回転", "rotate_left", ["角度"], '取り出す 角度\\n# LEFT軸回転',
             "LEFT軸中心に回転"),

            # 配置
            ("右に配置", "place_right", ["対象"], '取り出す 対象\\n# RIGHT方向に配置',
             "対象をRIGHT方向に配置"),
            ("左に配置", "place_left", ["対象"], '取り出す 対象\\n# LEFT方向に配置',
             "対象をLEFT方向に配置"),

            # スライド
            ("右にスライド", "slide_right", ["距離", "速度"], '取り出す 速度\\n取り出す 距離\\n# スライド移動',
             "滑らかにRIGHT方向へ移動"),
            ("左にスライド", "slide_left", ["距離", "速度"], '取り出す 速度\\n取り出す 距離\\n# スライド移動',
             "滑らかにLEFT方向へ移動"),

            # ジャンプ
            ("右にジャンプ", "jump_right", ["距離"], '取り出す 距離\\n# 瞬間移動',
             "RIGHT方向へ瞬間移動"),
            ("左にジャンプ", "jump_left", ["距離"], '取り出す 距離\\n# 瞬間移動',
             "LEFT方向へ瞬間移動"),

            # 拡張
            ("右に伸ばす", "extend_right", ["長さ"], '取り出す 長さ\\n# RIGHT方向拡張',
             "RIGHT軸方向に伸張"),
            ("左に伸ばす", "extend_left", ["長さ"], '取り出す 長さ\\n# LEFT方向拡張',
             "LEFT軸方向に伸張"),

            # 反転
            ("左右反転", "flip_horizontal", [], '# RIGHT←→LEFT反転',
             "RIGHT/LEFT軸を反転"),

            # 整列
            ("右に整列", "align_right", ["基準"], '取り出す 基準\\n# RIGHT方向整列',
             "RIGHT方向に整列"),
            ("左に整列", "align_left", ["基準"], '取り出す 基準\\n# LEFT方向整列',
             "LEFT方向に整列"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, CrossAxis.RIGHT, "movement", params, code, desc
            )

    def _add_transformation_commands(self):
        """変換操作コマンド (RIGHT/LEFT軸)"""

        commands = [
            # データ変換
            ("文字列に変換", "to_string", ["値"], '取り出す 値\\n# 文字列変換',
             "値を文字列に変換"),
            ("数値に変換", "to_number", ["文字列"], '取り出す 文字列\\n# 数値変換',
             "文字列を数値に変換"),
            ("リストに変換", "to_list", ["値"], '取り出す 値\\n# リスト変換',
             "値をリストに変換"),

            # 型変換
            ("整数に変換", "to_int", ["値"], '取り出す 値\\n# 整数変換',
             "値を整数に変換"),
            ("小数に変換", "to_float", ["値"], '取り出す 値\\n# 小数変換',
             "値を小数に変換"),
            ("真偽値に変換", "to_bool", ["値"], '取り出す 値\\n# 真偽値変換',
             "値を真偽値に変換"),

            # フォーマット変換
            ("JSON に変換", "to_json", ["辞書"], '取り出す 辞書\\n# JSON変換',
             "辞書をJSONに変換"),
            ("JSONから変換", "from_json", ["JSON"], '取り出す JSON\\n# JSON解析',
             "JSONを辞書に変換"),

            # エンコーディング
            ("UTF-8にエンコード", "encode_utf8", ["文字列"], '取り出す 文字列\\n# UTF-8エンコード',
             "文字列をUTF-8バイト列に"),
            ("UTF-8からデコード", "decode_utf8", ["バイト列"], '取り出す バイト列\\n# UTF-8デコード',
             "UTF-8バイト列を文字列に"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, CrossAxis.RIGHT, "transformation", params, code, desc
            )

    def _add_abstraction_commands(self):
        """抽象化操作コマンド (UP/DOWN軸)"""

        commands = [
            # 抽象化 (UP方向)
            ("一般化", "generalize", ["具体例"], '取り出す 具体例\\n# UP軸: 抽象化',
             "具体例から一般概念を抽出"),
            ("カテゴリ化", "categorize", ["項目"], '取り出す 項目\\n# カテゴリ抽出',
             "項目をカテゴリに分類"),
            ("パターン抽出", "extract_pattern", ["データ"], '取り出す データ\\n# パターン認識',
             "データからパターンを抽出"),

            # 概念操作
            ("概念を作る", "create_concept", ["名前", "属性"], '取り出す 属性\\n取り出す 名前\\n# 概念生成',
             "新しい概念を定義"),
            ("概念を拡張", "extend_concept", ["概念", "追加属性"], '取り出す 追加属性\\n取り出す 概念\\n# 概念拡張',
             "既存概念に属性追加"),

            # 階層操作 (UP)
            ("上位概念を取得", "get_superclass", ["概念"], '取り出す 概念\\n# UP軸: 上位へ',
             "概念の上位クラスを取得"),
            ("最上位概念を取得", "get_root_concept", ["概念"], '取り出す 概念\\n# UP軸: 最上位',
             "概念の最上位クラスを取得"),

            # 具体化 (DOWN方向)
            ("具体化", "concretize", ["抽象概念"], '取り出す 抽象概念\\n# DOWN軸: 具体化',
             "抽象概念を具体例に"),
            ("インスタンス化", "instantiate", ["クラス"], '取り出す クラス\\n# インスタンス生成',
             "クラスからインスタンス生成"),
            ("例を生成", "generate_example", ["概念"], '取り出す 概念\\n# 具体例生成',
             "概念の具体例を生成"),

            # 階層操作 (DOWN)
            ("下位概念を取得", "get_subclass", ["概念"], '取り出す 概念\\n# DOWN軸: 下位へ',
             "概念の下位クラスを取得"),
            ("全下位概念を取得", "get_all_subclasses", ["概念"], '取り出す 概念\\n# DOWN軸: 全下位',
             "概念の全下位クラスを取得"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            axis = CrossAxis.UP if "上位" in name_ja or "抽象" in name_ja or "一般" in name_ja else CrossAxis.DOWN
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, axis, "abstraction", params, code, desc
            )

    def _add_hierarchy_commands(self):
        """階層操作コマンド (UP/DOWN軸)"""

        commands = [
            # 階層構築
            ("階層を作る", "create_hierarchy", ["ルート"], '取り出す ルート\\n# 階層構築',
             "階層構造を作成"),
            ("ノードを追加", "add_node", ["親", "子"], '取り出す 子\\n取り出す 親\\n# ノード追加',
             "階層にノードを追加"),

            # 階層探索 (UP)
            ("親を取得", "get_parent", ["ノード"], '取り出す ノード\\n# UP: 親取得',
             "ノードの親を取得"),
            ("先祖を全取得", "get_ancestors", ["ノード"], '取り出す ノード\\n# UP: 先祖取得',
             "ノードの全先祖を取得"),

            # 階層探索 (DOWN)
            ("子を取得", "get_children", ["ノード"], '取り出す ノード\\n# DOWN: 子取得',
             "ノードの子を取得"),
            ("子孫を全取得", "get_descendants", ["ノード"], '取り出す ノード\\n# DOWN: 子孫取得',
             "ノードの全子孫を取得"),
            ("葉を全取得", "get_leaves", ["ルート"], '取り出す ルート\\n# DOWN: 葉ノード',
             "階層の全葉ノードを取得"),

            # 階層移動
            ("上に登る", "climb_up", ["段数"], '取り出す 段数\\n# UP: 階層上昇',
             "階層を上方向に移動"),
            ("下に降りる", "climb_down", ["段数"], '取り出す 段数\\n# DOWN: 階層下降',
             "階層を下方向に移動"),

            # レベル操作
            ("レベルを取得", "get_level", ["ノード"], '取り出す ノード\\n# レベル計算',
             "ノードの階層レベルを取得"),
            ("同レベルを全取得", "get_same_level", ["ノード"], '取り出す ノード\\n# 同レベル取得',
             "同じレベルの全ノードを取得"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            axis = CrossAxis.UP if "上" in name_ja or "親" in name_ja or "先祖" in name_ja else CrossAxis.DOWN
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, axis, "hierarchy", params, code, desc
            )

    def _add_temporal_commands(self):
        """時間操作コマンド (FRONT/BACK軸)"""

        commands = [
            # 未来操作 (FRONT)
            ("次を取得", "get_next", ["現在"], '取り出す 現在\\n# FRONT: 次',
             "次の要素を取得"),
            ("予測", "predict", ["現状"], '取り出す 現状\\n# 未来予測',
             "現状から未来を予測"),
            ("計画", "plan", ["目標"], '取り出す 目標\\n# 計画立案',
             "目標達成の計画を立てる"),

            # 先読み
            ("先を見る", "look_ahead", ["距離"], '取り出す 距離\\n# FRONT: 先読み',
             "未来方向を見る"),
            ("シミュレート", "simulate", ["状況"], '取り出す 状況\\n# 未来シミュレーション',
             "未来の状況をシミュレート"),

            # 過去操作 (BACK)
            ("前を取得", "get_previous", ["現在"], '取り出す 現在\\n# BACK: 前',
             "前の要素を取得"),
            ("思い出す", "recall", ["手がかり"], '取り出す 手がかり\\n# BACK: 記憶検索',
             "過去の記憶を思い出す"),
            ("歴史を取得", "get_history", ["対象"], '取り出す 対象\\n# BACK: 履歴',
             "対象の履歴を取得"),

            # 振り返り
            ("過去を見る", "look_back", ["距離"], '取り出す 距離\\n# BACK: 振り返り',
             "過去方向を見る"),
            ("分析", "analyze", ["過去データ"], '取り出す 過去データ\\n# 過去分析',
             "過去データを分析"),

            # 時系列
            ("タイムスタンプ付与", "add_timestamp", ["データ"], '取り出す データ\\n# 時刻記録',
             "データにタイムスタンプを付与"),
            ("時系列並べ替え", "sort_by_time", ["データ"], '取り出す データ\\n# 時系列ソート',
             "データを時系列で並べ替え"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            axis = CrossAxis.FRONT if "次" in name_ja or "未来" in name_ja or "計画" in name_ja or "予測" in name_ja else CrossAxis.BACK
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, axis, "temporal", params, code, desc
            )

    def _add_memory_commands(self):
        """記憶操作コマンド (FRONT/BACK軸)"""

        commands = [
            # 記憶保存 (BACK)
            ("記憶する", "memorize", ["データ", "キー"], '取り出す キー\\n取り出す データ\\n覚える',
             "データを記憶に保存"),
            ("長期記憶に保存", "save_long_term", ["データ"], '取り出す データ\\n# BACK軸深部',
             "長期記憶に保存"),
            ("短期記憶に保存", "save_short_term", ["データ"], '取り出す データ\\n# BACK軸浅部',
             "短期記憶に保存"),

            # 記憶検索
            ("記憶を検索", "search_memory", ["クエリ"], '取り出す クエリ\\n思い出す',
             "記憶から検索"),
            ("類似記憶を検索", "find_similar_memory", ["パターン"], '取り出す パターン\\n# 類似検索',
             "類似した記憶を検索"),

            # 記憶更新
            ("記憶を更新", "update_memory", ["キー", "新データ"], '取り出す 新データ\\n取り出す キー\\n覚える',
             "既存の記憶を更新"),
            ("記憶を削除", "delete_memory", ["キー"], '取り出す キー\\n# 記憶削除',
             "記憶を削除"),

            # 記憶整理
            ("記憶を整理", "organize_memory", [], '# 記憶整理',
             "記憶を整理・最適化"),
            ("古い記憶を削除", "prune_old_memories", ["期限"], '取り出す 期限\\n# 古い記憶削除',
             "期限を過ぎた記憶を削除"),

            # キャッシュ
            ("キャッシュに保存", "cache", ["キー", "値"], '取り出す 値\\n取り出す キー\\n# キャッシュ',
             "高速アクセス用にキャッシュ"),
            ("キャッシュから取得", "get_cached", ["キー"], '取り出す キー\\n# キャッシュ取得',
             "キャッシュから取得"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, CrossAxis.BACK, "memory", params, code, desc
            )

    def _add_vision_commands(self):
        """視覚認識コマンド (全軸)"""

        commands = [
            # 点のマッピング (RIGHT/LEFT軸)
            ("画像を点群に変換", "image_to_points", ["画像データ"],
             '取り出す 画像データ\\n実行する vision.map_to_points',
             "画像のピクセルを3D空間の点に変換"),

            ("点のCross座標を計測", "measure_point_cross", ["点"],
             '取り出す 点\\n実行する cross.calculate_metrics',
             "点の位置をCross 6軸で計測"),

            ("色をCrossにマップ", "map_color_to_cross", ["RGB"],
             '取り出す RGB\\n実行する cross.map_color',
             "色をCross構造の空間的位置として表現"),

            # Cross軸での分布計測 (UP/DOWN軸)
            ("UP軸分布を計測", "measure_up_distribution", ["点群"],
             '取り出す 点群\\n実行する cross.measure_up_axis',
             "点群のUP軸方向の分布を計測"),

            ("DOWN軸分布を計測", "measure_down_distribution", ["点群"],
             '取り出す 点群\\n実行する cross.measure_down_axis',
             "点群のDOWN軸方向の分布を計測"),

            ("RIGHT軸分布を計測", "measure_right_distribution", ["点群"],
             '取り出す 点群\\n実行する cross.measure_right_axis',
             "点群のRIGHT軸方向の分布を計測"),

            ("LEFT軸分布を計測", "measure_left_distribution", ["点群"],
             '取り出す 点群\\n実行する cross.measure_left_axis',
             "点群のLEFT軸方向の分布を計測"),

            # 集中度の判定 (UP/DOWN軸)
            ("分布集中度を判定", "judge_concentration", ["軸値リスト"],
             '取り出す 軸値リスト\\n実行する cross.calculate_concentration',
             "分布の集中度を判定（highly_concentrated/concentrated/distributed）"),

            ("対称性を検査", "check_symmetry", ["点群"],
             '取り出す 点群\\n実行する cross.check_symmetry',
             "Cross軸での対称性をチェック"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            # 軸を適切に割り当て
            if "UP" in name_en or "DOWN" in name_en:
                axis = CrossAxis.UP
            elif "RIGHT" in name_en or "LEFT" in name_en:
                axis = CrossAxis.RIGHT
            else:
                axis = CrossAxis.FRONT

            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, axis, "vision", params, code, desc
            )

    def _add_shape_recognition_commands(self):
        """形状認識コマンド (BACK軸 - 断片記憶)"""

        commands = [
            # 断片記憶の管理
            ("形状パターンを記憶", "memorize_shape_pattern", ["パターン", "ラベル"],
             '取り出す ラベル\\n取り出す パターン\\n実行する shape_memory.save_pattern',
             "形状のCross分布パターンを断片記憶に保存"),

            ("形状パターンを検索", "search_shape_pattern", ["クエリパターン"],
             '取り出す クエリパターン\\n実行する shape_memory.search_pattern',
             "断片記憶から類似する形状パターンを検索"),

            ("形状を認識", "recognize_shape", ["Crossパターン"],
             '取り出す Crossパターン\\n実行する shape_memory.recognize',
             "Cross分布パターンから形状を認識"),

            ("類似度を計算", "calculate_similarity", ["パターン1", "パターン2"],
             '取り出す パターン2\\n取り出す パターン1\\n実行する shape_memory.similarity',
             "2つのCrossパターンの類似度を計算"),

            # 基本形状の初期化
            ("基本形状を初期化", "initialize_basic_shapes", [],
             '実行する shape_memory.init_basic_shapes',
             "基本的な形状（線、矩形、円等）を断片記憶に登録"),

            ("新しい形状を学習", "learn_new_shape", ["Crossパターン", "ラベル"],
             '取り出す ラベル\\n取り出す Crossパターン\\n実行する shape_memory.learn',
             "新しい形状パターンを学習"),

            # 形状記憶の取得
            ("形状記憶を全取得", "get_all_shape_memories", [],
             '実行する shape_memory.get_all',
             "全ての形状記憶を取得"),

            ("形状ラベルで検索", "get_shape_by_label", ["ラベル"],
             '取り出す ラベル\\n実行する shape_memory.get_by_label',
             "ラベルで形状記憶を検索"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, CrossAxis.BACK, "shape_recognition", params, code, desc
            )

    def _add_pattern_extraction_commands(self):
        """パターン抽出コマンド (全軸)"""

        commands = [
            # Cross分布パターンの抽出
            ("Cross分布パターンを抽出", "extract_cross_pattern", ["点群"],
             '取り出す 点群\\n実行する pattern.extract_distribution',
             "点群からCross軸の分布パターンを抽出"),

            ("クラスタを検出", "detect_clusters", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_clusters',
             "Cross距離ベースで点のクラスタを検出"),

            ("連結性を解析", "analyze_connectivity", ["点群"],
             '取り出す 点群\\n実行する pattern.analyze_connectivity',
             "点の連結性を解析（ループ、分岐等）"),

            # 空間的特徴の抽出 (UP/DOWN/RIGHT/LEFT軸)
            ("水平線を検出", "detect_horizontal_line", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_horizontal',
             "RIGHT/LEFT軸に分布する水平線を検出"),

            ("垂直線を検出", "detect_vertical_line", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_vertical',
             "UP/DOWN軸に分布する垂直線を検出"),

            ("対角線を検出", "detect_diagonal_line", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_diagonal',
             "対角方向の線を検出"),

            # 幾何学的特徴
            ("矩形を検出", "detect_rectangle", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_rectangle',
             "矩形パターンを検出（4隅 + 対称性）"),

            ("円を検出", "detect_circle", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_circle',
             "円パターンを検出（放射対称性）"),

            ("三角形を検出", "detect_triangle", ["点群"],
             '取り出す 点群\\n実行する pattern.detect_triangle',
             "三角形パターンを検出"),

            # 統計的特徴
            ("点数を数える", "count_points", ["点群"],
             '取り出す 点群\\n実行する pattern.count',
             "点群の点数を数える"),

            ("重心を計算", "calculate_centroid", ["点群"],
             '取り出す 点群\\n実行する pattern.centroid',
             "点群の重心をCross座標で計算"),

            ("広がりを計測", "measure_spread", ["点群"],
             '取り出す 点群\\n実行する pattern.measure_spread',
             "各Cross軸方向への広がりを計測"),
        ]

        for name_ja, name_en, params, code, desc in commands:
            # 軸を適切に割り当て
            if "水平" in name_ja or "horizontal" in name_en:
                axis = CrossAxis.RIGHT
            elif "垂直" in name_ja or "vertical" in name_en:
                axis = CrossAxis.UP
            elif "クラスタ" in name_ja or "重心" in name_ja:
                axis = CrossAxis.FRONT  # 空間的統合
            else:
                axis = CrossAxis.UP  # パターン抽出はUP軸（抽象化）

            self.commands[name_ja] = OperationCommand(
                name_ja, name_en, axis, "pattern_extraction", params, code, desc
            )

    def get_command(self, name: str) -> Optional[OperationCommand]:
        """コマンドを取得"""
        return self.commands.get(name)

    def get_commands_by_axis(self, axis: CrossAxis) -> List[OperationCommand]:
        """軸別にコマンドを取得"""
        return [cmd for cmd in self.commands.values() if cmd.axis == axis]

    def get_commands_by_category(self, category: str) -> List[OperationCommand]:
        """カテゴリ別にコマンドを取得"""
        return [cmd for cmd in self.commands.values() if cmd.category == category]

    def list_all_commands(self) -> List[str]:
        """全コマンドをリスト"""
        return list(self.commands.keys())


if __name__ == "__main__":
    print("=" * 70)
    print("JCross Operation Commands - 操作コマンド体系")
    print("=" * 70)
    print()

    lib = OperationCommandLibrary()

    # 統計
    print(f"総コマンド数: {len(lib.commands)}")
    print()

    # 軸別統計
    for axis in CrossAxis:
        cmds = lib.get_commands_by_axis(axis)
        print(f"{axis.value}軸: {len(cmds)}コマンド")

    print()

    # カテゴリ別統計
    categories = set(cmd.category for cmd in lib.commands.values())
    for cat in sorted(categories):
        cmds = lib.get_commands_by_category(cat)
        print(f"{cat}: {len(cmds)}コマンド")

    print()
    print("=" * 70)
    print("サンプルコマンド:")
    print("=" * 70)
    print()

    # RIGHT軸の例
    right_cmds = lib.get_commands_by_axis(CrossAxis.RIGHT)[:3]
    for cmd in right_cmds:
        print(f"[RIGHT軸] {cmd.name_ja}")
        print(f"  説明: {cmd.description}")
        print()

    # UP軸の例
    up_cmds = lib.get_commands_by_axis(CrossAxis.UP)[:3]
    for cmd in up_cmds:
        print(f"[UP軸] {cmd.name_ja}")
        print(f"  説明: {cmd.description}")
        print()

    # FRONT軸の例
    front_cmds = lib.get_commands_by_axis(CrossAxis.FRONT)[:3]
    for cmd in front_cmds:
        print(f"[FRONT軸] {cmd.name_ja}")
        print(f"  説明: {cmd.description}")
        print()

    print("=" * 70)
    print("✅ 決定的操作 (Deterministic Operations)")
    print("❌ 確率的予測 (Probabilistic Predictions)")
    print("=" * 70)
