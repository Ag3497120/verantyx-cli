import os
import re
import json

def scan_directory(target_dir: str):
    nodes = []
    links = []
    file_map = {}
    
    # 拡張子のフィルタ
    valid_exts = {'.py', '.js', '.ts', '.html', '.css', '.md', '.json'}
    
    # Step 1: Collect Nodes
    for root, _, files in os.walk(target_dir):
        # 隠しディレクトリや環境ディレクトリを除外
        if any(part.startswith('.') or part in ('node_modules', 'venv', '__pycache__') for part in root.split(os.sep)):
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in valid_exts or file == 'Makefile':
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, target_dir)
                node_id = rel_path
                
                # Determine group by extension
                group = 1
                if ext in ('.py',): group = 2
                elif ext in ('.js', '.ts'): group = 3
                elif ext in ('.html', '.css'): group = 4
                
                nodes.append({"id": node_id, "group": group, "name": file})
                file_map[node_id] = file_path

    # Step 2: Very Basic Dependency Extraction (Heuristic)
    for node in nodes:
        file_path = file_map[node['id']]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Simple regex for finding potential file references
                # This is just a visual scaffold, accuracy is secondary to aesthetic representation
                for other_node in nodes:
                    if node['id'] != other_node['id']:
                        base_name = os.path.splitext(other_node['name'])[0]
                        # Look for exact basename matches in imports/requires
                        if re.search(r'\b(import|require|from).*?\b' + re.escape(base_name) + r'\b', content):
                            links.append({"source": node['id'], "target": other_node['id'], "value": 1})
        except Exception:
            pass

    return {"nodes": nodes, "links": links}

def generate_base_scaffold(target_dir: str, output_html_path: str):
    """
    Generates a D3.js Force-Directed Graph representing the project's dependency structure.
    This serves as the 'Visual Scaffold' where AI can later inject dynamic animations
    (pulsing red for errors, active data streams) without using words.
    """
    graph_data = scan_directory(target_dir)
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verantyx Visual Scaffold (D3.js)</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #0b0c10;
            color: #c5c6c7;
            font-family: 'Inter', -apple-system, sans-serif;
            overflow: hidden;
        }}
        #graph-container {{
            width: 100vw;
            height: 100vh;
        }}
        .node text {{
            pointer-events: none;
            font-size: 10px;
            fill: #c5c6c7;
            opacity: 0.8;
        }}
        .link {{
            stroke: #1f2833;
            stroke-opacity: 0.6;
        }}
        .node circle {{
            stroke: #45a29e;
            stroke-width: 1.5px;
            cursor: pointer;
            transition: r 0.2s, fill 0.2s;
        }}
        .node circle:hover {{
            stroke: #66fcf1;
            stroke-width: 3px;
        }}
        #info-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            width: 300px;
            background: rgba(31, 40, 51, 0.9);
            border: 1px solid #45a29e;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            backdrop-filter: blur(5px);
            display: none;
        }}
        h2 {{ margin-top: 0; color: #66fcf1; font-size: 16px; font-weight: normal; }}
        .pulse {{
            animation: pulse-animation 2s infinite;
        }}
        @keyframes pulse-animation {{
            0% {{ filter: drop-shadow(0 0 5px #ff003c); }}
            50% {{ filter: drop-shadow(0 0 20px #ff003c); fill: #ff003c; stroke: #ff003c; }}
            100% {{ filter: drop-shadow(0 0 5px #ff003c); }}
        }}
        .progress-bar-container {{
            width: 100%;
            height: 4px;
            background: #0b0c10;
            border-radius: 2px;
            margin-top: 15px;
            overflow: hidden;
        }}
        .progress-bar {{
            width: 0%;
            height: 100%;
            background: #66fcf1;
            transition: width 0.1s linear;
        }}
    </style>
    <!-- Load D3.js -->
    <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
    <div id="graph-container"></div>
    
    <!-- AI Output Canvas (Silent Communication Panel) -->
    <div id="info-panel">
        <h2 id="node-title">Node</h2>
        <div style="font-size: 12px; margin-top: 10px; color: #888;">
            Latency Waveform: <span id="node-wave">...</span>
        </div>
        <div class="progress-bar-container">
            <div id="node-progress" class="progress-bar"></div>
        </div>
    </div>

    <script>
        const graphData = {json.dumps(graph_data)};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#graph-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }}))
            .append("g");
            
        const g = svg.append("g");
            
        const simulation = d3.forceSimulation()
            .force("link", d3.forceLink().id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
            
        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(graphData.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.value));
            
        // Colors by group
        const colorScale = d3.scaleOrdinal()
            .domain([1, 2, 3, 4])
            .range(["#c5c6c7", "#45a29e", "#66fcf1", "#1f2833"]);
            
        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll("g")
            .data(graphData.nodes)
            .enter().append("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
                
        node.append("circle")
            .attr("r", 8)
            .attr("fill", d => colorScale(d.group))
            .on("click", handleNodeClick);
            
        node.append("text")
            .attr("dx", 12)
            .attr("dy", ".35em")
            .text(d => d.name);
            
        simulation
            .nodes(graphData.nodes)
            .on("tick", ticked);
            
        simulation.force("link")
            .links(graphData.links);
            
        function ticked() {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
                
            node
                .attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }}
        
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        // --- The Silent Architect Hook ---
        // This function simulates the non-verbal AI interaction.
        let progressInterval;
        function handleNodeClick(event, d) {{
            const panel = document.getElementById("info-panel");
            panel.style.display = "block";
            document.getElementById("node-title").innerText = d.id;
            
            // AI Action Simulation: Inject class to pulse node visually
            d3.selectAll("circle").classed("pulse", false);
            d3.select(this).classed("pulse", true);
            
            // Animate progress bar (Latency wave simulation)
            clearInterval(progressInterval);
            let p = 0;
            const pBar = document.getElementById("node-progress");
            const wave = document.getElementById("node-wave");
            
            progressInterval = setInterval(() => {{
                p += Math.random() * 10;
                if (p > 100) p = 100;
                pBar.style.width = p + "%";
                wave.innerText = `[${{Math.random().toFixed(4)}}]`;
                if (p === 100) clearInterval(progressInterval);
            }}, 50);
        }}
    </script>
</body>
</html>
"""
    
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    return f"[Visual Scaffold] Dependency graph rendered to {output_html_path}"
