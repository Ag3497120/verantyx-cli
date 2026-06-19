import sys
import argparse
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging
import json

import swarm_harness
from swarm_socket_util import send_tensor_socket, recv_tensor_socket, create_server_socket, connect_to_server

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='[Node %(name)s] %(message)s')

MODEL_ID = "Qwen/Qwen1.5-0.5B"

SYSTEM_PROMPT_WORKER = """You are a node in a Swarm. You can use tools if necessary to complete the task.
To use a tool, output exactly: [TOOL_CALL] {"action": "read_file", "path": "filename"} [/TOOL_CALL]
Available actions: read_file, write_file, list_directory
If you do not need tools, just continue thinking or output the final result."""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node_id", type=int, required=True, help="Node ID (0=Commander, 1-8=Worker, 9=Final, 100+=SubCommander)")
    parser.add_argument("--role", type=str, required=True, choices=["commander", "worker", "final", "sub_commander"])
    parser.add_argument("--listen_port", type=int, required=True)
    parser.add_argument("--send_port", type=int, required=True)
    parser.add_argument("--persona", type=str, default="", help="System prompt for sub_commanders")
    args = parser.parse_args()
    
    node_id = args.node_id
    role = args.role
    logger = logging.getLogger(f"{role}_{node_id}")
    logger.info("Initializing...")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map=device,
        low_cpu_mem_usage=True
    )
    model.eval()
    for param in model.parameters():
        param.requires_grad = False

    logger.info(f"Ready. Listening on port {args.listen_port}, sending to port {args.send_port}")

    server_sock = create_server_socket(args.listen_port)
    
    while True:
        conn, addr = server_sock.accept()
        logger.info(f"Accepted connection from {addr}")

        if role == "sub_commander":
            data = conn.recv(16384).decode('utf-8')
            if not data:
                break
            prompt = data.strip()
            
            full_prompt = f"{args.persona}\\nUser: {prompt}\\nAssistant:"
            inputs = tokenizer(full_prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_new_tokens=200, pad_token_id=tokenizer.eos_token_id)
            
            input_length = inputs.input_ids.shape[1]
            response = tokenizer.decode(generated_ids[0][input_length:], skip_special_tokens=True)
            
            send_sock = connect_to_server(args.send_port)
            send_sock.sendall(response.encode('utf-8'))
            send_sock.close()
            
        elif role == "commander":
            data = conn.recv(32768).decode('utf-8')
            if not data:
                break
            
            try:
                req = json.loads(data)
                req_type = req.get("type", "execute")
                prompt = req.get("prompt", "")
                dyn_send_port = req.get("send_port", args.send_port)
            except:
                req_type = "execute"
                prompt = data.strip()
                dyn_send_port = args.send_port
            
            if req_type == "merge":
                logger.info("Commander: Merging discussion...")
                sys_prompt = "Merge the plans of Sub-Commanders. If logical errors exist, output [RE-DISCUSS] <reason>. Else output final plan."
                full_prompt = f"{sys_prompt}\\n\\n{prompt}\\n\\nMerged Plan or [RE-DISCUSS]:"
                inputs = tokenizer(full_prompt, return_tensors="pt").to(device)
                
                with torch.no_grad():
                    generated_ids = model.generate(**inputs, max_new_tokens=300, pad_token_id=tokenizer.eos_token_id)
                input_length = inputs.input_ids.shape[1]
                response = tokenizer.decode(generated_ids[0][input_length:], skip_special_tokens=True)
                
                send_sock = connect_to_server(dyn_send_port)
                send_sock.sendall(response.encode('utf-8'))
                send_sock.close()
                
            elif req_type == "execute":
                logger.info("Commander: Executing vector.")
                full_prompt = f"{SYSTEM_PROMPT_WORKER}\\nUser Plan: {prompt}\\nAssistant:"
                inputs = tokenizer(full_prompt, return_tensors="pt").to(device)
                with torch.no_grad():
                    outputs = model(**inputs, output_hidden_states=True)
                    initial_hidden = outputs.hidden_states[-1]
                
                send_sock = connect_to_server(dyn_send_port)
                send_tensor_socket(initial_hidden, send_sock)
                send_sock.close()

        elif role == "worker":
            send_sock = connect_to_server(args.send_port)
            hidden_states = recv_tensor_socket(conn, device)
            if hidden_states is not None:
                with torch.no_grad():
                    generated_ids = model.generate(inputs_embeds=hidden_states, max_new_tokens=40, pad_token_id=tokenizer.eos_token_id)
                    text_intention = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
                    tool_req = swarm_harness.parse_tool_call(text_intention)
                    
                    if tool_req:
                        rpc_request = {"jsonrpc": "2.0", "method": tool_req["action"], "params": tool_req, "id": node_id}
                        sys.stdout.write(json.dumps(rpc_request) + "\\n")
                        sys.stdout.flush()
                        try:
                            tool_result = json.loads(sys.stdin.readline()).get("result", "Error")
                        except Exception as e:
                            tool_result = f"Error: {e}"
                        
                        result_text = f"\\n[TOOL_RESULT] {tool_result} [/TOOL_RESULT]\\n"
                        result_inputs = tokenizer(result_text, return_tensors="pt").to(device)
                        result_embeds = model.get_input_embeddings()(result_inputs.input_ids)
                        new_hidden = torch.cat([hidden_states, result_embeds], dim=1)
                    else:
                        outputs = model(inputs_embeds=hidden_states, output_hidden_states=True)
                        new_hidden = outputs.hidden_states[-1]
                
                send_tensor_socket(new_hidden, send_sock)
            send_sock.close()

        elif role == "translator":
            # 翻訳役（最終文章の生成役）：テレパシーで直前のワーカーからテンソルを受信
            send_sock = connect_to_server(args.send_port)
            hidden_states = recv_tensor_socket(conn, device)
            
            if hidden_states is not None:
                logger.info("Translator: Received telepathy tensor. Applying high-fidelity (low-compression) reconstruction...")
                
                # 高度な圧縮を抑えて破損を防ぐ（テンソルのL2正規化によるスケール安定化と精度保持）
                # テンソルが大きくなりすぎないようにスケールを整えることで、文字化けや暴走を防ぐ
                norm = hidden_states.norm(p=2, dim=-1, keepdim=True)
                stabilized_hidden = hidden_states / torch.clamp(norm, min=1e-5) * (hidden_states.size(-1) ** 0.5)
                
                # 翻訳・文章生成に特化した強力な逆投影（Inverse Topology）アンカー
                inverse_prompt = "<|im_start|>system\\nYou are the Translator and Final Output Generator. Convert the given corrupted thought vector into highly fluent, clear, and perfectly grammatical natural language without any formatting errors or gibberish. Maintain the exact original intention.<|im_end|>\\n<|im_start|>assistant\\n"
                inverse_inputs = tokenizer(inverse_prompt, return_tensors="pt").to(device)
                inverse_embeds = model.get_input_embeddings()(inverse_inputs.input_ids)
                
                # アンカーテンソルと思考テンソルを結合し、高精度（低圧縮）のまま文章生成へ移行
                combined_embeds = torch.cat([inverse_embeds, stabilized_hidden], dim=1)
                
                with torch.no_grad():
                    # 翻訳に特化した生成パラメータ（幻覚や暴走を抑える）
                    generated_ids = model.generate(
                        inputs_embeds=combined_embeds,
                        max_new_tokens=500,
                        pad_token_id=tokenizer.eos_token_id,
                        temperature=0.3,
                        top_p=0.9,
                        repetition_penalty=1.1,
                        do_sample=True
                    )
                
                text = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
                send_sock.sendall(text.encode('utf-8'))
            send_sock.close()

        elif role == "final":
            send_sock = connect_to_server(args.send_port)
            hidden_states = recv_tensor_socket(conn, device)
            if hidden_states is not None:
                with torch.no_grad():
                    generated_ids = model.generate(inputs_embeds=hidden_states, max_new_tokens=100, pad_token_id=tokenizer.eos_token_id)
                text = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
                send_sock.sendall(text.encode('utf-8'))
            send_sock.close()

        conn.close()
        
        if role in ["worker", "final"]:
            break

if __name__ == "__main__":
    main()
