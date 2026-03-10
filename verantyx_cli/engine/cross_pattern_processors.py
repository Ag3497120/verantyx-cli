#!/usr/bin/env python3
"""
Cross構造6軸パターンマッチング推論プロセッサ

.jcross言語のパターンマッチング推論エンジンを実行するための
Pythonプロセッサ実装
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
from collections import defaultdict


class パターン抽出器:
    """
    テキストからパターンを抽出

    パターン要素:
    - キーワード（名詞、動詞）
    - 文構造（質問、命令、説明）
    - トピック（技術、手法、概念）
    """

    def __init__(self):
        # 質問パターン
        self.質問パターン = [
            r'どうやって', r'どのように', r'なぜ', r'何',
            r'いつ', r'どこ', r'誰', r'どれ',
            r'方法', r'やり方', r'手順'
        ]

        # 命令パターン
        self.命令パターン = [
            r'書いて', r'作って', r'実行', r'説明',
            r'教えて', r'見せて', r'変更', r'修正'
        ]

    def 抽出(self, テキスト: str) -> Dict[str, Any]:
        """パターンを抽出"""
        パターン = {
            "元テキスト": テキスト,
            "種別": self._種別を判定(テキスト),
            "キーワード": self._キーワードを抽出(テキスト),
            "トピック": self._トピックを抽出(テキスト),
            "構造": self._文構造を分析(テキスト)
        }
        return パターン

    def _種別を判定(self, テキスト: str) -> str:
        """テキストの種別を判定"""
        for パターン in self.質問パターン:
            if re.search(パターン, テキスト):
                return "質問"

        for パターン in self.命令パターン:
            if re.search(パターン, テキスト):
                return "命令"

        if "。" in テキスト and len(テキスト) > 20:
            return "説明"

        return "その他"

    def _キーワードを抽出(self, テキスト: str) -> List[str]:
        """キーワードを抽出"""
        # 簡易的な形態素解析（文字種別ベース）
        キーワード = []

        # カタカナ語を抽出
        カタカナ = re.findall(r'[ァ-ヴー]+', テキスト)
        キーワード.extend(カタカナ)

        # 英単語を抽出
        英単語 = re.findall(r'[A-Za-z]+', テキスト)
        キーワード.extend(英単語)

        # 漢字+ひらがなの組み合わせ
        漢字語 = re.findall(r'[一-龯ぁ-ん]{2,}', テキスト)
        キーワード.extend(漢字語)

        return list(set(キーワード))

    def _トピックを抽出(self, テキスト: str) -> str:
        """トピックを抽出"""
        # 技術関連キーワード
        技術キーワード = ['Python', 'Java', 'C', 'プログラミング', 'コード', 'API']
        for キー in 技術キーワード:
            if キー in テキスト:
                return "プログラミング"

        # データ関連
        データキーワード = ['データ', 'ファイル', '読み込み', '保存', 'JSON']
        for キー in データキーワード:
            if キー in テキスト:
                return "データ処理"

        # AI関連
        AIキーワード = ['機械学習', 'AI', '学習', 'モデル', 'ニューラル']
        for キー in AIキーワード:
            if キー in テキスト:
                return "機械学習"

        return "一般"

    def _文構造を分析(self, テキスト: str) -> Dict[str, Any]:
        """文構造を分析"""
        return {
            "長さ": len(テキスト),
            "文数": テキスト.count('。') + テキスト.count('?'),
            "質問形": '?' in テキスト or any(p in テキスト for p in ['どう', '何', 'なぜ'])
        }


class 類似度計算器:
    """
    パターン間の類似度を計算
    """

    def 計算(self, パターン1: Dict, パターン2: Dict) -> float:
        """類似度を計算（0.0〜1.0）"""
        スコア = 0.0

        # キーワードの重複度
        キーワード1 = set(パターン1.get("キーワード", []))
        キーワード2 = set(パターン2.get("キーワード", []))

        if キーワード1 and キーワード2:
            重複 = len(キーワード1 & キーワード2)
            合計 = len(キーワード1 | キーワード2)
            スコア += (重複 / 合計) * 0.4

        # 種別の一致
        if パターン1.get("種別") == パターン2.get("種別"):
            スコア += 0.3

        # トピックの一致
        if パターン1.get("トピック") == パターン2.get("トピック"):
            スコア += 0.3

        return スコア


class Cross軸探索器:
    """
    Cross構造の各軸から関連パターンを探索
    """

    def __init__(self):
        self.類似度計算器 = 類似度計算器()

    def UP軸から収集(self, パターンCross: Dict, 現在パターン: Dict, 閾値: float = 0.3) -> List[Dict]:
        """UP軸（抽象）から関連パターンを収集"""
        UP軸 = パターンCross.get("UP", [])
        関連 = []

        for 点 in UP軸:
            パターン群 = 点.get("パターン", [])
            for パターン in パターン群:
                類似度 = self.類似度計算器.計算(現在パターン, パターン)
                if 類似度 >= 閾値:
                    関連.append({
                        "パターン": パターン,
                        "類似度": 類似度,
                        "軸": "UP",
                        "抽象度": 点.get("抽象度")
                    })

        return sorted(関連, key=lambda x: x["類似度"], reverse=True)

    def DOWN軸から収集(self, パターンCross: Dict, 現在パターン: Dict, 閾値: float = 0.3) -> List[Dict]:
        """DOWN軸（具体）から関連パターンを収集"""
        DOWN軸 = パターンCross.get("DOWN", [])
        関連 = []

        for 点 in DOWN軸:
            対話リスト = 点.get("対話", [])
            for 対話 in 対話リスト:
                # ユーザー発言とClaude応答の両方をチェック
                ユーザー = 対話.get("ユーザー", "")
                Claude = 対話.get("Claude", "")

                抽出器 = パターン抽出器()
                ユーザーパターン = 抽出器.抽出(ユーザー)

                類似度 = self.類似度計算器.計算(現在パターン, ユーザーパターン)
                if 類似度 >= 閾値:
                    関連.append({
                        "対話": 対話,
                        "類似度": 類似度,
                        "軸": "DOWN"
                    })

        return sorted(関連, key=lambda x: x["類似度"], reverse=True)

    def LEFT軸から収集(self, パターンCross: Dict, 現在パターン: Dict, 閾値: float = 0.3) -> List[Dict]:
        """LEFT軸（原因）から関連パターンを収集"""
        LEFT軸 = パターンCross.get("LEFT", [])
        関連 = []

        for 点 in LEFT軸:
            ユーザーパターン群 = 点.get("ユーザーパターン", [])
            for パターン in ユーザーパターン群:
                類似度 = self.類似度計算器.計算(現在パターン, パターン)
                if 類似度 >= 閾値:
                    関連.append({
                        "パターン": パターン,
                        "類似度": 類似度,
                        "軸": "LEFT"
                    })

        return sorted(関連, key=lambda x: x["類似度"], reverse=True)

    def RIGHT軸から収集(self, パターンCross: Dict, 現在パターン: Dict, 閾値: float = 0.3) -> List[Dict]:
        """RIGHT軸（結果）から関連パターンを収集"""
        RIGHT軸 = パターンCross.get("RIGHT", [])
        関連 = []

        for 点 in RIGHT軸:
            Claudeパターン群 = 点.get("Claudeパターン", [])
            for パターン in Claudeパターン群:
                類似度 = self.類似度計算器.計算(現在パターン, パターン)
                if 類似度 >= 閾値:
                    関連.append({
                        "パターン": パターン,
                        "類似度": 類似度,
                        "軸": "RIGHT"
                    })

        return sorted(関連, key=lambda x: x["類似度"], reverse=True)

    def BACK軸から収集(self, パターンCross: Dict, 現在パターン: Dict, 閾値: float = 0.3) -> List[Dict]:
        """BACK軸（過去）から関連パターンを収集"""
        BACK軸 = パターンCross.get("BACK", [])
        関連 = []

        for 点 in BACK軸:
            履歴 = 点.get("履歴", [])
            for 対話 in 履歴[-10:]:  # 最新10件
                ユーザー = 対話.get("ユーザー", "")
                抽出器 = パターン抽出器()
                パターン = 抽出器.抽出(ユーザー)

                類似度 = self.類似度計算器.計算(現在パターン, パターン)
                if 類似度 >= 閾値:
                    関連.append({
                        "対話": 対話,
                        "類似度": 類似度,
                        "軸": "BACK"
                    })

        return sorted(関連, key=lambda x: x["類似度"], reverse=True)

    def FRONT軸から収集(self, パターンCross: Dict, 現在パターン: Dict, 閾値: float = 0.3) -> List[Dict]:
        """FRONT軸（未来/予測）から関連パターンを収集"""
        FRONT軸 = パターンCross.get("FRONT", [])
        関連 = []

        for 点 in FRONT軸:
            予測パターン群 = 点.get("予測パターン", [])
            for パターン in 予測パターン群:
                類似度 = self.類似度計算器.計算(現在パターン, パターン)
                if 類似度 >= 閾値:
                    関連.append({
                        "パターン": パターン,
                        "類似度": 類似度,
                        "軸": "FRONT"
                    })

        return sorted(関連, key=lambda x: x["類似度"], reverse=True)


class パズル推論器:
    """
    パズル的にパターンを組み合わせて推論
    """

    def 抽象具体の整合性を確認(self, UP関連: List[Dict], DOWN関連: List[Dict]) -> float:
        """抽象と具体の整合性を確認"""
        if not UP関連 or not DOWN関連:
            return 0.0

        # UP軸の抽象パターンがDOWN軸の具体例で裏付けられているか
        整合数 = 0
        for UP in UP関連[:3]:  # 上位3件
            for DOWN in DOWN関連[:3]:
                # キーワードの重複をチェック
                UPキーワード = set(UP.get("パターン", {}).get("キーワード", []))
                DOWN対話 = DOWN.get("対話", {})
                DOWNテキスト = DOWN対話.get("ユーザー", "") + DOWN対話.get("Claude", "")

                重複 = sum(1 for k in UPキーワード if k in DOWNテキスト)
                if 重複 > 0:
                    整合数 += 1

        return min(整合数 / 9.0, 1.0)  # 最大9ペア

    def 因果関係の強度を測定(self, LEFT関連: List[Dict], RIGHT関連: List[Dict]) -> float:
        """因果関係の強度を測定"""
        if not LEFT関連 or not RIGHT関連:
            return 0.0

        # LEFT（原因）とRIGHT（結果）の共起度を測定
        強度スコア = 0.0

        for LEFT in LEFT関連[:3]:
            for RIGHT in RIGHT関連[:3]:
                LEFTキーワード = set(LEFT.get("パターン", {}).get("キーワード", []))
                RIGHTキーワード = set(RIGHT.get("パターン", {}).get("キーワード", []))

                # キーワードの関連性
                if LEFTキーワード & RIGHTキーワード:
                    強度スコア += 0.2

        return min(強度スコア, 1.0)

    def 時系列連続性を測定(self, BACK関連: List[Dict], FRONT関連: List[Dict]) -> float:
        """時系列の連続性を測定"""
        if not BACK関連:
            return 0.0

        # BACK軸の過去パターンから未来を予測できるか
        return len(BACK関連) / 10.0  # 過去データが多いほど予測精度が上がる

    def 抽象具体推論文を生成(self, UP関連: List[Dict], DOWN関連: List[Dict]) -> str:
        """抽象-具体推論文を生成"""
        if not UP関連 or not DOWN関連:
            return "推論データ不足"

        UP = UP関連[0]
        DOWN = DOWN関連[0]

        推論文 = f"抽象パターン「{UP.get('パターン', {}).get('トピック', '不明')}」は、"
        推論文 += f"具体例「{DOWN.get('対話', {}).get('ユーザー', '')[:30]}...」で裏付けられる。"

        return 推論文

    def 因果推論文を生成(self, LEFT関連: List[Dict], RIGHT関連: List[Dict]) -> str:
        """因果推論文を生成"""
        if not LEFT関連 or not RIGHT関連:
            return "推論データ不足"

        LEFT = LEFT関連[0]
        RIGHT = RIGHT関連[0]

        推論文 = f"原因「{LEFT.get('パターン', {}).get('元テキスト', '')[:30]}...」により、"
        推論文 += f"結果「{RIGHT.get('パターン', {}).get('元テキスト', '')[:30]}...」が生じる。"

        return 推論文

    def 時系列推論文を生成(self, BACK関連: List[Dict], FRONT関連: List[Dict]) -> str:
        """時系列推論文を生成"""
        if not BACK関連:
            return "推論データ不足"

        BACK = BACK関連[0]

        推論文 = f"過去の対話「{BACK.get('対話', {}).get('ユーザー', '')[:30]}...」から、"
        推論文 += "類似パターンを予測できる。"

        return 推論文


def 時刻を取得() -> str:
    """現在時刻を取得"""
    return datetime.now().isoformat()


def パターンを表示(パターン: Dict):
    """パターンを表示"""
    print(f"  種別: {パターン.get('種別')}")
    print(f"  トピック: {パターン.get('トピック')}")
    print(f"  キーワード: {', '.join(パターン.get('キーワード', [])[:5])}")


def 類似パターンを表示(類似リスト: List[Dict]):
    """類似パターンを表示"""
    for i, 項目 in enumerate(類似リスト[:3], 1):
        print(f"  {i}. 類似度: {項目.get('類似度', 0):.2f}")
        if "パターン" in 項目:
            print(f"     {項目['パターン'].get('元テキスト', '')[:40]}...")


def Cross構造を表示(関連Cross: Dict):
    """Cross構造を表示"""
    for 軸名, 関連リスト in 関連Cross.items():
        print(f"  {軸名}軸: {len(関連リスト)}件")


def 推論結果を表示(候補リスト: List[Dict]):
    """推論結果を表示"""
    for i, 候補 in enumerate(候補リスト, 1):
        print(f"  候補{i}: {候補.get('種別')}")
        print(f"    確信度: {候補.get('確信度', 0):.2f}")
        print(f"    推論: {候補.get('推論内容', '')[:60]}...")


def 最適推論を表示(推論: Dict):
    """最適推論を表示"""
    print(f"  種別: {推論.get('種別')}")
    print(f"  確信度: {推論.get('確信度', 0):.2f}")
    print(f"  推論内容: {推論.get('推論内容')}")


def 学習データを読み込み(データパス: str = "~/.verantyx/user_data/learning_data.json") -> List[Dict]:
    """学習データを読み込み"""
    パス = Path(os.path.expanduser(データパス))

    if not パス.exists():
        print(f"⚠️ 学習データが見つかりません: {パス}")
        return []

    with open(パス, 'r', encoding='utf-8') as f:
        データ = json.load(f)

    print(f"✅ {len(データ)}件の学習データを読み込み")
    return データ


def 推論結果を保存(推論: Dict, 保存パス: str = "~/.verantyx/user_data/inference_results.json"):
    """推論結果を保存"""
    パス = Path(os.path.expanduser(保存パス))
    パス.parent.mkdir(parents=True, exist_ok=True)

    # 既存データを読み込み
    if パス.exists():
        with open(パス, 'r', encoding='utf-8') as f:
            結果リスト = json.load(f)
    else:
        結果リスト = []

    # 新しい推論結果を追加
    推論["時刻"] = datetime.now().isoformat()
    結果リスト.append(推論)

    # 保存
    with open(パス, 'w', encoding='utf-8') as f:
        json.dump(結果リスト, f, ensure_ascii=False, indent=2)

    print(f"✅ 推論結果を保存: {パス}")


# グローバル変数として提供
_パターン抽出器 = パターン抽出器()
_類似度計算器 = 類似度計算器()
_Cross軸探索器 = Cross軸探索器()
_パズル推論器 = パズル推論器()


# プロセッサ関数をエクスポート
def パターンを抽出(テキスト: str) -> Dict:
    return _パターン抽出器.抽出(テキスト)


def 類似パターンを探索(現在パターン: Dict) -> List[Dict]:
    """グローバルパターンCrossから類似パターンを探索"""
    # TODO: グローバルパターンCrossへのアクセス実装
    return []


def UP軸から収集(パターンCross: Dict, 現在パターン: Dict) -> List[Dict]:
    return _Cross軸探索器.UP軸から収集(パターンCross, 現在パターン)


def DOWN軸から収集(パターンCross: Dict, 現在パターン: Dict) -> List[Dict]:
    return _Cross軸探索器.DOWN軸から収集(パターンCross, 現在パターン)


def LEFT軸から収集(パターンCross: Dict, 現在パターン: Dict) -> List[Dict]:
    return _Cross軸探索器.LEFT軸から収集(パターンCross, 現在パターン)


def RIGHT軸から収集(パターンCross: Dict, 現在パターン: Dict) -> List[Dict]:
    return _Cross軸探索器.RIGHT軸から収集(パターンCross, 現在パターン)


def BACK軸から収集(パターンCross: Dict, 現在パターン: Dict) -> List[Dict]:
    return _Cross軸探索器.BACK軸から収集(パターンCross, 現在パターン)


def FRONT軸から収集(パターンCross: Dict, 現在パターン: Dict) -> List[Dict]:
    return _Cross軸探索器.FRONT軸から収集(パターンCross, 現在パターン)


def 抽象具体の整合性を確認(UP関連: List[Dict], DOWN関連: List[Dict]) -> float:
    return _パズル推論器.抽象具体の整合性を確認(UP関連, DOWN関連)


def 因果関係の強度を測定(LEFT関連: List[Dict], RIGHT関連: List[Dict]) -> float:
    return _パズル推論器.因果関係の強度を測定(LEFT関連, RIGHT関連)


def 時系列連続性を測定(BACK関連: List[Dict], FRONT関連: List[Dict]) -> float:
    return _パズル推論器.時系列連続性を測定(BACK関連, FRONT関連)


def 抽象具体推論文を生成(UP関連: List[Dict], DOWN関連: List[Dict]) -> str:
    return _パズル推論器.抽象具体推論文を生成(UP関連, DOWN関連)


def 因果推論文を生成(LEFT関連: List[Dict], RIGHT関連: List[Dict]) -> str:
    return _パズル推論器.因果推論文を生成(LEFT関連, RIGHT関連)


def 時系列推論文を生成(BACK関連: List[Dict], FRONT関連: List[Dict]) -> str:
    return _パズル推論器.時系列推論文を生成(BACK関連, FRONT関連)


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("Cross構造6軸パターンマッチング推論プロセッサ テスト")
    print("=" * 60)
    print()

    # パターン抽出テスト
    テスト文 = "Pythonでファイルを読み込む方法は？"
    パターン = パターンを抽出(テスト文)

    print(f"テスト文: {テスト文}")
    print(f"種別: {パターン['種別']}")
    print(f"トピック: {パターン['トピック']}")
    print(f"キーワード: {パターン['キーワード']}")
    print()

    print("=" * 60)
    print("✅ テスト完了")
    print("=" * 60)
