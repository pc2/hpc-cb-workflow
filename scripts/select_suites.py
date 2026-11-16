"""Select the benchmark suites of a finished pipeline from its collected job archives."""

import fnmatch
import json
import os
from pathlib import Path
import re
import sys
import zipfile

# The selected commit decides the number of written suites, each one starts a job.
WRITTEN_LIMIT = 100


def select(suites, statuses, artifacts):
    """Return the suites to compare and the notes for the run summary.

    Named suites need the archive of a successful job.
    Rules, the suites with a match, take their suites from the files
    hpc-benchmarks/<suite name>.json of these archives, only the member names are read.
    """
    rules = [suite for suite in suites if 'match' in suite]
    named = [suite for suite in suites if 'match' not in suite]
    selected, notes = [], []
    for suite in named:
        status = statuses.get(suite.get('archive'))
        if status == 'success':
            selected.append(suite)
        elif status is None:
            notes.append(f'Benchmark suite {suite.get("name")} skipped, this run collected no archive {suite.get("archive")}.')
        else:
            notes.append(f'Benchmark suite {suite.get("name")} skipped, the job of archive {suite.get("archive")} finished with {status}.')
    if not rules:
        return selected, notes
    names = {suite.get('name') for suite in named}
    found = {}
    searched = 0
    for archive, status in sorted(statuses.items()):
        path = Path(artifacts) / archive
        if status != 'success' or not path.is_file():
            continue
        searched += 1
        with zipfile.ZipFile(path) as source:
            members = source.namelist()
        for member in members:
            parts = re.fullmatch(r'hpc-benchmarks/([^/]+)\.json', member)
            if not parts:
                continue
            name = parts[1]
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,100}', name):
                raise ValueError(f'The archive {archive} holds the invalid suite name {name!r}.')
            if name in names:
                raise ValueError(f'Benchmark suite {name} is defined more than once, last in archive {archive}.')
            names.add(name)
            rule = next((rule for rule in rules if fnmatch.fnmatchcase(name, rule['match'])), None)
            if rule is None:
                raise ValueError(f'No suite rule matches the benchmark suite {name} of archive {archive}.')
            found[name] = {key: value for key, value in rule.items() if key != 'match'} | {
                'name': name, 'archive': archive, 'file': member}
            notes.append(f'Benchmark suite {name} found in archive {archive}, rule {rule["match"]}.')
    if len(found) > WRITTEN_LIMIT:
        raise ValueError(f'The jobs wrote {len(found)} benchmark suites, at most {WRITTEN_LIMIT} are supported.')
    notes.append(f'Found {len(found)} written benchmark suites in {searched} archives of successful jobs.')
    return selected + [found[name] for name in sorted(found)], notes


def main():
    suites = json.loads(os.environ['SUITES'])
    statuses = json.loads(Path(os.environ['STATUS_FILE']).read_text())
    try:
        selected, notes = select(suites, statuses, os.environ['ARTIFACTS'])
    except ValueError as error:
        print(f'::error::{error}')
        sys.exit(1)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write(''.join(f'{note}\n' for note in notes))
    for suite in selected:
        print(f'Benchmark suite {suite.get("name")} selected, file {suite.get("file")} of archive {suite.get("archive")}.')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'suites={json.dumps(selected, separators=(",", ":"))}\n')


if __name__ == '__main__':
    main()
