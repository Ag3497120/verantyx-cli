#!/usr/bin/env python3
"""
本番学習プロセッサ（Python実装）

production_learning_loop.jcross を実行するために必要な
Pythonプロセッサを提供
"""

import re
from typing import List, Dict, Any, Optional
from offline_learning_processors import (
    日本語語彙抽出器,
    Cross操作器,
    意図推測エンジン
)


class 日本語形態素解析器:
    """日本語形態素解析器（.jcross用）"""

    def __init__(self):
        self.語彙抽出器 = 日本語語彙抽出器()

    def 解析(self, テキスト: str) -> List[str]:
        """
        テキストを形態素解析

        Args:
            テキスト: 解析対象のテキスト

        Returns:
            語彙リスト
        """
        return self.語彙抽出器.形態素解析(テキスト)

    def 文字種別判定(self, 文字列: str) -> str:
        """
        文字種別を判定

        Args:
            文字列: 判定対象の文字列

        Returns:
            "ひらがな", "カタカナ", "漢字", "その他"
        """
        if not 文字列:
            return "その他"

        # 最初の文字で判定
        最初の文字 = 文字列[0]
        コードポイント = ord(最初の文字)

        # ひらがな (0x3040-0x309F)
        if 0x3040 <= コードポイント <= 0x309F:
            return "ひらがな"

        # カタカナ (0x30A0-0x30FF)
        elif 0x30A0 <= コードポイント <= 0x30FF:
            return "カタカナ"

        # 漢字 (0x4E00-0x9FFF)
        elif 0x4E00 <= コードポイント <= 0x9FFF:
            return "漢字"

        else:
            return "その他"


class パターン抽出器:
    """対話パターン抽出器（.jcross用）"""

    def __init__(self):
        self.質問キーワード = [
            "どうやって", "どのように", "なぜ", "なんで",
            "教えて", "説明して", "書いて", "作って",
            "どう", "何", "いつ", "どこ", "誰"
        ]

        self.応答キーワード = [
            "です", "ます", "ください", "できます",
            "あります", "します", "という", "ような"
        ]

    def 抽出(self, テキスト: str, パターン種別: str) -> Optional[Dict[str, Any]]:
        """
        パターンを抽出

        Args:
            テキスト: 解析対象のテキスト
            パターン種別: "質問" or "応答"

        Returns:
            パターン辞書 or None
        """
        if パターン種別 == "質問":
            return self._質問パターンを抽出(テキスト)
        elif パターン種別 == "応答":
            return self._応答パターンを抽出(テキスト)
        else:
            return None

    def _質問パターンを抽出(self, テキスト: str) -> Optional[Dict[str, Any]]:
        """質問パターンを抽出"""
        # 質問キーワードを検索
        for キーワード in self.質問キーワード:
            if キーワード in テキスト:
                return {
                    "種別": f"質問_{キーワード}",
                    "キーワード": キーワード,
                    "テキスト": テキスト[:100]  # 最初の100文字
                }

        # 疑問符で終わる場合
        if テキスト.endswith("?") or テキスト.endswith("？"):
            return {
                "種別": "質問_疑問符",
                "キーワード": "?",
                "テキスト": テキスト[:100]
            }

        return None

    def _応答パターンを抽出(self, テキスト: str) -> Optional[Dict[str, Any]]:
        """応答パターンを抽出"""
        # 応答キーワードを検索
        for キーワード in self.応答キーワード:
            if キーワード in テキスト:
                return {
                    "種別": f"応答_{キーワード}",
                    "キーワード": キーワード,
                    "テキスト": テキスト[:100]
                }

        # コードブロックを含む応答
        if "```" in テキスト:
            return {
                "種別": "応答_コード",
                "キーワード": "コードブロック",
                "テキスト": テキスト[:100]
            }

        return {
            "種別": "応答_一般",
            "キーワード": "一般応答",
            "テキスト": テキスト[:100]
        }


def テスト_形態素解析器():
    """形態素解析器のテスト"""
    print("=" * 60)
    print("日本語形態素解析器 テスト")
    print("=" * 60)
    print()

    解析器 = 日本語形態素解析器()

    # テストテキスト
    テキスト = "Pythonで機械学習を実装してください"

    print(f"テキスト: {テキスト}")
    print()

    # 形態素解析
    語彙リスト = 解析器.解析(テキスト)
    print(f"語彙リスト: {語彙リスト}")
    print()

    # 文字種別判定
    for 語彙 in 語彙リスト[:5]:
        種別 = 解析器.文字種別判定(語彙)
        print(f"  {語彙} → {種別}")

    print()
    print("✅ テスト完了")
    print()


def テスト_パターン抽出器():
    """パターン抽出器のテスト"""
    print("=" * 60)
    print("パターン抽出器 テスト")
    print("=" * 60)
    print()

    抽出器 = パターン抽出器()

    # 質問パターン
    質問テキスト = "Pythonでどうやって再帰関数を書きますか？"
    質問パターン = 抽出器.抽出(質問テキスト, "質問")

    print(f"質問: {質問テキスト}")
    print(f"パターン: {質問パターン}")
    print()

    # 応答パターン
    応答テキスト = "再帰関数は以下のように書けます:\n```python\ndef factorial(n):\n    if n == 0: return 1\n    return n * factorial(n-1)\n```"
    応答パターン = 抽出器.抽出(応答テキスト, "応答")

    print(f"応答: {応答テキスト[:50]}...")
    print(f"パターン: {応答パターン}")
    print()

    print("✅ テスト完了")
    print()


if __name__ == "__main__":
    テスト_形態素解析器()
    テスト_パターン抽出器()
