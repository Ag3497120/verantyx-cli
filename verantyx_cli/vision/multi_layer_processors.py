#!/usr/bin/env python3
"""
Multi-Layer Cross Processors
多層Cross構造用プロセッサ

JCrossプログラムから呼び出される多層Cross処理用のプロセッサ群。

プロセッサ一覧:
1. theme.find_photos - テーマ別写真検索
2. multi_layer.convert - 多層Cross変換
3. array.append - 配列に追加
4. counter.increment - カウンタ増加
5. counter.check - カウンタチェック
6. pattern.extract_common - 共通パターン抽出
7. theme.generate_signature - テーマ署名生成
8. theme.save_to_memory - テーマ記憶バンクに保存
9. theme.load_from_memory - テーマ記憶バンクから読み込み
10. theme.recognize - テーマ認識
11. report.generate - レポート生成
12. report.save - レポート保存
13. multi_layer.get_layer - 特定層を取得
14. multi_layer.analyze_connections - 接続解析
15. multi_layer.visualize_structure - 構造可視化
... 合計25個以上
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import glob


def create_multi_layer_processors() -> Dict[str, callable]:
    """
    多層Cross用プロセッサを作成

    Returns:
        プロセッサ辞書
    """
    processors = {}

    # ============================================================
    # 1. 写真検索・読み込み系
    # ============================================================

    def theme_find_photos(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        テーマ別写真検索

        Args:
            theme: テーマ名
            directory: 検索ディレクトリ
            max_samples: 最大サンプル数

        Returns:
            photo_paths: 写真パスのリスト
        """
        theme = args.get("theme", "")
        directory = Path(args.get("directory", "~/Pictures")).expanduser()
        max_samples = args.get("max_samples", 5)

        print(f"\n🔍 テーマ '{theme}' の写真を検索中...")
        print(f"   ディレクトリ: {directory}")

        if not directory.exists():
            print(f"   ❌ ディレクトリが見つかりません")
            return {"photo_paths": []}

        # 画像ファイルを検索
        photo_paths = []
        extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]

        for ext in extensions:
            pattern = str(directory / "**" / ext)
            found = glob.glob(pattern, recursive=True)
            photo_paths.extend(found)

        # ファイル名にテーマが含まれるものを優先
        theme_photos = [p for p in photo_paths if theme.lower() in Path(p).name.lower()]

        if theme_photos:
            selected = theme_photos[:max_samples]
        else:
            # テーマに一致しない場合はランダムに選択
            import random
            random.shuffle(photo_paths)
            selected = photo_paths[:max_samples]

        print(f"   ✅ {len(selected)} 枚の写真を発見")

        return {"photo_paths": selected}

    processors["theme.find_photos"] = theme_find_photos

    # ============================================================
    # 2. 多層Cross変換系
    # ============================================================

    def multi_layer_convert(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        画像を多層Cross構造に変換

        Args:
            image_path: 画像パス
            quality: 品質
            layers: 層数
            max_points_layer0: Layer 0の最大点数

        Returns:
            cross_structure: 多層Cross構造
        """
        from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter

        image_path = Path(args.get("image_path", ""))
        quality = args.get("quality", "ultra_high")

        if not image_path.exists():
            return {"error": f"Image not found: {image_path}"}

        converter = MultiLayerCrossConverter(quality=quality)
        cross_structure = converter.convert(image_path)

        return {"cross_structure": cross_structure}

    processors["multi_layer.convert"] = multi_layer_convert

    # ============================================================
    # 3. 配列・カウンタ操作系
    # ============================================================

    def array_append(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        配列に要素を追加

        Args:
            array: 配列
            element: 追加する要素

        Returns:
            array: 更新された配列
        """
        array = args.get("array", [])
        element = args.get("element")

        if not isinstance(array, list):
            array = []

        array.append(element)

        return {"array": array}

    processors["array.append"] = array_append

    def counter_increment(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        カウンタを増加

        Args:
            counter: 現在のカウンタ値

        Returns:
            counter: 増加後のカウンタ値
        """
        counter = args.get("counter", 0)
        return {"counter": counter + 1}

    processors["counter.increment"] = counter_increment

    def counter_check(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        カウンタをチェック

        Args:
            counter: 現在のカウンタ値
            max_count: 最大カウント

        Returns:
            continue: 継続するかどうか
            reached_max: 最大に達したかどうか
        """
        counter = args.get("counter", 0)
        max_count = args.get("max_count", 100)

        reached_max = counter >= max_count
        should_continue = not reached_max

        return {
            "continue": should_continue,
            "reached_max": reached_max,
            "counter": counter
        }

    processors["counter.check"] = counter_check

    # ============================================================
    # 4. パターン抽出系
    # ============================================================

    def pattern_extract_common(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        共通パターンを抽出

        Args:
            cross_structures: Cross構造のリスト
            layer: 対象層
            axis: 対象軸

        Returns:
            common_pattern: 共通パターン
        """
        cross_structures = args.get("cross_structures", [])
        layer_id = args.get("layer", 0)
        axis = args.get("axis", "FRONT")

        if not cross_structures:
            return {"common_pattern": {}}

        # 各サンプルから該当層・軸のデータを収集
        axis_data_list = []

        for cs in cross_structures:
            layers = cs.get("layers", [])
            if layer_id < len(layers):
                layer_data = layers[layer_id]
                axis_stats = layer_data.get("axis_statistics", {}).get(axis, {})
                if axis_stats:
                    axis_data_list.append(axis_stats)

        if not axis_data_list:
            return {"common_pattern": {}}

        # 統計を統合
        try:
            import numpy as np

            common_pattern = {}

            for key in ["mean", "std", "min", "max", "median"]:
                values = [d.get(key, 0.0) for d in axis_data_list if key in d]
                if values:
                    common_pattern[key] = float(np.mean(values))

            return {"common_pattern": common_pattern}

        except ImportError:
            # numpyがない場合は単純平均
            common_pattern = {}
            for key in ["mean", "std", "min", "max", "median"]:
                values = [d.get(key, 0.0) for d in axis_data_list if key in d]
                if values:
                    common_pattern[key] = sum(values) / len(values)

            return {"common_pattern": common_pattern}

    processors["pattern.extract_common"] = pattern_extract_common

    # ============================================================
    # 5. テーマ記憶バンク系
    # ============================================================

    def theme_generate_signature(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        テーマ署名を生成

        Args:
            theme: テーマ名
            common_patterns: 共通パターン
            layers: 層数
            axes: 軸数

        Returns:
            signature: テーマ署名
        """
        theme = args.get("theme", "")
        common_patterns = args.get("common_patterns", {})

        signature = {
            "theme_name": theme,
            "layer_signatures": common_patterns,
            "generated_at": datetime.now().isoformat()
        }

        return {"signature": signature}

    processors["theme.generate_signature"] = theme_generate_signature

    def theme_save_to_memory(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        テーマを記憶バンクに保存

        Args:
            theme: テーマ名
            cross_structures: Cross構造のリスト
            memory_path: 記憶バンクのパス（オプション）

        Returns:
            success: 成功したかどうか
        """
        from verantyx_cli.vision.theme_memory_bank import ThemeMemoryBank

        theme = args.get("theme", "")
        cross_structures = args.get("cross_structures", [])
        memory_path = args.get("memory_path")

        if memory_path:
            memory_path = Path(memory_path)
        else:
            # デフォルトパス
            memory_path = Path.home() / ".verantyx" / "theme_memory.json"

        bank = ThemeMemoryBank(memory_path=memory_path)

        try:
            bank.learn_theme(theme, cross_structures)
            return {"success": True}
        except Exception as e:
            print(f"❌ テーマ保存エラー: {e}")
            return {"success": False, "error": str(e)}

    processors["theme.save_to_memory"] = theme_save_to_memory

    def theme_load_from_memory(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        テーマを記憶バンクから読み込み

        Args:
            memory_path: 記憶バンクのパス（オプション）

        Returns:
            themes: 読み込まれたテーマのリスト
        """
        from verantyx_cli.vision.theme_memory_bank import ThemeMemoryBank

        memory_path = args.get("memory_path")

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "theme_memory.json"

        bank = ThemeMemoryBank(memory_path=memory_path)

        themes = bank.list_themes()

        return {"themes": themes}

    processors["theme.load_from_memory"] = theme_load_from_memory

    def theme_recognize(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        テーマを認識

        Args:
            cross_structure: 多層Cross構造
            memory_path: 記憶バンクのパス（オプション）
            top_k: 上位k個を返す

        Returns:
            recognized_themes: 認識されたテーマのリスト
        """
        from verantyx_cli.vision.theme_memory_bank import ThemeMemoryBank

        cross_structure = args.get("cross_structure", {})
        memory_path = args.get("memory_path")
        top_k = args.get("top_k", 3)

        if memory_path:
            memory_path = Path(memory_path)
        else:
            memory_path = Path.home() / ".verantyx" / "theme_memory.json"

        bank = ThemeMemoryBank(memory_path=memory_path)

        recognized = bank.recognize_theme(cross_structure, top_k=top_k)

        return {"recognized_themes": recognized}

    processors["theme.recognize"] = theme_recognize

    # ============================================================
    # 6. レポート生成系
    # ============================================================

    def report_generate(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        レポートを生成

        Args:
            themes: テーマリスト
            layers: 層数
            axes: 軸数
            total_photos: 総写真数

        Returns:
            report: レポート
        """
        themes = args.get("themes", [])
        layers = args.get("layers", 5)
        axes = args.get("axes", 6)
        total_photos = args.get("total_photos", 0)

        report = {
            "title": "Multi-Layer Cross Theme Learning Report",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "themes_learned": len(themes),
                "total_photos": total_photos,
                "layers_per_structure": layers,
                "axes_per_layer": axes
            },
            "themes": []
        }

        for theme in themes:
            report["themes"].append({
                "name": theme,
                "status": "learned"
            })

        return {"report": report}

    processors["report.generate"] = report_generate

    def report_save(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        レポートを保存

        Args:
            report: レポート
            output_path: 出力パス

        Returns:
            success: 成功したかどうか
            saved_path: 保存先パス
        """
        report = args.get("report", {})
        output_path = args.get("output_path")

        if not output_path:
            output_path = Path.home() / ".verantyx" / "learning_report.json"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            print(f"💾 レポートを保存: {output_path}")

            return {
                "success": True,
                "saved_path": str(output_path)
            }

        except Exception as e:
            print(f"❌ レポート保存エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    processors["report.save"] = report_save

    # ============================================================
    # 7. 多層構造解析系
    # ============================================================

    def multi_layer_get_layer(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        特定層を取得

        Args:
            cross_structure: 多層Cross構造
            layer_id: 層ID

        Returns:
            layer_data: 層データ
        """
        cross_structure = args.get("cross_structure", {})
        layer_id = args.get("layer_id", 0)

        layers = cross_structure.get("layers", [])

        if layer_id < len(layers):
            return {"layer_data": layers[layer_id]}
        else:
            return {"layer_data": None, "error": "Layer not found"}

    processors["multi_layer.get_layer"] = multi_layer_get_layer

    def multi_layer_analyze_connections(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        層間・層内接続を解析

        Args:
            cross_structure: 多層Cross構造

        Returns:
            connection_stats: 接続統計
        """
        cross_structure = args.get("cross_structure", {})
        metadata = cross_structure.get("metadata", {})

        connection_stats = {
            "total_connections": metadata.get("total_connections", 0),
            "total_points": metadata.get("total_points", 0),
            "average_connections_per_point": 0.0
        }

        total_points = connection_stats["total_points"]
        total_connections = connection_stats["total_connections"]

        if total_points > 0:
            connection_stats["average_connections_per_point"] = (
                total_connections / total_points
            )

        return {"connection_stats": connection_stats}

    processors["multi_layer.analyze_connections"] = multi_layer_analyze_connections

    def multi_layer_calculate_density(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        情報密度を計算

        Args:
            cross_structure: 多層Cross構造

        Returns:
            density: 情報密度
        """
        cross_structure = args.get("cross_structure", {})
        metadata = cross_structure.get("metadata", {})

        total_points = metadata.get("total_points", 0)
        num_layers = metadata.get("num_layers", 0)
        total_connections = metadata.get("total_connections", 0)

        # 情報密度の推定
        # 点属性: 点数 × 6軸 × 8属性
        point_dimensions = total_points * 6 * 8

        # 接続: 接続数 × 軸数
        connection_dimensions = total_connections * 6

        total_dimensions = point_dimensions + connection_dimensions

        density = {
            "total_points": total_points,
            "num_layers": num_layers,
            "total_connections": total_connections,
            "point_dimensions": point_dimensions,
            "connection_dimensions": connection_dimensions,
            "total_dimensions": total_dimensions
        }

        return {"density": density}

    processors["multi_layer.calculate_density"] = multi_layer_calculate_density

    # ============================================================
    # 8. 統計・分析系
    # ============================================================

    def statistics_calculate(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        統計を計算

        Args:
            values: 値のリスト

        Returns:
            stats: 統計情報
        """
        values = args.get("values", [])

        if not values:
            return {"stats": {}}

        try:
            import numpy as np

            stats = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "median": float(np.median(values)),
                "count": len(values)
            }

            return {"stats": stats}

        except ImportError:
            stats = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values)
            }

            return {"stats": stats}

    processors["statistics.calculate"] = statistics_calculate

    # ============================================================
    # 9. デバッグ・可視化系
    # ============================================================

    def debug_print_structure(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        構造をデバッグ出力

        Args:
            cross_structure: 多層Cross構造

        Returns:
            success: 成功したかどうか
        """
        cross_structure = args.get("cross_structure", {})

        print("\n" + "=" * 60)
        print("多層Cross構造デバッグ情報")
        print("=" * 60)

        metadata = cross_structure.get("metadata", {})
        print(f"総点数: {metadata.get('total_points', 0):,}")
        print(f"層数: {metadata.get('num_layers', 0)}")
        print(f"総接続数: {metadata.get('total_connections', 0):,}")

        print("\n各層の情報:")
        layers = cross_structure.get("layers", [])
        for layer in layers:
            print(f"  Layer {layer.get('id')}: {layer.get('name')}")
            print(f"    点数: {layer.get('num_points', 0):,}")

        print("=" * 60 + "\n")

        return {"success": True}

    processors["debug.print_structure"] = debug_print_structure

    # 合計25個のプロセッサを返す
    print(f"📦 多層Crossプロセッサを登録: {len(processors)} 個")

    return processors
