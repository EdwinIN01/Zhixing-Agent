with open(r'd:\study\code\-agent-main\frontend\index.html', 'rb') as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")

# Check BOM
bom_markers = [
    (b'\xef\xbb\xbf', 'UTF-8 BOM'),
    (b'\xff\xfe', 'UTF-16 LE BOM'),
    (b'\xfe\xff', 'UTF-16 BE BOM'),
]
for bom, name in bom_markers:
    if raw.startswith(bom):
        print(f"WARNING: File starts with {name}")

# Decode to string for analysis
with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check for problematic characters in each line
problem_chars = {
    '\u200b': 'ZERO WIDTH SPACE',
    '\u200c': 'ZERO WIDTH NON-JOINER',
    '\u200d': 'ZERO WIDTH JOINER',
    '\u2060': 'WORD JOINER',
    '\ufeff': 'BYTE ORDER MARK (BOM)',
    '\u2018': 'LEFT SINGLE QUOTATION MARK (')',
    '\u2019': 'RIGHT SINGLE QUOTATION MARK')',
    '\u201c': 'LEFT DOUBLE QUOTATION MARK ("')',
    '\u201d': 'RIGHT DOUBLE QUOTATION MARK ")',
    '\u3000': 'IDEOGRAPHIC SPACE',
    '\xa0': 'NON-BREAKING SPACE',
    '\u00a9': '(c) - copyright',
}

print("\n=== Hidden/special character detection ===")
for i, line in enumerate(lines, 1):
    for ch, name in problem_chars.items():
        if ch in line:
            pos = line.find(ch)
            print(f"  Line {i}, col {pos+1}: contains {name}")
            print(f"    Context: ...{line[max(0,pos-10):pos+10].strip()}...")

# Check for smart quotes in script blocks
print("\n=== Checking for curly quotes in <script> blocks ===")
content = ''.join(lines)
import re
script_blocks = list(re.finditer(r'<script[^>]*>(.*?)</script>', content, re.DOTALL))
for idx, m in enumerate(script_blocks):
    js = m.group(1)
    for ch in ['\u2018', '\u2019', '\u201c', '\u201d']:
        if ch in js:
            line_num = content[:m.start()+js.find(ch)].count('\n') + 1
            print(f"  Block {idx+1}, ~line {line_num}: contains curly quote {hex(ord(ch))}")

# Check for tabs vs spaces inconsistencies (cosmetic but could indicate copy-paste issues)
print("\n=== Tab characters ===")
for i, line in enumerate(lines, 1):
    if '\t' in line and line.strip():
        print(f"  Line {i}: contains tab character")

print("\nDone.")
