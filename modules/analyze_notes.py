import re
from collections import Counter
from modules.load_notes import get_all_notes_from_vault
from modules.memory import StructureStyleMemory
from modules.input_processing import note_density, avg_sentence_length, lexical_diversity, top_ngrams
import concurrent.futures
import time
import os
import datetime

# --- CONFIGURABLE BATCHING FOR SPEED ---
ANALYZE_NOTES_CONFIG = {
    'BATCH_SIZE': 20000,      # Default batch size
    'OVERLAP': 500,         # Overlap to preserve context between batches
    'DRY_RUN': False,        # Set to True to always run dry run simulation and skip analysis
    'MIN_BATCH': 8000,       # Minimum batch size for simulation
    'MAX_BATCH': 1087998,     # Maximum batch size for simulation
    'STEP': 8000,            # Step size for simulation
    'SIM_OVERLAP': 2000,     # Overlap for simulation
    'CHARS_PER_SEC': 484,     # Empirically measured LLM throughput (chars/sec)
    'NUM_PARALLEL': 4,     # Number of parallel workers for LLM calls
}

# --- Update config from analysis history (max batch size, chars/sec) ---
def update_config_from_history(config):
    mem = StructureStyleMemory()
    history = mem.get_preference('analysis_history') or []
    max_batch = config.get('BATCH_SIZE', 20000)
    chars_per_sec = config.get('CHARS_PER_SEC', 484)
    # Find max batch size and most recent/average corrected_chars_per_sec
    batch_sizes = []
    chars_per_secs = []
    for run in history:
        # Try to get batch size from run (if present)
        if 'batch_size' in run:
            batch_sizes.append(run['batch_size'])
        # Try to get corrected_chars_per_sec from run (if present)
        if 'corrected_chars_per_sec' in run:
            chars_per_secs.append(run['corrected_chars_per_sec'])
    if batch_sizes:
        max_batch = max(batch_sizes)
        config['BATCH_SIZE'] = max_batch
    if chars_per_secs:
        # Use most recent, or average if you prefer
        config['CHARS_PER_SEC'] = chars_per_secs[-1]
    print(f"[CONFIG] Updated BATCH_SIZE from history: {config['BATCH_SIZE']}")
    print(f"[CONFIG] Updated CHARS_PER_SEC from history: {config['CHARS_PER_SEC']}")
    return config

