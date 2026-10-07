#!/usr/bin/env python3
"""Compare creation choices with upstream masks and actual engine characters."""
import json
import importlib.util
from itertools import product
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / 'engine/runtime'
spec = importlib.util.spec_from_file_location('engine_test', ROOT / 'scripts/test-engine.py')
engine_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_test)


def upstream_rules():
    source = (ROOT / 'vendor/NetHack-5.0.0/src/role.c').read_text()
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)

    def entries(name):
        body = source.split(f'const struct {name} ', 1)[1].split('= {', 1)[1]
        depth = 0
        start = 0
        for match in re.finditer(r'"(?:\\.|[^"\\])*"|[{}]', body):
            token = match.group()
            if token == '{':
                if depth == 0:
                    start = match.start()
                depth += 1
            elif token == '}':
                if depth == 0:
                    break
                depth -= 1
                if depth == 0:
                    yield body[start:match.end()]

    def parse(entry, role):
        name = re.search(r'"([^"]+)"', entry).group(1)
        mask = next(m.group() for m in re.finditer(
            r'MH_[A-Z]+(?:\s*\|\s*(?:MH_|ROLE_)[A-Z]+)*', entry)
            if 'ROLE_' in m.group())
        flags = set(re.findall(r'(?:MH_|ROLE_)[A-Z]+', mask))
        result = {
            'genders': [v for v in ['male', 'female'] if 'ROLE_' + v.upper() in flags],
            'alignments': [v for v in ['lawful', 'neutral', 'chaotic']
                           if 'ROLE_' + v.upper() in flags],
        }
        if role:
            result['races'] = [v for v in ['human', 'elf', 'dwarf', 'gnome', 'orc']
                               if 'MH_' + v.upper() in flags]
        return name, result

    roles = dict(parse(entry, True) for entry in entries('Role'))
    races = dict(parse(entry, False) for entry in entries('Race'))
    assert len(roles) == 13 and len(races) == 5, (roles, races)
    return {'roles': roles, 'races': races}


def check_frontend(expected):
    actual = json.loads(subprocess.check_output([
        'node', '-e', 'const {roles,races}=require("./web/character.js");'
        'process.stdout.write(JSON.stringify({roles,races}));'], cwd=ROOT, text=True))
    for category in expected:
        assert actual[category].keys() == expected[category].keys(), category
        for name, fields in expected[category].items():
            for field, values in fields.items():
                assert set(actual[category][name][field]) == set(values), (
                    category, name, field, actual[category][name][field], values)
    print('PASS: all 13 roles and 5 races match upstream sex/race/alignment masks')

    fields = ['role', 'race', 'gender', 'alignment']
    full_tuples = [
        (role, race, gender, alignment)
        for role, rule in expected['roles'].items()
        for race in rule['races']
        for gender in rule['genders']
        for alignment in rule['alignments']
        if gender in expected['races'][race]['genders']
        and alignment in expected['races'][race]['alignments']
    ]
    candidates = list(product(
        [*expected['roles'], 'random', '', 'unknown'],
        [*expected['races'], 'random', '', 'unknown'],
        ['male', 'female', 'random', '', 'unknown'],
        ['lawful', 'neutral', 'chaotic', 'random', '', 'unknown'],
    ))
    oracle = [any(all(want == 'random' or want == value
                      for want, value in zip(candidate, full))
                  for full in full_tuples)
              for candidate in candidates]
    resolve_cases = [
        # Changing a male human Wizard to Valkyrie forces the only legal sex.
        ({'role': 'Valkyrie', 'race': 'human', 'gender': 'male', 'alignment': 'neutral'},
         {'role': 'Valkyrie', 'race': 'human', 'gender': 'female', 'alignment': 'neutral'}),
        # Knight forces human/lawful while retaining an explicitly selected sex.
        ({'role': 'Knight', 'race': 'orc', 'gender': 'female', 'alignment': 'chaotic'},
         {'role': 'Knight', 'race': 'human', 'gender': 'female', 'alignment': 'lawful'}),
        # An invalid non-forced alignment must require another explicit choice.
        ({'role': 'Wizard', 'race': 'human', 'gender': 'male', 'alignment': 'lawful'},
         {'role': 'Wizard', 'race': 'human', 'gender': 'male', 'alignment': ''}),
        # Random remains explicit when more than one permissible value exists.
        ({'role': 'Wizard', 'race': 'random', 'gender': 'random', 'alignment': 'random'},
         {'role': 'Wizard', 'race': 'random', 'gender': 'random', 'alignment': 'random'}),
    ]
    payload = {
        'selections': [dict(zip(fields, values)) for values in candidates],
        'resolve': [before for before, after in resolve_cases],
    }
    result = subprocess.run([
        'node', '-e',
        'const c=require("./web/character.js");'
        'const input=JSON.parse(require("fs").readFileSync(0,"utf8"));'
        'const resolved=input.resolve.map(c.resolve);'
        'process.stdout.write(JSON.stringify({'
        'valid:input.selections.map(c.valid),resolved,'
        'resolvedValid:resolved.map(c.valid)}));',
    ], input=json.dumps(payload), cwd=ROOT, text=True, capture_output=True, check=True)
    results = json.loads(result.stdout)
    for selection, actual_valid, expected_valid in zip(candidates, results['valid'], oracle):
        assert actual_valid == expected_valid, (selection, actual_valid, expected_valid)
    assert results['resolved'] == [after for before, after in resolve_cases], results['resolved']
    assert results['resolvedValid'] == [True, True, False, True], results['resolvedValid']
    print(f'PASS: {len(candidates)} combinations, including random and invalid values, '
          'match the upstream legal-character oracle; dependent choices normalize correctly')


