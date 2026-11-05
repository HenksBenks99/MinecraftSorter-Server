"""Self-check della logica pura di gui.py (nessuna finestra). Esegui: python test_gui.py"""
import json
import tempfile
from pathlib import Path

import gui


def touch(folder, *names):
    for n in names:
        (folder / n).write_bytes(b'x')


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    a, b, out = d / 'a', d / 'b', d / 'out'
    for p in (a, b, out):
        p.mkdir()
    touch(a, 'jei-1.20.1-1.0.jar', 'jei-1.20.1-2.0.jar', 'create-5.0.jar', 'shared-1.0.jar')
    touch(b, 'shared-1.0.jar', 'only_b-1.0.jar')

    rep = gui.diff_report(a, b)
    assert 'Same mods (exact match): 1' in rep and 'create-5.0.jar' in rep and 'only_b-1.0.jar' in rep

    text, data = gui.list_report(a)
    assert data['total'] == 4 and list(data['conflicts']) == ['jei'] and 'POSSIBLE CONFLICTS' in text
    json.dumps(data)  # serializzabile

    res = [dict(file='create-5.0.jar', side='unknown', reason='PARSER: side=unknown (forge)', action='SKIP', parser_type='forge'),
           dict(file='shared-1.0.jar', side='client', reason='BLACKLIST: x', action='SKIP', parser_type='forge')]
    assert [gui.confidence(r) for r in res] == [50, 90]
    stats = dict(total=2, server=0, client=1, unknown=1)
    gui.apply_manual(dict(stats=stats, results=res), {'create-5.0.jar', 'shared-1.0.jar'}, a, out, dry=False)
    assert (out / 'create-5.0.jar').exists() and not (out / 'shared-1.0.jar').exists()  # solo gli unknown vengono promossi
    assert stats == dict(total=2, server=1, client=1, unknown=0) and (out / 'separation_report.json').exists()
print('ok')
