import re

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
content = ''.join(lines)

# Check for hidden/special unicode chars
print("=== Hidden character detection ===")
bad_chars = {
    '\u200b': 'ZWS',
    '\u200c': 'ZWNJ',
    '\u200d': 'ZWJ',
    '\ufeff': 'BOM',
    '\u2018': 'LSQ',
    '\u2019': 'RSQ',
    '\u201c': 'LDQ',
    '\u201d': 'RDQ',
    '\xa0': 'NBSP',
}

for i, line in enumerate(lines, 1):
    for ch, name in bad_chars.items():
        if ch in line:
            pos = line.find(ch)
            print(f"  Line {i}, col {pos+1}: {name}")

# Check script blocks for curly quotes
print("\n=== Curly quotes in script blocks ===")
script_blocks = list(re.finditer(r'<script[^>]*>(.*?)</script>', content, re.DOTALL))
for idx, m in enumerate(script_blocks):
    js = m.group(1)
    for ch in ['\u2018', '\u2019', '\u201c', '\u201d']:
        if ch in js:
            print(f"  Block {idx+1}: has curly quote {hex(ord(ch))}")

# Check for tabs
print("\n=== Tab characters in code lines ===")
for i, line in enumerate(lines, 1):
    if '\t' in line and line.strip():
        print(f"  Line {i}: has tab")

# Let me try a different approach - actually parse via py_mini_racer or just check specific patterns
print("\n=== Potential JS syntax issues ===")
# Check for common issues in the main script block
start = content.rfind('<script>')
end = content.rfind('</script>')
main_js = content[start+len('<script>'):end]

# Check for missing semicolons before return/function (not definitive)
# Check for things like: "async function foo() { ... } function bar() {}" on same line
# Check for unterminated regex patterns (hard)
# Check for triple-backtick or string issues

# Print lines containing suspicious patterns
suspicious = [
    'return return',
    'function function',
    'var var ',
    'async async',
]
for i, line in enumerate(lines, 1):
    for pat in suspicious:
        if pat in line:
            print(f"  Line {i}: {pat!r}")

# Look for missing closing braces by checking balance in different regions
print("\n=== Brace balance by section ===")
# Split by function definitions and check each
in_script = False
balance = 0
func_start = None
for i, line in enumerate(lines, 1):
    if '<script' in line.lower():
        in_script = True
        continue
    if '</script' in line.lower():
        in_script = False
        continue
    if not in_script:
        continue
    for ch in line:
        if ch == '{':
            if balance == 0:
                func_start = i
            balance += 1
        elif ch == '}':
            balance -= 1
            if balance == 0 and func_start:
                func_start = None
    if balance < 0:
        print(f"  NEGATIVE balance at line {i}: balance={balance}")
        break

print(f"  Final brace balance: {balance}")
print("\nDone.")