def engine_character(role, race, gender, alignment, expected):
    with tempfile.TemporaryDirectory(prefix='atlas-character-') as directory:
        target = Path(directory)
        for name in ['nhdat', 'license', 'symbols', 'sysconf']:
            shutil.copy2(RUNTIME / name, target / name)
        for name in ['perm', 'record', 'logfile', 'xlogfile']:
            (target / name).touch()
        (target / 'save').mkdir()
        args = [str(RUNTIME / 'nethack'), '-u', 'AtlasCreation', '-@']
        for value, flag in [(role, '-p'), (race, '-r')]:
            if value != 'random':
                args += [flag, value]
        options = ['!news', '!autopickup']
        for value, key in [(gender, 'gender'), (alignment, 'align')]:
            if value != 'random':
                options.append(f'{key}:{value}')
        process = subprocess.Popen(args, cwd=target,
            env=engine_test.engine_environment(directory, options=','.join(options)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        events = queue.Queue()

        def read():
            for line in process.stdout:
                events.put(json.loads(line))
            events.put({'type': 'eof'})

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        welcome = None
        try:
            for _ in range(10000):
                event = events.get(timeout=10)
                assert event['type'] != 'eof', event
                if event['type'] == 'message' and 'welcome to NetHack!' in event['text']:
                    welcome = event['text']
                if event['type'] != 'input':
                    continue
                if event['kind'] == 'key' and event.get('command'):
                    break
                if event['kind'] == 'menu':
                    assert 'tutorial' in event['prompt'].lower(), event
                    selection = next(i['id'] for i in event['items'] if i['key'] == 'n')
                    reply = f'menu {selection}'
                elif event['kind'] in ['text', 'key']:
                    reply = 'key 32'
                else:
                    raise AssertionError(('Unexpected creation prompt', event))
                process.stdin.write(reply + '\n')
                process.stdin.flush()
            else:
                raise AssertionError('No command prompt')
            assert welcome, 'Missing real-engine character description'
            match = re.search(r'You are a (lawful|neutral|chaotic) '
                              r'(?:(male|female) )?'
                              r'(human|elven|dwarven|gnomish|orcish) (\w+)\.', welcome)
            assert match, welcome
            actual_alignment, actual_gender, race_adj, role_name = match.groups()
            actual_race = dict(human='human', elven='elf', dwarven='dwarf',
                               gnomish='gnome', orcish='orc')[race_adj]
            if actual_gender is None:
                actual_gender = 'female' if role_name in ['Valkyrie', 'Cavewoman', 'Priestess'] else 'male'
            actual_role = {'Cavewoman': 'Caveman', 'Priestess': 'Priest'}.get(role_name, role_name)
            actual = (actual_role, actual_race, actual_gender, actual_alignment)
            requested = (role, race, gender, alignment)
            for selected, result in zip(requested, actual):
                assert selected == 'random' or selected == result, (requested, actual, welcome)
            role_rules = expected['roles'][actual_role]
            race_rules = expected['races'][actual_race]
            assert actual_race in role_rules['races'], actual
            assert actual_gender in role_rules['genders'] and actual_gender in race_rules['genders'], actual
            assert actual_alignment in role_rules['alignments'] and actual_alignment in race_rules['alignments'], actual
            print('PASS:', '/'.join(requested), '->', '/'.join(actual))
        finally:
            process.stdin.close()  # Upstream hangup saves only this isolated test character.
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            reader.join(timeout=2)
        assert process.returncode == 0, process.stderr.read()


def main():
    expected = upstream_rules()
    check_frontend(expected)
    scenarios = [
        ('Knight', 'human', gender, 'lawful') for gender in ['male', 'female']
    ] + [
        ('Wizard', race, gender, alignment)
        for race, alignment in [('human', 'neutral'), ('elf', 'chaotic'),
                                ('gnome', 'neutral'), ('orc', 'chaotic')]
        for gender in ['male', 'female']
    ] + [
        ('Rogue', race, gender, 'chaotic')
        for race in ['human', 'orc'] for gender in ['male', 'female']
    ] + [
        ('Valkyrie', 'human', 'female', 'neutral'),
        ('Valkyrie', 'dwarf', 'female', 'lawful'),
        ('Knight', 'random', 'female', 'random'),
        ('Valkyrie', 'random', 'random', 'random'),
    ] + [
        ('random', 'random', gender, alignment)
        for gender in ['male', 'female'] for alignment in ['lawful', 'neutral', 'chaotic']
    ]
    for scenario in scenarios:
        engine_character(*scenario, expected)
    print(f'PASS: {len(scenarios)} real-engine starts preserve explicit choices and valid combinations')


if __name__ == '__main__':
    main()
