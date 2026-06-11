import re

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all script blocks with line numbers
lines = content.split('\n')
print(f"Total lines: {len(lines)}")

# Check each line for common HTML/JS issues
print("\n=== Lines potentially containing problematic quotes or entities ===")
for i, line in enumerate(lines, 1):
    # Check for problematic patterns
    if '&#x' in line and ('onclick' in line or 'onkeydown' in line or 'onchange' in line):
        print(f"  Line {i}: {line.strip()[:120]}")
    if line.count('"') % 2 != 0:
        print(f"  Line {i} (odd quotes): {line.strip()[:120]}")

# Check HTML tags open/close balance
print("\n=== HTML tag balance ===")
tags = re.findall(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)(?:\s|>)', content)
from collections import Counter
opens = Counter()
closes = Counter()
for close, tag in tags:
    if close == '/':
        closes[tag.lower()] += 1
    else:
        opens[tag.lower()] += 1

for tag in sorted(set(list(opens.keys()) + list(closes.keys()))):
    if opens[tag] != closes[tag]:
        print(f"  <{tag}>: open={opens[tag]}, close={closes[tag]}")

# Find last <script> block content and check for </script> inside
print("\n=== Checking last <script> block for embedded </script> ===")
start = content.rfind('<script>')
end = content.rfind('</script>')
if start >= 0 and end > start:
    js = content[start + len('<script>'):end]
    if '</script>' in js:
        print("  WARNING: </script> found inside script block!")
    # Check for unescaped backticks or template literal issues
    backtick_count = js.count('`')
    print(f"  Backtick count: {backtick_count}")
    # Check for unterminated strings (simplified)
    print(f"  Double quote count: {js.count('\"')}")
    print(f"  Single quote count: {js.count(\"'\")}")

    # Print lines with high likelihood of issues
    js_lines = js.split('\n')
    for i, jl in enumerate(js_lines, 1):
        # Check for broken strings - too many or too few quotes
        dq = jl.count('\"')
        sq = jl.count(\"'\")
        bt = jl.count('`')
        if (dq % 2 != 0 or sq % 2 != 0 or bt % 2 != 0) and not jl.strip().startswith('//'):
            # Only flag if not inside a multi-line string block (heuristic)
            print(f"  JS line {i}: odd quotes/special chars — {jl.strip()[:120]}")

print("\nDone.")
