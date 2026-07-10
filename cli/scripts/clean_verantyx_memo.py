import os
import json
import re

def sanitize_text(text):
    """
    Remove sensitive API keys and tokens from the text using Regex.
    """
    # OpenAI API Keys
    text = re.sub(r'sk-[A-Za-z0-9-_]{32,}', '[REDACTED_OPENAI_KEY]', text)
    # Anthropic API Keys
    text = re.sub(r'sk-ant-[A-Za-z0-9-_]+', '[REDACTED_ANTHROPIC_KEY]', text)
    # GitHub Tokens
    text = re.sub(r'gh[pousr]_[A-Za-z0-9_]{36}', '[REDACTED_GITHUB_TOKEN]', text)
    # AWS Access Key ID
    text = re.sub(r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]', text)
    # Bearer Tokens (General)
    text = re.sub(r'Bearer\s+[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*', 'Bearer [REDACTED_TOKEN]', text)
    
    return text

def clean_memo_data():
    input_file = '/Users/motonishikoudai/verantyx-cli/verantyx_memo.txt'
    output_file = '/Users/motonishikoudai/verantyx-cli/cli/scripts/verantyx_clean.jsonl'
    
    if not os.path.exists(input_file):
        print(f"Waiting for memo file: {input_file}")
        return
        
    cleaned_chunks = []
    current_chunk = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            
            # Skip massive blocks of empty lines
            if not stripped:
                if current_chunk:
                    # An empty line might mean a paragraph break. 
                    # If chunk is big enough, save it.
                    if len('\n'.join(current_chunk)) > 100:
                        chunk_text = '\n'.join(current_chunk)
                        chunk_text = sanitize_text(chunk_text)
                        cleaned_chunks.append(chunk_text)
                        current_chunk = []
                continue
                
            current_chunk.append(line.rstrip())
            
            # Arbitrary chunking roughly every 25 lines to keep context manageable
            if len(current_chunk) > 25:
                chunk_text = '\n'.join(current_chunk)
                chunk_text = sanitize_text(chunk_text)
                cleaned_chunks.append(chunk_text)
                current_chunk = []
                
    if current_chunk and len('\n'.join(current_chunk)) > 50:
        chunk_text = '\n'.join(current_chunk)
        chunk_text = sanitize_text(chunk_text)
        cleaned_chunks.append(chunk_text)
        
    # Write to JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for chunk in cleaned_chunks:
            f.write(json.dumps({'text': chunk}) + '\n')
                
    print(f"Sanitization complete! Masked API keys and extracted {len(cleaned_chunks)} clean knowledge blocks.")
    print(f"Output saved to {output_file}")

if __name__ == '__main__':
    clean_memo_data()
