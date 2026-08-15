import time
import csv
import os
from datetime import datetime
from modules.analyze_notes import analyze_notes, ANALYZE_NOTES_CONFIG

def log_analysis_run(vault_path, config=None, log_path='logs/analysis_runs.csv'):
    if config is None:
        config = ANALYZE_NOTES_CONFIG.copy()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    start_time = time.time()
    result = analyze_notes(vault_path, dry_run=False, config=config)
    end_time = time.time()
    elapsed = end_time - start_time
    parallel_time = result.get('parallel_time') if result and 'parallel_time' in result else ''
    empirical_chars_per_sec = ''
    if result and elapsed > 0 and result.get('total_chars'):
        empirical_chars_per_sec = round(result['total_chars'] / elapsed, 2)
    # Prepare log row
    row = {
        'timestamp': datetime.now().isoformat(),
        'vault_path': vault_path,
        'batch_size': config.get('BATCH_SIZE'),
        'overlap': config.get('OVERLAP'),
        'min_batch': config.get('MIN_BATCH'),
        'max_batch': config.get('MAX_BATCH'),
        'step': config.get('STEP'),
        'chars_per_sec': config.get('CHARS_PER_SEC'),
        'empirical_chars_per_sec': empirical_chars_per_sec,
        'parallel_time': parallel_time,
        'num_parallel': config.get('NUM_PARALLEL', ''),
        'overlap_pct': config.get('OVERLAP_PCT', ''),
        'min_overlap': config.get('MIN_OVERLAP', ''),
        'max_overlap': config.get('MAX_OVERLAP', ''),
        'total_notes': result.get('total_notes') if result else '',
        'total_chars': result.get('total_chars') if result else '',
        'header_count': result.get('header_count') if result else '',
        'avg_note_len': result.get('avg_note_len') if result else '',
        'wikilinks': result.get('wikilinks') if result else '',
        'tag_count': result.get('tag_count') if result else '',
        'todos': result.get('todos') if result else '',
        'elapsed_sec': round(elapsed, 2)
    }
    # Write header if file does not exist
    write_header = not os.path.exists(log_path)
    with open(log_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    print(f"[LOGGED] Analysis run complete. Elapsed: {elapsed:.2f}s. Log written to {log_path}")
    # Output results as JSON
    import json
    print(json.dumps(row, indent=2, default=str))

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python log_analysis_run.py <vault_path>")
        exit(1)
    vault_path = sys.argv[1]
    log_analysis_run(vault_path)
