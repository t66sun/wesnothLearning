"""Readers for preserved native WML capture data."""

def children(cfg):
    """Read the exporter's JSON object form and legacy JSON array form."""
    if isinstance(cfg, dict):
        pairs = [cfg[key] for key in sorted(
            (key for key in cfg if str(key).isdecimal()), key=lambda key: int(key))]
    else:
        pairs = cfg if isinstance(cfg, list) else []
    for pair in pairs:
        if isinstance(pair, dict):
            tag, value = pair.get('1'), pair.get('2')
        elif isinstance(pair, list) and len(pair) == 2:
            tag, value = pair
        else:
            raise ValueError('raw WML child is not a tag/config pair')
        if value == []:
            value = {}
        if not isinstance(tag, str) or not isinstance(value, dict):
            raise ValueError('raw WML child has no tag/config')
        yield tag, value

