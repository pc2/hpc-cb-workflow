"""Embed trusted helpers so reusable workflows need no source checkout to run them."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def render(template):
    lines = []
    for line in template.read_text().splitlines(keepends=True):
        if line.lstrip().startswith('# EMBED '):
            name = line.strip().removeprefix('# EMBED ')
            indent = line[:len(line) - len(line.lstrip())]
            lines.extend(indent + source + '\n' for source in (ROOT / 'scripts' / name).read_text().splitlines())
        else:
            lines.append(line)
    return ''.join(lines)


if __name__ == '__main__':
    for template in (ROOT / '.github/templates').glob('*.yml'):
        target = ROOT / '.github/workflows' / template.name
        content = render(template)
        if '--check' in sys.argv:
            if not target.exists() or target.read_text() != content:
                raise SystemExit(f'Regenerate {target.name} with scripts/embed_helpers.py.')
        else:
            target.write_text(content)
