#!/usr/bin/env python3
"""Capture real Vlad Tower terrain in both Modern families and Classic parity.

Requires fresh scripts/test-vlad-tower.py --prepare after the packaged build.
Every app uses its own copied save; the player's session is never addressed.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vlad', ROOT/'scripts/test-vlad-tower.py')
vlad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlad)


def main():
    rows = json.loads(vlad.INDEX.read_text())
    results = []
    for index, row in enumerate(rows):
        tilesets = ['lantern-modern', 'soot-and-brass']
        if index == 0: tilesets += ['lantern', 'soot-and-brass-classic']
        for tileset in tilesets:
            result = vlad.shapes.native(row, tileset)
            events = [json.loads(line) for line in
                (Path(result['run'])/'diagnostics.jsonl.engine.jsonl').read_text().splitlines()]
            cells = {}
            for event in events:
                if event['type'] == 'clear' and event.get('window') == 'map': cells.clear()
                elif event['type'] == 'cell': cells[event['x'],event['y']] = event
            known = [c for c in cells.values() if c.get('tile') not in (1469,1470)]
            hidden = [c for c in cells.values() if c.get('tile') in (1469,1470)]
            assert known and all(c.get('material') == 'vlad' for c in known), result
            assert all('material' not in c and 'groundTile' not in c for c in hidden), result
            result.update(material='vlad',knownMaterialCells=len(known),hiddenCells=len(hidden),
                noHiddenGround=True,noHiddenMaterial=True)
            results.append(result)
            (ROOT/'.artifacts/vlad-native-results.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS',result['case'],tileset,result['run'],flush=True)


if __name__ == '__main__': main()
