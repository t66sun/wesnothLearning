"""Apply the accepted native ambush fix to a copied frozen control add-on."""
from hashlib import sha256
from pathlib import Path


_OLD_MOVE = b"        assert((full and final_step and ai.move_full or ai.move)(u,next_hex).ok)"
_NEW_MOVE = (
    b"        local result=(full and final_step and ai.move_full or ai.move)(u,next_hex)",
    b"        if result.status==2005 then return false end -- Native ambush interrupts a legal move.",
    b"        assert(result.ok)",
)


def apply_ambush_compatibility(staged_root):
    """Patch only an already-copied add-on; the frozen parent remains read-only."""
    changes = {}
    for strategy in ('duel', 'four', 'eight'):
        relative = f'lua/{strategy}.lua'
        path = Path(staged_root) / relative
        original = path.read_bytes()
        if original.count(_OLD_MOVE) != 1:
            raise ValueError(f'{relative}: expected one frozen move assertion')
        newline = b'\r\n' if b'\r\n' in original else b'\n'
        updated = original.replace(_OLD_MOVE, newline.join(_NEW_MOVE))
        path.write_bytes(updated)
        changes[relative] = dict(old_sha256=sha256(original).hexdigest(),
                                 new_sha256=sha256(updated).hexdigest())
    return dict(files=changes)
