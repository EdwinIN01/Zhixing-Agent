def decode_amap_polyline(encoded):
    if not encoded or not isinstance(encoded, str):
        return []
    if ';' in encoded and ',' in encoded:
        try:
            result = []
            for pair in encoded.split(';'):
                if not pair:
                    continue
                parts = pair.split(',')
                if len(parts) >= 2:
                    lng = float(parts[0])
                    lat = float(parts[1])
                    if -180 <= lng <= 180 and -90 <= lat <= 90:
                        result.append([lng, lat])
            return result
        except (ValueError, TypeError):
            pass
    result = []
    prev_x, prev_y = 0, 0
    i = 0
    try:
        while i < len(encoded):
            byte = shift = result_byte = 0
            while True:
                if i >= len(encoded):
                    break
                byte = ord(encoded[i]) - 63
                i += 1
                result_byte |= (byte & 0x1f) << shift
                shift += 5
                if byte < 0x20:
                    break
            dx = ~(result_byte >> 1) if (result_byte & 1) else (result_byte >> 1)
            prev_x += dx
            byte = shift = result_byte = 0
            while True:
                if i >= len(encoded):
                    break
                byte = ord(encoded[i]) - 63
                i += 1
                result_byte |= (byte & 0x1f) << shift
                shift += 5
                if byte < 0x20:
                    break
            dy = ~(result_byte >> 1) if (result_byte & 1) else (result_byte >> 1)
            prev_y += dy
            result.append([prev_x / 1e5, prev_y / 1e5])
    except (IndexError, TypeError):
        pass
    return result

test1 = '116.486639,39.905255;116.487639,39.906255;116.488639,39.907255'
r1 = decode_amap_polyline(test1)
print('Test1 (plain):', len(r1), 'pts, first:', r1[0] if r1 else 'None')

test2 = 'o}yqBzgn}M'
r2 = decode_amap_polyline(test2)
print('Test2 (encoded):', len(r2), 'pts')

print('Test3 (empty):', decode_amap_polyline(''))
print('All tests done')
