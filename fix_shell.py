import sys

filename = '/Users/motonishikoudai/verantyx-cli/cli/scripts/verantyx_shell.py'
with open(filename, 'r') as f:
    lines = f.readlines()

new_lines = []
in_scout_try = False

for i, line in enumerate(lines):
    if "try:" in line and "scout_brain2 = JCrossBrain" in lines[i+1]:
        # tryブロックを閉じるようにする
        new_lines.append(line)
        in_scout_try = True
        continue
    
    if in_scout_try and "print(f\"\\n============================================================\")" in line:
        in_scout_try = False
        # Scoutのtryブロックをここで閉じる
        new_lines.append("                    except Exception as e:\n")
        new_lines.append("                        print(f\"  [\\033[31mError\\033[0m] Scout Execution Failed: {e}\")\n")
        new_lines.append("                    break\n") # whileループを抜ける
        
        # Code Synthesisはwhileループの外に出すため、インデントを16スペースにする
        indent = "                "
        new_lines.append(indent + "if action_vector is not None:\n")
        new_lines.append(indent + "    print(f\"\\n============================================================\")\n")
        continue

    if not in_scout_try and "print(f\"\\n============================================================\")" in line:
        pass # すでに処理済み
        
    if "print(f\"[\\033[95mVerantyx Code Synthesis\\033[0m]" in line or \
       "print(f\"============================================================\\n\")" in line or \
       "print(f\"  [\\033[94mTelepathic Coder\\033[0m] Receiving final Executable Latent vector" in line or \
       "final_tool, final_sim = action_space.match_action(action_vector)" in line or \
       "inferred_code = global_coder.synthesize_code(action_vector, subtask_prompt=subtask)" in line or \
       "if final_tool == \"discuss\" or \"```\" not in inferred_code:" in line or \
       "print(f\"  [\\033[94mTelepathic Coder\\033[0m] Spatial intent resolved" in line or \
       "ext = \".txt\"" in line or \
       "user_input_lower = user_input.lower()" in line or \
       "if \"c++\" in user_input_lower" in line or \
       "elif \"python\" in user_input_lower" in line or \
       "elif \"swift\" in user_input_lower" in line or \
       "elif \"javascript\" in user_input_lower" in line or \
       "elif \"typescript\" in user_input_lower" in line or \
       "elif \"rust\" in user_input_lower" in line or \
       "elif \"go\" in user_input_lower" in line or \
       "elif \"html\" in user_input_lower" in line or \
       "output_filename = f\"verantyx_synthesis_task{subtask_idx+1}{ext}\"" in line or \
       "with open(os.path.join(workspace_dir, output_filename), \"w\") as f:" in line or \
       "f.write(inferred_code)" in line or \
       "print(f\"  [\\033[94mTelepathic Coder\\033[0m] Decoding successful" in line or \
       "purge_memory()" in line or \
       "except Exception as e:" in line or \
       "import traceback" in line or \
       "print(f\"  [\\033[31mError\\033[0m] Coder Synthesis Failed: {e}\")" in line or \
       "traceback.print_exc()" in line or \
       "print(\"  [\\033[32mSwarm\\033[0m] Subtask declared complete. Moving to next subtask if any.\")" in line or \
       "intent_vector = action_vector.clone()" in line or \
       line.strip() == "break" and "intent_vector = action_vector.clone()" in lines[i-1]:
       
        # インデントを16スペースに揃える
        if line.strip() == "":
            new_lines.append("\n")
        else:
            # 既存のインデントを無視して16スペース+本来のインデントにする
            stripped = line.lstrip()
            # if, elif, with, print, except などで多少インデントが変わるが、ここは元のGitに合わせて置換
            if "except Exception as e:" in stripped:
                new_lines.append("                except Exception as e:\n")
            elif "import traceback" in stripped or "traceback.print_exc()" in stripped or "print(f\"  [\\033[31mError\\033[0m] Coder Synthesis" in stripped:
                new_lines.append("                    " + stripped + "\n")
            elif "print(\"  [\\033[32mSwarm" in stripped or "intent_vector =" in stripped:
                new_lines.append("                " + stripped + "\n")
            elif stripped == "break":
                # このbreakは不要（forループを抜けてしまうため）
                pass
            else:
                # Code Synthesis内は try で囲む
                if "print(f\"\\n=================" in line:
                    pass
                else:
                    new_lines.append("                try:\n" if "inferred_code =" in stripped else "")
                    new_lines.append("                    " + stripped + "\n")
        continue

    new_lines.append(line)

with open(filename, 'w') as f:
    f.writelines(new_lines)

print("Fixed shell.")
