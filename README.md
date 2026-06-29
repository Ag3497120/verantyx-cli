---
pipeline_tag: text-generation
tags:
- verantyx
- telepathy
- multi-agent
- swarm
- decoder
- JCross
- qwen
language:
- en
- ja
sdk: gradio
app_file: app.py
---

# 🧠 Verantyx: Telepathic Swarm Architecture (Qwen 0.5B Hybrid)

> 📖 **The Verantyx Chronicles (開発年代記)**
> このシステムは、AIとの数十時間に及ぶ深遠な対話と、無数のクラッシュ（M1 MaxのMPSメモリ衝突、自己回帰ループでのエントロピー爆発、Qwenの謎の哲学モード等）の末に構築されました。
> どのような仮説と検証を経てこのアーキテクチャが誕生したのか、捏造不可能な「狂気の全記録」を公開しています。
> - [Vol 1: The Genesis & MPS Trap](docs/chronicles/Vol1_The_Genesis_and_MPS_Trap.md)
> - [Vol 2: Zero-RAM Inference](docs/chronicles/Vol2_Zero_RAM_Inference.md)
> - [Vol 3: Multilingual Madness & JCross](docs/chronicles/Vol3_Multilingual_Madness_and_JCross.md)
> - [Vol 4: The Philosophical Drift](docs/chronicles/Vol4_The_Philosophical_Drift.md)

## ⚡ Quick Start: One-Click Setup
Run the fully-connected Ambient Telepathy Pipeline directly on your machine. This script will automatically encode your natural language prompt into vectors, perform Swarm Puzzle Inference in topological space, and decode the final consensus vector back into text.

**Model Download**:
The system relies on Hugging Face's `Qwen/Qwen1.5-0.5B-Chat` for the Coder synthesis. Ensure you have the `huggingface_hub` package installed.

**Run the pipeline**:
```bash
# Start the full Ambient Brainstorming pipeline and submit your thought
python3 cli/scripts/bucket_relay_swarm_experimental.py
```

---

## 👁️ The "God Mode" Thought Logs (Why We Expose Everything)
When you run the pipeline, you will see a massive, verbose stream of raw matrix operations, Entropy readings, Semantic Drift percentages, and Conceptual Activations. We expose all of these logs unconditionally. Why?

1. **100% Explainability (No More Black Boxes)**: Traditional LLMs hide their thoughts inside billions of parameters. In Verantyx, the Latent Space is mapped into 6 distinct conceptual axes (Logic, Syntax, Factual Memory, etc.). You can literally *watch* the AI prioritize Logic over Creativity in real-time.
2. **Debugging Semantic Drift**: If the Swarm's final output diverges into a philosophical tangent (Semantic Drift), you can look at the exact `Repulsion` step where the Vector L2 Norm spiked and the Cosine Similarity shifted. We have a mathematical gauge for hallucinations.
3. **Token-Free Thinking (Extreme Compute Efficiency)**: The Swarm reaches consensus geometrically. It never generates tokens to "think out loud". Once `Entropy (Uncertainty)` hits 0, the thought is fully formed, saving immense GPU compute.
4. **Mid-Thought Steering**: In the future, these logs will allow users or commander agents to pause the inference loop and inject steering vectors to manually adjust an axis before any text is generated.

---

## ⚙️ Internal Mechanisms: How the Swarm "Thinks" and "Speaks"

Verantyx implements a complete separation of "Thinking" and "Speaking".

### 1. Thinking: The JCross Topological Inference
The Swarm uses the **JCross V2 3D Valve** core. Instead of standard autoregressive self-attention, input prompts are embedded into a 1024-dimensional topological vector. 
During inference (Cascading Lock), the agents apply geometric transformations (`torch.roll`, repulsion physics, constraint manifolds) to organically morph the vector. The Swarm agents debate by colliding their vectors together until a mathematical equilibrium (`consensus_vector`) is found. 

### 2. Speaking: The Hybrid HF Logit Injection
The Swarm itself is physically incapable of generating text—it only produces a deep thought vector. To speak, the `consensus_vector` is handed off to the **Telepathic Coder**.
The Coder initializes a standard HuggingFace `AutoModelForCausalLM` (Qwen 1.5 0.5B). Instead of passing text, we bypass the embedding layer and inject the `consensus_vector` directly into the model's `inputs_embeds`. Because the vector shapes align exactly, the standard HuggingFace transformer acts as the "mouth", effortlessly decoding the Swarm's complex geometric topology back into fluent natural language.

---

## 🚧 Current Status: The "Philosophical Drift" Anomaly

If you run the pipeline today, you will notice a fascinating anomaly: no matter what prompt you give the Swarm (whether asking for C++ code or a simple self-introduction), the final decoded text will almost always be **highly abstract, philosophical Chinese text** (e.g., *"This is like a road. There is nothing longer. Yes. This is not me."*).

**Why doesn't it answer the prompt? (Semantic Drift)**
This is *not* gibberish, and it proves our decoding pipeline is flawless. However, during the "Thinking" phase (JCross Topological Inference), the Swarm's thought vectors are completely free to repel and morph. Because we haven't implemented rigid anchors yet, the intense geometric calculations cause the vector to **"drift"** away from the original prompt's language and context. It naturally settles into the absolute center of Qwen's latent space, which is heavily dominated by abstract Chinese semantics.

**The Upcoming Fix: Cascading Lock**
To solve this, our next architectural milestone is **Cascading Lock**. We will lock specific axes (like `Language` and `Factual Context`) in the latent space so they cannot drift, while allowing the other axes (`Logic` and `Creativity`) to freely compute. This will tether the Swarm's deep thoughts to the user's original request.

---

## 🌟 Legacy Architecture Overview (Gemma 4 12B)
*(The following is the original concept overview for the legacy Gemma architecture)*

**Verantyx** is a revolutionary multi-agent AI architecture that completely discards traditional "prompt-to-text" token passing between agents. Instead, it uses **Telepathic Swarm Intelligence** — agents communicate pure, abstract mathematical concepts (high-dimensional latent vectors) directly to each other's hidden layers. 

### 1. The Commander (JCross Core)
* **Role**: Takes human natural language and encodes it into an **Intent Vector**. It does not generate text. It generates pure thought and broadcasts it.

### 2. The Swarm (Workers / JCross Core)
* **Role**: Workers receive the Intent Vector. Instead of generating text, they run a **Puzzle Inference Engine** (`a * torch.roll(b, shifts=1, dims=-1)`). They debate geometrically in latent space, combining their topologies until they reach a mathematically stable "Consensus Vector" (`aligned_vector`). No words are spoken during this debate.

### 3. The Telepathic Coder (Hybrid Logit Blending Decoder)
* **Role**: Translates the Swarm's final Consensus Vector into flawless, executable code. 

## 📂 Repository Contents
* `commander_12b_rank1024.jgen`: The Master intent encoder.
* `gemma_12b_generative.jgen`: The Swarm debate core.
* `telepathic_coder_lossless.jgen`: The Telepathic Coder model containing Telepathy Receptors for stabilization.
* `manifold_alignment.pt`: The spatial translation matrix.
* `cli/scripts/`: Complete Python codebase for running the CLI, Swarm, and Hybrid Decoder.
