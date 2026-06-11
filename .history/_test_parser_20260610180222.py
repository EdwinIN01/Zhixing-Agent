import pyjsparser

with open(r'd:\study\code\-agent-main\frontend\index.html', 'r', encoding='utf-8') as f:
    content = f.read()
start = content.rfind('<script>')
end = content.rfind('</script>')
js = content[start+len('<script>'):end]
js_lines = js.split('\n')

L335 = js_lines[334]
L336 = js_lines[335]

combined = L335.strip() + '\n' + L336.strip()
print("Combined:", combined[:200])
print()

# Step 1: just the basic structure without the long string
t1 = 'var r=[{decoded_polyline:[], polyline:"x", origin_coord:"a", dest_coord:"b"}];\n' + \
     'console.log("origin=" +\n' + \
     '  (r[0].decoded_polyline && r[0].decoded_polyline.length) + ", polyline=" + (r[0].polyline ? r[0].polyline + ")" : "no");'
try:
    pyjsparser.parse(t1)
    print("Step 1: OK")
except Exception as e:
    print(f"Step 1 FAIL: {e}")
    print(t1)

# Step 2: add Chinese chars
t2 = 'var r=[{decoded_polyline:[], polyline:"x", origin_coord:"a", dest_coord:"b"}];\n' + \
     'console.log("origin=" +\n' + \
     '  (r[0].decoded_polyline && r[0].decoded_polyline.length) + ", polyline=" + (r[0].polyline ? "存在(" + r[0].polyline + "...)" : "无"));'
try:
    pyjsparser.parse(t2)
    print("Step 2: OK")
except Exception as e:
    print(f"Step 2 FAIL: {e}")

# Step 3: full length with substring
t3 = 'var r=[{decoded_polyline:[], polyline:"x", origin_coord:"a", dest_coord:"b"}];\n' + \
     'console.log("origin=" +\n' + \
     '  (r[0].decoded_polyline && r[0].decoded_polyline.length) + ", polyline=" + (r[0].polyline ? "存在(" + r[0].polyline.substring(0, 30) + "...)" : "无"));'
try:
    pyjsparser.parse(t3)
    print("Step 3: OK")
except Exception as e:
    print(f"Step 3 FAIL: {e}")

# Step 4: exact line content
t4 = 'var r=[{decoded_polyline:[], polyline:"x", origin_coord:"1,2", dest_coord:"3,4"}];\n' + \
     'console.log("[地图] 第1条路线概览: origin=" + r[0].origin_coord + ", dest=" + r[0].dest_coord + ", decoded_polyline 长度=" +\n' + \
     '  (r[0].decoded_polyline && r[0].decoded_polyline.length) + ", polyline=" + (r[0].polyline ? "存在(" + r[0].polyline.substring(0, 30) + "...)" : "无"));'
try:
    pyjsparser.parse(t4)
    print("Step 4: OK")
except Exception as e:
    print(f"Step 4 FAIL: {e}")
    print(t4)