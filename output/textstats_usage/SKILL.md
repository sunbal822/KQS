```yaml
-------
name: textstats_usage
description: Demonstrates usage of the textstats library.
--- 
usage_examples:
  - title: Counting words
    description: Calculates the word count of a given text.
    code: |
      from textstats import word_count
      text = "This is a sample text."
      count = word_count(text)
      print(f"Word count: {count}")

functions:
  - name: word_count
    description: Calculates the word count of a text.
    parameters:
      - name: text
        type: string
        description: The text to analyze.
    return_type: int
```