import os
import json

def clean_data():
    input_file = '/Users/motonishikoudai/verantyx-cli/arkit_reference.txt'
    output_file = '/Users/motonishikoudai/verantyx-cli/cli/scripts/arkit_clean.jsonl'
    
    ignore_lines = {
        'Skip Navigation', 'Swift.org', 'Blog', 'Download', 'Getting Started',
        'Documentation', 'The Swift Programming Language', 'Current page is'
    }
    
    cleaned_chunks = []
    current_chunk = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            
            # Skip empty lines or standard navigation garbage
            if not stripped:
                continue
            
            skip = False
            for ig in ignore_lines:
                if ig in stripped:
                    skip = True
                    break
                    
            if skip:
                # If we hit navigation headers, it usually means a section break.
                # Save the current chunk if it has enough content
                if current_chunk and len('\n'.join(current_chunk)) > 100:
                    cleaned_chunks.append('\n'.join(current_chunk))
                current_chunk = []
                continue
                
            current_chunk.append(line.rstrip())
            
            # Arbitrary chunking roughly every 20 lines to keep them manageable
            if len(current_chunk) > 20:
                cleaned_chunks.append('\n'.join(current_chunk))
                current_chunk = []
                
    if current_chunk and len('\n'.join(current_chunk)) > 100:
        cleaned_chunks.append('\n'.join(current_chunk))
        
    # Write to JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for chunk in cleaned_chunks:
            # We want to train on high quality chunks
            if len(chunk) > 100:
                f.write(json.dumps({'text': chunk}) + '\n')
                
    print(f"Cleaned {len(cleaned_chunks)} high-quality Swift/ARKit text blocks.")

if __name__ == '__main__':
    clean_data()
