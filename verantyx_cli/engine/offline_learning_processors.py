"""
オフライン学習プロセッサ（日本語完全特化）

.jcross言語で書かれたオフライン学習システムを実行
"""

from typing import Dict, List, Any, Optional
import json
import os
from pathlib import Path
from datetime import datetime
import re


class 日本語語彙抽出器:
    """日本語語彙を抽出（形態素解析簡易版）"""

    def __init__(self):
        self.ひらがな範囲 = (0x3040, 0x309F)
        self.カタカナ範囲 = (0x30A0, 0x30FF)
        self.漢字範囲 = (0x4E00, 0x9FFF)

    def 文字種別を判定(self, 文字: str) -> str:
        """文字種別を判定"""
        if not 文字:
            return "その他"

        コード = ord(文字)

        if self.ひらがな範囲[0] <= コード <= self.ひらがな範囲[1]:
            return "ひらがな"
        elif self.カタカナ範囲[0] <= コード <= self.カタカナ範囲[1]:
            return "カタカナ"
        elif self.漢字範囲[0] <= コード <= self.漢字範囲[1]:
            return "漢字"
        elif 文字.isalpha():
            return "アルファベット"
        elif 文字.isdigit():
            return "数字"
        else:
            return "記号"

    def 形態素解析(self, テキスト: str) -> List[str]:
        """簡易形態素解析"""
        単語リスト = []
        現在の単語 = ""
        前の文字種別 = ""

        for 文字 in テキスト:
            文字種別 = self.文字種別を判定(文字)

            # 記号は分割
            if 文字種別 == "記号":
                if 現在の単語:
                    単語リスト.append(現在の単語)
                    現在の単語 = ""
                前の文字種別 = ""
                continue

            # 文字種別が変わったら分割
            if 文字種別 != 前の文字種別 and 前の文字種別 != "":
                if 現在の単語:
                    単語リスト.append(現在の単語)
                    現在の単語 = ""

            現在の単語 += 文字
            前の文字種別 = 文字種別

        if 現在の単語:
            単語リスト.append(現在の単語)

        return 単語リスト


class Cross操作器:
    """Cross構造を操作"""

    @staticmethod
    def 検索(Cross構造: Dict, 検索キー: str) -> Optional[Dict]:
        """Cross構造内を検索"""
        for 軸名, 軸データ in Cross構造.items():
            if not isinstance(軸データ, list):
                continue

            for 点 in 軸データ:
                if not isinstance(点, dict):
                    continue

                for キー, 値 in 点.items():
                    if キー == 検索キー or 値 == 検索キー:
                        return {"軸": 軸名, "点": 点, "データ": 点}

        return None

    @staticmethod
    def 取得(Cross構造: Dict, 軸: str, 点インデックス: int, キー: str) -> Any:
        """Cross値を取得"""
        try:
            return Cross構造[軸][点インデックス].get(キー)
        except (KeyError, IndexError):
            return None

    @staticmethod
    def 設定(Cross構造: Dict, 軸: str, 点インデックス: int, キー: str, 値: Any):
        """Cross値を設定"""
        try:
            if 軸 not in Cross構造:
                Cross構造[軸] = []

            while len(Cross構造[軸]) <= 点インデックス:
                Cross構造[軸].append({})

            Cross構造[軸][点インデックス][キー] = 値
        except Exception as e:
            print(f"⚠️ Cross設定エラー: {e}")

    @staticmethod
    def 増加(Cross構造: Dict, 軸: str, 点インデックス: int, キー: str, 増分: float):
        """Cross値を増加"""
        現在値 = Cross操作器.取得(Cross構造, 軸, 点インデックス, キー) or 0
        新しい値 = 現在値 + 増分
        Cross操作器.設定(Cross構造, 軸, 点インデックス, キー, 新しい値)

    @staticmethod
    def 配列追加(Cross構造: Dict, 軸: str, 点インデックス: int, キー: str, 要素: Any):
        """Cross配列に追加"""
        配列 = Cross操作器.取得(Cross構造, 軸, 点インデックス, キー)
        if 配列 is None:
            配列 = []
            Cross操作器.設定(Cross構造, 軸, 点インデックス, キー, 配列)

        if isinstance(配列, list):
            配列.append(要素)

    @staticmethod
    def カウント(Cross構造: Dict, 軸: str) -> int:
        """軸の点数をカウント"""
        try:
            return len(Cross構造.get(軸, []))
        except:
            return 0


