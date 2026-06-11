from html.parser import HTMLParser
import sys

class MyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        self.line = 1

    def handle_starttag(self, tag, attrs):
        if tag not in ('br', 'img', 'input', 'meta', 'link', 'hr'):
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            # Look for it in stack
            found = False
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    self.errors.append(f"Line {self.getpos()[0]}: Mismatched </{tag}>, unclosed tags: {[s for s, _ in self.stack[i+1:]]}")
                    self.stack = self.stack[:i]
                    found = True
                    break
            if not found:
                self.errors.append(f"Line {self.getpos()[0]}: Closing </{tag}> but not open (stack: {[s for s, _ in self.stack[-5:]]})")

    def error(self, message):
        self.errors.append(f"Line {self.getpos()[0]}: {message}")

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

parser = MyParser()
parser.feed(content)

print(f"=== HTML Parse Errors: {len(parser.errors)} ===")
for e in parser.errors[:30]:
    print(f"  {e}")

if parser.stack:
    print(f"\n=== Unclosed tags ===")
    for tag, line in parser.stack:
        print(f"  <{tag}> opened at line {line}")

print("\nDone.")
