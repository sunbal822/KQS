--- 
metadata:
  name: use_textstats
  description: This skill teaches an agent how to use the textstats library.
  version: 1.0
  author: SkillForge
  date: 2023-10-27
  tags: [library, textstats]
---
# Skill Description

This skill provides an agent with the knowledge and instructions to effectively utilize the `textstats` library within the `demo_repo` repository. The agent will learn how to perform basic text analysis tasks, specifically word counting and identifying the most frequent words in a given text.

## Prerequisites

*   The agent must have access to the `demo_repo` repository.
*   The agent must understand basic Python syntax and how to import and use libraries.

## Steps

1.  **Import the `textstats` library:**
    The first step is to import the `textstats` library into the agent's code. This allows the agent to access the library's functions and classes.
    ```python
    from textstats import word_count, top_words
    ```

2.  **Using `word_count()`:**
    The `word_count()` function calculates the total number of words in a given text string.
    ```python
    text = "This is a sample text to count the words in."
    word_count_result = word_count(text)
    print(f"The number of words in the text is: {word_count_result}")
    ```

3.  **Using `top_words()`:**
    The `top_words()` function identifies the `n` most frequent words in a given text string.
    ```python
    text = "This is a sample text to count the words in. This text is repeated."
    top_words_result = top_words(text, 3)
    print(f"The top 3 words in the text are: {top_words_result}")
    ```

## Example Usage

```python
from textstats import word_count, top_words

text = "This is a sample text to count the words in. This text is repeated."

word_count_result = word_count(text)
print(f"The number of words in the text is: {word_count_result}")

top_words_result = top_words(text, 3)
print(f"The top 3 words in the text are: {top_words_result}")
```

## Further Exploration

*   Experiment with different text strings to see how the functions behave.
*   Explore the documentation for the `textstats` library (if available) to learn about advanced features and options.
