import re
from collections import Counter

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    content = f.read()
lines = content.split('\n')

# Check HTML tag balance
tags = re.findall(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)', content)
opens, closes = Counter(), Counter()
for close, tag in tags:
    if close == '/': closes[tag.lower()] += 1
    else: opens[tag.lower()] += 1

print("=== HTML tag balance (mismatches only) ===")
for tag in sorted(set(list(opens.keys()) + list(closes.keys()))):
    if opens[tag] != closes[tag]:
        print(f"  <{tag}>: open={opens[tag]}, close={closes[tag]}")

# Check for odd quotes per line
print("\n=== Lines with odd number of quotes ===")
for i, line in enumerate(lines, 1):
    dq = line.count('"')
    sq = line.count("'")
    bt = line.count('`')
    if dq % 2 != 0 or sq % 2 != 0 or bt % 2 != 0:
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('*'):
            continue
        print(f"  Line {i}: dq={dq} sq={sq} bt={bt} | {stripped[:100]}")

# Extract main script block and check
print("\n=== Main script block analysis ===")
start = content.rfind('<script>')
end = content.rfind('</script>')
if start >= 0 and end > start:
    js = content[start+len('<script>'):end]
    if '</script>' in js:
        print("  WARNING: </script> found inside script block")
    # Count and check balance
    print(f"  Total chars: {len(js)}")
    print(f"  Backticks: {js.count(chr(96))}")
    print(f"  Double quotes: {js.count('\"')}")
    print(f"  Single quotes: {js.count(chr(39))}")

    # Find unescaped </script> inside strings (common issue)
    js_lines = js.split('\n')
    line_offset = content[:start].count('\n') + 1
    for i, jl in enumerate(js_lines, 1):
        if '</script>' in jl:
            print(f"  Block line {i} (HTML line {line_offset+i-1}): contains </script>")
        dq = jl.count('\"')
        sq = jl.count(chr(39))
        bt = jl.count(chr(96))
        if (dq % 2 != 0 or sq % 2 != 0 or bt % 2 != 0):
            stripped = jl.strip()
            if stripped.startswith('//'): continue
            print(f"  Block line {i} (HTML line {line_offset+i-1}): dq={dq} sq={sq} bt={bt} | {stripped[:120]}")

print("\nDone.")
