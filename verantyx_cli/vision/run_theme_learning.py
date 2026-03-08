#!/usr/bin/env python3
"""
Theme Learning Runner
テーマ学習ランナー

ユーザーのコンピュータから写真を読み込み、
テーマごとに多層Cross構造を学習する。

使い方:
    # 自動でPicturesフォルダから写真を検索して学習
    python -m verantyx_cli.vision.run_theme_learning

    # 特定のテーマのみ学習
    python -m verantyx_cli.vision.run_theme_learning --theme sky

    # カスタムディレクトリから学習
    python -m verantyx_cli.vision.run_theme_learning --directory ~/Photos
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse

# Cross IR関連をインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kofdai_computer"))

from verantyx_cli.vision.multi_layer_cross import MultiLayerCrossConverter
from verantyx_cli.vision.theme_memory_bank import ThemeMemoryBank
import glob


def find_theme_photos(
    theme: str,
    directory: Path,
    max_samples: int = 5
) -> List[Path]:
    """
    テーマに関連する写真を検索

    Args:
        theme: テーマ名
        directory: 検索ディレクトリ
        max_samples: 最大サンプル数

    Returns:
        写真パスのリスト
    """
    print(f"\n🔍 テーマ '{theme}' の写真を検索中...")
    print(f"   ディレクトリ: {directory}")

    if not directory.exists():
        print(f"   ❌ ディレクトリが見つかりません")
        return []

    # 画像ファイルを検索
    photo_paths = []
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]

    for ext in extensions:
        pattern = str(directory / "**" / ext)
        found = glob.glob(pattern, recursive=True)
        photo_paths.extend([Path(p) for p in found])

    # ファイル名にテーマが含まれるものを優先
    theme_photos = [p for p in photo_paths if theme.lower() in p.name.lower()]

    if theme_photos:
        selected = theme_photos[:max_samples]
        print(f"   ✅ テーマに一致する写真を {len(selected)} 枚発見")
    else:
        # テーマに一致しない場合はランダムに選択
        import random
        random.shuffle(photo_paths)
        selected = photo_paths[:max_samples]
        print(f"   ⚠️  テーマに一致する写真が見つからないため、ランダムに {len(selected)} 枚選択")

    return selected


def convert_photos_to_multi_layer_cross(
    photo_paths: List[Path],
    quality: str = "ultra_high"
) -> List[Dict[str, Any]]:
    """
    写真を多層Cross構造に変換

    Args:
        photo_paths: 写真パスのリスト
        quality: 品質

    Returns:
        多層Cross構造のリスト
    """
    converter = MultiLayerCrossConverter(quality=quality)

    cross_structures = []

    for i, photo_path in enumerate(photo_paths, 1):
        print(f"\n📷 [{i}/{len(photo_paths)}] 変換中: {photo_path.name}")

        try:
            cross_structure = converter.convert(photo_path)
            cross_structures.append(cross_structure)
        except Exception as e:
            print(f"   ❌ エラー: {e}")
            continue

    return cross_structures


def learn_theme(
    theme_name: str,
    directory: Path,
    memory_bank: ThemeMemoryBank,
    max_samples: int = 5,
    quality: str = "ultra_high"
) -> bool:
    """
    テーマを学習

    Args:
        theme_name: テーマ名
        directory: 検索ディレクトリ
        memory_bank: テーマ記憶バンク
        max_samples: 最大サンプル数
        quality: 品質

    Returns:
        成功したかどうか
    """
    print("\n" + "=" * 70)
    print(f"🎓 テーマ学習: {theme_name}")
    print("=" * 70)

    # 1. 写真を検索
    photo_paths = find_theme_photos(theme_name, directory, max_samples)

    if not photo_paths:
        print(f"\n❌ テーマ '{theme_name}' の写真が見つかりませんでした")
        return False

    # 2. 多層Cross構造に変換
    cross_structures = convert_photos_to_multi_layer_cross(photo_paths, quality)

    if not cross_structures:
        print(f"\n❌ テーマ '{theme_name}' の変換に失敗しました")
        return False

    # 3. 記憶バンクに保存
    try:
        memory_bank.learn_theme(theme_name, cross_structures)
        return True
    except Exception as e:
        print(f"\n❌ テーマ '{theme_name}' の学習エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Theme Learning Runner - 多層Crossテーマ学習"
    )

    parser.add_argument(
        "--theme",
        type=str,
        help="学習するテーマ（指定しない場合は全テーマ）",
        choices=["sky", "flower", "human", "cloud", "tree", "water", "building", "face"]
    )

    parser.add_argument(
        "--directory",
        type=str,
        default="~/Pictures",
        help="写真を検索するディレクトリ（デフォルト: ~/Pictures）"
    )

    parser.add_argument(
        "--max-samples",
        type=int,
        default=5,
        help="テーマごとの最大サンプル数（デフォルト: 5）"
    )

    parser.add_argument(
        "--quality",
        type=str,
        default="ultra_high",
        choices=["standard", "high", "ultra_high"],
        help="変換品質（デフォルト: ultra_high）"
    )

    parser.add_argument(
        "--memory-path",
        type=str,
        help="記憶バンクの保存先（デフォルト: ~/.verantyx/theme_memory.json）"
    )

    args = parser.parse_args()

    # ディレクトリを展開
    directory = Path(args.directory).expanduser().absolute()

    # 記憶バンクのパス
    if args.memory_path:
        memory_path = Path(args.memory_path).expanduser().absolute()
    else:
        memory_path = Path.home() / ".verantyx" / "theme_memory.json"

    # 記憶バンクを初期化
    memory_bank = ThemeMemoryBank(memory_path=memory_path)

    print()
    print("=" * 70)
    print("🎓 Multi-Layer Cross Theme Learning")
    print("=" * 70)
    print(f"検索ディレクトリ: {directory}")
    print(f"品質: {args.quality}")
    print(f"最大サンプル数/テーマ: {args.max_samples}")
    print(f"記憶バンク: {memory_path}")
    print("=" * 70)

    # 学習するテーマを決定
    if args.theme:
        themes_to_learn = [args.theme]
    else:
        # デフォルト: 主要な3テーマ
        themes_to_learn = ["sky", "flower", "human"]

    print(f"\n学習するテーマ: {', '.join(themes_to_learn)}")

    # 各テーマを学習
    results = {}

    for theme in themes_to_learn:
        success = learn_theme(
            theme_name=theme,
            directory=directory,
            memory_bank=memory_bank,
            max_samples=args.max_samples,
            quality=args.quality
        )

        results[theme] = success

    # 結果サマリー
    print("\n" + "=" * 70)
    print("📊 学習結果サマリー")
    print("=" * 70)

    for theme, success in results.items():
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"  {theme}: {status}")

    # 記憶バンクを保存
    memory_bank.save()

    # 学習済みテーマの一覧を表示
    print("\n" + "=" * 70)
    print("💾 学習済みテーマ一覧")
    print("=" * 70)

    themes = memory_bank.list_themes()

    for theme_info in themes:
        print(f"  - {theme_info['name']}")
        print(f"    サンプル数: {theme_info['sample_count']}")
        print(f"    学習日時: {theme_info['learned_at']}")
        print()

    print("=" * 70)

    # 成功したテーマがあればexit code 0
    if any(results.values()):
        print("\n✅ テーマ学習が完了しました")
        return 0
    else:
        print("\n❌ すべてのテーマ学習が失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())
