#!/usr/bin/env python3
"""Run the released SEGALE-COMET pipeline on the example or benchmark data."""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANDS = ['4k', '8k', '16k', '32k', '64k']
SUITE_ID = 'nativelongbenchmark'
SYSTEM_KEY = 'prediction'


def read_rows(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def prepare_generations(rows):
    """Accept case_id/mt; preserve supplied metadata, mark absent values unknown."""
    result = []
    for row in rows:
        item = dict(row)
        item.setdefault('status', 'ok')
        if item['status'] == 'ok' and isinstance(item.get('mt'), str):
            for key in ['finish_reason', 'input_tokens', 'output_tokens', 'cap_hit',
                        'model_revision', 'generation_config_sha256']:
                item.setdefault(key, None)
            item.setdefault('output_sha256', hashlib.sha256(item['mt'].encode()).hexdigest())
        result.append(item)
    return result


def file_inputs(paths):
    """Input records that the COMET sidecar validation can re-verify."""
    return {name: {'path': str(path.resolve()),
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in paths.items()}


def write_empty_comet_run(comet_dir, inputs):
    """Write a validation-compliant COMET sidecar when no case was selected.

    The summarizer validates the COMET triple before trusting it, so an empty
    selection still has to ship a completed marker and artifact hashes.
    """
    comet_dir.mkdir()
    summary = {
        'schema_version': 'document-comet-v1', 'suite_id': SUITE_ID,
        'system_key': SYSTEM_KEY, 'inputs': inputs, 'experiment': {},
        'runtime': {'selection': 'no_scorable_cases', 'windows': 0},
        'metrics': {}, 'aggregate': {'documents': 0, 'windows': 0}, 'cases': [],
    }
    (comet_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (comet_dir / 'per_window.jsonl').write_text('')
    manifest = {name: hashlib.sha256((comet_dir / name).read_bytes()).hexdigest()
                for name in ('summary.json', 'per_window.jsonl')}
    (comet_dir / 'artifact-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (comet_dir / 'COMPLETED.json').write_text(json.dumps({
        'status': 'completed', 'scope': 'document-comet-empty-selection',
        'artifact_manifest_sha256': hashlib.sha256(
            (comet_dir / 'artifact-manifest.json').read_bytes()).hexdigest(),
        'suite_id': SUITE_ID, 'system_key': SYSTEM_KEY,
        'aggregate': {'documents': 0, 'windows': 0, 'macro_comet': None},
    }, indent=2) + '\n')


def five_band_macro(summary):
    groups = summary['groups'].get('length_band', {})
    means = {band: groups.get(band, {}).get('segale_comet') for band in BANDS}
    return {'value': statistics.fmean(means.values())
            if all(x is not None for x in means.values()) else None,
            'scale': [0, 1], 'band_means': means,
            'coverage': {band: {'scored': groups.get(band, {}).get('scored_cases', 0),
                                'scored_with_comet': groups.get(band, {}).get(
                                    'scored_with_comet_cases', 0),
                                'total': groups.get(band, {}).get('cases', 0)} for band in BANDS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example', action='store_true')
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--generations', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--case-workers', type=int, default=1)
    args = parser.parse_args()
    if args.example:
        if args.data_root or args.generations:
            parser.error('--example supplies both data and predictions')
        args.data_root = ROOT / 'example'
        args.generations = ROOT / 'example/generations.jsonl'
    if not args.data_root or not args.generations:
        parser.error('provide --example, or --data-root and --generations')
    if args.batch_size < 1 or args.case_workers < 1:
        parser.error('batch size and case workers must be positive')
    if args.output.exists():
        parser.error('--output must be a new directory')
    from huggingface_hub import hf_hub_download
    models = json.loads((ROOT / 'models.json').read_text())
    resolved = {}
    for name, spec in models.items():
        filename = 'checkpoints/model.ckpt' if name == 'comet' else 'config.json'
        resolved[name] = Path(hf_hub_download(spec['repo_id'], filename,
            revision=spec['revision'], local_files_only=True))
    args.output.mkdir(parents=True)
    generations = args.output / 'generations.jsonl'
    generations.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
        for r in prepare_generations(read_rows(args.generations))), encoding='utf-8')
    cases = args.data_root / 'cases.jsonl'
    units = args.data_root / 'segale/alignment-units.jsonl'
    adapter = args.output / 'adapter'
    comet = args.output / 'comet'
    chrf = args.output / 'chrf2'
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'vendor/segale'), str(ROOT / 'scripts')])
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    env['TOKENIZERS_PARALLELISM'] = 'false'
    env.setdefault('OMP_NUM_THREADS', '4')
    identity = ['--suite-id', SUITE_ID, '--system-key', SYSTEM_KEY]

    def run(script, *values):
        subprocess.run([sys.executable, str(ROOT / 'scripts' / script),
                        *map(str, values)], env=env, check=True)

    run('score_document_chrf.py', '--data-manifest', args.data_root / 'manifest.json',
        '--cases', cases, '--alignment-units', units, '--generations', generations,
        '--output-dir', chrf, '--group-by', 'length_band', *identity)
    run('prepare_document_segale.py', '--cases', cases, '--alignment-units', units,
        '--generations', generations, '--output-dir', adapter, '--allow-incomplete', *identity)
    selected = json.loads((adapter / 'manifest.json').read_text())['cases']
    if selected:
        run('run_document_segale_alignment.py', '--system-file', adapter / 'system.jsonl',
            '--ref-file', adapter / 'reference.jsonl', '--task-lang', 'en',
            '--proc-device', args.device, '--embedding-model', resolved['bge'].parent,
            '--max-size', '8', '--scratch-dir', args.output / 'scratch',
            '--case-workers', args.case_workers, '--search-mode', 'online-stop')
        run('evaluate_comet.py', '--input-file', adapter / 'system/aligned_spacy_system.jsonl',
            '--manifest', adapter / 'manifest.json', '--output-dir', comet,
            '--model-checkpoint', resolved['comet'], '--encoder-model', resolved['encoder'].parent,
            '--batch-size', args.batch_size, '--gpus', int(args.device == 'cuda'),
            '--spacy-model', 'en_core_web_sm',
            '--target-sentences', adapter / 'system/target_sentences.jsonl', *identity)
    else:
        write_empty_comet_run(comet, file_inputs({
            'manifest': adapter / 'manifest.json', 'cases': cases,
            'generations': generations}))
    run('summarize_document_segale.py', '--cases', cases, '--generations', generations,
        '--comet-summary', comet / 'summary.json', '--output', args.output / 'summary.json',
        '--group-by', 'work_id', '--group-by', 'length_band', '--chrf-dir', chrf, *identity)
    summary = json.loads((args.output / 'summary.json').read_text())
    summary['five_band_macro'] = five_band_macro(summary)
    summary['evaluation_profile'] = {'max_size': 8, 'segmenter': 'en_core_web_sm-3.8.0',
        'embedding_max_tokens': 512, 'search_mode': 'online-stop', 'device': args.device,
        'batch_size': args.batch_size, 'case_workers': args.case_workers,
        'models': {k: {'repo_id': v['repo_id'], 'revision': v['revision']} for k, v in models.items()}}
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'case_count': summary['case_count'], 'scored': summary['scored_case_count'],
                      'segale_comet': summary['scored']['segale_comet'],
                      'five_band_macro': summary['five_band_macro']['value'],
                      'summary': str(args.output / 'summary.json')}, indent=2))


if __name__ == '__main__':
    main()
