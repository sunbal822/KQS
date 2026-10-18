import json, harness
bad = "---\nname: Text Stats\ndescription: Use textstats\n---\n# textstats\nCall `word_count(text)` and `median_word_length(text)` to analyse text. This body is long enough to pass the length check easily.\n"
good = "---\nname: textstats\ndescription: Count words and find the most common words in text with the textstats library. Use for quick text statistics.\n---\n# textstats\nCall `word_count(text)` to count words and `top_words(text, n)` for the n most common words. Example: top_words('a b a', 1) returns [('a', 2)].\n"
script = iter([
 "not json at all",
 json.dumps({"action":"load_skill","arguments":{"name":"skillforge"}}),
 json.dumps({"action":"inspect_repository","arguments":{}}),
 json.dumps({"action":"generate_skill","arguments":{"name":"textstats","skill_md":bad}}),
 json.dumps({"action":"validate_skill","arguments":{"name":"textstats"}}),
 json.dumps({"action":"generate_skill","arguments":{"name":"textstats","skill_md":good}}),
 json.dumps({"action":"validate_skill","arguments":{"name":"textstats"}}),
 json.dumps({"action":"finish","arguments":{"name":"textstats"}}),
])
harness.call_model = lambda m: next(script)
ok = harness.run("demo_repo", "write a skill")
print("RESULT:", ok)
