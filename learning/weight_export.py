"""Lossless float32 weights in a self-contained, SDK-compatible Lua source file."""
import base64
import struct

import native


_DECODER = '''local alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local codes={[61]=0}
for i=1,#alphabet do codes[alphabet:byte(i)]=i-1 end
local function decode(encoded)
    local bytes=encoded:gsub('....',function(group)
        local a,b,c,d=group:byte(1,4)
        local bits=(codes[a]<<18)|(codes[b]<<12)|(codes[c]<<6)|codes[d]
        return string.char((bits>>16)&255,(bits>>8)&255,bits&255)
    end)
    local padding=encoded:sub(-2)=='==' and 2 or (encoded:sub(-1)=='=' and 1 or 0)
    local values={}
    for offset=1,#bytes-padding,4 do
        values[#values+1]=string.unpack('<f',bytes,offset)
    end
    return values
end
'''


def _table(value):
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], float):
            encoded = base64.b64encode(struct.pack('<' + str(len(value)) + 'f', *value)).decode('ascii')
            return 'decode("' + encoded + '")'
        return '{' + ','.join(map(_table, value)) + '}'
    if isinstance(value, dict):
        return '{' + ','.join('[' + native.lua(key) + ']=' + _table(item)
                              for key, item in value.items()) + '}'
    return native.lua(value)


def weight_source(parameters):
    return _DECODER + 'return ' + _table(parameters) + '\n'
