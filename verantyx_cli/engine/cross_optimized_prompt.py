#!/usr/bin/env python3
"""
Cross構造最適化プロンプト生成

ユーザーの質問の前に透明に挿入され、Claudeの応答をCross構造での学習に最適化する
"""

from typing import Dict, Any


def generate_cross_optimized_preprompt(user_message: str, context: Dict[str, Any] = None) -> str:
    """
    Cross構造学習に最適化されたプレプロンプトを生成

    このプロンプトは:
    1. ユーザーには表示されない（透明）
    2. Claudeの応答を構造化・体系化させる
    3. 関連キーワード・概念を明示的に含めさせる
    4. 双方向リンク可能な情報を提供させる

    Args:
        user_message: ユーザーの実際のメッセージ
        context: 追加コンテキスト（過去の会話など）

    Returns:
        最適化されたプレプロンプト
    """

    # 質問タイプを検出
    question_type = _detect_question_type(user_message)

    # 基本プロンプト
    base_prompt = """<verantyx_learning_mode>
あなたの応答は、Cross構造メモリシステムで学習されます。
以下の形式で応答することで、将来の質問に対してより正確に答えられるようになります：

"""

    # 質問タイプ別の指示
    if question_type == "definition":
        # 「〜とは」系の質問
        specific_instructions = """【定義質問への応答形式】

1. **主要な定義**（1-2文で簡潔に）

2. **重要な関連キーワード**を明示的に含める：
   - 開発元・提供元（企業名、組織名）
   - 技術用語・専門用語
   - 競合製品・類似製品
   - 関連人物・団体

3. **構造化された説明**：
   - 主な特徴（箇条書き）
   - 技術的詳細
   - 歴史・背景

4. **双方向リンク情報**：
   - 「Aと比較すると...」（比較対象を明示）
   - 「BはAの一部/発展形/競合」（関係性を明示）
   - 関連概念への言及

例：
「DeepSeekとは」への応答には：
- DeepSeek（主題）
- 中国、AI企業（開発元）
- GPT、Claude、Gemini（競合）
- LLM、大規模言語モデル（技術）
などを**明示的に**含めてください。

これにより、後で「中国のAI」「GPTの競合」などの質問にも答えられます。
"""

    elif question_type == "howto":
        # 「どうやって」系の質問
        specific_instructions = """【手順・方法への応答形式】

1. **概要**（何をするのか）

2. **関連ツール・技術**を明示：
   - 使用するツール名
   - 代替手段
   - 前提知識

3. **ステップバイステップ**：
   - 番号付き手順
   - 各ステップの目的
   - よくある問題と解決策

4. **関連情報**：
   - より詳細な情報源
   - 関連する概念
"""

    elif question_type == "comparison":
        # 比較質問
        specific_instructions = """【比較質問への応答形式】

1. **比較対象の明示**

2. **比較軸を構造化**：
   - 性能・機能
   - コスト・価格
   - 用途・適用場面
   - 長所・短所

3. **個別の詳細**：
   - 各項目について簡潔な説明
   - 関連キーワード

4. **推奨・使い分け**
"""

    elif question_type == "troubleshooting":
        # トラブルシューティング
        specific_instructions = """【問題解決への応答形式】

1. **問題の特定**

2. **原因**（可能性のあるもの全て）

3. **解決策**：
   - 優先度順
   - 各解決策の詳細
   - 使用するコマンド・ツール

4. **予防策**
"""

    else:
        # 一般的な質問
        specific_instructions = """【一般的な応答形式】

1. **明確な回答**

2. **関連キーワード**を含める：
   - 固有名詞（製品名、企業名、人名）
   - 技術用語
   - 関連概念

3. **文脈情報**：
   - 背景
   - なぜ重要か
   - 関連する話題

4. **参照可能な情報**：
   - 関連リンク
   - さらに詳しい情報源
"""

    # 追加の学習最適化指示
    optimization_instructions = """

【Cross構造学習の最適化】

重要：以下を意識して応答してください：

✓ **固有名詞を明示**：企業名、製品名、技術名を略さず記載
✓ **関係性を明示**：「AはBの〜」「AとBの違いは〜」
✓ **カテゴリを明示**：「これは〜の一種」「〜に分類される」
✓ **時系列を含める**：「2024年に発表」「〜の後継」
✓ **双方向性**：Aについて説明する際、関連するB, C, Dにも言及

これにより、将来「B」について質問された時に、「Aとの関連」から情報を提供できます。

</verantyx_learning_mode>

---

ユーザーの質問：
"""

    # 完全なプロンプトを構築
    full_prompt = base_prompt + specific_instructions + optimization_instructions

    return full_prompt


