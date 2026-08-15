import os

def get_all_notes_from_vault(vault_path):
    notes = []
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith('.md'):
                with open(os.path.join(root, file), encoding='utf-8', errors='ignore') as f:
                    notes.append({
                        "filename": os.path.relpath(os.path.join(root, file), vault_path),
                        "content": f.read()
                    })
    return notes

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python load_notes.py <vault_path>")
        exit(1)
    vault_path = sys.argv[1]
    notes = get_all_notes_from_vault(vault_path)
    print(f"Loaded {len(notes)} notes from {vault_path}.")
    for note in notes:
        print(f"\n--- {note['filename']} ---\n{note['content'][:500]}\n...")
