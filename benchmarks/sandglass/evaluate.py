#!/usr/bin/env python3
"""Evaluate saved predictions without GPU model loading or reference leakage."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import time
from urllib.parse import urlsplit
import syllable_calculation as sc
from judge_prompt import JUDGE_PROMPT, LANG_CN


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def read_jsonl_tolerant(path):
    """容错读取：跳过被中断写坏的半行/坏 JSON（仅用于可重建的 judge 缓存）。"""
    rows = []
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def redact_api_base(api_base):
    """summary 会随发布物公开：只保留 scheme+host，去掉 userinfo/路径/查询。"""
    if not api_base:
        return ''
    try:
        parsed = urlsplit(api_base)
        host = parsed.hostname
        if not parsed.scheme or not host:
            return '<redacted>'
        if ':' in host:
            host = f'[{host}]'
        if parsed.port is not None:
            host += f':{parsed.port}'
        return f'{parsed.scheme}://{host}'
    except ValueError:
        return '<redacted>'


def parse_score(text):
    text = text.strip()
    if text.startswith('[') and text.endswith(']'):
        text = text[1:-1].strip()
    return float(text) if re.fullmatch(r'(?:0(?:\.0+)?|0\.50*|1(?:\.0+)?)', text) else None


def load_predictions(path, valid_ids):
    result = {}
    for row in read_jsonl(path):
        key = row['case_id']
        if key not in valid_ids or key in result:
            raise ValueError('Unknown or duplicate case_id: ' + key)
        if not isinstance(row.get('prediction'), str):
            raise ValueError('prediction must be a string: ' + key)
        result[key] = row['prediction']
    return result


def syllable_metrics(hyp, meta):
    target = meta['target_syllables']
    if target <= 0:
        raise ValueError('Non-positive target')
    n = sc.cal_syllable_count(hyp, lang=meta['target_language']) if hyp.strip() else 0
    diff, dev = abs(n - target), abs(n - target) / target
    reward = 1.0 if diff <= 1 or dev <= .05 else 0.0 if dev >= .5 else (.5 - dev) / .45
    if not hyp.strip():
        reward = 0.0
    return dict(hyp_syllables=n, abs_diff=diff, dev=dev, signed_dev=(n-target)/target,
        syllable_reward=reward, hit_pm1=int(diff<=1), hit_strict5=int(dev<=.05), hit_10=int(dev<=.1), hit_20=int(dev<=.2))


def aggregate(rows):
    quality = [r['quality'] for r in rows if r['quality'] is not None]
    return dict(cases=len(rows), quality_cases=len(quality),
        quality=statistics.mean(quality) if quality else None,
        score=statistics.mean(r['score'] for r in rows) if rows and all(r['score'] is not None for r in rows) else None,
        **{k: statistics.mean(r[k] for r in rows) if rows else None for k in
           ['syllable_reward','hit_pm1','hit_strict5','hit_10','hit_20','dev']})


def controllability(rows):
    groups = defaultdict(dict)
    for r in rows:
        groups[(r['uuid'],r['target_language'])][r['target_kind']] = r
    slopes, short, long = [], [], []
    for g in groups.values():
        if set(g) != {'short','natural','long'}:
            continue
        xs = [r['target_syllables'] for r in g.values()]
        ys = [r['hyp_syllables'] for r in g.values()]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        denom = sum((x-mx)**2 for x in xs)
        if denom:
            slopes.append(sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denom)
        if all(r['quality'] is not None for r in g.values()):
            short.append(g['short']['quality']-g['natural']['quality'])
            long.append(g['long']['quality']-g['natural']['quality'])
    return dict(slope=statistics.mean(slopes) if slopes else None, complete_groups=len(slopes),
        q_gap_short=statistics.mean(short) if short else None, q_gap_long=statistics.mean(long) if long else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-file',type=Path,default=Path(__file__).parent/'sandglass_bench.jsonl')
    ap.add_argument('--predictions',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--skip-judge',action='store_true')
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--judge-model',default='gemini-2.5-flash')
    ap.add_argument('--judge-api-base',default=os.environ.get('JUDGE_API_BASE',''))
    args = ap.parse_args()
    if args.limit < 0:
        ap.error('--limit must be nonnegative')
    dataset = read_jsonl(args.data_file)
    if not dataset or len({r['case_id'] for r in dataset}) != len(dataset):
        ap.error('Empty dataset or duplicate case IDs')
    # --limit 只缩小评分范围；合法 case_id 集合始终取未截断的完整数据集
    rows = dataset[:args.limit] if args.limit else dataset
    preds = load_predictions(args.predictions,{r['case_id'] for r in dataset})
    args.output_dir.mkdir(parents=True,exist_ok=True)
    config = dict(model=args.judge_model,api_base=args.judge_api_base,reasoning_effort='low')
    cache_file = args.output_dir/'judge_cache.jsonl'
    cache = {r['key']:r['response'] for r in read_jsonl_tolerant(cache_file)} if cache_file.exists() else {}
    client = None
    if not args.skip_judge:
        if not args.judge_api_base or not os.environ.get('JUDGE_API_KEY'):
            ap.error('Set JUDGE_API_BASE and JUDGE_API_KEY, or use --skip-judge')
        from openai import OpenAI
        client = OpenAI(base_url=args.judge_api_base,api_key=os.environ['JUDGE_API_KEY'],timeout=120,max_retries=0)
    scored = []
    for row in rows:
        m, hyp = row['metadata'], preds.get(row['case_id'],'')
        quality = None if args.skip_judge else 0.0
        if client and hyp.strip():
            prompt = JUDGE_PROMPT.format(target_lang=LANG_CN[m['target_language']],duration=m['duration'],
                target_syllables=m['target_syllables'],summary=m.get('summary',''),up_context=m.get('up_context',''),
                down_context=m.get('down_context',''),origin_text=m['source'],translate_text=hyp,
                lang_notes='\n- 注意: 日语存在敬体/简体，打分时请忽略这一问题。' if m['target_language']=='ja' else '',
                bad_case='- 你需要特别注意中文汉字直出现象，若不是日语本土表达，算严重错误。' if m['target_language']=='ja' else '')
            key = hashlib.sha256(json.dumps(dict(config=config,prompt=prompt),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            response = cache.get(key)
            if response is None:
                for attempt in range(3):
                    try:
                        res = client.chat.completions.create(model=args.judge_model,messages=[dict(role='user',content=prompt)],reasoning_effort='low')
                        response = res.choices[0].message.content or ''
                        if parse_score(response) is None:
                            raise ValueError('Judge must return exactly 0, 0.5 or 1')
                        break
                    except Exception:
                        response = None
                        if attempt == 2:
                            raise
                        time.sleep(2**attempt)
                with cache_file.open('a',encoding='utf-8') as f:
                    f.write(json.dumps(dict(key=key,response=response),ensure_ascii=False)+'\n')
                cache[key] = response
            quality = parse_score(response)
            if quality is None:
                raise ValueError('Invalid cached Judge score')
        metrics = syllable_metrics(hyp,m)
        scored.append(dict(case_id=row['case_id'],uuid=m['uuid'],target_language=m['target_language'],
            target_kind=m['target_kind'],target_syllables=m['target_syllables'],prediction=hyp,**metrics,
            quality=quality,score=(metrics['syllable_reward']+quality)/2 if quality is not None else None))
    summary = dict(formal_result=not args.limit and not args.skip_judge,subset=bool(args.limit),skip_judge=args.skip_judge,
        data_sha256=hashlib.sha256(args.data_file.read_bytes()).hexdigest(),
        judge=dict(config,api_base=redact_api_base(config['api_base'])) if client else None,
        prediction_coverage=sum(bool(r['prediction'].strip()) for r in scored)/len(scored),
        overall=aggregate(scored),controllability=controllability(scored))
    for field in ['target_language','target_kind']:
        summary[field] = {k:aggregate([r for r in scored if r[field]==k]) for k in sorted({r[field] for r in scored})}
    (args.output_dir/'scores.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in scored),encoding='utf-8')
    (args.output_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary['overall'],ensure_ascii=False))

if __name__ == '__main__':
    main()
