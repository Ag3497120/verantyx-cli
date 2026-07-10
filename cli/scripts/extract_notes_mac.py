import subprocess
import re
import os
import json

def get_all_notes():
    script = '''
    set output to ""
    tell application "Notes"
        set total to count of notes
        repeat with i from 1 to total
            try
                set noteText to plaintext of note i
                set output to output & "---NOTE---\\n" & noteText & "\\n"
            end try
        end repeat
    end tell
    return output
    '''
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error fetching notes: {e.stderr}")
        return ""

def sanitize_pii(text):
    # 1. API Keys & Tokens
    text = re.sub(r'sk-[A-Za-z0-9-_]{32,}', '[REDACTED_OPENAI_KEY]', text)
    text = re.sub(r'sk-ant-[A-Za-z0-9-_]+', '[REDACTED_ANTHROPIC_KEY]', text)
    text = re.sub(r'gh[pousr]_[A-Za-z0-9_]{36}', '[REDACTED_GITHUB_TOKEN]', text)
    text = re.sub(r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]', text)
    text = re.sub(r'Bearer\s+[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*', 'Bearer [REDACTED_TOKEN]', text)
    
    # 2. Credit Cards
    text = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[REDACTED_CREDIT_CARD]', text)
    
    # 3. Phone Numbers (Japanese & International)
    text = re.sub(r'\b0\d{1,4}[-(]?\d{1,4}[-)]?\d{3,4}\b', '[REDACTED_PHONE]', text)
    text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[REDACTED_PHONE]', text)
    
    # 4. Email Addresses
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[REDACTED_EMAIL]', text)
    
    # 5. Zip Codes (Japanese)
    text = re.sub(r'\b\d{3}-\d{4}\b', '[REDACTED_ZIP_CODE]', text)
    
    # 6. IPv4/IPv6 Addresses
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[REDACTED_IP]', text)
    
    # 7. Passwords (Heuristic: password=... or pass: ...)
    text = re.sub(r'(?i)(password|pass|pw)[\s:=]+[^\s]+', r'\1 [REDACTED_PASSWORD]', text)
    
    return text

def main():
    print("Extracting all notes from Apple Notes...")
    raw_notes = get_all_notes()
    
    if not raw_notes:
        print("No notes found or access denied.")
        return
        
    print("Sanitizing Personal Identifiable Information (PII) and Credentials...")
    sanitized_text = sanitize_pii(raw_notes)
    
    output_path = '/Users/motonishikoudai/verantyx-cli/verantyx_memo.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(sanitized_text)
        
    print(f"Successfully extracted and sanitized notes.")
    print(f"Saved to: {output_path}")
    print("NOTE: Please visually inspect the file to ensure unstructured names/addresses are removed.")

if __name__ == "__main__":
    main()
