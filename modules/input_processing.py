"""
Utility functions for input size measurement and dynamic timeout calculation for LLM calls.
Also provides advanced text analysis for note analytics.
"""

def calculate_dynamic_timeout(text, base_timeout=30, per_500_chars=10, max_timeout=3600):
    """
    Calculate timeout based on input text length.
    - base_timeout: minimum timeout in seconds
    - per_500_chars: additional seconds per 500 chars
    - max_timeout: maximum allowed timeout (now 1 hour)
    """
    extra_timeout = max(0, (len(text) // 500) * per_500_chars)
    timeout = min(base_timeout + extra_timeout, max_timeout)
    return timeout

def get_input_size(text):
    """
    Return the length of the input text in characters and words.
    """
    char_count = len(text)
    word_count = len(text.split())
    return char_count, word_count

def note_density(text):
    """Return notes per 1000 words (for a vault or large text)."""
    word_count = len(text.split())
    return word_count / 1000 if word_count else 0

def avg_sentence_length(text):
    """Return average sentence length in words."""
    import re
    sentences = re.split(r'[.!?\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0
    total_words = sum(len(s.split()) for s in sentences)
    return total_words / len(sentences)

def lexical_diversity(text):
    """Return the ratio of unique words to total words."""
    words = [w.lower() for w in text.split() if w.isalpha()]
    if not words:
        return 0
    return len(set(words)) / len(words)

def top_ngrams(text, n=2, top_k=10):
    """Return the most common n-grams (default: bigrams) in the text."""
    from collections import Counter
    words = [w.lower() for w in text.split() if w.isalpha()]
    ngrams = zip(*[words[i:] for i in range(n)])
    ngram_counts = Counter([" ".join(ng) for ng in ngrams])
    return ngram_counts.most_common(top_k)
