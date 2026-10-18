--- 
name: textstats-usage 
description: This skill demonstrates how to use the textstats library to calculate word counts and get the top words in a text. 
--- 
# Usage Example 

```python 
from textstats import word_count, top_words 

text = "This is a sample text. It has some words."

word_count(text) # Returns the number of words

top_words(text, 3) # Returns the 3 most frequent words
