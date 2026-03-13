#!/usr/bin/env python3
"""
Background Learning Configuration
ユーザ設定とファイル活動分析
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz


class BackgroundLearningConfig:
    """
    背景学習の設定管理
    """

    def __init__(self, config_dir: Path = Path(".verantyx")):
        self.config_dir = config_dir
        self.config_file = config_dir / "background_learning_config.json"
        self.activity_file = config_dir / "file_activity_analysis.json"
        self.daemon_status_file = config_dir / "daemon_status.json"

        # 設定ディレクトリ作成
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def setup_user_preferences(self) -> Dict[str, Any]:
        """
        ユーザ設定を対話的に取得

        Returns:
            user_preferences: ユーザ設定辞書
        """
        print("\n" + "━" * 60)
        print("📚 背景学習モード (Background Learning Mode)")
        print("━" * 60)
        print("\nこの機能を有効にすると、Verantyxはあなたが使っていない")
        print("時間帯に自動的に学習を行い、知識を増やします。")
        print("\n実行内容:")
        print("  • 失敗した質問をWikipediaから学習")
        print("  • 操作コマンドの自動改善")
        print("  • 新しいQ&Aパターンの獲得")
        print("\nあなたのファイル更新パターンを分析し、非アクティブな")
        print("時間帯を自動検出して、その時間帯にのみ実行します。")
        print("━" * 60 + "\n")

        # 有効化確認
        enabled_input = input("背景学習モードを有効にしますか？ (y/n): ").strip().lower()
        if enabled_input not in ["y", "yes"]:
            print("❌ 背景学習モードは無効化されました")
            return {"enabled": False}

        # 国とタイムゾーン取得
        country = input("\nお住まいの国を教えてください (例: Japan, USA): ").strip()
        if not country:
            country = "Japan"

        timezone = input("タイムゾーンを教えてください (例: Asia/Tokyo, America/New_York): ").strip()
        if not timezone:
            timezone = "Asia/Tokyo"

        # タイムゾーン検証
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            print(f"⚠️  不明なタイムゾーン: {timezone}")
            print("Asia/Tokyoを使用します")
            timezone = "Asia/Tokyo"

        # 設定を保存
        preferences = {
            "enabled": True,
            "country": country,
            "timezone": timezone,
            "language": "ja",
            "configured_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(preferences, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 設定を保存しました: {self.config_file}")

        return preferences

    def load_preferences(self) -> Optional[Dict[str, Any]]:
        """
        保存された設定を読み込み

        Returns:
            preferences: ユーザ設定 (存在しない場合はNone)
        """
        if not self.config_file.exists():
            return None

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze_file_activity(
        self,
        lookback_days: int = 30,
        scan_directories: List[str] = ["."],
        exclude_patterns: List[str] = ["node_modules", ".git", "__pycache__", ".verantyx", "venv"],
        file_extensions: List[str] = [".py", ".jcross", ".json", ".md", ".txt"]
    ) -> Dict[str, Any]:
        """
        ファイル更新パターンを分析し、非アクティブ時間帯を検出

        Args:
            lookback_days: 分析対象の日数
            scan_directories: スキャン対象ディレクトリ
            exclude_patterns: 除外パターン
            file_extensions: 対象ファイル拡張子

        Returns:
            activity_analysis: 活動パターン分析結果
        """
        print(f"\n📊 ファイル活動を分析中 (過去{lookback_days}日間)...")

        # ファイル走査
        modification_times = []
        cutoff_time = datetime.now() - timedelta(days=lookback_days)

        for scan_dir in scan_directories:
            scan_path = Path(scan_dir)
            if not scan_path.exists():
                continue

            for file_path in scan_path.rglob("*"):
                # 除外パターンチェック
                if any(pattern in str(file_path) for pattern in exclude_patterns):
                    continue

                # ファイル拡張子チェック
                if file_path.suffix not in file_extensions:
                    continue

                # ファイルの更新時刻を取得
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime >= cutoff_time:
                        modification_times.append(mtime)
                except Exception:
                    continue

        print(f"   {len(modification_times)}個のファイル更新を検出")

        # 時間帯別活動度計算
        hourly_activity = {hour: 0 for hour in range(24)}

        for mtime in modification_times:
            hour = mtime.hour
            hourly_activity[hour] += 1

        # 正規化 (0.0 - 1.0)
        max_activity = max(hourly_activity.values()) if hourly_activity.values() else 1
        if max_activity > 0:
            for hour in hourly_activity:
                hourly_activity[hour] = hourly_activity[hour] / max_activity

        # 非アクティブ時間帯検出 (活動度 < 0.1)
        min_activity_threshold = 0.1
        inactive_periods = []

        current_period = None
        for hour in range(24):
            if hourly_activity[hour] < min_activity_threshold:
                if current_period is None:
                    # 新しい非アクティブ期間開始
                    current_period = {
                        "start_hour": hour,
                        "end_hour": hour,
                        "confidence": 1.0 - hourly_activity[hour]
                    }
                else:
                    # 既存の期間を延長
                    current_period["end_hour"] = hour
                    current_period["confidence"] = (
                        current_period["confidence"] + (1.0 - hourly_activity[hour])
                    ) / 2
            else:
                if current_period is not None:
                    # 期間終了
                    inactive_periods.append(current_period)
                    current_period = None

        # 最後の期間を追加
        if current_period is not None:
            inactive_periods.append(current_period)

        # 推奨学習時間帯の決定 (最も長い非アクティブ期間)
        recommended_period = None
        if inactive_periods:
            recommended_period = max(
                inactive_periods,
                key=lambda p: p["end_hour"] - p["start_hour"]
            )

            print(f"\n📊 ファイル活動分析結果:")
            print(f"   非アクティブ時間帯: {recommended_period['start_hour']:02d}:00 - {recommended_period['end_hour']:02d}:00")
            print(f"   信頼度: {recommended_period['confidence'] * 100:.1f}%")
            print(f"\n   この時間帯に背景学習を実行します。")
        else:
            print("\n⚠️  非アクティブ時間帯が検出できませんでした")
            print("   デフォルトで深夜2:00-6:00に実行します")
            recommended_period = {
                "start_hour": 2,
                "end_hour": 6,
                "confidence": 0.5
            }

        analysis_result = {
            "hourly_activity": hourly_activity,
            "inactive_periods": inactive_periods,
            "recommended_period": recommended_period,
            "analyzed_at": datetime.now().isoformat(),
            "lookback_days": lookback_days,
            "total_files": len(modification_times)
        }

        # 保存
        with open(self.activity_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

        print(f"   保存しました: {self.activity_file}")

        return analysis_result

    def load_activity_analysis(self) -> Optional[Dict[str, Any]]:
        """
        保存されたファイル活動分析を読み込み

        Returns:
            activity_analysis: 活動分析結果 (存在しない場合はNone)
        """
        if not self.activity_file.exists():
            return None

        with open(self.activity_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def is_inactive_period(self, current_hour: Optional[int] = None) -> bool:
        """
        現在時刻が非アクティブ時間帯かチェック

        Args:
            current_hour: チェック対象の時刻 (Noneの場合は現在時刻)

        Returns:
            is_inactive: 非アクティブ時間帯ならTrue
        """
        if current_hour is None:
            current_hour = datetime.now().hour

        activity_analysis = self.load_activity_analysis()
        if not activity_analysis:
            return False

        for period in activity_analysis.get("inactive_periods", []):
            if period["start_hour"] <= current_hour <= period["end_hour"]:
                return True

        return False

    def save_daemon_status(self, status: Dict[str, Any]):
        """
        デーモン状態を保存

        Args:
            status: デーモン状態辞書
        """
        with open(self.daemon_status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)

    def load_daemon_status(self) -> Optional[Dict[str, Any]]:
        """
        デーモン状態を読み込み

        Returns:
            daemon_status: デーモン状態 (存在しない場合はNone)
        """
        if not self.daemon_status_file.exists():
            return None

        with open(self.daemon_status_file, 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == "__main__":
    # テスト
    config = BackgroundLearningConfig()

    print("=== 背景学習設定テスト ===\n")

    # 設定セットアップ (実際はインタラクティブ)
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        prefs = config.setup_user_preferences()
        print(f"\n設定結果: {prefs}")

    # ファイル活動分析
    print("\n=== ファイル活動分析 ===")
    analysis = config.analyze_file_activity(lookback_days=7)

    print(f"\n時間帯別活動度:")
    for hour in range(24):
        activity = analysis["hourly_activity"][hour]
        bar = "█" * int(activity * 20)
        print(f"  {hour:02d}:00 |{bar:<20}| {activity:.2f}")

    # 現在時刻チェック
    print(f"\n現在時刻は非アクティブ期間か: {config.is_inactive_period()}")
