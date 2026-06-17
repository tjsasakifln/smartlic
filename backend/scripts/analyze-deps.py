#!/usr/bin/env python3
"""
Circular Dependency Analyzer for SmartLic backend.

Parses all Python files using AST, builds dependency graph,
detects circular dependencies using Tarjan's SCC algorithm.
"""

import ast
import os
import sys
from collections import defaultdict


def find_python_modules(root_dir):
    """Build a map of module_name -> filepath, excluding tests/ and venv."""
    module_map = {}
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden, venv, __pycache__, tests/, migrations/
        dirs[:] = [d for d in dirs if not d.startswith('.')
                   and d != '__pycache__' and d != 'venv' and d != 'migrations']
        if '/tests' in root or '/venv' in root or '/.' in root:
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
            rel = os.path.relpath(filepath, root_dir)
            if f == '__init__.py':
                module_name = rel[:-12].replace(os.sep, '.')
                if module_name.endswith('.'):
                    module_name = module_name[:-1]
            else:
                module_name = rel[:-3].replace(os.sep, '.')
            module_map[module_name] = os.path.abspath(filepath)
    return module_map


def extract_imports(filepath):
    """Extract top-level first-party imported module names from a file using AST."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split('.')[0]
                imports.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split('.')[0]
                imports.add(top)
    return imports


def tarjan_scc(graph):
    """Find strongly connected components using Tarjan's algorithm."""
    index_counter = [0]
    indices = {}
    lowlink = {}
    on_stack = set()
    stack = []
    sccs = []

    def strongconnect(node):
        indices[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in graph:
                continue
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif neighbor in on_stack:
                lowlink[node] = min(lowlink[node], indices[neighbor])

        if lowlink[node] == indices[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == node:
                    break
            if len(scc) > 1:
                sccs.append(scc)

    for node in graph:
        if node not in indices:
            strongconnect(node)
    return sccs


def main():
    args_list = sys.argv[1:]
    ci_mode = '--ci' in args_list
    args_list = [a for a in args_list if a != '--ci']

    if args_list:
        # Check for help
        if args_list[0] in ('-h', '--help'):
            print("Usage: python scripts/analyze-deps.py [--ci] [directory]")
            print("  --ci         : CI-friendly output (parsable exit code)")
            print("  directory     : Root directory to scan (default: current)")
            sys.exit(0)

    root_dir = args_list[0] if args_list else '.'

    if not ci_mode:
        print("=" * 70)
        print("  CIRCULAR DEPENDENCY ANALYZER")
        print("=" * 70)

    # Phase 1: Build module map
    module_map = find_python_modules(root_dir)
    if not ci_mode:
        print(f"\n[1/4] Found {len(module_map)} Python modules")

    # Phase 2: Extract imports
    if not ci_mode:
        print("[2/4] Extracting imports via AST...")
    top_level_pkgs = set()
    for m in module_map:
        pkg = m.split('.')[0]
        top_level_pkgs.add(pkg)

    graph = {}
    for mod_name, filepath in sorted(module_map.items()):
        if not os.path.exists(filepath):
            continue
        deps = extract_imports(filepath)
        local_deps = {d for d in deps if d in top_level_pkgs
                      and d != mod_name.split('.')[0]}
        graph[mod_name] = local_deps

    if not ci_mode:
        print(f"[3/4] Analyzing {len(graph)} nodes with {sum(len(v) for v in graph.values())} edges")

    # Phase 3: Find cycles (full graph)
    sccs = tarjan_scc(graph)

    # Phase 4: Condensed top-level graph
    top_graph = defaultdict(set)
    for mod, deps in graph.items():
        top_mod = mod.split('.')[0]
        for dep in deps:
            if dep != top_mod:
                top_graph[top_mod].add(dep)

    top_sccs = tarjan_scc(top_graph)

    # Phase 4b: Check against baseline (known/accepted cycles)
    baseline_path = os.path.join(os.path.abspath(root_dir), '.circular-dep-baseline')
    baseline_cycles = []
    if os.path.exists(baseline_path):
        with open(baseline_path) as f:
            for line in f:
                stripped = line.split('#')[0].strip()
                if stripped:
                    parts = stripped.split()
                    if len(parts) >= 2:
                        baseline_cycles.append(frozenset(parts))

    # Filter out baseline cycles
    new_cycles = []
    for scc in top_sccs:
        scc_set = frozenset(scc)
        if not any(scc_set == baseline for baseline in baseline_cycles):
            new_cycles.append(scc)

    # Use new_cycles for exit code decision; top_sccs for reporting

    if ci_mode:
        # CI mode: output summary line, exit with 0/1
        num_baseline = len(top_sccs) - len(new_cycles)
        if new_cycles:
            print(f"[CIRC-DEP] FAIL — {len(new_cycles)} NEW circular dependenc(ies) detected")
            for i, cycle in enumerate(new_cycles, 1):
                print(f"  Cycle {i}: {' <-> '.join(cycle)}")
            if num_baseline > 0:
                print(f"  ({num_baseline} known baseline cycle(s) ignored)")
            sys.exit(1)
        elif top_sccs:
            print(f"[CIRC-DEP] PASS — All {len(top_sccs)} cycle(s) match known baseline")
            sys.exit(0)
        else:
            print("[CIRC-DEP] PASS — No circular dependencies detected")
            sys.exit(0)

    # Report (interactive mode)
    print("[4/4] Results")
    print("=" * 70)

    if top_sccs:
        print(f"\n  TOP-LEVEL CYCLES FOUND: {len(top_sccs)}")
        if baseline_cycles:
            print(f"  ({len(top_sccs) - len(new_cycles)} matched baseline, {len(new_cycles)} new)")
        print("-" * 70)
        for i, cycle in enumerate(top_sccs, 1):
            scc_set = frozenset(cycle)
            is_baseline = any(scc_set == baseline for baseline in baseline_cycles)
            label = " (baseline)" if is_baseline else " (NEW)"
            print(f"  Cycle {i}: {' <-> '.join(cycle)}{label}")
        print()
    else:
        print("\n  [PASS] No top-level circular dependencies")
        print("  The top-level package graph is acyclic.")

    # If there are SCCs in the full graph but not at the top level,
    # they might be intra-package cycles
    if sccs and not top_sccs:
        print(f"\n  [INFO] {len(sccs)} intra-package cycle(s) detected (within same package):")
        for i, cycle in enumerate(sccs, 1):
            pkgs_in_cycle = set(m.split('.')[0] for m in cycle)
            print(f"  Cycle {i} in package(s) {', '.join(sorted(pkgs_in_cycle))}:")
            for mod in sorted(cycle):
                print(f"    - {mod}")

    # Dependency overview for key top-level packages
    print("\n  Top-level dependency map (first 30):")
    print("-" * 70)
    for mod in sorted(top_graph.keys()):
        deps = top_graph[mod]
        if deps:
            dep_str = ', '.join(sorted(deps))
            print(f"  {mod:30} -> {dep_str}")

    # Print known hot-spot analysis
    print("\n  Analysis for known cycles (auth<->admin, config<->pncp_client):")
    print("-" * 70)

    # Check auth -> admin -> auth
    if 'auth' in top_graph and 'admin' in top_graph:
        auth_deps = top_graph.get('auth', set())
        admin_deps = top_graph.get('admin', set())
        print(f"  auth -> {', '.join(sorted(auth_deps)) if auth_deps else '(nothing)'}")
        print(f"  admin -> {', '.join(sorted(admin_deps)) if admin_deps else '(nothing)'}")
        if 'admin' in auth_deps and 'auth' in admin_deps:
            print("  [CYCLE] auth <-> admin: DIRECT CIRCULAR DEPENDENCY!")
        elif 'admin' in auth_deps:
            print("  [OK] auth -> admin (one-directional)")
        elif 'auth' in admin_deps:
            print("  [OK] admin -> auth (one-directional)")
        else:
            print("  [OK] No direct dependency between auth and admin")

    if 'config' in top_graph:
        config_deps = top_graph.get('config', set())
        print(f"  config -> {', '.join(sorted(config_deps)) if config_deps else '(nothing)'}")
    for client in ['pncp_client', 'portal_compras_client', 'compras_gov_client']:
        if client in top_graph:
            client_deps = top_graph.get(client, set())
            print(f"  {client:30} -> {', '.join(sorted(client_deps)) if client_deps else '(nothing)'}")
            if 'config' in client_deps:
                # Check if config also depends on this client
                config_deps = top_graph.get('config', set())
                if client in config_deps:
                    print(f"  [CYCLE] config <-> {client}: CONFIG DEPENDENCY CYCLE!")

    sys.exit(1 if new_cycles else 0)


if __name__ == '__main__':
    main()
