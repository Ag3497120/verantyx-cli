#!/usr/bin/env python3
"""
コードキャプチャ強化モジュール

Claude Agentがコードを省略する問題を回避するための複数の手法を実装
"""

import os
import re
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET


class コードキャプチャ強化:
    """
    Claude Agentのコード省略問題を回避する統合モジュール

    機能:
    1. ツール呼び出しの監視（Edit/Write）
    2. git diffによる実際の変更取得
    3. ファイル変更のリアルタイム監視
    4. 完全なコード履歴の保存
    """

    def __init__(self, 作業ディレクトリ: str = "."):
        self.作業ディレクトリ = Path(作業ディレクトリ)
        self.コード変更履歴 = []
        self.完全コード履歴 = []
        self.ファイル監視履歴 = []

        print("📝 コードキャプチャ強化モジュール初期化")

    def ツール呼び出しを監視(self, 出力: str) -> List[Dict]:
        """
        Claude出力からツール呼び出しを検出してコード変更を取得

        Args:
            出力: Claudeの出力テキスト

        Returns:
            検出されたコード変更のリスト
        """
        変更リスト = []

        # Editツールの検出
        Edit検出 = self._Edit呼び出しを検出(出力)
        if Edit検出:
            変更リスト.extend(Edit検出)

        # Writeツールの検出
        Write検出 = self._Write呼び出しを検出(出力)
        if Write検出:
            変更リスト.extend(Write検出)

        return 変更リスト

    def _Edit呼び出しを検出(self, 出力: str) -> List[Dict]:
        """Edit tool呼び出しを検出"""
        変更リスト = []

        # パターン: <invoke name="Edit">...</invoke>
        Editパターン = r'<invoke name="Edit">(.*?)</invoke>'
        matches = re.findall(Editパターン, 出力, re.DOTALL)

        for match in matches:
            try:
                # XMLをパース
                invoke_xml = f'<invoke name="Edit">{match}</invoke>'
                root = ET.fromstring(invoke_xml)

                # パラメータを抽出
                file_path_elem = root.find('.//file_path')
                old_string_elem = root.find('.//old_string')
                new_string_elem = root.find('.//new_string')

                if all([file_path_elem is not None,
                        old_string_elem is not None,
                        new_string_elem is not None]):

                    変更 = {
                        "ツール": "Edit",
                        "ファイル": file_path_elem.text,
                        "旧コード": old_string_elem.text,
                        "新コード": new_string_elem.text,
                        "時刻": time.strftime("%Y-%m-%dT%H:%M:%S")
                    }

                    変更リスト.append(変更)
                    self.完全コード履歴.append(変更)

                    print(f"🔍 Edit検出: {file_path_elem.text}")

            except ET.ParseError as e:
                print(f"⚠️  XML解析エラー: {e}")

        return 変更リスト

    def _Write呼び出しを検出(self, 出力: str) -> List[Dict]:
        """Write tool呼び出しを検出"""
        変更リスト = []

        # パターン: <invoke name="Write">...</invoke>
        Writeパターン = r'<invoke name="Write">(.*?)</invoke>'
        matches = re.findall(Writeパターン, 出力, re.DOTALL)

        for match in matches:
            try:
                # XMLをパース
                invoke_xml = f'<invoke name="Write">{match}</invoke>'
                root = ET.fromstring(invoke_xml)

                # パラメータを抽出
                file_path_elem = root.find('.//file_path')
                content_elem = root.find('.//content')

                if file_path_elem is not None and content_elem is not None:

                    変更 = {
                        "ツール": "Write",
                        "ファイル": file_path_elem.text,
                        "新コード": content_elem.text,
                        "時刻": time.strftime("%Y-%m-%dT%H:%M:%S")
                    }

                    変更リスト.append(変更)
                    self.完全コード履歴.append(変更)

                    print(f"🔍 Write検出: {file_path_elem.text}")

            except ET.ParseError as e:
                print(f"⚠️  XML解析エラー: {e}")

        return 変更リスト

    def ファイル変更を検出(self, 出力: str) -> List[Dict]:
        """
        Claude出力からファイル変更を検出してgit diffで実際の変更を取得

        Args:
            出力: Claudeの出力テキスト

        Returns:
            検出されたファイル変更のリスト
        """
        変更リスト = []

        # パターン: "production_jcross_engine.pyを更新" など
        ファイルパターン = r'(\w+\.(?:py|js|ts|jsx|tsx|jcross))を(?:更新|作成|編集)'
        matches = re.findall(ファイルパターン, 出力)

        for ファイル名 in set(matches):  # 重複削除
            差分 = self._git_diffを取得(ファイル名)

            if 差分:
                変更 = {
                    "ファイル": ファイル名,
                    "差分": 差分,
                    "時刻": time.strftime("%Y-%m-%dT%H:%M:%S")
                }

                変更リスト.append(変更)
                self.コード変更履歴.append(変更)

                print(f"📝 ファイル変更検出: {ファイル名} ({len(差分)}文字)")

        return 変更リスト

    def _git_diffを取得(self, ファイル名: str) -> Optional[str]:
        """git diffでファイルの変更内容を取得"""
        try:
            # git diffを実行
            結果 = subprocess.run(
                ['git', 'diff', ファイル名],
                cwd=self.作業ディレクトリ,
                capture_output=True,
                text=True,
                timeout=5
            )

            if 結果.returncode == 0:
                return 結果.stdout
            else:
                # まだcommitされていない新規ファイルの場合
                # git diff --cached を試す
                結果2 = subprocess.run(
                    ['git', 'diff', '--cached', ファイル名],
                    cwd=self.作業ディレクトリ,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if 結果2.returncode == 0 and 結果2.stdout:
                    return 結果2.stdout

        except subprocess.TimeoutExpired:
            print(f"⚠️  git diffタイムアウト: {ファイル名}")
        except FileNotFoundError:
            print(f"⚠️  gitコマンドが見つかりません")
        except Exception as e:
            print(f"⚠️  git diff取得エラー: {e}")

        return None

    def 完全なファイル内容を取得(self, ファイルパス: str) -> Optional[str]:
        """
        ファイルの完全な内容を取得

        Args:
            ファイルパス: 取得するファイルのパス

        Returns:
            ファイルの内容（存在しない場合はNone）
        """
        try:
            完全パス = self.作業ディレクトリ / ファイルパス

            if 完全パス.exists():
                with open(完全パス, 'r', encoding='utf-8') as f:
                    内容 = f.read()

                print(f"📄 ファイル読み込み: {ファイルパス} ({len(内容)}文字)")
                return 内容
            else:
                print(f"⚠️  ファイルが存在しません: {ファイルパス}")
                return None

        except Exception as e:
            print(f"⚠️  ファイル読み込みエラー: {e}")
            return None

    def 統計を表示(self):
        """取得したコード変更の統計を表示"""
        print()
        print("=" * 80)
        print("📊 コードキャプチャ統計")
        print("=" * 80)
        print(f"  ツール呼び出し検出: {len(self.完全コード履歴)}件")
        print(f"  ファイル変更検出: {len(self.コード変更履歴)}件")
        print()

        if self.完全コード履歴:
            print("【完全コード履歴】")
            for i, 変更 in enumerate(self.完全コード履歴[-5:], 1):
                print(f"  {i}. {変更['ツール']}: {変更['ファイル']} ({変更['時刻']})")
            print()

        if self.コード変更履歴:
            print("【ファイル変更履歴】")
            for i, 変更 in enumerate(self.コード変更履歴[-5:], 1):
                print(f"  {i}. {変更['ファイル']} ({変更['時刻']})")
            print()


class ファイル変更リアルタイム監視:
    """
    ファイルシステムをリアルタイムで監視してコード変更を記録

    watchdogライブラリが必要（オプション）
    """

    def __init__(self, 監視ディレクトリ: str = "."):
        self.監視ディレクトリ = Path(監視ディレクトリ)
        self.変更履歴 = []

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            self.Observer = Observer
            self.FileSystemEventHandler = FileSystemEventHandler
            self.利用可能 = True

            print("👁️  ファイル監視システム初期化（watchdog使用）")

        except ImportError:
            self.利用可能 = False
            print("⚠️  watchdogライブラリが見つかりません（ファイル監視は無効）")

    def 監視開始(self, Cross構造: Dict):
        """ファイル監視を開始"""
        if not self.利用可能:
            print("⚠️  ファイル監視はwatchdogライブラリが必要です")
            print("   インストール: pip install watchdog")
            return None

        class 変更ハンドラ(self.FileSystemEventHandler):
            def __init__(self, 親):
                self.親 = 親
                self.Cross構造 = Cross構造

            def on_modified(self, event):
                if event.is_directory:
                    return

                # Pythonファイルと.jcrossファイルのみ
                if event.src_path.endswith(('.py', '.jcross')):
                    self.親._ファイル変更を記録(event.src_path, self.Cross構造)

        # 監視開始
        observer = self.Observer()
        handler = 変更ハンドラ(self)
        observer.schedule(handler, path=str(self.監視ディレクトリ), recursive=True)
        observer.start()

        print(f"👁️  ファイル監視開始: {self.監視ディレクトリ}")

        return observer

    def _ファイル変更を記録(self, ファイルパス: str, Cross構造: Dict):
        """ファイル変更を記録"""
        try:
            with open(ファイルパス, 'r', encoding='utf-8') as f:
                新内容 = f.read()

            変更 = {
                "ファイルパス": ファイルパス,
                "新内容": 新内容,
                "行数": len(新内容.splitlines()),
                "時刻": time.strftime("%Y-%m-%dT%H:%M:%S")
            }

            self.変更履歴.append(変更)

            # Cross構造に保存
            Cross構造.setdefault("ファイル監視履歴", []).append(変更)

            print(f"📁 ファイル変更: {ファイルパス} ({変更['行数']}行)")

        except Exception as e:
            print(f"⚠️  ファイル読み込みエラー: {e}")


def デモ():
    """デモ実行"""
    print()
    print("=" * 80)
    print("🔍 コードキャプチャ強化モジュール デモ")
    print("=" * 80)
    print()

    # 初期化
    キャプチャ = コードキャプチャ強化(".")

    # テスト用のClaude出力（ツール呼び出しを含む）
    テスト出力 = """
production_jcross_engine.pyを更新しました。

<invoke name="Edit">
<parameter name="file_path">production_jcross_engine.py</parameter>
<parameter name="old_string">def test():
    pass</parameter>
<parameter name="new_string">def test():
    print("Hello, World!")</parameter>
</invoke>
"""

    # ツール呼び出しを検出
    print("🔍 ツール呼び出しを検出中...")
    ツール変更 = キャプチャ.ツール呼び出しを監視(テスト出力)
    print(f"   検出: {len(ツール変更)}件")
    print()

    # ファイル変更を検出
    print("📝 ファイル変更を検出中...")
    ファイル変更 = キャプチャ.ファイル変更を検出(テスト出力)
    print(f"   検出: {len(ファイル変更)}件")
    print()

    # 統計表示
    キャプチャ.統計を表示()

    print("=" * 80)
    print("✅ デモ完了")
    print("=" * 80)
    print()


if __name__ == "__main__":
    デモ()
