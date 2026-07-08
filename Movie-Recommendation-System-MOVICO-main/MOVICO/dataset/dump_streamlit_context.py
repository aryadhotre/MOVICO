import re

html_path = r"Movie-Recommendation-System-MOVICO-main\MOVICO\dataset\app.py.html"
with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

print("Searching for 'streamlit' (case-insensitive) matches...")
matches = list(re.finditer(r"streamlit", content, re.IGNORECASE))
print(f"Found {len(matches)} matches.")
for idx, match in enumerate(matches):
    start = max(0, match.start() - 100)
    end = min(len(content), match.end() + 150)
    print(f"\nMatch {idx} at position {match.start()}:")
    print(repr(content[start:end]))