def _detect_question_type(message: str) -> str:
    """質問タイプを検出"""
    lower = message.lower()

    # 定義質問
    if 'とは' in message or 'って何' in message or 'what is' in lower or 'what are' in lower:
        return "definition"

    # 方法・手順
    if 'どうやって' in message or 'how to' in lower or 'how do' in lower or 'how can' in lower:
        return "howto"

    # 比較
    if '違い' in message or 'compare' in lower or 'difference' in lower or 'vs' in lower:
        return "comparison"

    # トラブルシューティング
    if 'エラー' in message or 'error' in lower or '動かない' in message or "doesn't work" in lower:
        return "troubleshooting"

    return "general"


def should_inject_preprompt(user_message: str) -> bool:
    """
    プレプロンプトを挿入すべきかどうか判定

    短すぎるメッセージや、コマンド的なメッセージには挿入しない
    """
    # 短すぎるメッセージ
    if len(user_message.strip()) < 3:
        return False

    # コマンド的なメッセージ（stats, exit, helpなど）
    command_patterns = ['stats', 'help', 'exit', 'quit', 'clear', 'reset']
    if user_message.strip().lower() in command_patterns:
        return False

    # 挨拶だけのメッセージ
    greeting_patterns = ['hi', 'hello', 'hey', 'こんにちは', 'おはよう', 'こんばんは']
    if user_message.strip().lower() in greeting_patterns:
        return False

    return True


# プレプロンプトのバリエーション（学習段階に応じて）
def get_preprompt_for_learning_stage(stage: str, user_message: str) -> str:
    """
    学習段階に応じたプレプロンプトを取得

    Args:
        stage: "initial" (初期), "intermediate" (中級), "advanced" (上級)
        user_message: ユーザーメッセージ
    """
    if stage == "initial":
        # 初期段階：基本的な構造化を重視
        return generate_cross_optimized_preprompt(user_message)

    elif stage == "intermediate":
        # 中級段階：関連性の強化
        return _generate_intermediate_preprompt(user_message)

    elif stage == "advanced":
        # 上級段階：文脈と推論の強化
        return _generate_advanced_preprompt(user_message)

    return generate_cross_optimized_preprompt(user_message)


def _generate_intermediate_preprompt(user_message: str) -> str:
    """中級段階のプレプロンプト"""
    return """<verantyx_learning_intermediate>
あなたの応答は学習されています。以下を特に意識してください：

1. **概念間の関係性**を明示
   - 「AはBの一部」「AとBは競合」「AがBに影響」

2. **時系列・因果関係**
   - 「Aの後にBが登場」「Aが原因でBが発生」

3. **カテゴリ階層**
   - 「AはBの一種であり、C, Dと並ぶ」

これにより、一つの知識から関連する質問に答えられます。
</verantyx_learning_intermediate>

ユーザーの質問：
"""


def _generate_advanced_preprompt(user_message: str) -> str:
    """上級段階のプレプロンプト"""
    return """<verantyx_learning_advanced>
高度な学習モード：

1. **メタ知識**を含める
   - なぜこれが重要か
   - どのような文脈で使われるか
   - 前提となる知識

2. **推論パターン**
   - 「もし〜なら〜」
   - 「〜の場合、〜が適切」

3. **知識の適用範囲**
   - 適用可能な状況
   - 適用不可な状況

将来の文脈推論に活用されます。
</verantyx_learning_advanced>

ユーザーの質問：
"""
