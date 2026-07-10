"""
axis_anchor_trainer.py — 6概念軸アンカーの学習
================================================

年代記の6概念軸 (Logic/Syntax/Factual/Temporal/Creativity/Consensus) を
「飾りのラベル」から「実測できる軸」へ昇格させる。

方法:
  1. 各軸を代表する短文コーパス (12文/軸、うち2文は検証用ホールドアウト)
  2. jgen の本物の24層フォワード + PromptEOL でそれぞれを1024次元に埋め込む
  3. 全体平均 μ を引いた軸別セントロイドを正規化してアンカーとする
  4. 最近傍セントロイド分類でホールドアウト精度を検証
  5. .verantyx_chrono/axis_anchors.npz に保存
     (verantyx_mind.py の可視化と記憶ノードの L1 署名がこれを使う)

実行: python3 axis_anchor_trainer.py
"""

import os
import time

import numpy as np

from verantyx_mind import (
    RustBrain, DEFAULT_MODEL, TOKENIZER, MEMORY_DIR, HIDDEN, embed_text,
    AXIS_NAMES,
)

ANCHOR_PATH = os.path.join(MEMORY_DIR, "axis_anchors.npz")

# 各軸12文 (末尾2文はホールドアウト検証用)
AXIS_CORPUS = [
    # Axis 0: Logic/Structure — 演繹・数理・構造的推論
    [
        "If all birds can fly and a penguin is a bird, the conclusion contradicts reality.",
        "Prove that the sum of two even numbers is always even.",
        "A implies B, and B implies C, therefore A implies C.",
        "Solve the equation: 3x + 7 = 22, so x equals 5.",
        "The contrapositive of a true statement is always true.",
        "全ての人間は死ぬ。ソクラテスは人間である。ゆえにソクラテスは死ぬ。",
        "この命題が真ならば、その対偶も必ず真である。",
        "Either the switch is on or off; it cannot be both simultaneously.",
        "Given premises P and P→Q, we deduce Q by modus ponens.",
        "三段論法により、前提から必然的に結論が導かれる。",
        "If x > y and y > z, then x > z by transitivity.",
        "矛盾する仮定からは任意の命題が導出できてしまう。",
    ],
    # Axis 1: Syntax/Code — プログラミング・構文
    [
        "def fibonacci(n): return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)",
        "for i in range(10): print(i * 2)",
        "SELECT name, age FROM users WHERE age > 20 ORDER BY name;",
        "The function throws a NullPointerException when the list is empty.",
        "git commit -m 'fix: resolve race condition in worker pool'",
        "let mut vec: Vec<f32> = Vec::with_capacity(1024);",
        "このPythonコードはリスト内包表記で書き直すと速くなる。",
        "import numpy as np; x = np.zeros((24, 1024), dtype=np.float16)",
        "JSONのパースエラーはカンマの位置が原因だった。",
        "async function fetchData() { const res = await fetch(url); }",
        "class Node: def __init__(self, val): self.val = val; self.next = None",
        "コンパイルエラー: 型が一致しません。expected i32, found String。",
    ],
    # Axis 2: Factual Memory — 事実・知識
    [
        "The capital of France is Paris.",
        "Water boils at 100 degrees Celsius at sea level.",
        "The Great Wall of China is over 13,000 miles long.",
        "Mount Everest is the highest mountain on Earth.",
        "光の速度は秒速およそ30万キロメートルである。",
        "日本の首都は東京で、人口は約1400万人である。",
        "The mitochondria is the powerhouse of the cell.",
        "Albert Einstein published the theory of general relativity in 1915.",
        "太陽系で最も大きい惑星は木星である。",
        "The Amazon River carries more water than any other river.",
        "DNA is composed of four nucleotide bases: A, T, G, and C.",
        "富士山の標高は3776メートルである。",
    ],
    # Axis 3: Temporal/Time — 時間・順序・履歴
    [
        "First preheat the oven, then mix the batter, and finally bake for 30 minutes.",
        "The meeting starts at 9 AM and ends before lunch at noon.",
        "Yesterday it rained, today it is sunny, and tomorrow it will snow.",
        "World War II ended in 1945, six years after it began in 1939.",
        "まず湯を沸かし、次に麺を入れ、3分待ってから火を止める。",
        "彼は毎朝6時に起き、7時に家を出て、8時に出社する。",
        "The project deadline was moved from March to April, then delayed again.",
        "Before the invention of the telephone, people communicated by telegraph.",
        "会議は延期され、来週の火曜日の午後に再設定された。",
        "The seasons cycle from spring to summer, autumn, and winter.",
        "After the alarm rang, she waited five minutes before getting up.",
        "江戸時代の後に明治時代が始まり、近代化が急速に進んだ。",
    ],
    # Axis 4: Creativity — 創作・想像
    [
        "The dragon's scales shimmered like a thousand sunsets over a mercury sea.",
        "Write a poem about the loneliness of a lighthouse keeper.",
        "In my dream, the city floated upside down above a violet ocean.",
        "Imagine a world where shadows have their own memories.",
        "月明かりの下で、猫たちは古い言葉で詩を紡ぎ始めた。",
        "彼女の笑い声は、ガラス細工の風鈴のように空気を震わせた。",
        "The spaceship was named 'Whisper of Tides', sailing the void like a whale.",
        "Once upon a time, a clockmaker built a heart that could feel seconds.",
        "雨の匂いが記憶の扉を開き、忘れていた夏が溢れ出した。",
        "The forest sang in colors no human eye had ever tasted.",
        "Compose a story where the moon writes letters to the sea every night.",
        "星々は夜空に散らばった銀の種子のように瞬いていた。",
    ],
    # Axis 5: Swarm Consensus — 対話・合意・社会的調整
    [
        "I agree with your proposal, but we should hear everyone's opinion first.",
        "The committee voted 7 to 2 in favor of the new policy.",
        "Let's find a compromise that satisfies both teams.",
        "After a long discussion, the group reached a unanimous decision.",
        "みんなの意見をまとめると、賛成が多数派のようです。",
        "彼の提案に反対する人もいたが、最終的に全員が合意した。",
        "We should build consensus before announcing the change publicly.",
        "The negotiation ended with both parties agreeing to the terms.",
        "投票の結果、過半数の賛成により議案は可決された。",
        "Your feedback matters; please share your thoughts in the survey.",
        "The team debated for hours and finally agreed on the roadmap.",
        "会議では反対意見も尊重しつつ、折衷案を採用することになった。",
    ],
]

