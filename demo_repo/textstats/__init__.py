from collections import Counter
import re

def word_count(text):
    """Return the number of words in text."""
    return len(re.findall(r"\w+", text))

def top_words(text, n=3):
    """Return the n most common words as (word, count) pairs."""
    return Counter(re.findall(r"\w+", text.lower())).most_common(n)
