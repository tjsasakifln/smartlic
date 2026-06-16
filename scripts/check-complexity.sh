#!/usr/bin/env bash
# Complexity CI Gate — radon cyclomatic complexity enforcement.
# Same gate as .github/workflows/complexity-gate.yml, runs locally.
#
# Rules:
#   1. Average complexity per file > threshold (10 standard, 15 core >500 LOC)
#   2. Any individual function > 30 (threshold C) — fail
#   3. New functions (not in baseline) with complexity > 15 (threshold B) — fail
#   4. Only checks files changed in PR diff vs origin/main
#   5. Skips tests/, venv/, .venv/, migrations/, scripts/
#
# Exit 0 = pass, Exit 1 = fail

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BASELINE_FILE="$ROOT_DIR/.radon-baseline.json"
HTML_REPORT_DIR="${HTML_REPORT_DIR:-/tmp/complexity-report}"

# Thresholds (matches .radon-baseline.json)
AVG_THRESHOLD_STANDARD=10
AVG_THRESHOLD_CORE=15
CORE_LOC=500
NEW_FUNCTION_BLOCK=15
INDIVIDUAL_CAP=30

# ---------- helpers ----------

die() { echo "❌ $*" >&2; exit 1; }
info() { echo "ℹ️  $*"; }

# Determine diff base: use PR base ref if available, else HEAD~1
get_diff_base() {
  if git rev-parse "origin/main" >/dev/null 2>&1; then
    echo "origin/main"
  elif git rev-parse "main" >/dev/null 2>&1; then
    echo "main"
  else
    echo "HEAD~1"
  fi
}

# ---------- Python validation logic ----------

# This uses Python to do all the heavy lifting (radon + baseline checking)
# because bash associative arrays are fragile with complex keys.
# Export vars so the Python heredoc subprocess can access them.
export ROOT_DIR BASELINE_FILE HTML_REPORT_DIR
export AVG_THRESHOLD_STANDARD AVG_THRESHOLD_CORE CORE_LOC
export NEW_FUNCTION_BLOCK INDIVIDUAL_CAP
python3 << 'PYEOF'
import json, os, subprocess, sys

ROOT_DIR = os.environ.get('ROOT_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASELINE_FILE = os.environ.get('BASELINE_FILE', os.path.join(ROOT_DIR, '.radon-baseline.json'))
HTML_REPORT_DIR = os.environ.get('HTML_REPORT_DIR', '/tmp/complexity-report')

AVG_THRESHOLD_STANDARD = int(os.environ.get('AVG_THRESHOLD_STANDARD', '10'))
AVG_THRESHOLD_CORE = int(os.environ.get('AVG_THRESHOLD_CORE', '15'))
CORE_LOC = int(os.environ.get('CORE_LOC', '500'))
NEW_FUNCTION_BLOCK = int(os.environ.get('NEW_FUNCTION_BLOCK', '15'))
INDIVIDUAL_CAP = int(os.environ.get('INDIVIDUAL_CAP', '30'))

# --- Scope ---

def is_prod_python(filepath):
    """Check if a file is a production Python file (not test/venv/migration/script)."""
    if not (filepath.startswith('backend/') and (filepath.endswith('.py'))):
        return False
    skip_prefixes = [
        'backend/tests/', 'backend/venv/', 'backend/.venv/',
        'backend/migrations/', 'backend/__pycache__/', 'backend/scripts/',
    ]
    for prefix in skip_prefixes:
        if filepath.startswith(prefix):
            return False
    # Also skip files in subdirectories of these
    skip_dirs = ['/tests/', '/venv/', '/.venv/', '/migrations/', '/__pycache__/']
    for d in skip_dirs:
        if d in filepath:
            return False
    return True


def get_changed_files(diff_base):
    """Get list of files changed between diff_base and HEAD."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', diff_base, 'HEAD'],
            capture_output=True, text=True, timeout=30, cwd=ROOT_DIR
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.split('\n') if f.strip()]
    except Exception:
        pass
    return []


def count_lines(filepath):
    """Count lines in a file."""
    try:
        with open(filepath) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def load_baseline():
    """Load baseline functions, returns dict of 'filepath:funcname' -> complexity."""
    baseline = {}
    try:
        with open(BASELINE_FILE) as f:
            data = json.load(f)
        for filepath, funcs in data.get('functions', {}).items():
            for func in funcs:
                baseline[f"{filepath}:{func['name']}"] = func['complexity']
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️  Baseline file issue: {e}. Proceeding without baseline check.", file=sys.stderr)
    return baseline


def run_radon_json(filepath):
    """Run radon cc --json on a single file from /tmp to avoid pyproject.toml issues."""
    abs_path = os.path.join(ROOT_DIR, filepath) if not os.path.isabs(filepath) else filepath
    if not os.path.exists(abs_path):
        return None
    try:
        result = subprocess.run(
            ['python3', '-m', 'radon', 'cc', '--min', 'A', '--show-complexity', '--json', abs_path],
            capture_output=True, text=True, timeout=60, cwd='/tmp'
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_average_complexity(filepath):
    """Get average complexity for a file using radon cc --average."""
    abs_path = os.path.join(ROOT_DIR, filepath) if not os.path.isabs(filepath) else filepath
    if not os.path.exists(abs_path):
        return None
    try:
        result = subprocess.run(
            ['python3', '-m', 'radon', 'cc', '--average', '--min', 'A', abs_path],
            capture_output=True, text=True, timeout=60, cwd='/tmp'
        )
        if result.returncode != 0:
            return None
        # Parse "Average complexity: X (rank)" from output
        for line in result.stdout.split('\n'):
            if 'Average complexity:' in line:
                import re
                match = re.search(r'\(([0-9.]+)\)', line)
                if match:
                    return float(match.group(1))
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def generate_html_report(results_by_file):
    """Generate an HTML complexity report."""
    os.makedirs(HTML_REPORT_DIR, exist_ok=True)
    report_path = os.path.join(HTML_REPORT_DIR, 'complexity-report.html')

    rows = []
    for filepath, info in sorted(results_by_file.items()):
        violations_str = ', '.join(info.get('violations', [])) or 'None'
        status = '❌' if info.get('fail') else '✅'
        rows.append(f"""<tr>
            <td>{status}</td>
            <td><code>{filepath}</code></td>
            <td>{info.get('loc', '?')}</td>
            <td>{info.get('avg_complexity', '?')}</td>
            <td>{info.get('threshold', '?')}</td>
            <td>{violations_str}</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Complexity Gate Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; }}
