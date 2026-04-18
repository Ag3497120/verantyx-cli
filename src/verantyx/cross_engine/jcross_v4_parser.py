import re
from typing import List, Dict, Optional
from datetime import datetime

class JCrossNode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.ontology_tags: Dict[str, float] = {}  # e.g., {"視": 0.9, "探": 1.0}
        self.concept: str = ""
        self.timestamp: Optional[str] = None
        self.relations: List[Dict[str, str]] = []  # e.g., [{"target": "...", "type": "基底", "strength": 0.9}]
        self.abstraction: float = 0.5
        self.env_hash: str = ""
        self.reflection: str = ""
        self.payload: str = ""

class JCrossParser:
    @staticmethod
    def parse(content: str) -> List[JCrossNode]:
        nodes = []
        # Split by node declaration
        raw_nodes = re.split(r'^■ JCROSS_NODE_', content, flags=re.MULTILINE)[1:]
        
        for raw_node in raw_nodes:
            lines = raw_node.strip().split('\n')
            if not lines: continue
            
            node_id = lines[0].strip()
            node = JCrossNode(node_id)
            
            current_section = None
            payload_lines = []
            
            for line in lines[1:]:
                line = line.strip()
                
                # Section detection
                if line.startswith('【') and line.endswith('】'):
                    current_section = line[1:-1]
                    continue
                elif line == '[本質記憶]':
                    current_section = "payload"
                    continue
                elif line == '===':
                    break # End of node
                    
                # Parsing logic based on section
                if current_section == "空間座相":
                    tags = re.findall(r'\[(.*?):([\d.]+)\]', line)
                    for tag, weight in tags:
                        node.ontology_tags[tag] = float(weight)
                        
                elif current_section == "次元概念":
                    if line: node.concept = line
                        
                elif current_section == "時間刻印":
                    if line: node.timestamp = line
                        
                elif current_section == "連帯":
                    if line:
                        parts = line.split(':')
                        if len(parts) == 3:
                            node.relations.append({
                                "target": parts[0],
                                "type": parts[1],
                                "strength": parts[2]
                            })
                            
                elif current_section == "抽象度":
                    if line:
                        try: node.abstraction = float(line.strip('<>'))
                        except ValueError: pass
                        
                elif current_section == "環境刻印":
                    if line: node.env_hash = line
                        
                elif current_section == "反射":
                    if line: node.reflection += line + "\n"
                        
                elif current_section == "payload":
                    # For payload, we want to keep original formatting (within reason)
                    payload_lines.append(line)
            
            node.payload = '\n'.join(payload_lines)
            nodes.append(node)
            
        return nodes

    @staticmethod
    def serialize(node: JCrossNode) -> str:
        out = [f"■ JCROSS_NODE_{node.node_id}\n"]
        
        out.append("【空間座相】")
        tags_str = " ".join([f"[{k}:{v}]" for k, v in node.ontology_tags.items()])
        out.append(f"{tags_str}\n")
        
        out.append("【次元概念】")
        out.append(f"{node.concept}\n")
        
        if node.timestamp:
            out.append("【時間刻印】")
            out.append(f"{node.timestamp}\n")
            
        if node.relations:
            out.append("【連帯】")
            for rel in node.relations:
                out.append(f"{rel['target']}:{rel['type']}:{rel['strength']}")
            out.append("")
            
        out.append("【抽象度】")
        out.append(f"<{node.abstraction}>\n")
        
        if node.env_hash:
            out.append("【環境刻印】")
            out.append(f"{node.env_hash}\n")
            
        if node.reflection:
            out.append("【反射】")
            out.append(f"{node.reflection}\n")
            
        out.append("---\n[本質記憶]")
        out.append(node.payload)
        out.append("===\n")
        
        return "\n".join(out)
