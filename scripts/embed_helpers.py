"""Embed trusted helpers so reusable workflows need no source checkout to run them.

A workflow marks the place of a helper from scripts/ with the comment lines
`# BEGIN EMBED <file>` and `# END EMBED <file>`, the text between them is generated.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def render(text):
    lines = []
    end = None
    for line in text.splitlines(keepends=True):
        marker = line.strip()
        if end:
            if marker == end:
                lines.append(line)
                end = None
        elif marker.startswith('# BEGIN EMBED '):
            name = marker.removeprefix('# BEGIN EMBED ')
            indent = line[:len(line) - len(line.lstrip())]
            lines.append(line)
            lines.extend(indent + source + '\n' for source in (ROOT / 'scripts' / name).read_text().splitlines())
            end = f'# END EMBED {name}'
        else:
            lines.append(line)
    if end:
        raise ValueError(f'Missing the line {end}.')
    return ''.join(lines)


if __name__ == '__main__':
    for workflow in sorted((ROOT / '.github/workflows').glob('*.yml')):
        text = workflow.read_text()
        content = render(text)
        if content == text:
            continue
        if '--check' in sys.argv:
            raise SystemExit(f'Regenerate {workflow.name} with scripts/embed_helpers.py.')
        workflow.write_text(content)
