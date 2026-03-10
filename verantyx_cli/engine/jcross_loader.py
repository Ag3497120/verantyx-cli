"""
JCrossファイルローダー

.jcrossファイルを読み込んでPythonオブジェクトに変換
"""

from typing import Dict, List, Any, Optional
import re
from pathlib import Path


class JCrossLoader:
    """
    .jcrossファイルをPythonオブジェクトに変換

    例:
    ```jcross
    生成する 重力Cross = {
      "UP": [{"点": 0, "優先度": 10}],
      "DOWN": [{"点": 0, "力": 9.8}]
    }
    ```

    → Python:
    {
      "重力Cross": {
        "UP": [{"点": 0, "優先度": 10}],
        "DOWN": [{"点": 0, "力": 9.8}]
      }
    }
    """

    def __init__(self):
        self.variables: Dict[str, Any] = {}

    def load_file(self, filepath: str) -> Dict[str, Any]:
        """
        .jcrossファイルを読み込み

        Args:
            filepath: .jcrossファイルのパス

        Returns:
            変数の辞書
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"{filepath} が見つかりません")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        return self.parse(content)

    def parse(self, jcross_code: str) -> Dict[str, Any]:
        """
        JCrossコードをパース

        Args:
            jcross_code: JCrossソースコード

        Returns:
            変数の辞書
        """
        self.variables = {}

        # コメントを削除
        lines = []
        for line in jcross_code.split('\n'):
            # #以降はコメント
            if '#' in line:
                line = line[:line.index('#')]
            lines.append(line.strip())

        code = '\n'.join(lines)

        # 変数定義を抽出
        self._parse_variable_definitions(code)

        return self.variables

    def _parse_variable_definitions(self, code: str):
        """変数定義を解析"""

        # パターン: 生成する 変数名 = { ... }
        # ネストした辞書に対応するため、再帰的にマッチ
        pattern = r'生成する\s+(\S+)\s*=\s*(\{.*?\n\s*\})'

        matches = re.finditer(pattern, code, re.DOTALL)

        for match in matches:
            var_name = match.group(1)
            var_value_str = match.group(2)

            # 値を評価
            try:
                # Pythonの辞書リテラルとして評価
                # 日本語キーを文字列として認識
                var_value_str_fixed = var_value_str.replace('"点"', '"点"').replace('"優先度"', '"優先度"')

                var_value = eval(var_value_str_fixed)
                self.variables[var_name] = var_value
            except Exception as e:
                # evalエラーの場合、手動パース
                try:
                    var_value = self._manual_parse_dict(var_value_str)
                    self.variables[var_name] = var_value
                except Exception as e2:
                    print(f"⚠️ 変数 {var_name} の解析に失敗: {e}")

    def _manual_parse_dict(self, dict_str: str) -> Dict:
        """
        辞書を手動でパース

        evalが失敗した場合の fallback
        """
        # 簡易的な実装: Pythonの辞書リテラルとして評価
        # 改行とインデントを除去
        dict_str = dict_str.replace('\n', ' ')
        dict_str = re.sub(r'\s+', ' ', dict_str)

        try:
            return eval(dict_str)
        except:
            return {}

    def get_variable(self, var_name: str) -> Any:
        """変数を取得"""
        return self.variables.get(var_name)

    def get_cross_structure(self, var_name: str) -> Optional[Dict]:
        """
        Cross構造を取得

        Args:
            var_name: 変数名（例: "重力Cross"）

        Returns:
            Cross構造の辞書
        """
        var = self.get_variable(var_name)

        if var is None:
            return None

        # Cross構造は6軸を持つ辞書
        required_axes = ["UP", "DOWN", "RIGHT", "LEFT", "FRONT", "BACK"]

        # 少なくとも1つの軸があればCross構造
        if isinstance(var, dict):
            for axis in required_axes:
                if axis in var:
                    return var

        return None


class CrossStructureLoader:
    """
    Cross構造を読み込んで使いやすい形式に変換
    """

    def __init__(self, jcross_file: str):
        self.loader = JCrossLoader()
        self.structures = self.loader.load_file(jcross_file)

    def get_gravity_params(self) -> Dict[str, float]:
        """
        重力パラメータを取得

        Returns:
            {"force": 9.8, "priority": 10, ...}
        """
        gravity_cross = self.loader.get_cross_structure("重力Cross")

        if not gravity_cross:
            return {"force": -9.8}  # デフォルト

        params = {}

        # DOWN軸から重力の大きさ
        if "DOWN" in gravity_cross and len(gravity_cross["DOWN"]) > 0:
            down_data = gravity_cross["DOWN"][0]
            if "力" in down_data:
                params["force"] = -abs(down_data["力"])  # 下向きなので負

        # UP軸から優先度
        if "UP" in gravity_cross and len(gravity_cross["UP"]) > 0:
            up_data = gravity_cross["UP"][0]
            if "優先度" in up_data:
                params["priority"] = up_data["優先度"]

        return params

    def get_object_permanence_params(self) -> Dict[str, Any]:
        """
        物の永続性パラメータを取得

        Returns:
            {"exists_when_hidden": True, ...}
        """
        obj_cross = self.loader.get_cross_structure("物体表現Cross")

        if not obj_cross:
            return {"exists_when_hidden": True}  # デフォルト

        params = {"exists_when_hidden": True}

        # BACK軸から永続性
        if "BACK" in obj_cross:
            for item in obj_cross["BACK"]:
                if "存在" in item:
                    params["exists_when_hidden"] = True
                    break

        return params

    def get_surprise_threshold(self) -> float:
        """
        驚き検出の閾値を取得

        Returns:
            閾値 (m)
        """
        surprise_cross = self.loader.get_cross_structure("驚きCross")

        if not surprise_cross:
            return 0.1  # デフォルト: 10cm

        # UP軸から閾値
        if "UP" in surprise_cross and len(surprise_cross["UP"]) > 0:
            up_data = surprise_cross["UP"][0]
            if "閾値" in up_data:
                return up_data["閾値"]

        return 0.1

    def get_all_parameters(self) -> Dict[str, Any]:
        """
        全パラメータを取得

        Returns:
            {
              "gravity": {...},
              "object_permanence": {...},
              "surprise_threshold": ...
            }
        """
        return {
            "gravity": self.get_gravity_params(),
            "object_permanence": self.get_object_permanence_params(),
            "surprise_threshold": self.get_surprise_threshold()
        }


def test_jcross_loader():
    """JCrossローダーのテスト"""

    print("=" * 60)
    print("JCrossローダー テスト")
    print("=" * 60)
    print()

    # テストコード
    jcross_code = """
    # 重力をCross構造で表現
    生成する 重力Cross = {
      "UP": [
        {"点": 0, "優先度": 10, "意味": "重力は常に働く"}
      ],
      "DOWN": [
        {"点": 0, "力": 9.8, "方向": "下"}
      ],
      "FRONT": [
        {"点": 0, "予測": "物は落ちる"}
      ],
      "BACK": [
        {"点": 0, "経験": "全ての物体で確認済み"}
      ]
    }

    # 物体表現
    生成する 物体表現Cross = {
      "UP": [
        {"点": 0, "抽象": "物体は実在する"}
      ],
      "BACK": [
        {"点": 2, "存在": "見えなくても存在"}
      ]
    }

    # 驚き検出
    生成する 驚きCross = {
      "UP": [
        {"点": 0, "閾値": 0.1, "単位": "m"}
      ]
    }
    """

    # パース
    loader = JCrossLoader()
    variables = loader.parse(jcross_code)

    print(f"読み込んだ変数: {len(variables)}個")
    for var_name in variables:
        print(f"  - {var_name}")
    print()

    # 重力Cross
    print("【重力Cross】")
    gravity = loader.get_cross_structure("重力Cross")
    if gravity:
        print(f"  DOWN軸: {gravity.get('DOWN', [])}")
        print(f"  UP軸: {gravity.get('UP', [])}")
    print()

    # 物体表現Cross
    print("【物体表現Cross】")
    obj_cross = loader.get_cross_structure("物体表現Cross")
    if obj_cross:
        print(f"  BACK軸: {obj_cross.get('BACK', [])}")
    print()

    print("=" * 60)
    print("✅ JCrossローダー テスト完了")
    print("=" * 60)


if __name__ == "__main__":
    test_jcross_loader()