class 意図推測エンジン:
    """ユーザー意図を推測（日本語特化）"""

    def __init__(self):
        self.キーワードマップ = {
            "実装": "コード実装を求めている",
            "作成": "コード実装を求めている",
            "書いて": "コード実装を求めている",
            "説明": "説明を求めている",
            "教えて": "説明を求めている",
            "どうやって": "説明を求めている",
            "修正": "バグ修正を求めている",
            "直して": "バグ修正を求めている",
            "エラー": "バグ修正を求めている",
            "なぜ": "理由説明を求めている",
            "理由": "理由説明を求めている",
            "どうして": "理由説明を求めている",
            "テスト": "テスト実行を求めている",
            "確認": "確認を求めている",
            "見せて": "表示を求めている",
        }

    def 推測(self, 発言: str) -> str:
        """意図を推測"""
        for キーワード, 意図 in self.キーワードマップ.items():
            if キーワード in 発言:
                return 意図

        return "一般的な質問"


class オフライン学習エンジン:
    """
    オフライン学習エンジン（日本語完全特化）

    .jcross言語で定義された学習システムをPythonで実行
    """

    def __init__(self, ユーザーデータディレクトリ: str = "~/.verantyx/user_data"):
        self.ユーザーデータディレクトリ = Path(ユーザーデータディレクトリ).expanduser()
        self.ユーザーデータディレクトリ.mkdir(parents=True, exist_ok=True)

        # Cross構造
        self.日本語語彙Cross = self._初期化_日本語語彙Cross()
        self.対話パターンCross = self._初期化_対話パターンCross()
        self.ユーザー理解Cross = self._初期化_ユーザー理解Cross()
        self.学習データCross = self._初期化_学習データCross()

        # ヘルパー
        self.語彙抽出器 = 日本語語彙抽出器()
        self.Cross操作器 = Cross操作器()
        self.意図推測エンジン = 意図推測エンジン()

        # 統計
        self.学習回数 = 0
        self.獲得語彙数 = 0
        self.理解深度 = 0

    def _初期化_日本語語彙Cross(self) -> Dict:
        """日本語語彙Crossを初期化"""
        return {
            "UP": [
                {"点": 0, "カテゴリ": "プロジェクト用語"},
                {"点": 1, "カテゴリ": "技術用語"},
                {"点": 2, "カテゴリ": "日常用語"}
            ],
            "DOWN": [],  # 動的に追加
            "FRONT": [
                {"点": 0, "意味推測": "文脈から推測中"},
                {"点": 1, "関連語": []}
            ],
            "BACK": [
                {"点": 0, "全語彙": []},
                {"点": 1, "使用例": {}}
            ]
        }

    def _初期化_対話パターンCross(self) -> Dict:
        """対話パターンCrossを初期化"""
        return {
            "UP": [
                {"点": 0, "パターン種別": "質問→回答"},
                {"点": 1, "パターン種別": "指示→実行"},
                {"点": 2, "パターン種別": "説明→理解確認"}
            ],
            "DOWN": [],  # 動的に追加
            "RIGHT": [{"点": 0, "次の展開": "予測待ち"}],
            "BACK": [
                {"点": 0, "学習回数": 0},
                {"点": 1, "成功例": [], "失敗例": []}
            ]
        }

    def _初期化_ユーザー理解Cross(self) -> Dict:
        """ユーザー理解Crossを初期化"""
        return {
            "UP": [
                {"点": 0, "理解レベル": "表層", "内容": []},
                {"点": 1, "理解レベル": "意図", "内容": []},
                {"点": 2, "理解レベル": "背景", "内容": []},
                {"点": 3, "理解レベル": "本質", "内容": []}
            ],
            "DOWN": [
                {"点": 0, "観察": []},
                {"点": 1, "観察": []},
                {"点": 2, "観察": []}
            ],
            "FRONT": [
                {"点": 0, "予測": []},
                {"点": 1, "予測": []},
                {"点": 2, "予測": []}
            ],
            "BACK": [
                {"点": 0, "蓄積": "過去の全対話"},
                {"点": 1, "蓄積": "学習した好み"},
                {"点": 2, "蓄積": "確立された理解"}
            ]
        }

    def _初期化_学習データCross(self) -> Dict:
        """学習データCrossを初期化"""
        return {
            "UP": [
                {"点": 0, "抽象度": "最上位", "意味": "全学習データの統合"}
            ],
            "DOWN": [
                {"点": 0, "具体": "生の対話ログ", "ログ": []}
            ],
            "BACK": [
                {"点": 0, "過去": "全対話履歴", "記憶": []},
                {"点": 1, "過去": "学習済みパターン", "記憶": []},
                {"点": 2, "過去": "ユーザー固有語彙", "記憶": []}
            ]
        }

    def 対話から学習する(self, ユーザー発言: str, Claude応答: str):
        """
        Claude API対話から学習（完全オフライン）
        """
        # 対話をCross構造化
        対話Cross = {
            "UP": [{"点": 0, "抽象": "対話"}],
            "DOWN": [
                {"点": 0, "発言": ユーザー発言},
                {"点": 1, "応答": Claude応答}
            ],
            "BACK": [
                {"点": 0, "時刻": datetime.now().isoformat(), "保存": "永続"}
            ],
            "RIGHT": [
                {"点": 0, "次": "予測待ち"}
            ]
        }

        # 1. 日本語語彙を抽出
        self._日本語語彙を抽出(ユーザー発言)

        # 2. パターンを学習
        self._パターンを学習(対話Cross)

        # 3. ユーザー理解を深化
        self._ユーザー理解を深化(対話Cross)

        # 4. 生データを保存
        self.Cross操作器.配列追加(
            self.学習データCross, "DOWN", 0, "ログ", 対話Cross
        )

        # 統計更新
        self.学習回数 += 1
        self.獲得語彙数 = len(self.日本語語彙Cross["BACK"][0].get("全語彙", []))

    def _日本語語彙を抽出(self, テキスト: str):
        """日本語語彙を抽出"""
        単語リスト = self.語彙抽出器.形態素解析(テキスト)

        全語彙 = self.日本語語彙Cross["BACK"][0].get("全語彙", [])
        if not isinstance(全語彙, list):
            全語彙 = []
            self.Cross操作器.設定(self.日本語語彙Cross, "BACK", 0, "全語彙", 全語彙)

        for 単語 in 単語リスト:
            if not 単語.strip():
                continue

            # 既存語彙か確認
            if 単語 not in 全語彙:
                全語彙.append(単語)

                # 新規語彙のCross構造を作成
                新規語彙データ = {
                    "単語": 単語,
                    "頻度": 1,
                    "初出": テキスト[:50]
                }

                self.Cross操作器.配列追加(
                    self.日本語語彙Cross, "DOWN", 0, "語彙一覧", 新規語彙データ
                )

    def _パターンを学習(self, 対話Cross: Dict):
        """対話パターンを学習"""
        # 対話の種類を判定
        ユーザー発言 = 対話Cross["DOWN"][0]["発言"]
        意図 = self.意図推測エンジン.推測(ユーザー発言)

        # パターンに追加
        self.Cross操作器.配列追加(
            self.対話パターンCross, "DOWN", 0, "パターン例", {
                "意図": 意図,
                "発言": ユーザー発言[:100],
                "時刻": 対話Cross["BACK"][0]["時刻"]
            }
        )

        # 学習回数を増加
        self.Cross操作器.増加(self.対話パターンCross, "BACK", 0, "学習回数", 1)

    def _ユーザー理解を深化(self, 対話Cross: Dict):
        """ユーザー理解を深化"""
        ユーザー発言 = 対話Cross["DOWN"][0]["発言"]
        Claude応答 = 対話Cross["DOWN"][1]["応答"]

        # レベル0: 表層理解（言葉そのもの）
        self.Cross操作器.配列追加(
            self.ユーザー理解Cross, "DOWN", 0, "観察", ユーザー発言
        )

        # レベル1: 意図理解（何を求めているか）
        意図 = self.意図推測エンジン.推測(ユーザー発言)
        self.Cross操作器.配列追加(
            self.ユーザー理解Cross, "UP", 1, "内容", 意図
        )

        # レベル2: 背景理解（プロジェクト文脈）
        # プロジェクト名を抽出
        プロジェクト関連語 = ["verantyx", "jcross", "Cross"]
        for 語 in プロジェクト関連語:
            if 語.lower() in ユーザー発言.lower():
                self.Cross操作器.配列追加(
                    self.ユーザー理解Cross, "UP", 2, "内容", f"プロジェクト: {語}"
                )

        # レベル3: 本質理解（目的・価値観）
        # 本質的な目的を推測
        if "実装" in ユーザー発言 or "完成" in ユーザー発言:
            本質 = "完全実装を重視している"
            self.Cross操作器.配列追加(
                self.ユーザー理解Cross, "UP", 3, "内容", 本質
            )

    def 学習データを保存(self):
        """学習データをローカル保存（外部送信なし）"""
        保存パス = self.ユーザーデータディレクトリ / "learning.json"

        保存データ = {
            "語彙": self.日本語語彙Cross,
            "パターン": self.対話パターンCross,
            "理解": self.ユーザー理解Cross,
            "生データ": self.学習データCross,
            "統計": {
                "学習回数": self.学習回数,
                "獲得語彙数": self.獲得語彙数,
                "理解深度": self.理解深度
            },
            "更新日時": datetime.now().isoformat()
        }

        with open(保存パス, 'w', encoding='utf-8') as f:
            json.dump(保存データ, f, ensure_ascii=False, indent=2)

        print(f"✅ 学習データをローカル保存しました: {保存パス}")
        print(f"   外部送信: なし（完全オフライン）")

    def 学習データを読み込み(self):
        """学習データをローカルから読み込み"""
        保存パス = self.ユーザーデータディレクトリ / "learning.json"

        if not 保存パス.exists():
            print("⚠️ 学習データが見つかりません。新規作成します。")
            return

        with open(保存パス, 'r', encoding='utf-8') as f:
            保存データ = json.load(f)

        self.日本語語彙Cross = 保存データ.get("語彙", self._初期化_日本語語彙Cross())
        self.対話パターンCross = 保存データ.get("パターン", self._初期化_対話パターンCross())
        self.ユーザー理解Cross = 保存データ.get("理解", self._初期化_ユーザー理解Cross())
        self.学習データCross = 保存データ.get("生データ", self._初期化_学習データCross())

        統計 = 保存データ.get("統計", {})
        self.学習回数 = 統計.get("学習回数", 0)
        self.獲得語彙数 = 統計.get("獲得語彙数", 0)
        self.理解深度 = 統計.get("理解深度", 0)

        print(f"✅ 学習データを読み込みました: {保存パス}")
        print(f"   学習回数: {self.学習回数}回")
        print(f"   獲得語彙: {self.獲得語彙数}語")

    def 統計を取得(self) -> Dict:
        """学習統計を取得"""
        return {
            "学習回数": self.学習回数,
            "獲得語彙数": self.獲得語彙数,
            "理解深度": self.理解深度,
            "語彙一覧": self.日本語語彙Cross["BACK"][0].get("全語彙", [])[:50],  # 最初の50語
            "最新の理解": self.ユーザー理解Cross["UP"][3].get("内容", [])[-5:]  # 最新5件
        }


