import re
import subprocess
import tempfile
import os

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)
print(f"Total lines: {len(lines)}")

# Extract each <script> block and run node --check
matches = list(re.finditer(r'<script[^>]*>(.*?)</script>', content, re.DOTALL))
print(f"Found {len(matches)} <script> blocks")

for idx, m in enumerate(matches):
    js = m.group(1)
    block_start_line = content[:m.start()].count('\n') + 1

    tf = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8')
    tf.write(js)
    tf.close()
    try:
        r = subprocess.run(['node', '--check', tf.name], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            print(f"\n=== BLOCK {idx+1} (starts HTML line {block_start_line}) SYNTAX ERROR ===")
            print(r.stderr[:800])
            # Show context around first error
            err_match = re.search(r'line (\d+)', r.stderr)
            if err_match:
                rel_line = int(err_match.group(1))
                abs_line = block_start_line + rel_line - 1
                print(f"\n  → HTML line ~{abs_line}, JS line {rel_line} in this block:")
                start = max(0, rel_line - 3)
                end = min(len(js.split('\n')), rel_line + 2)
                js_lines = js.split('\n')
                for j in range(start, end):
                    marker = '>>>' if j + 1 == rel_line else '   '
                    print(f"  {marker} {block_start_line + j}: {js_lines[j]}")
        else:
            print(f"  Block {idx+1}: OK ({len(js)} chars)")
    except FileNotFoundError:
        # No node, try basic check
        print(f"  (node not found, falling back to brace check for block {idx+1})")
        balance = 0
        in_str = None
        in_cmt_line = False
        in_cmt_block = False
        escape = False
        line = 1
        first_neg = None
        for i, ch in enumerate(js):
            if ch == '\n':
                line += 1
                if in_cmt_line: in_cmt_line = False
                continue
            if in_cmt_line: continue
            if in_cmt_block:
                if ch == '*' and i+1 < len(js) and js[i+1] == '/': in_cmt_block = False
                continue
            if escape: escape = False; continue
            if in_str:
                if ch == '\\': escape = True
                elif ch == in_str: in_str = None
                continue
            if ch == '/' and i+1 < len(js):
                nxt = js[i+1]
                if nxt == '/': in_cmt_line = True; continue
                if nxt == '*': in_cmt_block = True; continue
            if ch in ("'", '"', '`'):
                in_str = ch
            elif ch == '{': balance += 1
            elif ch == '}':
                balance -= 1
                if balance < 0 and first_neg is None: first_neg = line
        print(f"    brace_balance={balance}, first_negative_line={first_neg}")
    finally:
        try: os.unlink(tf.name)
        except: pass

print("\nDone.")
