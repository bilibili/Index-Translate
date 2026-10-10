#!/usr/bin/env python3
"""CPU-only whole-document chrF2 sidecar; never rewrites source artifacts."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from prepare_document_segale import read_jsonl, sha_text, write_jsonl
from summarize_document_segale import STANDARD_METADATA_FIELDS, case_metadata

VERSION = "2.6.0"
PARAMETERS = dict(char_order=6, word_order=0, beta=2, lowercase=False,
                  whitespace=False, eps_smoothing=False)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def metric():
    import sacrebleu
    from sacrebleu.metrics import CHRF
    if sacrebleu.__version__ != VERSION:
        raise ValueError(f"Expected sacrebleu=={VERSION}, got {sacrebleu.__version__}")
    return CHRF(**PARAMETERS)


def aggregate(rows):
    scores = [r['chrf2'] for r in rows if r['chrf2'] is not None]
    return {
        'label': 'document macro chrF2', 'scale': [0, 100],
        'value': statistics.fmean(scores) if scores else None,
        'case_count': len(rows), 'scored_case_count': len(scores),
        'macro_denominator': len(scores), 'failed_case_count': len(rows) - len(scores),
        'empty_output_count': sum(r['empty_output'] is True and r['chrf2'] is not None for r in rows),
        'generation_status_counts': dict(sorted(Counter(r['generation_status'] for r in rows).items())),
        'eligibility_status_counts': dict(sorted(Counter(r['eligibility_status'] for r in rows).items())),
    }


def score(cases, units, generations):
    scorer = metric()
    by_id = {r['case_id']: r for r in cases}
    runs = {r['case_id']: r for r in generations}
    if not cases or len(by_id) != len(cases) or len(runs) != len(generations):
        raise ValueError('Empty cases or duplicate case_id')
    if set(runs) - set(by_id):
        raise ValueError('Unexpected generations')
    grouped = defaultdict(list)
    for unit in units:
        if unit['case_id'] not in by_id:
            raise ValueError('Unexpected alignment unit case_id')
        grouped[unit['case_id']].append(unit)
    result = []
    for case in cases:
        cid = case['case_id']
        ordered = grouped[cid]
        indices = [u['alignment_unit_index'] for u in ordered]
        if any(type(i) is not int for i in indices) or len(set(indices)) != len(indices):
            raise ValueError(f'Invalid or duplicate alignment_unit_index: {cid}')
        ordered = sorted(ordered, key=lambda u: u['alignment_unit_index'])
        if len(ordered) != case['alignment_unit_count']:
            raise ValueError(f'Alignment unit count mismatch: {cid}')
        ref = case['reference']
        reconstructed = '\n'.join(u['reference'] for u in ordered)
        if not isinstance(ref, str) or ref not in (reconstructed, reconstructed + '\n'):
            raise ValueError(f'Reference reconstruction mismatch: {cid}')
        run = runs.get(cid)
        status = 'missing' if run is None else run.get('status', 'ok')
        if not isinstance(status, str) or not status:
            raise ValueError(f'Invalid generation status: {cid}')
        mt = None if run is None else run.get('mt')
        if status == 'ok':
            if not isinstance(mt, str):
                raise ValueError(f'Missing string mt: {cid}')
            if sha_text(mt) != run.get('output_sha256'):
                raise ValueError(f'Generation output hash mismatch: {cid}')
        eligible = status == 'ok' and bool(ref.strip())
        result.append({
            'case_id': cid, 'metadata': case_metadata(case),
            'generation_status': status,
            'eligibility_status': ('scored_empty_output' if not mt.strip() else 'scored') if eligible
                else (status if status != 'ok' else 'empty_reference'),
            'chrf2': scorer.sentence_score(mt, [ref]).score if eligible else None,
            'empty_output': not mt.strip() if isinstance(mt, str) else None,
            'hypothesis_chars': len(mt) if isinstance(mt, str) else None,
            'reference_chars': len(ref),
            'hypothesis_sha256': sha_text(mt) if isinstance(mt, str) else None,
            'reference_sha256': sha_text(ref),
            'reference_unit_count': len(ordered),
            'reference_unit_indices_sha256': sha_text(json.dumps(sorted(indices))),
        })
    # The signature needs a reference count even for an all-failed batch.
    scorer.num_refs = 1
    return result, str(scorer.get_signature())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data-manifest', 'cases', 'alignment-units', 'generations', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--suite-id', required=True)
    parser.add_argument('--system-key', required=True)
    parser.add_argument('--group-by', action='append', default=[])
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise ValueError('Output directory already exists; use a new independent directory')
    if any((parent / 'COMPLETED.json').exists() for parent in args.output_dir.resolve().parents):
        raise ValueError('Output must be outside completed runs; use an independent directory')
    inputs = {name: {'path': str(getattr(args, name).resolve()),
                     'sha256': sha_file(getattr(args, name))}
              for name in ('data_manifest', 'cases', 'alignment_units', 'generations')}
    rows, signature = score(read_jsonl(args.cases), read_jsonl(args.alignment_units),
                            read_jsonl(args.generations))
    groups = {}
    for field in args.group_by:
        if field not in STANDARD_METADATA_FIELDS and not any(
            field in row['metadata'] for row in rows
        ):
            raise ValueError(f'Unknown grouping field: {field}')
        buckets = defaultdict(list)
        for row in rows:
            value = row['metadata'].get(field)
            if isinstance(value, (dict, list)):
                raise ValueError(f'Grouping field {field} must be a scalar')
            buckets['__missing__' if value is None else str(value)].append(row)
        groups[field] = {key: aggregate(value) for key, value in sorted(buckets.items())}
    import sacrebleu.metrics.chrf as implementation
    import sacrebleu.metrics.helpers as helpers
    import sacrebleu.metrics.base as base
    summary = {
        'schema_version': 'document-chrf2-v1', 'suite_id': args.suite_id,
        'system_key': args.system_key, 'metric': {
            'implementation': 'sacrebleu', 'version': VERSION, 'parameters': PARAMETERS,
            'signature': signature, 'reference_count': 1,
            'implementation_sha256': {m.__name__: sha_file(inspect.getfile(m))
                                      for m in (implementation, helpers, base)},
            'aggregation': 'document macro chrF2', 'scale': [0, 100],
        },
        'inputs': inputs, 'python_version': platform.python_version(),
        'scorer_sha256': sha_file(__file__),
        'reference_policy': 'cases.reference verbatim; verified against all canonical units sorted by alignment_unit_index joined with LF, allowing one final LF; no null-source filtering',
        'hypothesis_policy': 'generations.mt verbatim; no truncation, deduplication or cleanup',
        'eligibility_policy': 'status ok (including empty mt) and nonblank reference; failures/missing/empty reference retain null; macro denominator is scored_case_count',
        'aggregate': aggregate(rows), 'groups': groups,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_jsonl(args.output_dir / 'cases.jsonl', rows)
    (args.output_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    manifest = {name: sha_file(args.output_dir / name) for name in ('cases.jsonl', 'summary.json')}
    (args.output_dir / 'artifact-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (args.output_dir / 'COMPLETED.json').write_text(json.dumps({
        'status': 'completed', 'scope': 'document-chrf2-sidecar-only',
        'artifact_manifest_sha256': sha_file(args.output_dir / 'artifact-manifest.json'),
        'aggregate': summary['aggregate'],
    }, indent=2) + '\n')
    print(json.dumps(summary['aggregate']))


if __name__ == '__main__':
    main()