def テスト_オフライン学習():
    """オフライン学習のテスト"""

    print("=" * 80)
    print("オフライン学習システム テスト（日本語完全特化）")
    print("=" * 80)
    print()

    # エンジン作成
    エンジン = オフライン学習エンジン()

    # テスト対話
    テスト対話リスト = [
        ("verantyxの実装を進めてください", "はい、verantyxの実装を進めます。"),
        ("Crossシミュレータを説明して", "Crossシミュレータは物理世界をシミュレートします。"),
        (".jcross言語で書いて", ".jcross言語で実装します。"),
        ("なぜ日本語に特化するのですか", "日本語に特化することで..."),
        ("オフライン学習を完成させて", "オフライン学習システムを完成させます。"),
    ]

    for ユーザー発言, Claude応答 in テスト対話リスト:
        print(f"対話: {ユーザー発言[:40]}...")
        エンジン.対話から学習する(ユーザー発言, Claude応答)

    print()
    print("=" * 80)
    print("学習結果")
    print("=" * 80)
    print()

    統計 = エンジン.統計を取得()
    print(f"学習回数: {統計['学習回数']}回")
    print(f"獲得語彙数: {統計['獲得語彙数']}語")
    print()

    print("語彙一覧（最初の20語）:")
    for i, 語 in enumerate(統計['語彙一覧'][:20], 1):
        print(f"  {i}. {語}")
    print()

    print("最新の理解:")
    for 理解 in 統計['最新の理解']:
        print(f"  - {理解}")
    print()

    # 保存
    エンジン.学習データを保存()

    print()
    print("✅ テスト完了")


if __name__ == "__main__":
    テスト_オフライン学習()
