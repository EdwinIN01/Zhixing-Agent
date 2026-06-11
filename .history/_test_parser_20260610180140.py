import pyjsparser

# Minimal reproduction
tests = [
    # Test: multi-line with ternary
    'var r=[{a:1,b:"x"}];\nconsole.log("x=" +\n  (r[0].b ? "yes" : "no"));',
    # Test: multi-line without ternary
    'var r=[{a:1,b:"x"}];\nconsole.log("x=" +\n  r[0].b + "y");',  
    # Test: multi-line with && 
    'var r=[{a:1,b:"x"}];\nconsole.log("x=" +\n  (r[0].a && r[0].b));',
    # Test: single-line ternary (LONG line)
    'var r=[{a:1,b:"x"}];\nconsole.log("x=" + (r[0].b ? "yes" : "no"));',
]

for i, test in enumerate(tests):
    print(f"Test {i+1}: {test[:80]}...")
    try:
        pyjsparser.parse(test)
        print("  OK")
    except Exception as e:
        print(f"  FAIL: {e}")
    print()