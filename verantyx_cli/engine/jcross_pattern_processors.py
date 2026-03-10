#!/usr/bin/env python3
"""
JCross パターン推論プロセッサ

cross_pattern_matching.jcrossから呼び出されるプロセッサ関数を実装
"""

from typing import List, Dict, Any
from datetime import datetime
import re


class パターン推論プロセッサ:
    """パターン推論用のプロセッサ"""

    def __init__(self):
        self.パターンデータベース = []

    def パターンを抽出(self, テキスト: str) -> Dict:
        """
        テキストからパターンを抽出

        Args:
            テキスト: ユーザー発言またはClaude応答

        Returns:
            抽出されたパターン
        """
        パターン = {
            "元テキスト": テキスト,
            "キーワード": self._キーワード抽出(テキスト),
            "トピック": self._トピック推定(テキスト),
            "意図": self._意図推定(テキスト),
            "時刻": datetime.now().isoformat()
        }

        return パターン

    def _キーワード抽出(self, テキスト: str) -> List[str]:
        """キーワード抽出（簡易版）"""
        # 日本語の助詞などを除く
        除外語 = ["を", "が", "に", "は", "の", "で", "と", "や", "から", "まで"]

        # 単語分割（簡易）
        単語リスト = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\w]+', テキスト)

        # 除外語を除く
        キーワード = [語 for 語 in 単語リスト if 語 not in 除外語 and len(語) > 1]

        return キーワード[:10]  # 上位10個

    def _トピック推定(self, テキスト: str) -> str:
        """トピック推定（簡易版）"""
        # キーワードベースの簡易トピック分類
        if "データ" in テキスト or "分析" in テキスト:
            return "データ分析"
        elif "エラー" in テキスト or "修正" in テキスト or "バグ" in テキスト:
            return "デバッグ"
        elif "最適化" in テキスト or "性能" in テキスト or "パフォーマンス" in テキスト:
            return "最適化"
        elif "設計" in テキスト or "アーキテクチャ" in テキスト:
            return "設計"
        elif "実装" in テキスト or "コード" in テキスト:
            return "実装"
        else:
            return "一般"

    def _意図推定(self, テキスト: str) -> str:
        """意図推定（簡易版）"""
        if "?" in テキスト or "教えて" in テキスト or "どう" in テキスト:
            return "質問"
        elif "作成" in テキスト or "実装" in テキスト or "追加" in テキスト:
            return "作成依頼"
        elif "修正" in テキスト or "直して" in テキスト or "fix" in テキスト.lower():
            return "修正依頼"
        elif "説明" in テキスト or "詳しく" in テキスト:
            return "説明依頼"
        else:
            return "情報提供"

    def 類似パターンを探索(self, パターン: Dict) -> List[Dict]:
        """
        類似パターンを探索

        Args:
            パターン: 現在のパターン

        Returns:
            類似パターンのリスト
        """
        類似パターン = []

        # パターンデータベースから類似性の高いものを検索
        for 既存パターン in self.パターンデータベース:
            類似度 = self._類似度計算(パターン, 既存パターン)
            if 類似度 > 0.3:  # 閾値
                類似パターン.append({
                    "パターン": 既存パターン,
                    "類似度": 類似度
                })

        # 類似度でソート
        類似パターン.sort(key=lambda x: x["類似度"], reverse=True)

        return 類似パターン[:5]  # 上位5件

    def _類似度計算(self, パターン1: Dict, パターン2: Dict) -> float:
        """2つのパターンの類似度を計算"""
        # キーワードの重複度
        キーワード1 = set(パターン1.get("キーワード", []))
        キーワード2 = set(パターン2.get("キーワード", []))

        if not キーワード1 or not キーワード2:
            return 0.0

        重複 = len(キーワード1 & キーワード2)
        合計 = len(キーワード1 | キーワード2)

        類似度 = 重複 / 合計 if 合計 > 0 else 0.0

        # トピックが同じなら加点
        if パターン1.get("トピック") == パターン2.get("トピック"):
            類似度 += 0.2

        return min(類似度, 1.0)

    def 関連パターンを6軸で収集(self, パターン: Dict) -> Dict:
        """
        6軸でパターンを収集

        Args:
            パターン: 現在のパターン

        Returns:
            6軸Cross構造
        """
        関連Cross = {
            "UP": [],    # 抽象的なパターン
            "DOWN": [],  # 具体的なパターン
            "LEFT": [],  # 入力側のパターン
            "RIGHT": [], # 出力側のパターン
            "FRONT": [], # 未来・予測
            "BACK": []   # 過去・履歴
        }

        トピック = パターン.get("トピック", "")
        意図 = パターン.get("意図", "")

        # UP軸: 抽象パターン
        関連Cross["UP"].append({
            "抽象レベル": "トピック",
            "値": トピック
        })
        関連Cross["UP"].append({
            "抽象レベル": "意図",
            "値": 意図
        })

        # DOWN軸: 具体パターン
        関連Cross["DOWN"].append({
            "具体例": パターン.get("元テキスト", ""),
            "キーワード": パターン.get("キーワード", [])
        })

        # LEFT軸: 入力パターン（質問など）
        if 意図 == "質問":
            関連Cross["LEFT"].append(パターン)

        # RIGHT軸: 出力パターン（応答など）
        if 意図 in ["情報提供", "説明依頼"]:
            関連Cross["RIGHT"].append(パターン)

        # BACK軸: 履歴
        関連Cross["BACK"].append({
            "時刻": パターン.get("時刻", ""),
            "パターン": パターン
        })

        return 関連Cross

    def パズルピースを組み合わせ(self, 関連Cross: Dict) -> List[Dict]:
        """
        パズルピースを組み合わせて推論候補を生成

        Args:
            関連Cross: 6軸で収集されたパターン

        Returns:
            推論結果候補のリスト
        """
        推論候補 = []

        # UP軸（抽象）とDOWN軸（具体）を組み合わせ
        UP軸 = 関連Cross.get("UP", [])
        DOWN軸 = 関連Cross.get("DOWN", [])

        for UP項目 in UP軸:
            for DOWN項目 in DOWN軸:
                推論候補.append({
                    "抽象": UP項目,
                    "具体": DOWN項目,
                    "信頼度": 0.8,
                    "推論タイプ": "抽象-具体マッチング"
                })

        # LEFT軸（入力）とRIGHT軸（出力）を組み合わせ
        LEFT軸 = 関連Cross.get("LEFT", [])
        RIGHT軸 = 関連Cross.get("RIGHT", [])

        for LEFT項目 in LEFT軸:
            for RIGHT項目 in RIGHT軸:
                推論候補.append({
                    "入力": LEFT項目,
                    "出力": RIGHT項目,
                    "信頼度": 0.7,
                    "推論タイプ": "入力-出力マッチング"
                })

        return 推論候補[:10]  # 上位10候補

    def 最適推論を選択(self, 推論候補: List[Dict]) -> Dict:
        """
        最も信頼度の高い推論を選択

        Args:
            推論候補: 推論候補のリスト

        Returns:
            最適推論
        """
        if not 推論候補:
            return {"推論": "なし", "信頼度": 0.0}

        # 信頼度でソート
        推論候補.sort(key=lambda x: x.get("信頼度", 0.0), reverse=True)

        return 推論候補[0]

    def パターンを登録(self, パターンリスト: List, パターン: Dict):
        """パターンをデータベースに登録"""
        パターンリスト.append(パターン)
        self.パターンデータベース.append(パターン)

    # デバッグ用表示関数
    def パターンを表示(self, パターン: Dict):
        """パターンを表示"""
        print(f"【パターン】")
        print(f"  トピック: {パターン.get('トピック', '')}")
        print(f"  意図: {パターン.get('意図', '')}")
        print(f"  キーワード: {', '.join(パターン.get('キーワード', []))}")

    def 類似パターンを表示(self, 類似パターンリスト: List):
        """類似パターンを表示"""
        print(f"【類似パターン】({len(類似パターンリスト)}件)")
        for 項目 in 類似パターンリスト[:3]:
            print(f"  - 類似度: {項目['類似度']:.2f}")

    def Cross構造を表示(self, Cross: Dict):
        """Cross構造を表示"""
        print(f"【Cross構造】")
        for 軸名 in ["UP", "DOWN", "LEFT", "RIGHT", "FRONT", "BACK"]:
            軸データ = Cross.get(軸名, [])
            print(f"  {軸名}: {len(軸データ)}件")

    def 推論結果を表示(self, 推論候補: List):
        """推論結果を表示"""
        print(f"【推論候補】({len(推論候補)}件)")
        for i, 候補 in enumerate(推論候補[:3], 1):
            print(f"  {i}. 信頼度: {候補.get('信頼度', 0.0):.2f}")

    def 最適推論を表示(self, 推論: Dict):
        """最適推論を表示"""
        print(f"【最適推論】")
        print(f"  信頼度: {推論.get('信頼度', 0.0):.2f}")
        print(f"  タイプ: {推論.get('推論タイプ', '')}")
