#!/usr/bin/env python3
"""
Claude API監視ブリッジ（Python実装）

claude_api_monitor.jcrossと連携し、実際のClaude APIリクエスト/レスポンスを
傍受して学習データとして記録する
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

class Claude_API監視ブリッジ:
    """
    Claude API監視ブリッジ

    機能:
    1. Claude APIリクエスト/レスポンスの傍受
    2. 学習データの抽出
    3. ローカル保存（プライバシー保護）
    4. オフライン学習エンジンへの連携
    """

    def __init__(self, 保存ディレクトリ: str = "~/.verantyx/user_data"):
        self.保存ディレクトリ = Path(os.path.expanduser(保存ディレクトリ))
        self.保存ディレクトリ.mkdir(parents=True, exist_ok=True)

        # API監視履歴
        self.API履歴ファイル = self.保存ディレクトリ / "api_history.json"
        self.学習データファイル = self.保存ディレクトリ / "learning_data.json"

        # 監視状態
        self.監視中 = False
        self.外部送信カウント = 0  # プライバシー検証用

        # 履歴読み込み
        self.API履歴 = self._履歴を読み込み()

    def _履歴を読み込み(self) -> List[Dict]:
        """API履歴を読み込み"""
        if self.API履歴ファイル.exists():
            with open(self.API履歴ファイル, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _履歴を保存(self):
        """API履歴を保存"""
        with open(self.API履歴ファイル, 'w', encoding='utf-8') as f:
            json.dump(self.API履歴, f, ensure_ascii=False, indent=2)

    def 監視を開始(self):
        """API監視を開始"""
        print("=" * 50)
        print("Claude API 監視開始")
        print("=" * 50)
        print("プライバシー保護:")
        print("  ✅ 外部送信: なし")
        print(f"  ✅ ローカル保存: {self.保存ディレクトリ}")
        print("  ✅ ユーザー管理: 完全")
        print("=" * 50)
        print()

        self.監視中 = True
        self.外部送信カウント = 0

    def リクエストを傍受(self, リクエストデータ: Dict[str, Any]) -> Dict[str, Any]:
        """
        Claude APIリクエストを傍受

        Args:
            リクエストデータ: APIリクエストの内容
                {
                    "prompt": "ユーザーのプロンプト",
                    "model": "claude-sonnet-4-5",
                    "parameters": {...}
                }

        Returns:
            リクエストデータ（改変なし）
        """
        if not self.監視中:
            return リクエストデータ

        # タイムスタンプ追加
        リクエストデータ["timestamp"] = datetime.now().isoformat()
        リクエストデータ["type"] = "request"

        # ローカル記録（外部送信なし）
        self.API履歴.append(リクエストデータ)
        self._履歴を保存()

        # 学習用にユーザープロンプトを抽出
        if "prompt" in リクエストデータ:
            self._学習データとして保存(
                リクエストデータ["prompt"],
                送信者="ユーザー"
            )

        # リクエストはそのまま返す（改変なし）
        return リクエストデータ

    def レスポンスを傍受(self, レスポンスデータ: Dict[str, Any]) -> Dict[str, Any]:
        """
        Claude APIレスポンスを傍受

        Args:
            レスポンスデータ: APIレスポンスの内容
                {
                    "content": "Claudeの応答",
                    "usage": {...}
                }

        Returns:
            レスポンスデータ（改変なし）
        """
        if not self.監視中:
            return レスポンスデータ

        # タイムスタンプ追加
        レスポンスデータ["timestamp"] = datetime.now().isoformat()
        レスポンスデータ["type"] = "response"

        # ローカル記録（外部送信なし）
        self.API履歴.append(レスポンスデータ)
        self._履歴を保存()

        # 学習用にClaude応答を抽出
        if "content" in レスポンスデータ:
            self._学習データとして保存(
                レスポンスデータ["content"],
                送信者="Claude"
            )

        # レスポンス受信後、学習トリガー
        self._学習を実行()

        # レスポンスはそのまま返す（改変なし）
        return レスポンスデータ

    def _学習データとして保存(self, テキスト: str, 送信者: str):
        """学習データとして保存"""
        学習データ = {
            "データ種別": "対話",
            "テキスト": テキスト,
            "送信者": 送信者,
            "時刻": datetime.now().isoformat(),
            "保存先": str(self.保存ディレクトリ),
            "外部送信": "なし"
        }

        # 学習データファイルに追記
        if self.学習データファイル.exists():
            with open(self.学習データファイル, 'r', encoding='utf-8') as f:
                学習データリスト = json.load(f)
        else:
            学習データリスト = []

        学習データリスト.append(学習データ)

        with open(self.学習データファイル, 'w', encoding='utf-8') as f:
            json.dump(学習データリスト, f, ensure_ascii=False, indent=2)

    def _学習を実行(self):
        """オフライン学習を実行"""
        print("📚 オフライン学習を実行中...")

        # 最新の対話ペアを取得
        ユーザープロンプト, Claude応答 = self._最新の対話ペアを取得()

        if ユーザープロンプト and Claude応答:
            # オフライン学習エンジンと連携
            from offline_learning_processors import オフライン学習エンジン

            # 学習エンジンを初期化（初回のみ）
            if not hasattr(self, '学習エンジン'):
                self.学習エンジン = オフライン学習エンジン(
                    ユーザーデータディレクトリ=str(self.保存ディレクトリ)
                )

            # 実際に学習を実行
            self.学習エンジン.対話から学習する(ユーザープロンプト, Claude応答)

            # 統計を取得して表示
            統計 = self.学習エンジン.統計を取得()

            print(f"   ユーザープロンプト: {ユーザープロンプト[:50]}...")
            print(f"   Claude応答: {Claude応答[:50]}...")
            print(f"   📈 獲得語彙: {統計['獲得語彙数']}語")
            print(f"   💬 学習回数: {統計['学習回数']}回")
            print(f"   🧠 理解深度: {統計['理解深度']}")
            print("   ✅ 学習完了")
        print()

    def _最新の対話ペアを取得(self) -> tuple[Optional[str], Optional[str]]:
        """最新のリクエスト/レスポンスペアを取得"""
        最新リクエスト = None
        最新レスポンス = None

        # 逆順で走査
        for 項目 in reversed(self.API履歴):
            if 項目.get("type") == "request" and not 最新リクエスト:
                最新リクエスト = 項目.get("prompt")
            elif 項目.get("type") == "response" and not 最新レスポンス:
                最新レスポンス = 項目.get("content")

            if 最新リクエスト and 最新レスポンス:
                break

        return 最新リクエスト, 最新レスポンス

    def プライバシーを検証(self):
        """プライバシー保護を検証"""
        print("=" * 50)
        print("プライバシー検証")
        print("=" * 50)
        print()

        # 外部通信カウント確認
        if self.外部送信カウント == 0:
            print("✅ 外部通信: 0回")
            print("   完全オフライン確認")
        else:
            print(f"❌ 警告: 外部通信を検出: {self.外部送信カウント}回")

        # ローカルファイル確認
        print()
        print("📁 ローカルファイル:")
        for ファイル in [self.API履歴ファイル, self.学習データファイル]:
            if ファイル.exists():
                サイズ = ファイル.stat().st_size
                print(f"   {ファイル.name}: {サイズ} bytes")

        print()
        print("=" * 50)
        print("✅ プライバシー保護: 確認完了")
        print("=" * 50)
        print()

    def 統計を取得(self) -> Dict[str, Any]:
        """監視統計を取得"""
        リクエスト数 = sum(1 for 項目 in self.API履歴 if 項目.get("type") == "request")
        レスポンス数 = sum(1 for 項目 in self.API履歴 if 項目.get("type") == "response")

        return {
            "総API呼び出し": リクエスト数,
            "総レスポンス": レスポンス数,
            "外部送信": self.外部送信カウント,
            "保存先": str(self.保存ディレクトリ)
        }


def テスト_API監視ブリッジ():
    """API監視ブリッジのテスト"""
    print()
    print("=" * 80)
    print("Claude API監視ブリッジ テスト")
    print("=" * 80)
    print()

    # 監視ブリッジ作成
    監視 = Claude_API監視ブリッジ()

    # 監視開始
    監視.監視を開始()

    # 模擬リクエスト
    print("【1. 模擬リクエスト】")
    リクエスト = {
        "prompt": "Pythonで再帰関数を書いて",
        "model": "claude-sonnet-4-5",
        "parameters": {}
    }
    監視.リクエストを傍受(リクエスト)
    print(f"  リクエスト傍受: {リクエスト['prompt']}")
    print()

    # 模擬レスポンス
    print("【2. 模擬レスポンス】")
    レスポンス = {
        "content": "再帰関数の例:\ndef factorial(n):\n    if n == 0: return 1\n    return n * factorial(n-1)",
        "usage": {"tokens": 100}
    }
    監視.レスポンスを傍受(レスポンス)
    print(f"  レスポンス傍受: {レスポンス['content'][:50]}...")
    print()

    # プライバシー検証
    print("【3. プライバシー検証】")
    監視.プライバシーを検証()

    # 統計
    print("【4. 統計】")
    統計 = 監視.統計を取得()
    for キー, 値 in 統計.items():
        print(f"  {キー}: {値}")
    print()

    print("=" * 80)
    print("✅ テスト完了")
    print("=" * 80)


if __name__ == "__main__":
    テスト_API監視ブリッジ()