def simulate_optimal_batching(all_text, config=ANALYZE_NOTES_CONFIG):
    """
    Simulate batching for a given vault and print optimal batch size/overlap for speed vs. context.
    Estimate total LLM time for each config using chars per batch and LLM throughput.
    Overlap is set dynamically as a percentage of batch size.
    """
    print("\n[DRY RUN] Simulating batch sizes for optimal LLM analysis speed...")
    best = None
    best_batches = None
    best_time = None
    best_parallel_time = None
    min_batch = config.get('MIN_BATCH', 8000)
    max_batch = config.get('MAX_BATCH', 128000)
    step = config.get('STEP', 8000)
    chars_per_sec = config.get('CHARS_PER_SEC', 50)
    overlap_pct = config.get('OVERLAP_PCT', 0.1)  # 10% default
    # Tiny-vault fast path: avoid printing hundreds of simulated lines for very small input.
    if len(all_text) <= min_batch:
        import math
        overlap = int(min_batch * (0.1 + 0.05 * math.log10(2)))
        est_parallel_time = 0
        print(f"  Batch size: {min_batch:6d} | Overlap: {overlap:6d} | Batches:   1 | Avg chars/batch: {len(all_text)} | Est. total time: 0m 0s (0.0 min) | Est. parallel: 0m 0s (0.0 min) [{config.get('NUM_PARALLEL', 4)} threads]")
        print(f"\n[DRY RUN] Recommended batch_size for parallel speed: {min_batch} (batches: 1) | Est. parallel time: 0m 0s (0.0 min)")
        print(f"[DRY RUN] Best batch size: {min_batch} | Use this value for optimal parallel speed with your current config and LLM throughput.")
        config['BATCH_SIZE'] = min_batch
        return min_batch, 1, est_parallel_time

    # Bound search range by input size to avoid excessive simulation output.
    dynamic_max = max(min_batch, min(max_batch, len(all_text) * 8))
    max_batch = dynamic_max
    for batch_size in range(min_batch, max_batch+1, step):
        # Calculate overlap logarithmically, no min/max limit
        import math
        overlap = int(batch_size * (0.1 + 0.05 * math.log10(batch_size / min_batch + 1)))
        batches = []
        i = 0
        while i < len(all_text):
            end = i + batch_size
            if end < len(all_text):
                # Move end back to last whitespace to avoid breaking a word
                while end > i and not all_text[end-1].isspace():
                    end -= 1
                if end == i:
                    end = i + batch_size  # fallback: force split if no whitespace
            batch = all_text[i:end]
            batches.append(batch)
            i += (end - i) - overlap
        # Parallel time estimate: divide total batch time by number of workers
        est_times = [(len(b) / chars_per_sec) if chars_per_sec else 60 for b in batches]
        est_total_time = int(sum(est_times))
        num_workers = config.get('NUM_PARALLEL', 4)
        est_parallel_time = int(max(est_times) * ((len(batches) + num_workers - 1) // num_workers)) if batches else 0
        est_total_mins = est_total_time / 60
        est_parallel_mins = est_parallel_time / 60
        avg_chars = sum(len(b) for b in batches)//max(1,len(batches))
        print(f"  Batch size: {batch_size:6d} | Overlap: {overlap:6d} | Batches: {len(batches):3d} | Avg chars/batch: {avg_chars} | Est. total time: {est_total_time//60}m {est_total_time%60}s ({est_total_mins:.1f} min) | Est. parallel: {est_parallel_time//60}m {est_parallel_time%60}s ({est_parallel_mins:.1f} min) [{num_workers} threads]")
        # Recommend the batch size with the lowest parallel time
        if best is None or est_parallel_time < best_parallel_time:
            best = batch_size
            best_batches = len(batches)
            best_time = est_total_time
            best_parallel_time = est_parallel_time
    best_time_mins = best_time / 60 if best_time else 0
    best_parallel_mins = best_parallel_time / 60 if best_parallel_time else 0
    print(f"\n[DRY RUN] Recommended batch_size for parallel speed: {best} (batches: {best_batches}) | Est. parallel time: {best_parallel_time//60}m {best_parallel_time%60}s ({best_parallel_mins:.1f} min)")
    print(f"[DRY RUN] Best batch size: {best} | Use this value for optimal parallel speed with your current config and LLM throughput.")
    config['BATCH_SIZE'] = best  # Set the config batch size to the recommended value
    return best, best_batches, best_parallel_time

def classify_note_type(note_content, filename=None):
    """
    Classify a note as atomic, index, rough, or other based on content heuristics and folder path.
    - Atomic: in 'Atomic Notes' folder, or strong atomic heuristics
    - Index: in 'Indices' folder, or strong index heuristics
    - Rough: incomplete, lots of TODOs, or lacks structure
    - Template: contains placeholders like {{...}} or <template>
    - Literature: has citation, reference, or summary sections
    """
    # --- Folder-based detection ---
    if filename:
        lower_fname = filename.lower()
        if 'templates' in lower_fname:
            return 'template'
        if 'indices' in lower_fname:
            return 'index'
        if 'atomic notes' in lower_fname:
            return 'atomic'
    # --- Content-based detection ---
    lines = note_content.strip().splitlines()
    header_lines = [l for l in lines if l.strip().startswith('#')]
    header_count = len(header_lines)
    wikilinks = re.findall(r'\[\[.*?\]\]', note_content)
    dataview = re.search(r'```dataview|```dataviewjs', note_content)
    is_template = re.search(r'\{\{.*?\}\}|<template>', note_content, re.I)
    has_todo = re.search(r'- \[ \]', note_content)
    has_citation = re.search(r'(doi:|arxiv:|@\w+|reference|citation)', note_content, re.I)
    # --- Improved atomic note detection ---
    # Look for: single main header, clear definition section, multiple section headers, linking notes section, not too many wikilinks
    has_definition = re.search(r'^##?\s*Definition', note_content, re.M)
    has_linking = re.search(r'^##?\s*Linking Notes', note_content, re.M)
    has_sections = len([l for l in lines if re.match(r'^##?\s', l)]) >= 4  # e.g. Definition, Intuitive Explanation, Properties, etc.
    is_atomic = (
        header_count >= 1 and
        has_definition and
        has_linking and
        has_sections and
        len(wikilinks) < 12 and
        not dataview and
        not is_template
    )
    if is_atomic:
        return 'atomic'
    # Index: many links, or index/map/toc in header
    if len(wikilinks) >= 12 or re.search(r'#.*index|map of content|table of contents', note_content, re.I):
        return 'index'
    # Rough: lots of TODOs, or very short, or lacks structure
    if has_todo or (header_count == 0 and len(note_content) < 300):
        return 'rough'
    # Template
    if is_template:
        return 'template'
    # Literature
    if has_citation:
        return 'literature'
    return 'general'

def detect_obsidian_features(note_content):
    """
    Detect Obsidian extension/plugin features in a note.
    Returns a set of features detected.
    """
    features = set()
    if re.search(r'```dataview|```dataviewjs', note_content):
        features.add('dataview')
    if re.search(r'\[\[.*?\]\]', note_content):
        features.add('backlinks')
    if re.search(r'#[a-zA-Z0-9_]+', note_content):
        features.add('tags')
    if re.search(r'- \[ \]', note_content):
        features.add('tasks')
    if re.search(r'```kanban', note_content):
        features.add('kanban')
    if re.search(r'calendar', note_content, re.I):
        features.add('calendar')
    # Add more plugin/feature detection as needed
    return features

def analyze_notes(vault_path, dry_run=False, config=ANALYZE_NOTES_CONFIG):
    # Update config from history before running analysis
    config = update_config_from_history(config)
    import time as _time
    notes = get_all_notes_from_vault(vault_path)
    all_text = "\n".join([n['content'] for n in notes])
    est_parallel_time = 0  # Ensure always defined
    time_error = 0         # Ensure always defined
    batch_size = config.get('BATCH_SIZE', 20000)
    if config.get('DRY_RUN', False) or dry_run:
        simulate_optimal_batching(all_text, config)
        print(f"[DRY RUN] Number of notes in vault: {len(notes)}")
        return None
    # --- New: Per-note type and feature analysis ---
    note_type_counts = {'atomic': 0, 'index': 0, 'rough': 0, 'template': 0, 'literature': 0, 'general': 0}
    feature_counts = {}
    per_note_types = []
    per_note_features = []
    # Track filenames for each type
    note_type_files = {'atomic': [], 'index': [], 'rough': [], 'template': [], 'literature': [], 'general': []}
    for idx, n in enumerate(notes):
        ntype = classify_note_type(n['content'], n.get('filename', f'note_{idx}'))
        note_type_counts[ntype] = note_type_counts.get(ntype, 0) + 1
        per_note_types.append(ntype)
        feats = detect_obsidian_features(n['content'])
        for f in feats:
            feature_counts[f] = feature_counts.get(f, 0) + 1
        per_note_features.append(feats)
        # Store filename for each type
        fname = n.get('filename', f'note_{idx}')
        note_type_files[ntype].append(fname)
    # Style detection
    style = "zettelkasten" if re.search(r'\d{12,}', all_text) else "mixed"
    # Note types (legacy, keep for compatibility)
    types = set()
    if re.search(r'#task|TODO|\[ \]', all_text, re.I):
        types.add("task")
    if re.search(r'#journal|diary|mood', all_text, re.I):
        types.add("journal")
    if re.search(r'#meeting|minutes', all_text, re.I):
        types.add("meeting")
    if re.search(r'#idea|insight', all_text, re.I):
        types.add("idea")
    if re.search(r'#project|milestone', all_text, re.I):
        types.add("project")
    if not types:
        types.add("general note")
    # Interests: LLM-powered topic extraction
    try:
        from modules.model_router import get_llm_model
        from modules.llm_client import call_ollama
        from modules.input_processing import calculate_dynamic_timeout, get_input_size
        model_info = get_llm_model()

        overlap = config.get('OVERLAP', 2500)
        num_workers = config.get('NUM_PARALLEL', 4)
        batches = []
        i = 0
        while i < len(all_text):
            end = i + batch_size
            if end < len(all_text):
                while end > i and not all_text[end-1].isspace():
                    end -= 1
                if end == i:
                    end = i + batch_size
            batch = all_text[i:end]
            batches.append(batch)
            i += (end - i) - overlap
        if len(batches) > 10:
            print(f"[WARN] Large vault: {len(batches)} batches will be sent to the LLM. Consider increasing BATCH_SIZE for speed.")
        all_llm_topics = []
        def process_batch(args):
            idx, sample_text = args
            char_count, word_count = get_input_size(sample_text)
            timeout = max(60, calculate_dynamic_timeout(sample_text))
            print(f"[DEBUG] LLM interest extraction (batch {idx+1}/{len(batches)}): input size = {char_count} chars, {word_count} words | Timeout: {timeout}s")
            prompt = (
                "Analyze the following collection of notes and extract a comprehensive, structured list of ALL main topics, subtopics, and recurring themes present in the notes. "
                "For each topic, include any relevant subtopics or examples in parentheses or as sub-bullets. "
                "Also list any recurring themes or patterns you detect. "
                "Be as detailed and exhaustive as possible, covering everything present in the notes. "
                "Avoid generic headers like 'Main topics' or 'Interests'. "
                "Return a comma-separated or line-separated list, grouping related items where possible.\n\nNotes:\n" + sample_text
            )
            llm_response = call_ollama(prompt, endpoint=model_info["endpoint"], model=model_info["model"], timeout=timeout)
            if isinstance(llm_response, str) and llm_response.strip().startswith("(LLM error"):
                return []
            raw_interests = [t.strip('-• \n') for t in re.split(r'[\n,]', llm_response) if t.strip() and len(t.strip()) > 2]
            return raw_interests
        # --- Track actual analysis time ---
        analysis_start = _time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(executor.map(process_batch, enumerate(batches)))
        parallel_elapsed = time.time() - analysis_start
        print(f"[PARALLEL] LLM batch processing completed in {parallel_elapsed:.2f} seconds using {num_workers} threads.")
        for batch_topics in results:
            all_llm_topics.extend(batch_topics)
        # Enhanced flattening: extract all parenthetical/nested subtopics recursively
        def extract_all_topics(items):
            topics = []
            for item in items:
                # Remove leading numbering and generic headers
                cleaned = re.sub(r'^\d+\s*[\.|\)]?\s*', '', item)
                cleaned = re.sub(r'^(Main topics:|Topics and Interests:|Interests:)', '', cleaned, flags=re.I).strip()
                # Recursively extract parenthetical subtopics
                while '(' in cleaned and ')' in cleaned:
                    pre, rest = cleaned.split('(', 1)
                    sub, post = rest.split(')', 1)
                    pre = pre.strip()
                    if pre:
                        topics.append(pre)
                    for subtopic in re.split(r',|;', sub):
                        subtopic = subtopic.strip()
                        if subtopic:
                            topics.append(subtopic)
                    cleaned = post.strip()
                if cleaned:
                    topics.append(cleaned)
            return topics
        interests = extract_all_topics(all_llm_topics)
        def _is_errorish_topic(text):
            t = text.lower()
            error_markers = [
                'llm error', 'httpconnectionpool', 'read timed out', 'timeout=',
                'used timeout', 'client error', 'connection'
            ]
            return any(m in t for m in error_markers)
        # Deduplicate and filter
        interests = [
            i for i in dict.fromkeys([
                x for x in (i.strip() for i in interests)
                if x and x.lower() not in ['topics and interests', 'main topics', 'interests'] and not _is_errorish_topic(x)
            ])
        ]
        if not interests:
            raise ValueError("No LLM interests found")
    except Exception as e:
        # Fallback: frequent nouns
        words = re.findall(r'\b\w+\b', all_text.lower())
        stopwords = set(['the','and','to','of','in','a','is','for','on','with','as','by','at','from','it','an','be','this','that','are','or','was','but','not','have','has','if','can','will','do','so','all','your','my','we','you','i'])
        common = Counter([w for w in words if w not in stopwords and len(w) > 3])
        interests = [w for w, c in common.most_common(15)]
        parallel_elapsed = 0
        est_parallel_time = 0  # Ensure defined in fallback
        time_error = 0         # Ensure defined in fallback
    # Detailed analysis: header usage, average note length, link density, tag usage
    header_count = len(re.findall(r'^#+ ', all_text, re.M))
    avg_note_len = sum(len(n['content']) for n in notes) / max(1, len(notes))
    wikilinks = len(re.findall(r'\[\[.*?\]\]', all_text))
    tag_count = len(re.findall(r'#[a-zA-Z0-9_]+', all_text))
    todos = len(re.findall(r'- \[ \]', all_text))
    density = note_density(all_text)
    avg_sent_len = avg_sentence_length(all_text)
    lex_div = lexical_diversity(all_text)
    bigrams = top_ngrams(all_text, n=2, top_k=5)
    trigrams = top_ngrams(all_text, n=3, top_k=3)
    # --- Store actual/estimated time and error in memory ---
    mem = StructureStyleMemory()
    # Store timestamped analysis summary
    analysis_summary = {
        'timestamp': datetime.datetime.now().isoformat(),
        'style': style,
        'types': list(types),
        'interests': interests,
        'header_count': header_count,
        'avg_note_len': avg_note_len,
        'wikilinks': wikilinks,
        'tag_count': tag_count,
        'todos': todos,
        'total_notes': len(notes),
        'total_chars': len(all_text),
        'note_density': density,
        'avg_sentence_length': avg_sent_len,
        'lexical_diversity': lex_div,
        'top_bigrams': bigrams,
        'top_trigrams': trigrams,
        'parallel_time': parallel_elapsed,
        'estimated_parallel_time': est_parallel_time,
        'parallel_time_error': time_error,
        'note_type_counts': note_type_counts,
        'feature_counts': feature_counts,
        'note_type_files': note_type_files,
        'batch_size': batch_size,  # <-- Add batch_size to summary for history
    }
    # Log all runs in a list for history
    all_runs = mem.get_preference('analysis_history') or []
    all_runs.append(analysis_summary)
    mem.set_preference('analysis_history', all_runs)
    mem.set_preference('last_analysis_summary', analysis_summary)
    mem.set_preference('detected_style', style)
    mem.set_preference('detected_types', list(types))
    mem.set_preference('detected_interests', interests)
    mem.set_preference('header_count', header_count)
    mem.set_preference('avg_note_length', avg_note_len)
    mem.set_preference('wikilink_count', wikilinks)
    mem.set_preference('tag_count', tag_count)
    mem.set_preference('todo_count', todos)
    mem.set_preference('note_density', density)
    mem.set_preference('avg_sentence_length', avg_sent_len)
    mem.set_preference('lexical_diversity', lex_div)
    mem.set_preference('top_bigrams', bigrams)
    mem.set_preference('top_trigrams', trigrams)
    mem.set_preference('actual_parallel_time', parallel_elapsed)
    mem.set_preference('estimated_parallel_time', est_parallel_time)
    mem.set_preference('parallel_time_error', time_error)
    mem.set_preference('note_type_files', note_type_files)
    # Try to estimate expected parallel time for this batch size
    chars_per_sec = config.get('CHARS_PER_SEC', 50)
    num_workers = config.get('NUM_PARALLEL', 4)
    batch_size = config.get('BATCH_SIZE', 20000)
    # Recompute batches for estimate
    batches = []
    i = 0
    while i < len(all_text):
        end = i + batch_size
        if end < len(all_text):
            while end > i and not all_text[end-1].isspace():
                end -= 1
            if end == i:
                end = i + batch_size
        batch = all_text[i:end]
        batches.append(batch)
        i += (end - i) - config.get('OVERLAP', 2500)
    est_times = [(len(b) / chars_per_sec) if chars_per_sec else 60 for b in batches]
    est_parallel_time = int(max(est_times) * ((len(batches) + num_workers - 1) // num_workers)) if batches else 0
    mem.set_preference('estimated_parallel_time', est_parallel_time)
    # Track error and update config for next run
    time_error = parallel_elapsed - est_parallel_time
    mem.set_preference('parallel_time_error', time_error)
    # Optionally, update CHARS_PER_SEC for next run (simple correction)
    if parallel_elapsed > 0 and est_parallel_time > 0:
        new_chars_per_sec = chars_per_sec * (est_parallel_time / parallel_elapsed)
        mem.set_preference('corrected_chars_per_sec', new_chars_per_sec)
        # Optionally, update config['CHARS_PER_SEC'] = new_chars_per_sec for next run
    # Return results for printing
    result = {
        'style': style,
        'types': types,
        'interests': interests,  # full list, not truncated
        'header_count': header_count,
        'avg_note_len': avg_note_len,
        'wikilinks': wikilinks,
        'tag_count': tag_count,
        'todos': todos,
        'total_notes': len(notes),
        'total_chars': len(all_text),
        'note_density': density,
        'avg_sentence_length': avg_sent_len,
        'lexical_diversity': lex_div,
        'top_bigrams': bigrams,
        'top_trigrams': trigrams,
        'parallel_time': parallel_elapsed,
        'estimated_parallel_time': est_parallel_time,
        'parallel_time_error': time_error,
        'note_type_counts': note_type_counts,
        'feature_counts': feature_counts,
        'per_note_types': per_note_types,
        'per_note_features': per_note_features,
        'note_type_files': note_type_files,
    }
    return result
