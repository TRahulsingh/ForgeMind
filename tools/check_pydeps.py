import importlib.metadata, pathlib, sys
from packaging.version import Version
import importlib.util

args = sys.argv[1:]
gte = "--gte" in args
list_missing = "--list-missing" in args

reqs = [l.strip() for l in pathlib.Path('requirements.txt').read_text().splitlines() if '==' in l and not l.strip().startswith('#')]
miss = []
miss_pkgs = []
for r in reqs:
    try:
        name = r.split('==')[0].split('[')[0].strip()
        ver = r.split('==')[1].strip()
        # Check if module exists
        if importlib.util.find_spec(name.replace('-','_')) is None and importlib.util.find_spec(name) is None:
            # Try import via metadata
            try:
                importlib.metadata.version(name)
            except:
                miss.append(r)
                miss_pkgs.append(r)
                continue
        if gte:
            # Only missing if installed version < required (never downgrade)
            installed = importlib.metadata.version(name)
            if Version(installed) < Version(ver):
                miss.append(f"{name} {installed} < {ver}")
                miss_pkgs.append(r)
        else:
            # Strict == check (for CI)
            if importlib.metadata.version(name) != ver:
                miss.append(f"{name} {importlib.metadata.version(name)} != {ver}")
                miss_pkgs.append(r)
    except Exception:
        miss.append(r)
        miss_pkgs.append(r)

if list_missing:
    for m in miss_pkgs:
        print(m)
    sys.exit(0 if not miss else 1)
else:
    sys.exit(0 if not miss else 1)
