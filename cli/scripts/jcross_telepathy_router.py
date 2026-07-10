import torch
import torch.nn as nn
import torch.nn.functional as F

class JCrossEnergyEncoder(nn.Module):
    """
    GemmaのHidden StatesをJCrossの普遍的概念空間（エネルギー分布）に射影する層
    """
    def __init__(self, gemma_dim, jcross_dim, num_axes=6):
        super().__init__()
        self.gemma_dim = gemma_dim
        self.jcross_dim = jcross_dim
        self.num_axes = num_axes
        
        self.axis_routers = nn.ModuleList()
        base_dim = jcross_dim // num_axes
        for i in range(num_axes):
            out_dim = base_dim if i < num_axes - 1 else jcross_dim - base_dim * (num_axes - 1)
            self.axis_routers.append(nn.Sequential(
                nn.Linear(gemma_dim, gemma_dim // 2),
                nn.GELU(),
                nn.Linear(gemma_dim // 2, out_dim)
            ))
        
    def forward(self, x):
        # x: [batch_size, seq_len, gemma_dim]
        axis_energies = []
        for router in self.axis_routers:
            energy = F.relu(router(x))
            axis_energies.append(energy)
            
        # [batch_size, seq_len, jcross_dim]
        jcross_energy = torch.cat(axis_energies, dim=-1)
        # Phase 2: シーケンス長を維持したまま返す
        return jcross_energy

class JCrossSequenceAttentionDecoder(nn.Module):
    """
    JCross空間の可変長エネルギー分布から、Qwenの固定長（または可変長）シーケンスへ
    Attentionを用いて動的にルーティングする層
    """
    def __init__(self, jcross_dim, qwen_dim, target_seq_len, num_heads=8):
        super().__init__()
        self.jcross_dim = jcross_dim
        self.qwen_dim = qwen_dim
        self.target_seq_len = target_seq_len
        
        # ターゲットとなるQwen側のシーケンス構造（Query）の学習パラメータ
        self.query_embeds = nn.Parameter(torch.randn(1, target_seq_len, jcross_dim) * 0.02)
        
        # Multi-head attention (Query: Qwen_len, Key/Value: Gemma_len)
        self.attention = nn.MultiheadAttention(embed_dim=jcross_dim, num_heads=num_heads, batch_first=True)
        
        self.renderer = nn.Sequential(
            nn.Linear(jcross_dim, jcross_dim),
            nn.LayerNorm(jcross_dim),
            nn.GELU(),
            nn.Linear(jcross_dim, qwen_dim)
        )
        
    def forward(self, jcross_energy):
        # jcross_energy: [batch_size, src_seq_len, jcross_dim]
        batch_size = jcross_energy.size(0)
        
        # Queryをバッチサイズに拡張
        q = self.query_embeds.expand(batch_size, -1, -1)
        
        # Attention Pooling
        attn_output, _ = self.attention(q, jcross_energy, jcross_energy) # [batch_size, target_seq_len, jcross_dim]
        
        # 最終的なQwen次元への変換
        qwen_soft_prompts = self.renderer(attn_output) # [batch_size, target_seq_len, qwen_dim]
        
        return qwen_soft_prompts

class JCrossTelepathyRouter(nn.Module):
    def __init__(self, gemma_dim=3840, jcross_dim=4096, qwen_dim=1024, qwen_seq_len=8):
        super().__init__()
        self.encoder = JCrossEnergyEncoder(gemma_dim, jcross_dim)
        self.decoder = JCrossSequenceAttentionDecoder(jcross_dim, qwen_dim, qwen_seq_len)
        
    def forward(self, gemma_hidden_states):
        energy_sequence = self.encoder(gemma_hidden_states)
        qwen_prompts = self.decoder(energy_sequence)
        return qwen_prompts, energy_sequence

if __name__ == "__main__":
    # --- Dummy Test for Phase 2 ---
    batch_size = 2
    gemma_seq_len = 13
    gemma_dim = 3840
    qwen_dim = 1024
    qwen_seq_len = 8
    jcross_dim = 4096
    
    print("[*] Initializing JCross Telepathy Router (Phase 2)...")
    model = JCrossTelepathyRouter(gemma_dim, jcross_dim, qwen_dim, qwen_seq_len)
    
    dummy_gemma_states = torch.randn(batch_size, gemma_seq_len, gemma_dim)
    print(f"[*] Input shape: {dummy_gemma_states.shape}")
    
    qwen_prompts, jcross_energy_seq = model(dummy_gemma_states)
    
    print(f"[*] JCross Energy Sequence shape: {jcross_energy_seq.shape}")
    print(f"[*] Output shape (Qwen soft prompts): {qwen_prompts.shape}")
