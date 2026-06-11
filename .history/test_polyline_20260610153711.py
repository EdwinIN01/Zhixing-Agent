import sys
sys.path.insert(0, 'd:\\study\\code\\-agent-main')

from backend.tools.tools import decode_amap_polyline

test1 = '116.486639,39.905255;116.487639,39.906255;116.488639,39.907255'
result1 = decode_amap_polyline(test1)
print('Test1 (plain coords):', len(result1), 'points')
print('  first:', result1[0] if result1 else 'None')

test2 = 'o}yqBzgn}M'
result2 = decode_amap_polyline(test2)
print('Test2 (encoded):', len(result2), 'points')
print('  first:', result2[0] if result2 else 'None')

print('Test3 (empty):', decode_amap_polyline(''))

from backend.tools.tools import _parse_driving_response
mock_resp = {
    'status': '1',
    'route': {
        'origin': '116.486639,39.905255',
        'destination': '116.556639,39.955255',
        'paths': [{
            'distance': 10000,
            'duration': 1200,
            'polyline': '116.486639,39.905255;116.506639,39.915255;116.556639,39.955255',
            'steps': []
        }]
    }
}
parsed = _parse_driving_response(mock_resp)
if parsed.get('routes'):
    route = parsed['routes'][0]
    print('Test4 decoded_polyline present:', 'decoded_polyline' in route)
    print('  points:', len(route.get('decoded_polyline', [])))
    print('  first:', route.get('decoded_polyline', [[]])[0])
print('All tests done')