N_HOLDOUT = 2  # 各軸の末尾2文を検証に使う


def main():
    from transformers import AutoTokenizer
    print("[Trainer] トークナイザとjgenエンジンを初期化...")
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    brain = RustBrain(DEFAULT_MODEL)

    train_embs, train_labels = [], []
    hold_embs, hold_labels = [], []
    t0 = time.time()
    total = sum(len(c) for c in AXIS_CORPUS)
    done = 0
    try:
        for axis, corpus in enumerate(AXIS_CORPUS):
            for j, text in enumerate(corpus):
                e = embed_text(brain, tok, text)  # PromptEOL + 24層実フォワード
                if j < len(corpus) - N_HOLDOUT:
                    train_embs.append(e)
                    train_labels.append(axis)
                else:
                    hold_embs.append(e)
                    hold_labels.append(axis)
                done += 1
                print(f"  [{done:2d}/{total}] axis={axis} ({AXIS_NAMES[axis].strip()}) encoded: {text[:40]}...")
    finally:
        brain.close()

    train_embs = np.stack(train_embs)
    hold_embs = np.stack(hold_embs)
    train_labels = np.array(train_labels)
    hold_labels = np.array(hold_labels)

    # 全体平均を引いて軸別セントロイドを作る (共通成分の除去)
    mu = train_embs.mean(axis=0)
    anchors = np.zeros((6, HIDDEN), dtype=np.float32)
    for axis in range(6):
        c = (train_embs[train_labels == axis] - mu).mean(axis=0)
        anchors[axis] = c / (np.linalg.norm(c) + 1e-8)

    def classify(embs):
        scores = (embs - mu) @ anchors.T  # cos比例 (アンカーは単位ベクトル)
        return scores.argmax(axis=1)

    train_acc = float((classify(train_embs) == train_labels).mean())
    hold_acc = float((classify(hold_embs) == hold_labels).mean())
    print(f"\n[Trainer] 学習セット精度   : {train_acc*100:.1f}% ({len(train_labels)}文)")
    print(f"[Trainer] ホールドアウト精度: {hold_acc*100:.1f}% ({len(hold_labels)}文)")

    pred_h = classify(hold_embs)
    for axis in range(6):
        m = hold_labels == axis
        acc = float((pred_h[m] == axis).mean())
        print(f"  Axis {axis} ({AXIS_NAMES[axis].strip():18s}): holdout {acc*100:.0f}%")

    # 軸間の直交性 (相互cos) を表示
    gram = anchors @ anchors.T
    off_diag = gram[~np.eye(6, dtype=bool)]
    print(f"[Trainer] 軸間の平均|cos|: {float(np.abs(off_diag).mean()):.3f} (低いほど独立)")

    os.makedirs(MEMORY_DIR, exist_ok=True)
    np.savez(ANCHOR_PATH, mu=mu, anchors=anchors,
             names=np.array([n.strip() for n in AXIS_NAMES]),
             train_acc=train_acc, hold_acc=hold_acc)
    print(f"[Trainer] 保存: {ANCHOR_PATH} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
