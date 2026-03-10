"""
本番JCrossエンジン

.jcrossファイルを直接読み込んで実行する完全実装
オフライン学習・自己進化の基盤
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import re
import json
import time
from datetime import datetime

# kofdai_computerをインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kofdai_computer"))

from cross_ir import Op, Instr, ProgramIR
from cross_ir_vm import CrossIRVM
from kernel import KofdaiKernel


class 本番JCrossエンジン:
    """
    本番レベルのJCrossエンジン

    .jcrossファイルを読み込み、ラベルを実行
    オフライン学習と自己進化をサポート
    """

    def __init__(self, 作業ディレクトリ: str = "~/.verantyx/user_data"):
        self.作業ディレクトリ = Path(作業ディレクトリ).expanduser()
        self.作業ディレクトリ.mkdir(parents=True, exist_ok=True)

        # JCrossプログラムのキャッシュ
        self.ラベル辞書: Dict[str, List[str]] = {}
        self.変数: Dict[str, Any] = {}
        self.グローバルCross構造: Dict[str, Dict] = {}

        # 実行コンテキスト
        self.スタック: List[Any] = []
        self.実行中 = False

        # プロセッサ（外部Python関数）
        self.プロセッサ辞書: Dict[str, Callable] = {}

        # コマンド辞書（日本語操作コマンド）
        self.コマンド辞書: Dict[str, Dict] = {}

        # 初期化
        self._基本プロセッサを登録()
        self._コマンド辞書を読み込み()

    def _基本プロセッサを登録(self):
        """基本的なプロセッサを登録"""

        # 出力
        self.プロセッサ辞書["出力する"] = lambda *args: print(*args)

        # ファイル操作
        self.プロセッサ辞書["ファイル.読み込み"] = self._ファイル読み込み
        self.プロセッサ辞書["ファイル.書き込み"] = self._ファイル書き込み

        # Cross操作
        self.プロセッサ辞書["cross.取得"] = self._Cross取得
        self.プロセッサ辞書["cross.設定"] = self._Cross設定
        self.プロセッサ辞書["cross.配列追加"] = self._Cross配列追加
        self.プロセッサ辞書["cross.検索"] = self._Cross検索
        self.プロセッサ辞書["cross.カウント"] = self._Crossカウント

        # 時刻
        self.プロセッサ辞書["現在時刻"] = lambda: datetime.now().isoformat()

        # 配列操作
        self.プロセッサ辞書["配列.push"] = lambda arr, item: arr.append(item)
        self.プロセッサ辞書["配列.ソート"] = self._配列ソート
        self.プロセッサ辞書["配列.長さ"] = lambda arr: len(arr) if arr else 0
        self.プロセッサ辞書["配列.取得"] = lambda arr, idx: arr[idx] if arr and 0 <= idx < len(arr) else None

        # 待機
        self.プロセッサ辞書["待機"] = lambda ms: time.sleep(ms / 1000.0)

        # 学習プロセッサ
        self._学習プロセッサを登録()

    def _ファイル読み込み(self, パス: str) -> str:
        """ファイルを読み込み"""
        パス = Path(パス).expanduser()
        with open(パス, 'r', encoding='utf-8') as f:
            return f.read()

    def _ファイル書き込み(self, パス: str, 内容: str, 形式: str = "text"):
        """ファイルに書き込み"""
        パス = Path(パス).expanduser()
        パス.parent.mkdir(parents=True, exist_ok=True)

        if 形式 == "JSON":
            with open(パス, 'w', encoding='utf-8') as f:
                if isinstance(内容, str):
                    f.write(内容)
                else:
                    json.dump(内容, f, ensure_ascii=False, indent=2)
        else:
            with open(パス, 'w', encoding='utf-8') as f:
                f.write(str(内容))

    def _Cross取得(self, Cross構造: Dict, 軸: str, 点: int, キー: str) -> Any:
        """Cross構造から値を取得"""
        try:
            return Cross構造[軸][点].get(キー)
        except (KeyError, IndexError):
            return None

    def _Cross設定(self, Cross構造: Dict, 軸: str, 点: int, キー: str, 値: Any):
        """Cross構造に値を設定"""
        if 軸 not in Cross構造:
            Cross構造[軸] = []

        while len(Cross構造[軸]) <= 点:
            Cross構造[軸].append({})

        Cross構造[軸][点][キー] = 値

    def _Cross配列追加(self, Cross構造: Dict, 軸: str, 点: int, キー: str, 要素: Any):
        """Cross配列に要素を追加"""
        現在値 = self._Cross取得(Cross構造, 軸, 点, キー)
        if 現在値 is None:
            現在値 = []
            self._Cross設定(Cross構造, 軸, 点, キー, 現在値)

        if isinstance(現在値, list):
            現在値.append(要素)

    def _Cross検索(self, Cross構造: Dict, 検索キー: str) -> Optional[Dict]:
        """Cross構造を検索"""
        for 軸名, 軸データ in Cross構造.items():
            if not isinstance(軸データ, list):
                continue

            for 点 in 軸データ:
                if not isinstance(点, dict):
                    continue

                for キー, 値 in 点.items():
                    if キー == 検索キー or 値 == 検索キー:
                        return {"軸": 軸名, "点": 点}

        return None

    def _Crossカウント(self, Cross構造: Dict, 軸: str) -> int:
        """Cross軸の点数をカウント"""
        return len(Cross構造.get(軸, []))

    def _学習プロセッサを登録(self):
        """学習専用プロセッサを登録"""
        # パターン推論プロセッサ
        try:
            from jcross_pattern_processors import パターン推論プロセッサ

            推論プロセッサ = パターン推論プロセッサ()

            self.プロセッサ辞書["パターンを抽出"] = 推論プロセッサ.パターンを抽出
            self.プロセッサ辞書["類似パターンを探索"] = 推論プロセッサ.類似パターンを探索
            self.プロセッサ辞書["関連パターンを6軸で収集"] = 推論プロセッサ.関連パターンを6軸で収集
            self.プロセッサ辞書["パズルピースを組み合わせ"] = 推論プロセッサ.パズルピースを組み合わせ
            self.プロセッサ辞書["最適推論を選択"] = 推論プロセッサ.最適推論を選択
            self.プロセッサ辞書["パターンを登録"] = 推論プロセッサ.パターンを登録

            # デバッグ用
            self.プロセッサ辞書["パターンを表示"] = 推論プロセッサ.パターンを表示
            self.プロセッサ辞書["類似パターンを表示"] = 推論プロセッサ.類似パターンを表示
            self.プロセッサ辞書["Cross構造を表示"] = 推論プロセッサ.Cross構造を表示
            self.プロセッサ辞書["推論結果を表示"] = 推論プロセッサ.推論結果を表示
            self.プロセッサ辞書["最適推論を表示"] = 推論プロセッサ.最適推論を表示

            print(f"✅ パターン推論プロセッサ登録完了")

        except ImportError as e:
            print(f"⚠️ パターン推論プロセッサのインポートに失敗: {e}")

        # 小世界シミュレータプロセッサ
        try:
            from jcross_world_processors import 小世界シミュレータプロセッサ

            シミュレータプロセッサ = 小世界シミュレータプロセッサ()

            self.プロセッサ辞書["小世界を構築"] = シミュレータプロセッサ.小世界を構築
            self.プロセッサ辞書["パターン分析"] = シミュレータプロセッサ.パターン分析
            self.プロセッサ辞書["因果推論"] = シミュレータプロセッサ.因果推論
            self.プロセッサ辞書["未来を予測"] = シミュレータプロセッサ.未来を予測
            self.プロセッサ辞書["シミュレーション実行"] = シミュレータプロセッサ.シミュレーション実行

            # デバッグ用
            self.プロセッサ辞書["小世界を表示"] = シミュレータプロセッサ.小世界を表示
            self.プロセッサ辞書["パターン分析結果を表示"] = シミュレータプロセッサ.パターン分析結果を表示
            self.プロセッサ辞書["因果推論結果を表示"] = シミュレータプロセッサ.因果推論結果を表示
            self.プロセッサ辞書["予測結果を表示"] = シミュレータプロセッサ.予測結果を表示
            self.プロセッサ辞書["シミュレーション結果を表示"] = シミュレータプロセッサ.シミュレーション結果を表示

            print(f"✅ 小世界シミュレータプロセッサ登録完了")

        except ImportError as e:
            print(f"⚠️ 小世界シミュレータプロセッサのインポートに失敗: {e}")

        # 旧学習プロセッサ（後方互換性）
        try:
            from production_learning_processors import (
                日本語形態素解析器,
                パターン抽出器
            )

            # 形態素解析器
            形態素解析器インスタンス = 日本語形態素解析器()
            self.プロセッサ辞書["日本語形態素解析器.解析"] = 形態素解析器インスタンス.解析
            self.プロセッサ辞書["日本語形態素解析器.文字種別判定"] = 形態素解析器インスタンス.文字種別判定

            # パターン抽出器
            パターン抽出器インスタンス = パターン抽出器()
            self.プロセッサ辞書["パターン抽出器.抽出"] = パターン抽出器インスタンス.抽出

        except ImportError as e:
            pass  # オプショナル

    def _コマンド辞書を読み込み(self):
        """日本語操作コマンド辞書を読み込み"""
        コマンドパス = Path.home() / ".verantyx/commands/claude_supervised_commands.json"

        if not コマンドパス.exists():
            print(f"⚠️ コマンド辞書が見つかりません: {コマンドパス}")
            return

        try:
            with open(コマンドパス, 'r', encoding='utf-8') as f:
                データ = json.load(f)

            self.コマンド辞書 = データ.get("コマンド", {})
            print(f"✅ コマンド辞書読み込み完了: {len(self.コマンド辞書):,}個のコマンド")

            # コマンドマッチングプロセッサを登録
            self.プロセッサ辞書["コマンド.マッチング"] = self._コマンドマッチング
            self.プロセッサ辞書["コマンド.Cross構造生成"] = self._コマンドからCross構造生成

        except Exception as e:
            print(f"⚠️ コマンド辞書の読み込みに失敗: {e}")

    def _コマンドマッチング(self, テキスト: str) -> List[Dict]:
        """
        テキストからマッチするコマンドを検索

        Args:
            テキスト: ユーザーの発言やClaude応答

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
                    "Cross軸": コマンド情報.get("Cross軸配置", {}),
                    "用法": コマンド情報.get("用法", [])
                })

        return マッチ結果

    def _コマンドからCross構造生成(self, テキスト: str, マッチ結果: List[Dict] = None) -> Dict:
        """
        マッチ結果からCross構造を生成

        Args:
            テキスト: 元のテキスト
            マッチ結果: マッチしたコマンドのリスト（Noneの場合は自動マッチング）

        Returns:
            6軸Cross構造
        """
        # マッチ結果がない場合は自動マッチング
        if マッチ結果 is None:
            マッチ結果 = self._コマンドマッチング(テキスト)

        Cross構造 = {
            "UP": [],
            "DOWN": [],
            "LEFT": [],
            "RIGHT": [],
            "FRONT": [],
            "BACK": [],
            "メタ": {
                "元テキスト": テキスト,
                "マッチ数": len(マッチ結果),
                "時刻": datetime.now().isoformat()
            }
        }

        # 各マッチしたコマンドのCross軸を統合
        for マッチ in マッチ結果:
            Cross軸 = マッチ.get("Cross軸", {})

            for 軸名 in ["UP", "DOWN", "LEFT", "RIGHT", "FRONT", "BACK"]:
                if 軸名 in Cross軸:
                    Cross構造[軸名].append({
                        "コマンド": マッチ["コマンド"],
                        "内容": Cross軸[軸名]
                    })

        return Cross構造

    def _配列ソート(self, 配列: List[Dict], キー: str, 順序: str = "昇順"):
        """配列をソート"""
        reverse = (順序 == "降順")
        配列.sort(key=lambda x: x.get(キー, 0), reverse=reverse)

    def jcrossファイルを読み込み(self, ファイルパス: str):
        """
        .jcrossファイルを読み込んでパース
        """
        ファイルパス = Path(ファイルパス)

        if not ファイルパス.exists():
            raise FileNotFoundError(f".jcrossファイルが見つかりません: {ファイルパス}")

        with open(ファイルパス, 'r', encoding='utf-8') as f:
            jcrossコード = f.read()

        # パース
        self._jcrossコードをパース(jcrossコード)

    def _jcrossコードをパース(self, コード: str):
        """
        .jcrossコードをパースしてラベル辞書を作成
        """
        # コメント行を削除（文字列内の#は保護）
        行リスト = []
        Cross構造バッファ = []
        Cross構造中 = False

        for 行_生 in コード.split('\n'):
            行 = 行_生.strip()
            # print(f"DEBUG 処理中: Cross構造中={Cross構造中}, 行={repr(行[:70])}")

            # Cross構造の複数行をバッファリング
            if '生成する ' in 行 and '= {' in 行:
                if '}' not in 行:
                    Cross構造中 = True
                    Cross構造バッファ = [行]
                    continue
                else:
                    # 単一行Cross構造
                    行リスト.append(行)
                    continue

            if Cross構造中:
                # Cross構造内ではコメント削除しない
                if 行:  # 空行はスキップ
                    # print(f"DEBUG バッファ追加: {repr(行)}")
                    Cross構造バッファ.append(行)
                # Cross構造の終了判定: 行が}で終わるまたは}のみ
                if 行 == '}' or 行.endswith('}'):
                    # Cross構造完成 - 1行にまとめる
                    Cross構造完成 = ' '.join(Cross構造バッファ)
                    行リスト.append(Cross構造完成)
                    Cross構造バッファ = []
                    Cross構造中 = False
                continue

            # コメント行をスキップ
            if 行.startswith('#'):
                continue

            # 行末コメントを削除（文字列外の#のみ）
            if '#' in 行:
                # 文字列内かどうかチェック
                引用符カウント = 0
                for i, c in enumerate(行):
                    if c == '"':
                        引用符カウント += 1
                    elif c == '#' and 引用符カウント % 2 == 0:
                        # 文字列外の#
                        行 = 行[:i].strip()
                        break

            if 行:
                行リスト.append(行)

        # ラベルを抽出
        現在のラベル = None
        現在のラベル内容 = []

        for 行 in 行リスト:
            if not 行:
                continue

            # ラベル開始
            if 行.startswith('ラベル '):
                if 現在のラベル:
                    self.ラベル辞書[現在のラベル] = 現在のラベル内容

                現在のラベル = 行.replace('ラベル ', '').strip()
                現在のラベル内容 = []

            # ラベル終了
            elif 行 == 'ラベル終了':
                if 現在のラベル:
                    self.ラベル辞書[現在のラベル] = 現在のラベル内容
                    現在のラベル = None
                    現在のラベル内容 = []

            # ラベル内の命令
            elif 現在のラベル:
                現在のラベル内容.append(行)

            # グローバル変数生成
            elif 行.startswith('生成する '):
                self._グローバル変数を生成(行)

        # 最後のラベルを保存
        if 現在のラベル:
            self.ラベル辞書[現在のラベル] = 現在のラベル内容

    def _グローバル変数を生成(self, 行: str):
        """グローバル変数を生成"""
        # パターン: 生成する 変数名 = {...}
        match = re.match(r'生成する\s+(\S+)\s*=\s*(.+)', 行)
        if match:
            変数名 = match.group(1)
            値文字列 = match.group(2).strip()

            try:
                # JSON形式に変換（Pythonの辞書をJSON準拠に）
                # 単一引用符を二重引用符に変換
                値文字列_JSON = 値文字列.replace("'", '"')

                # JSON/Python辞書として評価
                値 = eval(値文字列_JSON)
                self.グローバルCross構造[変数名] = 値
                self.変数[変数名] = 値
            except Exception as e:
                print(f"⚠️ 変数生成エラー: {変数名}: {e}")

    def ラベルを実行(self, ラベル名: str, 引数: Dict[str, Any] = None) -> Any:
        """
        ラベルを実行

        これが本番実装の核心部分
        """
        if ラベル名 not in self.ラベル辞書:
            raise ValueError(f"ラベル '{ラベル名}' が見つかりません")

        命令リスト = self.ラベル辞書[ラベル名]

        # ローカル変数
        ローカル変数 = 引数.copy() if 引数 else {}

        # 命令を順次実行
        i = 0
        while i < len(命令リスト):
            命令 = 命令リスト[i]

            # 命令を実行
            制御 = self._命令を実行(命令, ローカル変数)

            # 制御フロー
            if 制御 == "返す":
                break
            elif 制御 == "次のループへ":
                continue
            elif 制御 is not None and isinstance(制御, str):
                # ループ制御
                if 制御.startswith("LOOP:"):
                    # ループ処理
                    parts = 制御.split(':', 2)
                    ループ変数名 = parts[1]
                    # リストをJSONから復元
                    import json
                    リストJSON = parts[2]
                    リスト = json.loads(リストJSON)

                    # ループ本体を探す
                    ループ開始 = i + 1
                    ループ終了 = self._ループ終了を探す(命令リスト, ループ開始)

                    # 各要素でループ実行
                    for 要素 in リスト:
                        ローカル変数[ループ変数名] = 要素
                        # ループ本体を実行
                        j = ループ開始
                        while j < ループ終了:
                            ループ制御 = self._命令を実行(命令リスト[j], ローカル変数)
                            if ループ制御 == "返す":
                                return self.スタック.pop() if self.スタック else None
                            j += 1

                    # ループ終了後は繰り返し終了の次へ
                    i = ループ終了
                    continue

                # 条件分岐制御
                elif 制御.startswith("COND:"):
                    parts = 制御.split(':', 1)
                    条件結果 = parts[1] == 'True'

                    if not 条件結果:
                        # 条件が偽なら条件終了まで スキップ
                        i = self._条件終了を探す(命令リスト, i + 1)
                        continue

            elif 制御 is not None and isinstance(制御, int):
                # ジャンプ
                i = 制御
                continue

            i += 1

        # 戻り値（スタックのトップ）
        return self.スタック.pop() if self.スタック else None

    def _ループ終了を探す(self, 命令リスト: List[str], 開始位置: int) -> int:
        """繰り返し終了の位置を探す"""
        for i in range(開始位置, len(命令リスト)):
            if 命令リスト[i].strip() == '繰り返し終了':
                return i
        return len(命令リスト)

    def _条件終了を探す(self, 命令リスト: List[str], 開始位置: int) -> int:
        """条件終了の位置を探す"""
        for i in range(開始位置, len(命令リスト)):
            if 命令リスト[i].strip() == '条件終了':
                return i
        return len(命令リスト)

    def _命令を実行(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """
        1つの命令を実行

        返り値: 制御フロー（"返す"、"次のループへ" など）
        """
        命令 = 命令.strip()

        if not 命令:
            return None

        # 実行する
        if 命令.startswith('実行する '):
            return self._実行する命令(命令, ローカル変数)

        # 取り出す
        elif 命令.startswith('取り出す '):
            return self._取り出す命令(命令, ローカル変数)

        # 設定する
        elif 命令.startswith('設定する '):
            return self._設定する命令(命令, ローカル変数)

        # 生成する
        elif 命令.startswith('生成する '):
            return self._生成する命令(命令, ローカル変数)

        # 比較する
        elif 命令.startswith('比較する '):
            return self._比較する命令(命令, ローカル変数)

        # 条件分岐
        elif 命令.startswith('条件分岐 '):
            return self._条件分岐命令(命令, ローカル変数)

        # 計算する
        elif 命令.startswith('計算する '):
            return self._計算する命令(命令, ローカル変数)

        # 返す
        elif 命令.startswith('返す'):
            return self._返す命令(命令, ローカル変数)

        # 出力する
        elif 命令.startswith('出力する '):
            return self._出力する命令(命令, ローカル変数)

        # 繰り返す
        elif 命令.startswith('繰り返す '):
            return self._繰り返す命令(命令, ローカル変数)

        # 繰り返し終了
        elif 命令 == '繰り返し終了':
            return None  # ループ処理で使用

        # 追加する
        elif 命令.startswith('追加する '):
            return self._追加する命令(命令, ローカル変数)

        # 条件
        elif 命令.startswith('条件 '):
            return self._条件命令(命令, ローカル変数)

        # 条件終了
        elif 命令 == '条件終了':
            return None  # 条件分岐処理で使用

        # 積む
        elif 命令.startswith('積む '):
            return self._積む命令(命令, ローカル変数)

        return None

    def _実行する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """実行する命令"""
        # パターン: 実行する 関数名 引数1 引数2 ...
        parts = 命令.replace('実行する ', '').split()

        if not parts:
            return None

        関数名 = parts[0]
        引数リスト = parts[1:] if len(parts) > 1 else []

        # 引数を評価
        評価済み引数 = []
        for 引数 in 引数リスト:
            評価済み引数.append(self._値を評価(引数, ローカル変数))

        # プロセッサを実行
        if 関数名 in self.プロセッサ辞書:
            結果 = self.プロセッサ辞書[関数名](*評価済み引数)
            if 結果 is not None:
                self.スタック.append(結果)

        # ラベルを実行
        elif 関数名 in self.ラベル辞書:
            結果 = self.ラベルを実行(関数名, {})
            if 結果 is not None:
                self.スタック.append(結果)

        else:
            print(f"⚠️ 不明な関数: {関数名}")

        return None

    def _取り出す命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """取り出す命令"""
        変数名 = 命令.replace('取り出す ', '').strip()

        # スタックから取り出す場合
        if self.スタック:
            値 = self.スタック.pop()
            ローカル変数[変数名] = 値
        # スタックが空の場合、変数から直接参照を取得
        else:
            # ドット記法のサポート (例: Cross.UP)
            if '.' in 変数名:
                parts = 変数名.split('.')
                値 = self._値を評価(parts[0], ローカル変数)
                for part in parts[1:]:
                    if isinstance(値, dict):
                        値 = 値.get(part)
                    elif isinstance(値, list) and part.isdigit():
                        値 = 値[int(part)]
                    else:
                        break
                ローカル変数[parts[-1]] = 値
            else:
                # 変数の値を別名で取得
                if 変数名 in self.変数:
                    ローカル変数[変数名] = self.変数[変数名]
                elif 変数名 in self.グローバルCross構造:
                    ローカル変数[変数名] = self.グローバルCross構造[変数名]

        return None

    def _設定する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """設定する命令"""
        # パターン: 設定する 変数名 = 値
        match = re.match(r'設定する\s+(\S+)\s*=\s*(.+)', 命令)
        if match:
            変数名 = match.group(1)
            値文字列 = match.group(2)

            値 = self._値を評価(値文字列, ローカル変数)
            ローカル変数[変数名] = 値

        return None

    def _生成する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """生成する命令"""
        # パターン: 生成する 変数名 = 値
        match = re.match(r'生成する\s+(\S+)\s*=\s*(.+)', 命令)
        if match:
            変数名 = match.group(1)
            値文字列 = match.group(2)

            try:
                値 = eval(値文字列)
                ローカル変数[変数名] = 値
            except:
                値 = 値文字列
                ローカル変数[変数名] = 値

        return None

    def _比較する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """比較する命令"""
        # パターン: 比較する 値1 値2
        parts = 命令.replace('比較する ', '').split()

        if len(parts) >= 2:
            値1 = self._値を評価(parts[0], ローカル変数)
            値2 = self._値を評価(parts[1], ローカル変数)

            結果 = (値1 == 値2)
            self.スタック.append(結果)

        return None

    def _条件分岐命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """条件分岐命令"""
        # 最新の比較結果をチェック
        if self.スタック and self.スタック[-1]:
            # 条件が真 - 何もしない（次の命令を実行）
            pass
        else:
            # 条件が偽 - 条件分岐終了までスキップ
            # TODO: 実装
            pass

        return None

    def _計算する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """計算する命令"""
        # パターン: 計算する 変数名 = 式
        match = re.match(r'計算する\s+(\S+)\s*=\s*(.+)', 命令)
        if match:
            変数名 = match.group(1)
            式 = match.group(2)

            # 式を評価
            try:
                # 変数を置換
                for var, val in ローカル変数.items():
                    if var in 式:
                        式 = 式.replace(var, str(val))

                結果 = eval(式)
                ローカル変数[変数名] = 結果
            except Exception as e:
                print(f"⚠️ 計算エラー: {e}")

        return None

    def _返す命令(self, 命令: str, ローカル変数: Dict) -> str:
        """返す命令"""
        # パターン: 返す 値
        parts = 命令.split()

        if len(parts) > 1:
            値文字列 = ' '.join(parts[1:])
            値 = self._値を評価(値文字列, ローカル変数)
            self.スタック.append(値)

        return "返す"

    def _出力する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """出力する命令"""
        # パターン: 出力する "メッセージ" + 変数
        メッセージ部分 = 命令.replace('出力する ', '')

        # 文字列リテラルと変数を解析
        出力 = self._文字列を評価(メッセージ部分, ローカル変数)
        print(出力)

        return None

    def _値を評価(self, 値文字列: str, ローカル変数: Dict) -> Any:
        """値を評価"""
        値文字列 = 値文字列.strip()

        # 文字列リテラル
        if 値文字列.startswith('"') and 値文字列.endswith('"'):
            return 値文字列[1:-1]

        # 数値
        try:
            return int(値文字列)
        except:
            pass

        try:
            return float(値文字列)
        except:
            pass

        # ブール値
        if 値文字列 == "true":
            return True
        if 値文字列 == "false":
            return False
        if 値文字列 == "null":
            return None

        # 変数参照
        if 値文字列 in ローカル変数:
            return ローカル変数[値文字列]

        if 値文字列 in self.変数:
            return self.変数[値文字列]

        if 値文字列 in self.グローバルCross構造:
            return self.グローバルCross構造[値文字列]

        # そのまま返す
        return 値文字列

    def _文字列を評価(self, 文字列: str, ローカル変数: Dict) -> str:
        """文字列を評価（変数展開）"""
        # "文字列" + 変数 の形式
        if ' + ' in 文字列:
            parts = 文字列.split(' + ')
            結果 = ""
            for part in parts:
                値 = self._値を評価(part.strip(), ローカル変数)
                結果 += str(値)
            return 結果
        else:
            return str(self._値を評価(文字列, ローカル変数))

    def _繰り返す命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """
        繰り返し命令

        パターン: 繰り返す 変数 in リスト:
                   ...
                 繰り返し終了
        """
        # パターンマッチング: 繰り返す <変数> in <リスト>:
        match = re.match(r'繰り返す\s+(\S+)\s+in\s+(.+):', 命令)
        if not match:
            print(f"⚠️ 繰り返し構文エラー: {命令}")
            return None

        ループ変数名 = match.group(1)
        リスト式 = match.group(2).strip()

        # リストを評価
        リスト = self._値を評価(リスト式, ローカル変数)

        if not isinstance(リスト, (list, tuple)):
            print(f"⚠️ 繰り返し対象がリストではありません: {type(リスト)} - {リスト}")
            return None

        # リストをJSON形式で保存（制御フロー文字列として渡す）
        import json
        リストJSON = json.dumps(リスト, ensure_ascii=False)

        # 現在の命令リストとインデックスを取得
        # ループ本体を探す（繰り返し終了まで）
        return f"LOOP:{ループ変数名}:{リストJSON}"

    def _追加する命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """
        追加命令

        パターン: 追加する 値 to 配列
        """
        # パターンマッチング: 追加する <値> to <配列>
        match = re.match(r'追加する\s+(.+?)\s+to\s+(.+)', 命令)
        if not match:
            print(f"⚠️ 追加構文エラー: {命令}")
            return None

        値式 = match.group(1).strip()
        配列式 = match.group(2).strip()

        # 値を評価
        値 = self._値を評価(値式, ローカル変数)

        # 配列パスを解析（例: Cross.UP, 小世界Cross.FRONT.予測状態）
        if '.' in 配列式:
            parts = 配列式.split('.')
            オブジェクト = self._値を評価(parts[0], ローカル変数)

            # ネストされたパスをたどる
            for part in parts[1:-1]:
                if isinstance(オブジェクト, dict):
                    オブジェクト = オブジェクト.get(part)
                elif isinstance(オブジェクト, list) and part.isdigit():
                    オブジェクト = オブジェクト[int(part)]
                else:
                    print(f"⚠️ パスが無効: {配列式}")
                    return None

            # 最後のキーに追加
            最後のキー = parts[-1]
            if isinstance(オブジェクト, dict):
                if 最後のキー not in オブジェクト:
                    オブジェクト[最後のキー] = []
                if isinstance(オブジェクト[最後のキー], list):
                    オブジェクト[最後のキー].append(値)
            elif isinstance(オブジェクト, list):
                オブジェクト.append(値)
        else:
            # 単純な配列参照
            配列 = self._値を評価(配列式, ローカル変数)
            if isinstance(配列, list):
                配列.append(値)

        return None

    def _条件命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """
        条件命令

        パターン: 条件 変数 == 値:
                   ...
                 条件終了
        """
        # パターンマッチング: 条件 <式>:
        match = re.match(r'条件\s+(.+):', 命令)
        if not match:
            print(f"⚠️ 条件構文エラー: {命令}")
            return None

        条件式 = match.group(1).strip()

        # 条件式を評価
        # 例: 変数 == 値, 変数 > 値, など
        if '==' in 条件式:
            左辺, 右辺 = 条件式.split('==')
            左値 = self._値を評価(左辺.strip(), ローカル変数)
            右値 = self._値を評価(右辺.strip(), ローカル変数)
            結果 = (左値 == 右値)
        elif '!=' in 条件式:
            左辺, 右辺 = 条件式.split('!=')
            左値 = self._値を評価(左辺.strip(), ローカル変数)
            右値 = self._値を評価(右辺.strip(), ローカル変数)
            結果 = (左値 != 右値)
        elif '>' in 条件式:
            左辺, 右辺 = 条件式.split('>')
            左値 = self._値を評価(左辺.strip(), ローカル変数)
            右値 = self._値を評価(右辺.strip(), ローカル変数)
            # 型を揃える
            try:
                if isinstance(左値, str) and 右値 is not None:
                    左値 = type(右値)(左値)
                elif isinstance(右値, str) and 左値 is not None:
                    右値 = type(左値)(右値)
            except:
                pass
            結果 = (左値 > 右値)
        elif '<' in 条件式:
            左辺, 右辺 = 条件式.split('<')
            左値 = self._値を評価(左辺.strip(), ローカル変数)
            右値 = self._値を評価(右辺.strip(), ローカル変数)
            # 型を揃える
            try:
                if isinstance(左値, str) and 右値 is not None:
                    左値 = type(右値)(左値)
                elif isinstance(右値, str) and 左値 is not None:
                    右値 = type(左値)(右値)
            except:
                pass
            結果 = (左値 < 右値)
        else:
            # 単純なブール式
            結果 = self._値を評価(条件式, ローカル変数)

        # 結果をスタックに積む（条件分岐制御で使用）
        self.スタック.append(結果)

        return f"COND:{結果}"

    def _積む命令(self, 命令: str, ローカル変数: Dict) -> Optional[str]:
        """
        積む命令

        パターン: 積む 値
        """
        parts = 命令.split(maxsplit=1)
        if len(parts) > 1:
            値文字列 = parts[1]
            値 = self._値を評価(値文字列, ローカル変数)
            self.スタック.append(値)

        return None

    def ラベルを動的に追加(self, ラベル名: str, 命令リスト: List[str]):
        """実行時に新しいラベルを追加（動的コード生成用）"""
        self.ラベル辞書[ラベル名] = 命令リスト
        print(f"✅ 動的ラベル追加: {ラベル名} ({len(命令リスト)}命令)")


def テスト_本番JCrossエンジン():
    """本番JCrossエンジンのテスト"""

    print("=" * 80)
    print("本番JCrossエンジン テスト")
    print("=" * 80)
    print()

    # エンジン作成
    エンジン = 本番JCrossエンジン()

    # テスト用.jcrossコード
    テストコード = """
# テスト用.jcrossプログラム

# グローバル変数
生成する テストCross = {
  "UP": [{"点": 0, "値": "テスト"}],
  "DOWN": [{"点": 0, "データ": []}]
}

# テストラベル
ラベル テスト実行
  出力する "=== JCrossエンジン テスト開始 ==="
  出力する ""

  # 変数設定
  設定する カウント = 0

  # ループ（簡易版）
  ラベル ループテスト
    出力する "ループ " + カウント

    計算する カウント = カウント + 1

    比較する カウント 3
    条件分岐 未満
      実行する 次のループへ
    条件分岐終了
  ラベル終了

  出力する ""
  出力する "=== テスト完了 ==="

  返す
"""

    # パース
    print("【1. .jcrossコードをパース】")
    エンジン._jcrossコードをパース(テストコード)
    print(f"  ラベル数: {len(エンジン.ラベル辞書)}")
    print(f"  ラベル名: {list(エンジン.ラベル辞書.keys())}")
    print()

    # 実行
    print("【2. ラベルを実行】")
    エンジン.ラベルを実行("テスト実行")
    print()

    print("=" * 80)
    print("✅ 本番JCrossエンジン テスト完了")
    print("=" * 80)


if __name__ == "__main__":
    テスト_本番JCrossエンジン()
