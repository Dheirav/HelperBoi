"""
Interest/Topic Enhancement Features for Jarvis
- Visualization (word cloud, bar chart)
- Change tracking
- Interest-to-note mapping
- Grouping/clustering
- Export/sharing
- Recommendations
- Tagging automation
- Interest-driven summaries
- Reminders/tasks
- Similarity search
"""
import os
import json
import re
from collections import defaultdict, Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt


# --- 1. Visualization ---
def visualize_interests(interests, out_path="interest_wordcloud.png"):
    text = " ".join(interests)
    wc = WordCloud(width=800, height=400, background_color='white').generate(text)
    wc.to_file(out_path)
    print(f"[Interest Visualization] Word cloud saved to {out_path}")

def plot_interest_barchart(interests, out_path="interest_barchart.png", top_k=20):
    counts = Counter(interests)
    top = counts.most_common(top_k)
    labels, values = zip(*top)
    plt.figure(figsize=(10, 5))
    plt.barh(labels[::-1], values[::-1])
    plt.xlabel('Frequency')
    plt.title('Top Interests/Topics')
    plt.tight_layout()
    plt.savefig(out_path)
    print(f"[Interest Visualization] Bar chart saved to {out_path}")

# --- 2. Change Tracking ---
def save_interest_snapshot(interests, snapshot_dir="memory/interest_snapshots"):
    os.makedirs(snapshot_dir, exist_ok=True)
    from datetime import datetime
    fname = os.path.join(snapshot_dir, f"interests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(interests, f, indent=2)
    print(f"[Interest Tracking] Snapshot saved: {fname}")

def list_interest_snapshots(snapshot_dir="memory/interest_snapshots"):
    if not os.path.exists(snapshot_dir):
        return []
    return sorted([os.path.join(snapshot_dir, f) for f in os.listdir(snapshot_dir) if f.endswith('.json')])

# --- 3. Interest-to-Note Mapping ---
def map_interests_to_notes(interests, notes):
    mapping = defaultdict(list)
    for note in notes:
        for topic in interests:
            if topic.lower() in note['content'].lower():
                mapping[topic].append(note['filename'])
    return dict(mapping)

# --- 4. Grouping/Clustering (simple string similarity) ---
def group_similar_interests(interests, threshold=0.7):
    from difflib import SequenceMatcher
    groups = []
    for topic in interests:
        found = False
        for group in groups:
            if SequenceMatcher(None, topic, group[0]).ratio() > threshold:
                group.append(topic)
                found = True
                break
        if not found:
            groups.append([topic])
    return groups

# --- 5. Export/Sharing ---
def export_interests(interests, out_path="interests_export.json"):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(interests, f, indent=2)
    print(f"[Interest Export] Exported to {out_path}")

def export_interest_mapping(mapping, out_path="interest_note_mapping.json"):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)
    print(f"[Interest Export] Mapping exported to {out_path}")

# --- 6. Recommendations ---
def recommend_notes_for_interest(interest, mapping, notes, top_k=5):
    note_files = mapping.get(interest, [])
    note_objs = [n for n in notes if n['filename'] in note_files]
    # Recommend longest, most-linked, or most-recent notes (simple: longest)
    note_objs.sort(key=lambda n: len(n['content']), reverse=True)
    return note_objs[:top_k]

# --- 7. Tagging Automation ---
def auto_tag_notes_with_interests(notes, interests):
    for note in notes:
        tags = set(re.findall(r'#\w+', note['content']))
        for topic in interests:
            tag = '#' + topic.replace(' ', '_').lower()
            if tag not in tags and topic.lower() in note['content'].lower():
                note['content'] += f"\n{tag}"
    print("[Tagging] Notes auto-tagged with detected interests.")
    return notes

# --- 8. Interest-Driven Summaries ---
def summarize_notes_by_interest(interest, notes):
    relevant = [n for n in notes if interest.lower() in n['content'].lower()]
    summary = f"Summary for interest '{interest}':\n"
    for note in relevant:
        summary += f"- {note['filename']}: {note['content'][:120].replace('\n',' ')}...\n"
    return summary

# --- 9. Reminders/Tasks ---
def find_stale_interests(mapping, notes, days_stale=90):
    from datetime import datetime
    stale = []
    for topic, files in mapping.items():
        latest = None
        for fname in files:
            note = next((n for n in notes if n['filename'] == fname), None)
            if note and 'modified' in note:
                dt = datetime.fromisoformat(note['modified'])
                if not latest or dt > latest:
                    latest = dt
        if not latest or (datetime.now() - latest).days > days_stale:
            stale.append(topic)
    return stale

# --- 10. Similarity Search ---
def find_similar_interests(query, interests, threshold=0.6):
    from difflib import SequenceMatcher
    return [i for i in interests if SequenceMatcher(None, query, i).ratio() > threshold]

# --- 11. Detect Interests (for compatibility with test and CLI) ---
def detect_interests(notes):
    """Detect interests/topics from a dict of {filename: content}. Returns a list of keywords."""
    from collections import Counter
    import re
    all_text = " ".join(notes.values()).lower()
    # Simple keyword extraction: words longer than 3 chars, not stopwords
    stopwords = set(["the", "and", "for", "with", "that", "this", "from", "have", "are", "was", "but", "not", "you", "all", "can", "has", "will", "one", "about", "your", "out", "get", "use", "just", "like", "now", "more", "some", "what", "when", "then", "than", "how", "why", "who", "which", "their", "them", "they", "his", "her", "him", "she", "our", "were", "had", "did", "its", "may", "also", "any", "each", "per", "new", "see", "too", "let", "via", "etc"])
    words = [w for w in re.findall(r"\b\w{4,}\b", all_text) if w not in stopwords]
    freq = Counter(words)
    # Return top 10 interests
    return [w for w, _ in freq.most_common(10)]

# --- Utility: Load notes from vault ---
def load_notes_from_vault(vault_path):
    from modules.load_notes import get_all_notes_from_vault
    return get_all_notes_from_vault(vault_path)

# --- Utility: Load interests from memory ---
def load_detected_interests():
    with open('memory/assistant_context.json', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('preferences', {}).get('detected_interests', [])

# --- Utility: Load mapping from file ---
def load_interest_mapping(path="interest_note_mapping.json"):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)
