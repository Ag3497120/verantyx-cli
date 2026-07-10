import torch
import os
import time

class MatrixUIDecoder:
    """
    Visual/UI Decoder that translates pure JCross tensor vectors into
    non-linguistic visual representations (Progress bars & HTML Heatmaps).
    Bypasses the symbol grounding problem by mapping latent energy directly to UI.
    """
    def __init__(self, html_export_path="/Users/motonishikoudai/verantyx-cli/cortex/verantyx-browser/brain_wave.html"):
        self.html_export_path = html_export_path
        self.history = []
        self.ensure_dir_exists()

    def ensure_dir_exists(self):
        dir_name = os.path.dirname(self.html_export_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

    def extract_features(self, current_vector: torch.Tensor, previous_vector: torch.Tensor = None):
        """
        Extracts spatial mathematics features from a JCross tensor.
        """
        with torch.no_grad():
            v = current_vector.detach().cpu().float().flatten()
            
            # Energy (Magnitude of thought)
            energy = torch.norm(v, p=2).item()
            
            # Variance (Complexity/Confusion level)
            variance = torch.var(v).item()
            
            # Bias (Positive/Negative sentiment or direction)
            bias = torch.mean(v).item()
            
            # Convergence (How much the thought has settled compared to previous)
            convergence = 0.0
            if previous_vector is not None:
                pv = previous_vector.detach().cpu().float().flatten()
                if torch.norm(v) > 0 and torch.norm(pv) > 0:
                    # Align dimensions for similarity matching
                    if v.shape[-1] < pv.shape[-1]:
                        v = torch.nn.functional.pad(v, (0, pv.shape[-1] - v.shape[-1]))
                    elif pv.shape[-1] < v.shape[-1]:
                        pv = torch.nn.functional.pad(pv, (0, v.shape[-1] - pv.shape[-1]))
                        
                    sim = torch.nn.functional.cosine_similarity(v.unsqueeze(0), pv.unsqueeze(0)).item()
                    # Map [-1, 1] to [0, 1] for progress bar
                    convergence = max(0.0, min(1.0, (sim + 1.0) / 2.0))
                else:
                    convergence = 0.5
            else:
                convergence = 0.1 # Initial state

            return {
                "energy": energy,
                "variance": variance,
                "bias": bias,
                "convergence": convergence,
                "timestamp": time.time()
            }

    def render_terminal_progress(self, role_name, features, color_code="\033[36m"):
        """
        Renders a dynamic progress bar for the terminal output.
        """
        bar_length = 20
        conv_percent = int(features["convergence"] * 100)
        filled_len = int(bar_length * features["convergence"])
        
        # Decide bar color based on bias and variance
        bar_color = "\033[92m" # Green (Stable)
        if features["variance"] > 1.5:
            bar_color = "\033[93m" # Yellow (High complexity/thinking)
        if features["bias"] < -0.1:
            bar_color = "\033[91m" # Red (Negative drift/Correction)
            
        bar = "█" * filled_len + "░" * (bar_length - filled_len)
        
        # Format the output string
        c_reset = "\033[0m"
        ui_str = f"{color_code}[{role_name}]{c_reset} 思考収束: {bar_color}[{bar}]{c_reset} {conv_percent:3d}% (Energy: {features['energy']:.1f}, Div: {features['variance']:.2f})"
        return ui_str

    def record_step(self, role_name, current_vector, previous_vector=None):
        """
        Records the current step features and updates the HTML UI.
        """
        features = self.extract_features(current_vector, previous_vector)
        self.history.append({
            "role": role_name,
            "features": features
        })
        self.export_html()
        return features

    def export_html(self):
        """
        Generates a sleek, dynamic HTML visualization of the swarm's brain waves.
        """
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verantyx Brain Wave Monitor</title>
            <style>
                body {
                    background-color: #0f172a;
                    color: #e2e8f0;
                    font-family: 'SF Pro Display', -apple-system, sans-serif;
                    padding: 2rem;
                }
                h1 {
                    color: #38bdf8;
                    text-align: center;
                    font-weight: 300;
                    letter-spacing: 0.1em;
                }
                .container {
                    max-width: 800px;
                    margin: 0 auto;
                }
                .wave-card {
                    background: #1e293b;
                    border-radius: 8px;
                    padding: 1.5rem;
                    margin-bottom: 1rem;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                    border-left: 4px solid #38bdf8;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }
                .role-name {
                    font-weight: bold;
                    width: 120px;
                }
                .progress-container {
                    flex-grow: 1;
                    margin: 0 1.5rem;
                    background: #334155;
                    height: 12px;
                    border-radius: 6px;
                    overflow: hidden;
                }
                .progress-bar {
                    height: 100%;
                    transition: width 0.3s ease;
                }
                .stats {
                    font-size: 0.85rem;
                    color: #94a3b8;
                    width: 180px;
                    text-align: right;
                }
            </style>
            <script>
                // Auto-refresh the page to show real-time updates
                setTimeout(function(){
                   window.location.reload(1);
                }, 1000);
            </script>
        </head>
        <body>
            <h1>VERANTYX 🧠 BRAIN WAVE MONITOR</h1>
            <div class="container">
        """
        
        # Render each history item
        for item in self.history[-20:]: # Show last 20 steps
            role = item["role"]
            feat = item["features"]
            conv_pct = feat["convergence"] * 100
            
            # Determine color
            color = "#22c55e" # Green
            if feat["variance"] > 1.5: color = "#eab308" # Yellow
            if feat["bias"] < -0.1: color = "#ef4444" # Red
            
            html_content += f"""
                <div class="wave-card" style="border-left-color: {color};">
                    <div class="role-name">{role}</div>
                    <div class="progress-container">
                        <div class="progress-bar" style="width: {conv_pct}%; background-color: {color}; box-shadow: 0 0 10px {color};"></div>
                    </div>
                    <div class="stats">
                        {conv_pct:.0f}% Conv | E: {feat["energy"]:.1f}
                    </div>
                </div>
            """
            
        html_content += """
            </div>
        </body>
        </html>
        """
        
        try:
            with open(self.html_export_path, "w", encoding="utf-8") as f:
                f.write(html_content)
        except Exception as e:
            pass # Ignore export errors during fast loops
