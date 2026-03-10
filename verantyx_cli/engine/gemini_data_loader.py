#!/usr/bin/env python3
"""
Gemini学習データ統合システム

Gemini応答ファイルを読み込み、コマンドマッチングでCross構造に変換し、
production_jcross_engine.pyで学習させる統合層
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import sys

# production_jcross_engine.pyをインポート
from production_jcross_engine import 本番JCrossエンジン


class Gemini学習データ統合:
    """
    Gemini応答データをCross構造で学習する統合システム

    フロー:
    1. Gemini応答ファイルを読み込み
    2. 対話ペアに分割
    3. コマンドマッチング
    4. Cross構造に変換
    5. production_jcross_engine.pyで保存
    6. パターン抽出
    """

    def __init__(self):
        print("=" * 80)
        print("Gemini学習データ統合システム 初期化")
        print("=" * 80)
        print()

        # 1. JCrossエンジンを初期化
        print("📦 JCrossエンジンを初期化中...")
        self.エンジン = 本番JCrossエンジン()
        print("   ✅ JCrossエンジン初期化完了")
        print()

        # 2. コマンド辞書を読み込み
        print("📚 コマンド辞書を読み込み中...")
        self.コマンド辞書 = self._コマンド辞書を読み込み()
        print(f"   ✅ {len(self.コマンド辞書):,}個のコマンドを読み込みました")
        print()

        # 3. 学習統計
        self.学習統計 = {
            "総対話数": 0,
            "総マッチ数": 0,
            "平均マッチ率": 0.0,
            "学習開始時刻": datetime.now().isoformat()
        }

    def _コマンド辞書を読み込み(self) -> Dict:
        """コマンド辞書を読み込み"""
        コマンドパス = Path.home() / ".verantyx/commands/claude_supervised_commands.json"

        if not コマンドパス.exists():
            print(f"   ⚠️  コマンド辞書が見つかりません: {コマンドパス}")
            return {}

        with open(コマンドパス, 'r', encoding='utf-8') as f:
            データ = json.load(f)

        return データ.get("コマンド", {})

    def Gemini応答ファイルを読み込み(self, ファイルパス: str) -> int:
        """
        Gemini応答ファイルを読み込んで学習

        Args:
            ファイルパス: Gemini応答ファイルのパス

        Returns:
            学習した対話の数
        """
        print("=" * 80)
        print(f"📖 ファイル読み込み: {ファイルパス}")
        print("=" * 80)
        print()

        パス = Path(ファイルパス)
        if not パス.exists():
            print(f"❌ ファイルが見つかりません: {ファイルパス}")
            return 0

        # ファイルサイズを確認
        サイズMB = パス.stat().st_size / (1024 * 1024)
        print(f"ファイルサイズ: {サイズMB:.2f} MB")
        print()

        # ファイルを読み込み
        print("読み込み中...")
        with open(パス, 'r', encoding='utf-8') as f:
            内容 = f.read()

        print(f"✅ {len(内容):,}文字読み込みました")
        print()

        # 対話に分割
        print("対話ペアに分割中...")
        対話リスト = self._対話に分割(内容)
        print(f"✅ {len(対話リスト)}個の対話ペアを抽出しました")
        print()

        # 各対話を学習
        print("学習開始...")
        print()

        学習数 = 0
        for i, 対話 in enumerate(対話リスト, 1):
            if i % 10 == 0:
                print(f"  進捗: {i}/{len(対話リスト)} ({i/len(対話リスト)*100:.1f}%)")

            self._学習する(対話.get("user", ""), 対話.get("assistant", ""))
            学習数 += 1

            # 最初の100件のみ学習（テスト用）
            if 学習数 >= 100:
                print(f"\n  ⚠️  テストモード: 最初の{学習数}件のみ学習")
                break

        print()
        print(f"✅ 学習完了: {学習数}件の対話を学習しました")

        return 学習数

    def _対話に分割(self, テキスト: str) -> List[Dict]:
        """
        テキストを対話ペアに分割

        フォーマット想定:
        User: ...
        Assistant: ...
        """
        対話リスト = []

        # シンプルな分割（実際のフォーマットに応じて調整が必要）
        行リスト = テキスト.split('\n')

        現在の対話 = {"user": "", "assistant": ""}
        現在の役割 = None

        for 行 in 行リスト:
            if 行.startswith("User:") or 行.startswith("user:") or 行.startswith("ユーザー:"):
                # 前の対話を保存
                if 現在の対話["user"] or 現在の対話["assistant"]:
                    対話リスト.append(現在の対話)
                    現在の対話 = {"user": "", "assistant": ""}

                現在の役割 = "user"
                現在の対話["user"] = 行.split(":", 1)[1].strip() if ":" in 行 else ""

            elif 行.startswith("Assistant:") or 行.startswith("assistant:") or 行.startswith("Gemini:") or 行.startswith("gemini:"):
                現在の役割 = "assistant"
                現在の対話["assistant"] = 行.split(":", 1)[1].strip() if ":" in 行 else ""

            elif 現在の役割 and 行.strip():
                # 継続行
                if 現在の役割 == "user":
                    現在の対話["user"] += " " + 行.strip()
                else:
                    現在の対話["assistant"] += " " + 行.strip()

        # 最後の対話を保存
        if 現在の対話["user"] or 現在の対話["assistant"]:
            対話リスト.append(現在の対話)

        return 対話リスト

    def _学習する(self, ユーザー発言: str, 応答: str):
        """
        対話ペアをCross構造で学習

        フロー:
        1. コマンドマッチング（ユーザー発言）
        2. コマンドマッチング（応答）
        3. Cross構造生成
        4. グローバルCross構造に保存
        """
        if not ユーザー発言 or not 応答:
            return

        # 1. コマンドマッチング
        ユーザーマッチ = self._コマンドマッチング(ユーザー発言)
        応答マッチ = self._コマンドマッチング(応答)

        # 統計更新
        self.学習統計["総対話数"] += 1
        self.学習統計["総マッチ数"] += len(ユーザーマッチ) + len(応答マッチ)

        # 2. Cross構造生成
        対話Cross = {
            "LEFT": self._Cross構造生成(ユーザー発言, ユーザーマッチ),
            "RIGHT": self._Cross構造生成(応答, 応答マッチ),
            "UP": [{
                "抽象": "対話パターン",
                "カテゴリ": "Q&A",
                "マッチ成功": len(ユーザーマッチ) > 0 and len(応答マッチ) > 0
            }],
            "DOWN": [{
                "具体": "個別対話",
                "ユーザー": ユーザー発言[:100] + "..." if len(ユーザー発言) > 100 else ユーザー発言,
                "応答": 応答[:100] + "..." if len(応答) > 100 else 応答
            }],
            "BACK": [{
                "時刻": datetime.now().isoformat(),
                "対話番号": self.学習統計["総対話数"]
            }],
            "FRONT": [{
                "学習状態": "Cross構造で保存完了",
                "パターン抽出可能": len(ユーザーマッチ) > 0 or len(応答マッチ) > 0
            }]
        }

        # 3. グローバルCross構造に保存
        if "学習履歴" not in self.エンジン.グローバルCross構造:
            self.エンジン.グローバルCross構造["学習履歴"] = []

        self.エンジン.グローバルCross構造["学習履歴"].append(対話Cross)

    def _コマンドマッチング(self, テキスト: str) -> List[Dict]:
        """
        テキストからマッチするコマンドを検索

        Returns:
            マッチしたコマンドのリスト
        """
        マッチ結果 = []

        for コマンド名, コマンド情報 in self.コマンド辞書.items():
            if コマンド名 in テキスト:
                マッチ結果.append({
                    "コマンド": コマンド名,
                    "カテゴリ": コマンド情報.get("カテゴリ", "不明"),
                    "意味": コマンド情報.get("意味", ""),
                    "Cross軸": コマンド情報.get("Cross軸配置", {})
                })

        return マッチ結果

    def _Cross構造生成(self, テキスト: str, マッチ結果: List[Dict]) -> Dict:
        """
        マッチ結果からCross構造を生成

        Args:
            テキスト: 元のテキスト
            マッチ結果: マッチしたコマンドのリスト

        Returns:
            Cross構造
        """
        Cross構造 = {
            "元テキスト": テキスト,
            "マッチ数": len(マッチ結果),
            "マッチしたコマンド": [m["コマンド"] for m in マッチ結果],
            "Cross軸統合": self._Cross軸を統合(マッチ結果)
        }

        return Cross構造

    def _Cross軸を統合(self, マッチ結果: List[Dict]) -> Dict:
        """
        複数のマッチ結果のCross軸を統合

        Args:
            マッチ結果: マッチしたコマンドのリスト

        Returns:
            統合されたCross軸
        """
        統合Cross = {
            "UP": [],
            "DOWN": [],
            "LEFT": [],
            "RIGHT": [],
            "FRONT": [],
            "BACK": []
        }

        for マッチ in マッチ結果:
            Cross軸 = マッチ.get("Cross軸", {})

            for 軸名 in ["UP", "DOWN", "LEFT", "RIGHT", "FRONT", "BACK"]:
                if 軸名 in Cross軸:
                    統合Cross[軸名].append({
                        "コマンド": マッチ["コマンド"],
                        "内容": Cross軸[軸名]
                    })

        return 統合Cross

    def 統計を表示(self):
        """学習統計を表示"""
        print()
        print("=" * 80)
        print("📊 学習統計")
        print("=" * 80)
        print()

        print(f"総対話数: {self.学習統計['総対話数']:,}件")
        print(f"総マッチ数: {self.学習統計['総マッチ数']:,}個")

        if self.学習統計["総対話数"] > 0:
            平均 = self.学習統計["総マッチ数"] / self.学習統計["総対話数"]
            print(f"平均マッチ数/対話: {平均:.2f}個")

        print(f"学習開始時刻: {self.学習統計['学習開始時刻']}")
        print()

        # グローバルCross構造のサイズ
        履歴数 = len(self.エンジン.グローバルCross構造.get("学習履歴", []))
        print(f"グローバルCross構造に保存された履歴: {履歴数:,}件")
        print()

    def Cross構造を保存(self, 出力パス: str = None):
        """
        グローバルCross構造をJSONファイルに保存

        Args:
            出力パス: 保存先パス（省略時は~/.verantyx/learning/）
        """
        if 出力パス is None:
            出力ディレクトリ = Path.home() / ".verantyx/learning"
            出力ディレクトリ.mkdir(parents=True, exist_ok=True)

            タイムスタンプ = datetime.now().strftime("%Y%m%d_%H%M%S")
            出力パス = 出力ディレクトリ / f"learned_cross_{タイムスタンプ}.json"

        出力パス = Path(出力パス)

        print(f"💾 Cross構造を保存中: {出力パス}")

        with open(出力パス, 'w', encoding='utf-8') as f:
            json.dump(self.エンジン.グローバルCross構造, f, ensure_ascii=False, indent=2)

        サイズMB = 出力パス.stat().st_size / (1024 * 1024)
        print(f"✅ 保存完了: {サイズMB:.2f} MB")


if __name__ == "__main__":
    print()
    print("=" * 80)
    print("🧠 Gemini学習データ統合システム")
    print("=" * 80)
    print()

    # 統合システムを初期化
    統合システム = Gemini学習データ統合()

    # テスト: サンプルデータで動作確認
    print("🧪 テストモード: サンプルデータで動作確認")
    print()

    サンプル対話 = [
        {
            "user": "Pythonでデータを分析する方法を教えて",
            "assistant": "pandasライブラリを使ってCSVを読み込み、describe()で統計分析できます"
        },
        {
            "user": "システムの性能を最適化したい",
            "assistant": "まずプロファイリングでボトルネックを特定し、それから最適化します"
        }
    ]

    for i, 対話 in enumerate(サンプル対話, 1):
        print(f"サンプル {i}:")
        print(f"  User: {対話['user']}")
        print(f"  Assistant: {対話['assistant']}")
        統合システム._学習する(対話["user"], 対話["assistant"])
        print()

    # 統計表示
    統合システム.統計を表示()

    # Cross構造を保存
    統合システム.Cross構造を保存()

    print()
    print("=" * 80)
    print("✅ テスト完了")
    print("=" * 80)
    print()
