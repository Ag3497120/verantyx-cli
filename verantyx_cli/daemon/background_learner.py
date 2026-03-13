#!/usr/bin/env python3
"""
Background Learning Daemon
バックグラウンドで自律学習を実行するデーモン
"""

import os
import sys
import time
import json
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# verantyx_cliモジュールをインポート可能にする
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from verantyx_cli.engine.autonomous_learner import AutonomousLearner
from verantyx_cli.engine.background_learning_config import BackgroundLearningConfig


class BackgroundLearningDaemon:
    """
    背景学習デーモン
    非アクティブ時間帯に自律学習を実行
    """

    def __init__(
        self,
        config_file: Path = Path(".verantyx/background_learning_config.json"),
        log_file: Path = Path(".verantyx/background_learning.log")
    ):
        self.config_file = config_file
        self.log_file = log_file
        self.running = True
        self.config = BackgroundLearningConfig()

        # 自律学習エンジン
        learning_queue_file = Path(".verantyx/learning_queue.json")
        knowledge_file = Path(".verantyx/autonomous_knowledge.json")
        self.autonomous_learner = AutonomousLearner(learning_queue_file, knowledge_file)

        # シグナルハンドラ設定
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # ログファイル初期化
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _signal_handler(self, signum, frame):
        """シグナルハンドラ"""
        self.log(f"シグナル受信: {signum}")
        self.running = False

    def log(self, message: str):
        """ログ出力"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"

        # ファイルに出力
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")

        # 標準出力にも出力
        print(log_message)

    def execute_learning_session(self, max_tasks: int = 10) -> Dict[str, Any]:
        """
        学習セッションを実行

        Args:
            max_tasks: 最大タスク数

        Returns:
            session_stats: セッション統計
        """
        self.log("学習セッション開始")

        session_stats = {
            "started_at": datetime.now().isoformat(),
            "tasks_processed": 0,
            "knowledge_acquired": 0,
            "commands_improved": 0,
            "errors": []
        }

        try:
            # 自律学習実行
            stats = self.autonomous_learner.execute_autonomous_learning(max_tasks=max_tasks)

            session_stats["tasks_processed"] = stats["tasks_processed"]
            session_stats["knowledge_acquired"] = stats["knowledge_acquired"]

            self.log(f"処理タスク数: {stats['tasks_processed']}")
            self.log(f"獲得知識数: {stats['knowledge_acquired']}")

            # 学習結果を適用
            if stats["knowledge_acquired"] > 0:
                apply_stats = self.autonomous_learner.apply_learned_knowledge()
                self.log(f"Q&Aパターン追加: {apply_stats['qa_patterns_added']}")

        except Exception as e:
            error_msg = f"学習セッションエラー: {e}"
            self.log(error_msg)
            session_stats["errors"].append(str(e))

        session_stats["completed_at"] = datetime.now().isoformat()

        # セッション履歴を保存
        self._save_session_history(session_stats)

        return session_stats

    def _save_session_history(self, session_stats: Dict[str, Any]):
        """セッション履歴を保存"""
        history_file = Path(".verantyx/background_learning_history.json")

        # 既存履歴を読み込み
        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = []

        # 新しいセッションを追加
        history.append(session_stats)

        # 最新100件のみ保持
        history = history[-100:]

        # 保存
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def run(self, check_interval: int = 3600):
        """
        デーモンメインループ

        Args:
            check_interval: チェック間隔（秒）デフォルト1時間
        """
        self.log("背景学習デーモン起動")
        self.log(f"PID: {os.getpid()}")
        self.log(f"チェック間隔: {check_interval}秒")

        # デーモン状態を保存
        daemon_status = {
            "running": True,
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "current_task": "waiting",
            "total_sessions": 0
        }
        self.config.save_daemon_status(daemon_status)

        while self.running:
            try:
                # 現在時刻が非アクティブ時間帯かチェック
                if self.config.is_inactive_period():
                    self.log("非アクティブ時間帯を検出 - 学習セッション開始")

                    # 学習セッション実行
                    session_stats = self.execute_learning_session(max_tasks=10)

                    # デーモン状態更新
                    daemon_status["total_sessions"] += 1
                    daemon_status["last_active"] = datetime.now().isoformat()
                    daemon_status["current_task"] = "waiting"
                    self.config.save_daemon_status(daemon_status)

                    self.log(f"学習セッション完了 (セッション数: {daemon_status['total_sessions']})")

                else:
                    current_hour = datetime.now().hour
                    self.log(f"アクティブ時間帯 ({current_hour:02d}:00) - 待機中")

                # 次のチェックまで待機
                time.sleep(check_interval)

            except Exception as e:
                self.log(f"エラー発生: {e}")
                time.sleep(60)  # エラー時は1分待機

        # 終了処理
        daemon_status["running"] = False
        daemon_status["stopped_at"] = datetime.now().isoformat()
        self.config.save_daemon_status(daemon_status)

        self.log("背景学習デーモン終了")


def main():
    """メイン関数"""
    # 引数解析
    config_file = Path(".verantyx/background_learning_config.json")
    log_file = Path(".verantyx/background_learning.log")

    # デーモン起動
    daemon = BackgroundLearningDaemon(config_file, log_file)

    # チェック間隔（デフォルト1時間）
    check_interval = 3600

    # 環境変数から変更可能
    if "BACKGROUND_LEARNING_INTERVAL" in os.environ:
        check_interval = int(os.environ["BACKGROUND_LEARNING_INTERVAL"])

    daemon.run(check_interval=check_interval)


if __name__ == "__main__":
    main()
