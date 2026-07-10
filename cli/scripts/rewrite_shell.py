import sys

filename = '/Users/motonishikoudai/verantyx-cli/cli/scripts/verantyx_shell.py'
with open(filename, 'r') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "while step_count < max_steps:" in line and "matrix_ui =" in lines[i-2]:
        start_idx = i
    if "del scout_brain2" in line and start_idx != -1 and end_idx == -1:
        end_idx = i
        break

if start_idx == -1 or end_idx == -1:
    print(f"Indices not found. start={start_idx}, end={end_idx}")
    sys.exit(1)

new_lines = []
new_lines.extend(lines[:start_idx])

# Insert RPC logic
new_lines.append("                if args.cluster_mode == 'master' and rpc is not None:\n")
new_lines.append("                    print(f\"  [\\033[36mThunderbolt RPC\\033[0m] Offloading Swarm Debate to Worker Node...\")\n")
new_lines.append("                    intent_vector = global_coder.align_intent(intent_vector, original_prompt=subtask)\n")
new_lines.append("                    rpc.send_tensor(intent_vector)\n")
new_lines.append("                    print(f\"  [\\033[36mThunderbolt RPC\\033[0m] Waiting for Worker to finish thinking...\")\n")
new_lines.append("                    action_vector = rpc.recv_tensor(dtype=torch.float16, shape=(1, 3840), device=device)\n")
new_lines.append("                    if action_vector is None:\n")
new_lines.append("                        print(f\"  [\\033[31mError\\033[0m] Worker disconnected.\")\n")
new_lines.append("                        break\n")
new_lines.append("                else:\n")

# Indent the original while loop
for i in range(start_idx, end_idx + 1):
    new_lines.append("    " + lines[i])

new_lines.extend(lines[end_idx+1:])

with open(filename, 'w') as f:
    f.writelines(new_lines)

print("Rewritten successfully.")
