#!/usr/bin/env python3
"""
Claude学習ラッパー - PTYでClaude Codeの入出力を読み取り、学習に活用

Claude APIではなく、PTY（疑似端末）でClaude Codeプロセスを起動し、
ユーザー入力とClaude出力を直接読み取って学習します。
"""

import os
import sys
import pty
import select
import threading
import time
import re
from pathlib import Path
from typing import Optional, List

# 学習エンジンをインポート
from offline_learning_processors import オフライン学習エンジン


class Claude学習ラッパー:
    """
    PTYでClaude Codeを起動し、入出力を学習に活用

    動作:
    1. PTYでClaude Codeを起動
    2. ユーザー入力を検出
    3. Claude出力を検出
    4. ペアで学習エンジンに送信
    5. 語彙・パターンを蓄積
    """

    def __init__(self, プロジェクトパス: str = "."):
        self.プロジェクトパス = プロジェクトパス

        # PTY
        self.master_fd = None
        self.claude_pid = None

        # 学習エンジン
        self.学習エンジン = オフライン学習エンジン()

        # 入出力バッファ
        self.ユーザー入力バッファ = []
        self.Claude出力バッファ = []

        # 対話検出
        self.最後のユーザー入力 = ""
        self.Claude出力蓄積中 = False

        self.running = True

    def Claudeを起動(self) -> bool:
        """PTYでClaude Codeを起動"""
        try:
            print("🚀 Claude Codeを起動中...")

            # プロジェクトディレクトリに移動
            os.chdir(self.プロジェクトパス)

            # PTYでClaude Codeを起動
            self.claude_pid, self.master_fd = pty.fork()

            if self.claude_pid == 0:
                # 子プロセス - Claude Codeを実行
                os.environ['TERM'] = 'xterm-256color'
                os.execvp("claude", ["claude"])
                # 成功すれば到達しない
            else:
                # 親プロセス
                print(f"✅ Claude Code起動成功 (PID: {self.claude_pid})")
                return True

        except Exception as e:
            print(f"❌ Claude Code起動失敗: {e}")
            return False

    def 入出力ループを開始(self):
        """入出力を読み取り、学習するループ"""
        print("📚 学習ループ開始")
        print("=" * 60)
        print("ユーザーの入力とClaudeの出力を検出して学習します")
        print("=" * 60)
        print()

        try:
            while self.running:
                # selectで読み取り可能を待機
                r, w, e = select.select([self.master_fd, sys.stdin], [], [], 0.1)

                # Claude出力を読み取り
                if self.master_fd in r:
                    try:
                        出力 = os.read(self.master_fd, 1024).decode('utf-8', errors='ignore')
                        if 出力:
                            # 標準出力に表示
                            sys.stdout.write(出力)
                            sys.stdout.flush()

                            # Claude出力として記録
                            self._Claude出力を処理(出力)
                    except OSError:
                        # PTYが閉じた
                        break

                # ユーザー入力を読み取り
                if sys.stdin in r:
                    入力 = sys.stdin.read(1)
                    if 入力:
                        # Claudeに送信
                        os.write(self.master_fd, 入力.encode('utf-8'))

                        # ユーザー入力として記録
                        self._ユーザー入力を処理(入力)

        except KeyboardInterrupt:
            print("\n⚠️ 中断されました")
        finally:
            self.クリーンアップ()

    def _ユーザー入力を処理(self, 入力: str):
        """ユーザー入力を処理"""
        # 改行までバッファリング
        if 入力 == '\n':
            if self.最後のユーザー入力.strip():
                print(f"\n[学習] ユーザー入力検出: {self.最後のユーザー入力[:50]}...")

                # Claude出力待機開始
                self.Claude出力蓄積中 = True
                self.Claude出力バッファ = []

            self.最後のユーザー入力 = ""
        else:
            self.最後のユーザー入力 += 入力

    def _Claude出力を処理(self, 出力: str):
        """Claude出力を処理"""
        if not self.Claude出力蓄積中:
            return

        # 出力をバッファに追加
        self.Claude出力バッファ.append(出力)

        # 出力が完了したか判定（プロンプトが表示されたら完了）
        # Claude Codeは "> " でプロンプトを表示
        if "> " in 出力 or "?" in 出力:
            # 出力完了 - 学習実行
            Claude出力全体 = ''.join(self.Claude出力バッファ)

            # ANSIエスケープシーケンスを削除
            Claude出力クリーン = self._ANSIを削除(Claude出力全体)

            if Claude出力クリーン.strip():
                print(f"\n[学習] Claude出力検出: {Claude出力クリーン[:50]}...")

                # 学習実行
                self._対話から学習(self.最後のユーザー入力, Claude出力クリーン)

            # リセット
            self.Claude出力蓄積中 = False
            self.Claude出力バッファ = []

    def _ANSIを削除(self, テキスト: str) -> str:
        """ANSIエスケープシーケンスを削除"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', テキスト)

    def _対話から学習(self, ユーザー入力: str, Claude出力: str):
        """対話ペアから学習"""
        if not ユーザー入力.strip() or not Claude出力.strip():
            return

        print("\n" + "=" * 60)
        print("📚 学習実行中...")

        # オフライン学習エンジンで学習
        self.学習エンジン.対話から学習する(ユーザー入力, Claude出力)

        # 統計を取得
        統計 = self.学習エンジン.統計を取得()

        print(f"   📈 獲得語彙: {統計['獲得語彙数']}語")
        print(f"   💬 学習回数: {統計['学習回数']}回")
        print(f"   🧠 理解深度: {統計['理解深度']}")
        print("=" * 60)
        print()

    def クリーンアップ(self):
        """リソースをクリーンアップ"""
        print("\n🧹 クリーンアップ中...")

        self.running = False

        if self.claude_pid:
            try:
                import signal
                os.kill(self.claude_pid, signal.SIGTERM)
                os.waitpid(self.claude_pid, 0)
            except:
                pass

        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass

        # 最終統計を表示
        統計 = self.学習エンジン.統計を取得()
        print("\n" + "=" * 60)
        print("📊 最終学習統計")
        print("=" * 60)
        print(f"✅ 獲得語彙数: {統計['獲得語彙数']}語")
        print(f"✅ 学習回数: {統計['学習回数']}回")
        print(f"✅ 理解深度: {統計['理解深度']}")
        print()
        print("語彙サンプル（最初の20語）:")
        for i, 語彙 in enumerate(統計['語彙一覧'][:20], 1):
            print(f"  {i}. {語彙}")
        print("=" * 60)


def メイン():
    """メインエントリーポイント"""
    print()
    print("=" * 60)
    print("Claude学習ラッパー - PTYベース学習システム")
    print("=" * 60)
    print()

    # プロジェクトパスを取得
    プロジェクトパス = os.getcwd()

    # ラッパーを作成
    ラッパー = Claude学習ラッパー(プロジェクトパス=プロジェクトパス)

    # Claudeを起動
    if not ラッパー.Claudeを起動():
        print("❌ Claude起動失敗")
        sys.exit(1)

    # 入出力ループを開始
    ラッパー.入出力ループを開始()


if __name__ == "__main__":
    メイン()