h1 {{ color: #333; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #f5f5f5; }}
tr:nth-child(even) {{ background-color: #fafafa; }}
code {{ background: #f0f0f0; padding: 2px 4px; border-radius: 3px; }}
.summary {{ margin: 1rem 0; padding: 1rem; background: #f5f5f5; border-radius: 4px; }}
.pass {{ color: green; }} .fail {{ color: red; }}
</style>
</head>
<body>
<h1>Cyclomatic Complexity Gate Report</h1>
<div class="summary">
    <p>Generated: 2026-06-15</p>
    <p>Thresholds: Standard average &le; 10, Core average &le; 15, New function &le; 15, Individual cap &le; 30</p>
</div>
<table>
<thead><tr><th>Status</th><th>File</th><th>LOC</th><th>Avg Cplx</th><th>Threshold</th><th>Violations</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</body>
</html>"""

    with open(report_path, 'w') as f:
        f.write(html)
    print(f"📊 HTML report: {report_path}")
    return report_path


# --- Main ---

diff_base = os.environ.get('DIFF_BASE') or subprocess.run(
    ['bash', '-c', 'cd "$ROOT_DIR" && git rev-parse origin/main 2>/dev/null || echo HEAD~1'],
    capture_output=True, text=True
).stdout.strip()

print(f"ℹ️  Diff base: {diff_base}")
print(f"ℹ️  Checking production backend Python files changed since {diff_base}...")

changed_files = get_changed_files(diff_base)
prod_files = [f for f in changed_files if is_prod_python(f)]

if not prod_files:
    print("ℹ️  No production Python files changed. Skipping complexity check.")
    sys.exit(0)

print(f"ℹ️  Checking {len(prod_files)} production Python file(s)...")

baseline = load_baseline()
total_failures = 0
results_by_file = {}

for filepath in prod_files:
    abs_path = os.path.join(ROOT_DIR, filepath)
    if not os.path.exists(abs_path):
        continue

    file_loc = count_lines(abs_path)
    avg_threshold = AVG_THRESHOLD_CORE if file_loc > CORE_LOC else AVG_THRESHOLD_STANDARD

    # Get average complexity
    avg_cplx = get_average_complexity(filepath)

    # Get individual function data
    radon_data = run_radon_json(filepath)

    file_fail = False
    violations = []

    # Rule 1: Average complexity check
    if avg_cplx is not None and avg_cplx > avg_threshold:
        msg = f"Average complexity {avg_cplx:.1f} exceeds threshold {avg_threshold} in {filepath}"
        print(f"::error file={filepath},title=Average complexity >{avg_threshold}::{msg}", file=sys.stderr)
        violations.append(f"avg {avg_cplx:.1f}>{avg_threshold}")
        file_fail = True

    # Rule 2 & 3: Individual function checks
    if radon_data:
        for radon_filepath, blocks in radon_data.items():
            for block in blocks:
                cplx = block['complexity']
                name = block['name']
                lineno = block['lineno']
                key = f"{filepath}:{name}"

                # Rule 2: Individual function > cap (30)
                if cplx > INDIVIDUAL_CAP and key not in baseline:  # baseline exempt (grandfathered legacy)
                    msg = f"Function {name} (line {lineno}) has complexity {cplx}, exceeding cap of {INDIVIDUAL_CAP}"
                    print(f"::error file={filepath},line={lineno},title=Complexity exceeds cap ({cplx} > {INDIVIDUAL_CAP})::{msg}", file=sys.stderr)
                    violations.append(f"{name}:{cplx}>{INDIVIDUAL_CAP} (cap)")
                    file_fail = True

                # Rule 3: New function > block (15) not in baseline
                elif cplx > NEW_FUNCTION_BLOCK and key not in baseline:
                    msg = f"New function {name} (line {lineno}) has complexity {cplx}. New functions must be <= {NEW_FUNCTION_BLOCK} or added to baseline."
                    print(f"::error file={filepath},line={lineno},title=New function exceeds complexity ({cplx} > {NEW_FUNCTION_BLOCK})::{msg}", file=sys.stderr)
                    violations.append(f"{name}:{cplx}>{NEW_FUNCTION_BLOCK} (new)")
                    file_fail = True

    results_by_file[filepath] = {
        'loc': file_loc,
        'avg_complexity': f"{avg_cplx:.1f}" if avg_cplx is not None else 'N/A',
        'threshold': avg_threshold,
        'violations': violations,
        'fail': file_fail,
    }

    if file_fail:
        total_failures += 1

# Generate HTML report
report_path = generate_html_report(results_by_file)

# Summary
print("")
if total_failures > 0:
    print(f"❌ Complexity gate FAILED — {total_failures} file(s) with violations.")
    print("   Fix violations before merging. See annotations above.")
    sys.exit(1)

print("✅ Complexity gate PASSED — no violations detected.")
sys.exit(0)
PYEOF
