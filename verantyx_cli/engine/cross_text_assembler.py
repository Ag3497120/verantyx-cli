#!/usr/bin/env python3
"""
Cross Text Assembler

文章をCross構造上で組み立てて意味理解

重要: 文章は文字列ではなく、Cross構造上の操作シーケンス
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import re


class CrossTextAssembler:
    """
    Cross構造上での文章組み立て

    文章の意味理解 = Cross構造上での操作コマンド実行

    例:
        「DeepSeekは中国勢としてはClaudeなどと同等かそれ以下」

        ↓ 組み立て

        1. 実体検出: DeepSeek, Claude, 中国
        2. 代名詞解決: それ → Claude
        3. 集合展開: など → {Claude, GPT, Gemini}
        4. 比較構築: DeepSeek ≈ Claude (中国AIの中で)
    """

    def __init__(self):
        # 汎用操作コマンド
        self.generic_commands = {
            # 参照解決
            'RESOLVE_PRONOUN': self._resolve_pronoun,
            'EXPAND_SET': self._expand_set,

            # 関係構築
            'BUILD_COMPARISON': self._build_comparison,
            'BUILD_CLASSIFICATION': self._build_classification,
            'BUILD_ATTRIBUTION': self._build_attribution,

            # エンティティ検出
            'DETECT_ENTITIES': self._detect_entities,
            'DETECT_RELATIONS': self._detect_relations,

            # 文脈理解
            'RESOLVE_CONTEXT': self._resolve_context,
            'INFER_IMPLICIT': self._infer_implicit,
        }

        # Cross構造（推論空間）
        self.cross_space = {
            'entities': {},  # エンティティとその属性
            'relations': [],  # エンティティ間の関係
            'context_stack': []  # 文脈スタック
        }

    def assemble_text(
        self,
        text: str,
        cross_structure: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        文章をCross構造上で組み立てて意味理解

        Args:
            text: 入力文章
            cross_structure: 既存のCross構造（知識ベース）

        Returns:
            組み立て結果（意味表現）
        """
        # Step 1: エンティティを検出
        entities = self._detect_entities(text, cross_structure)

        # Step 2: 代名詞を解決
        resolved_text, pronoun_map = self._resolve_pronouns_in_text(text, entities)

        # Step 3: 「など」「等」を展開
        expanded_text, set_expansions = self._expand_sets_in_text(resolved_text, cross_structure)

        # Step 4: 関係を検出
        relations = self._detect_relations(expanded_text, entities)

        # Step 5: Cross構造上で組み立て
        assembled = self._assemble_on_cross(
            text=expanded_text,
            entities=entities,
            pronoun_map=pronoun_map,
            set_expansions=set_expansions,
            relations=relations
        )

        return assembled

    def _detect_entities(self, text: str, cross_structure: Optional[Dict] = None) -> List[Dict]:
        """
        エンティティを検出

        既存のCross構造から既知のエンティティを優先的に検出
        """
        entities = []

        # 既知のエンティティ（Cross構造から）
        known_entities = self._get_known_entities(cross_structure) if cross_structure else []

        for entity_name in known_entities:
            if entity_name in text:
                entities.append({
                    'name': entity_name,
                    'type': 'known',
                    'positions': self._find_positions(entity_name, text)
                })

        # 新規エンティティ（固有名詞）
        new_entities = self._extract_proper_nouns(text)
        for entity_name in new_entities:
            if not any(e['name'] == entity_name for e in entities):
                entities.append({
                    'name': entity_name,
                    'type': 'new',
                    'positions': self._find_positions(entity_name, text)
                })

        return entities

    def _resolve_pronouns_in_text(
        self,
        text: str,
        entities: List[Dict]
    ) -> Tuple[str, Dict[str, str]]:
        """
        代名詞を解決

        重要: これがないと「それ」「これ」の意味が分からない
        """
        pronoun_map = {}
        resolved_text = text

        # 日本語の代名詞パターン
        pronouns = ['それ', 'これ', 'あれ', 'その', 'この', 'あの']

        for pronoun in pronouns:
            if pronoun in text:
                # 直前のエンティティを参照先と推定
                referent = self._find_referent(pronoun, text, entities)

                if referent:
                    pronoun_map[pronoun] = referent
                    # テキスト内で置換
                    resolved_text = resolved_text.replace(pronoun, f"[{referent}]")

        return resolved_text, pronoun_map

    def _expand_sets_in_text(
        self,
        text: str,
        cross_structure: Optional[Dict] = None
    ) -> Tuple[str, Dict[str, List[str]]]:
        """
        「など」「等」を展開

        例:
            「Claudeなど」→ {Claude, GPT, Gemini, ...}
        """
        set_expansions = {}
        expanded_text = text

        # 「〜など」パターンを検出
        pattern = r'([A-Za-z]+|[ぁ-んァ-ヶー]+)など'
        matches = re.finditer(pattern, text)

        for match in matches:
            anchor = match.group(1)  # 「Claude」
            full_match = match.group(0)  # 「Claudeなど」

            # Cross構造から関連エンティティを取得
            expanded_set = self._expand_set(anchor, cross_structure)

            if expanded_set:
                set_expansions[full_match] = expanded_set
                # 展開表現に置換
                expanded_text = expanded_text.replace(
                    full_match,
                    f"[{', '.join(expanded_set)}]"
                )

        return expanded_text, set_expansions

    def _resolve_pronoun(
        self,
        pronoun: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """代名詞の参照先を解決（汎用操作コマンド）"""
        # 文脈スタックから最も近いエンティティを取得
        if self.cross_space['context_stack']:
            return self.cross_space['context_stack'][-1]
        return None

    def _expand_set(
        self,
        anchor: str,
        cross_structure: Optional[Dict] = None
    ) -> List[str]:
        """
        集合を展開（汎用操作コマンド）

        例:
            anchor = "Claude"
            → {Claude, GPT, Gemini, DeepSeek} (同じカテゴリのAI)
        """
        expanded = [anchor]

        if not cross_structure:
            return expanded

        # Cross構造のFRONT軸から関連概念を取得
        if 'axes' in cross_structure and 'FRONT' in cross_structure['axes']:
            # 主概念を探す
            front_axis = cross_structure['axes']['FRONT']

            # 関連概念を検索
            for entry in front_axis.get('reasoning_patterns', []):
                # anchorが含まれているパターンを探す
                if anchor in str(entry):
                    # 同じトピックの概念を全て追加
                    topic = entry.get('topic', '')
                    # （簡易版: 実際はより高度な検索が必要）

        # UP軸からカテゴリが同じエンティティを取得
        if 'axes' in cross_structure and 'UP' in cross_structure['axes']:
            # （実装は省略）
            pass

        # デフォルト: 既知のAI名を追加
        known_ais = ['GPT', 'Claude', 'Gemini', 'DeepSeek', 'LLaMA']
        if anchor in known_ais:
            expanded.extend([ai for ai in known_ais if ai != anchor])

        return expanded[:5]  # 最大5個

    def _build_comparison(
        self,
        entity1: str,
        entity2: str,
        text: str
    ) -> Dict[str, Any]:
        """
        比較関係を構築（汎用操作コマンド）

        例:
            「DeepSeekはClaudeと同等」
            → {A: DeepSeek, B: Claude, relation: '同等'}
        """
        comparison = {
            'type': 'comparison',
            'entity1': entity1,
            'entity2': entity2,
            'relation': 'unknown'
        }

        # 比較表現を検出
        if '同等' in text or '等しい' in text:
            comparison['relation'] = 'equal'
        elif 'より優れ' in text or 'より高' in text:
            comparison['relation'] = 'greater'
        elif 'より劣' in text or 'より低' in text:
            comparison['relation'] = 'less'
        elif 'それ以下' in text:
            comparison['relation'] = 'less_or_equal'
        elif 'それ以上' in text:
            comparison['relation'] = 'greater_or_equal'

        return comparison

    def _detect_relations(
        self,
        text: str,
        entities: List[Dict]
    ) -> List[Dict]:
        """
        関係を検出

        エンティティ間の関係性を抽出
        """
        relations = []

        entity_names = [e['name'] for e in entities]

        # 比較関係
        if '同等' in text or 'より' in text or 'それ以下' in text:
            # エンティティのペアを検出
            for i, e1 in enumerate(entity_names):
                for e2 in entity_names[i+1:]:
                    if e1 in text and e2 in text:
                        comparison = self._build_comparison(e1, e2, text)
                        relations.append(comparison)

        # 分類関係
        if 'は' in text and ('です' in text or 'である' in text):
            # 「AはBです」パターン
            match = re.search(r'(.+?)は(.+?)(?:です|である)', text)
            if match:
                subject = match.group(1).strip()
                predicate = match.group(2).strip()

                # subjectがエンティティか確認
                if subject in entity_names:
                    relations.append({
                        'type': 'classification',
                        'entity': subject,
                        'category': predicate
                    })

        return relations

    def _assemble_on_cross(
        self,
        text: str,
        entities: List[Dict],
        pronoun_map: Dict[str, str],
        set_expansions: Dict[str, List[str]],
        relations: List[Dict]
    ) -> Dict[str, Any]:
        """
        Cross構造上で組み立て

        これが最終的な意味表現
        """
        assembled = {
            'original_text': text,
            'entities': entities,
            'pronoun_resolutions': pronoun_map,
            'set_expansions': set_expansions,
            'relations': relations,
            'semantic_structure': self._build_semantic_structure(
                entities, relations, pronoun_map, set_expansions
            )
        }

        return assembled

    def _build_semantic_structure(
        self,
        entities: List[Dict],
        relations: List[Dict],
        pronoun_map: Dict[str, str],
        set_expansions: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        意味構造を構築

        Cross構造上での立体的表現
        """
        structure = {
            'nodes': [],
            'edges': [],
            'context': {}
        }

        # ノード（エンティティ）を追加
        for entity in entities:
            structure['nodes'].append({
                'id': entity['name'],
                'type': entity['type'],
                'label': entity['name']
            })

        # エッジ（関係）を追加
        for relation in relations:
            if relation['type'] == 'comparison':
                structure['edges'].append({
                    'from': relation['entity1'],
                    'to': relation['entity2'],
                    'label': relation['relation'],
                    'type': 'comparison'
                })
            elif relation['type'] == 'classification':
                structure['edges'].append({
                    'from': relation['entity'],
                    'to': relation['category'],
                    'label': 'is_a',
                    'type': 'classification'
                })

        # 代名詞解決をコンテキストに追加
        structure['context']['pronoun_resolutions'] = pronoun_map
        structure['context']['set_expansions'] = set_expansions

        return structure

    # ========== ヘルパーメソッド ==========

    def _get_known_entities(self, cross_structure: Dict) -> List[str]:
        """Cross構造から既知のエンティティを取得"""
        entities = set()

        # FRONT軸から概念を取得
        if 'axes' in cross_structure and 'FRONT' in cross_structure['axes']:
            front = cross_structure['axes']['FRONT']
            for entry in front.get('reasoning_patterns', []):
                if 'topic' in entry:
                    entities.add(entry['topic'])

        # UP軸から質問の主題を取得
        if 'axes' in cross_structure and 'UP' in cross_structure['axes']:
            up = cross_structure['axes']['UP']
            for entry in up.get('user_inputs', []):
                # [CTX:...|TOPIC:X] から X を抽出
                match = re.search(r'TOPIC:([^\]]+)', str(entry))
                if match:
                    entities.add(match.group(1))

        return list(entities)

    def _extract_proper_nouns(self, text: str) -> List[str]:
        """固有名詞を抽出（簡易版）"""
        # 大文字で始まる単語
        words = re.findall(r'\b[A-Z][a-zA-Z]+\b', text)
        return words

    def _find_positions(self, entity: str, text: str) -> List[int]:
        """エンティティの出現位置を検索"""
        positions = []
        start = 0
        while True:
            pos = text.find(entity, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
        return positions

    def _find_referent(
        self,
        pronoun: str,
        text: str,
        entities: List[Dict]
    ) -> Optional[str]:
        """代名詞の参照先を推定"""
        # 代名詞の位置を取得
        pronoun_pos = text.find(pronoun)
        if pronoun_pos == -1:
            return None

        # 直前に出現したエンティティを探す
        candidates = []
        for entity in entities:
            positions = entity['positions']
            for pos in positions:
                if pos < pronoun_pos:
                    candidates.append({
                        'entity': entity['name'],
                        'distance': pronoun_pos - pos
                    })

        if candidates:
            # 最も近いエンティティを選択
            nearest = min(candidates, key=lambda x: x['distance'])
            return nearest['entity']

        return None

    def _build_classification(self, entity: str, category: str) -> Dict:
        """分類関係を構築"""
        return {
            'type': 'classification',
            'entity': entity,
            'category': category
        }

    def _build_attribution(self, entity: str, attribute: str) -> Dict:
        """属性関係を構築"""
        return {
            'type': 'attribution',
            'entity': entity,
            'attribute': attribute
        }

    def _resolve_context(self, text: str, cross_structure: Dict) -> Dict:
        """文脈を解決"""
        return {}

    def _infer_implicit(self, text: str, cross_structure: Dict) -> List[str]:
        """暗黙の情報を推論"""
        return []


# テスト用
if __name__ == '__main__':
    assembler = CrossTextAssembler()

    # テストケース1: 代名詞解決
    print("=" * 80)
    print("Test 1: Pronoun Resolution")
    print("=" * 80)

    text1 = "DeepSeekは中国のAI企業が開発しました。それはLLMです。"

    # 簡易Cross構造
    cross_structure = {
        'axes': {
            'FRONT': {
                'reasoning_patterns': [
                    {'topic': 'DeepSeek'}
                ]
            }
        }
    }

    result1 = assembler.assemble_text(text1, cross_structure)

    print(f"\nOriginal: {text1}")
    print(f"\nEntities: {[e['name'] for e in result1['entities']]}")
    print(f"\nPronoun Resolutions:")
    for pronoun, referent in result1['pronoun_resolutions'].items():
        print(f"  {pronoun} → {referent}")

    # テストケース2: 集合展開
    print("\n\n" + "=" * 80)
    print("Test 2: Set Expansion")
    print("=" * 80)

    text2 = "DeepSeekはClaudeなどと比較されます。"

    result2 = assembler.assemble_text(text2, cross_structure)

    print(f"\nOriginal: {text2}")
    print(f"\nSet Expansions:")
    for original, expanded in result2['set_expansions'].items():
        print(f"  {original} → {expanded}")

    # テストケース3: 複雑な文章
    print("\n\n" + "=" * 80)
    print("Test 3: Complex Sentence (Your Example)")
    print("=" * 80)

    text3 = "DeepSeekは中国勢としてはClaudeなどと同等かそれ以下です。"

    result3 = assembler.assemble_text(text3, cross_structure)

    print(f"\nOriginal: {text3}")
    print(f"\nEntities: {[e['name'] for e in result3['entities']]}")
    print(f"\nPronoun Resolutions: {result3['pronoun_resolutions']}")
    print(f"\nSet Expansions: {result3['set_expansions']}")
    print(f"\nRelations:")
    for rel in result3['relations']:
        print(f"  {rel}")

    print("\n\n" + "=" * 80)
    print("Semantic Structure (Graph)")
    print("=" * 80)
    sem = result3['semantic_structure']
    print(f"\nNodes: {[n['id'] for n in sem['nodes']]}")
    print(f"\nEdges:")
    for edge in sem['edges']:
        print(f"  {edge['from']} --[{edge['label']}]--> {edge['to']}")
