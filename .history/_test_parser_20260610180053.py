import pyjsparser

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    content = f.read()
start = content.rfind('<script>')
end = content.rfind('</script>')
js = content[start+len('<script>'):end]
js_lines = js.split('\n')

# The problematic line is around JS line 335-336 (0-indexed 334-335)
# Let me check what's on line 334
line_335 = js_lines[334]  # The console.log line
line_336 = js_lines[335]  # The continuation line

print(f"JS Line 335: [{line_335.strip()}]")
print(f"JS Line 336: [{line_336.strip()}]")
print()

# Test 1: Simple multi-line expression
test1 = 'console.log("a" +\n  "b");'
print(f"Test 1: {repr(test1)}")
try:
    pyjsparser.parse(test1)
    print("  OK")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 2: Simple ternary in multi-line
test2 = 'console.log("x=" + (true ? "A" : "B"));\n'
print(f"Test 2: {test2.strip()}")
try:
    pyjsparser.parse(test2)
    print("  OK")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 3: The actual line 335 content continued by \n
combined = line_335.strip() + '\n' + line_336.strip()
print(f"Test 3 (combined lines): {combined[:120]}...")
try:
    pyjsparser.parse(combined)
    print("  OK")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 4: Same but as simple expression
test4 = 'var r = [{decoded_polyline:[], polyline:"test", origin_coord:"1,2", dest_coord:"3,4"}];\n'
test4 += 'console.log("origin=" + r[0].origin_coord + ", dest=" + r[0].dest_coord + ", poly=" +\n'
test4 += '  (r[0].decoded_polyline && r[0].decoded_polyline.length) + ", extra=" + (r[0].polyline ? "yes(" + r[0].polyline + ")" : "no");\n'
print(f"Test 4: {test4[:120]}...")
try:
    pyjsparser.parse(test4)
    print("  OK")
except Exception as e:
    print(f"  FAIL: {e}")