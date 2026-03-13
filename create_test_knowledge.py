#!/usr/bin/env python3
"""
テスト用の知識データを作成
"""

from pathlib import Path
import json

def create_test_knowledge():
    """テスト用Q&Aデータを作成"""

    verantyx_dir = Path.home() / '.verantyx'
    verantyx_dir.mkdir(exist_ok=True)

    # テストQ&Aデータ
    test_data = {
        'qa_patterns': [
            {
                'question': 'openaiとは',
                'answer': 'OpenAIは人工知能の研究と開発を行う米国の企業です。GPT-4やChatGPTなどの大規模言語モデルを開発しています。2015年にサムアルトマンやイーロンマスクらによって設立されました。',
                'entity': 'openai',
                'intent': 'definition',
                'confidence': 1.0,
                'created_at': 1710000000.0
            },
            {
                'question': 'rustとは',
                'answer': 'Rustはメモリ安全性とパフォーマンスを重視したシステムプログラミング言語です。C/C++の代替として注目されており、並行処理の安全性が高く、ゼロコスト抽象化を提供します。',
                'entity': 'rust',
                'intent': 'definition',
                'confidence': 1.0,
                'created_at': 1710000100.0
            },
            {
                'question': 'pythonとは',
                'answer': 'Pythonは読みやすく書きやすい高水準プログラミング言語です。AI・機械学習、Webアプリ開発、データ分析など幅広い分野で使われています。豊富なライブラリと活発なコミュニティが特徴です。',
                'entity': 'python',
                'intent': 'definition',
                'confidence': 1.0,
                'created_at': 1710000200.0
            }
        ],
        'concepts': [
            {
                'name': 'openai',
                'category': '企業',
                'related': ['gpt', 'chatgpt', 'ai']
            },
            {
                'name': 'rust',
                'category': 'プログラミング言語',
                'related': ['systems programming', 'memory safety']
            },
            {
                'name': 'python',
                'category': 'プログラミング言語',
                'related': ['ai', 'ml', 'web']
            }
        ]
    }

    # 保存
    knowledge_file = verantyx_dir / 'test_knowledge.json'
    with open(knowledge_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Test knowledge created: {knowledge_file}")
    print(f"   - Q&A patterns: {len(test_data['qa_patterns'])}")
    print(f"   - Concepts: {len(test_data['concepts'])}")

    return knowledge_file


if __name__ == "__main__":
    create_test_knowledge()
