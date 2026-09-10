"""In-memory TXT reports. Nothing is written to disk; the user copies or downloads.

A report must let a reviewer who never saw the web page reconstruct why a task
is failed, passed or waiting: which policy applied, what was evaluated, how each
verdict was reached, what a human changed, and what nobody could establish.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re

import policy_model as pm

CHECKER_VERSION = 'tb-review-2.5'


def _normalise(text):
    return re.sub(r'\W+', ' ', str(text or '')).strip().lower()


def echoes_guidance(entry, item):
    """True when a model 'finding' is just the rubric text handed back.

    A small model asked to judge many criteria often restates the guidance it
    was given and marks the item satisfied. That reads like a verdict and is
    worth nothing, so it is surfaced as low confidence rather than trusted.
    """
    guidance = _normalise(item.get('guidance') or item.get('why_it_matters'))
    if len(guidance) < 80:
        return False
    for field in ('evidence', 'recommendation'):
        body = _normalise(entry.get(field))
        if len(body) >= 60 and body in guidance:
            return True
    return False


def summarise(review, checklist):
    """Attach the layered assessment. Never averages across layers."""
    profile = review.get('profile') or pm.PROFILE_T3
    items = checklist.get('items', [])
    assessment = pm.assess(profile, review.get('profile_status', 'stable'), items,
                           review.get('results', []), review.get('fallback_reason'))
    item_by_id = {i['id']: i for i in items}
    assessment['echoed_guidance'] = [
        r['id'] for r in review.get('results', [])
        if assessment['layer_of'].get(r['id']) == 'rubric'
        and echoes_guidance(r, item_by_id.get(r['id'], {}))
    ]
    review['assessment'] = assessment
    review['overall_state'] = assessment['overall_state']
    review['overall_state_label'] = assessment['overall_state_label']
    review['legacy_score'] = pm.legacy_score(items, review.get('results', []), profile)
    for result in review.get('results', []):
        result['layer'] = assessment['layer_of'].get(result['id'], 'rubric')
        result['lineage'] = pm.legacy_labels(profile, result['id'])
    review['status_counts'] = dict(Counter(r['status'] for r in review.get('results', [])))
    return review


_UNRESOLVED_ORDER = {('static', 'fail'): 0, ('static', 'unknown'): 1, ('rubric', 'concern'): 2,
                     ('rubric', 'partial'): 3, ('rubric', 'unknown'): 4, ('advisory', 'open'): 5}


def _outcome(result):
    layer = result.get('layer', 'rubric')
    status = result.get('status', 'unknown')
    if layer == 'static':
        return pm.static_outcome(status)
    if layer == 'rubric':
        return pm.rubric_outcome(status)
    return 'open' if status not in ('satisfied', 'not_applicable') else status


def _sort_key(result):
    return _UNRESOLVED_ORDER.get((result.get('layer', 'rubric'), _outcome(result)), 9)


def _ids(names, cap=12):
    if not names:
        return 'none'
    shown = ', '.join(names[:cap])
    return shown + (f' (+{len(names) - cap} more)' if len(names) > cap else '')


def render_report(review, checklist):
    """Build the TXT report from an already-summarised review. Pure: no I/O."""
    a = review['assessment']
    meta = review.get('report_metadata', {})
    legacy = review.get('legacy_score') or {}
    s, r = a['static'], a['rubric']
    overrides = review.get('human_overrides') or []
    profile = review.get('profile', 'unknown')

    lines = ['TERMINAL-BENCH TASK REVIEW REPORT', '=' * 64,
             f"Overall state:     {a['overall_state_label']} ({a['overall_state']})",
             f"Policy profile:    {profile.upper()} - {review.get('policy_profile', 'unspecified')}",
             f"Profile status:    {review.get('profile_status', 'unknown')}"
             f"   requested: {review.get('profile_requested', profile)}   actual: {profile}",
             '  Profiles are not interchangeable: the EC Terminus 3 programme forbids canary',
             '  strings and caps the agent timeout at 18000s; Terminal-Bench 4.0 requires the',
             '  canary and allows up to 28800s. A task compliant with one can fail the other.',
             '',
             f"Legacy experimental score: "
             f"{legacy.get('value') if legacy.get('value') is not None else 'n/a'}/100 (reference only)",
             f"  {legacy.get('disclaimer', '')}",
             f"  Formula: {legacy.get('formula', '')}",
             '',
             f"Static gate:        {s['pass']} passed · {s['fail']} failed · {s['unknown']} unknown · "
             f"{s['not_applicable']} not applicable   [deterministic]",
             f"Rubric assessment:  {r['satisfied']} satisfied · {r['partial']} partial · "
             f"{r['concern']} concerns · {r['unknown']} unknown · {r['not_applicable']} not applicable"
             f"   [model-assisted; cannot establish compliance]",
             f"Reviewer advisory:  {a['advisory']['findings']} findings across "
             f"{a['advisory']['total']} items   [display only; never scored]",
             '',
             f"Confirmed failures (required static):   {_ids(a['confirmed_failures'])}",
             f"Required unknowns (need evidence):      {_ids(a['required_unknowns'])}",
             f"Recommended static, unresolved:         {_ids(a['recommended_unresolved'])}",
             f"Rubric items flagged for review:        {_ids(a['rubric_flags'])}",
             f"Low-confidence rubric items:            {_ids(a.get('echoed_guidance', []))}",
             f"Human overrides:                        {len(overrides) or 'none'}",
             '',
             'HOW TO READ THIS',
             '  policy_fail        a required static rule failed. Nothing else can cancel it.',
             '  review_required    a required static rule is unknown, or rubric items need a',
             '                     human. Automatic approval is unavailable.',
             '  policy_pass        every required static rule passed and nothing is flagged.',
             '  profile_unverified the result would pass, but the selected profile is not yet',
             '                     approved, so it is not a policy decision.',
             '  unknown means the evidence was insufficient. It is never a confirmed failure.',
             '',
             'PROVENANCE']
    provenance = [
        ('zip_name', meta.get('zip_name')), ('zip_sha256', meta.get('zip_sha256')),
        ('checker_version', meta.get('checker_version')),
        ('profile_requested', review.get('profile_requested', profile)),
        ('profile_actual', profile), ('profile_status', review.get('profile_status')),
        ('policy_sha256', review.get('policy_sha256')),
        ('source_manifest_sha256', review.get('source_manifest_sha256')),
        ('model_requested', review.get('model_requested', meta.get('model'))),
        ('model_actual', review.get('model_actual') or 'not reported by Ollama'),
        ('model_tag', review.get('model_tag')), ('model_digest', review.get('model_digest')),
        ('prompt_version', review.get('prompt_version')),
        ('prompt_template_sha256', review.get('prompt_template_sha256')),
        ('assessment_mode', review.get('review_mode')),
        ('llm_succeeded', review.get('review_mode') in ('llm-assisted',)),
        ('fallback_reason', review.get('fallback_reason') or 'none'),
        ('model_excerpts_limited', review.get('model_excerpts_limited', False)),
        ('duration_sec', meta.get('duration_sec')), ('completed_at', meta.get('completed_at')),
    ]
    lines += [f'  {k}: {v}' for k, v in provenance]
    lines += ['',
              'EXECUTION',
              '  Task code was not executed. Nothing from the uploaded archive was run, imported',
              '  or built. Under Terminus 4 the benchmark\'s own grep-based check scripts read an',
              '  extracted copy in a temporary directory; they do not execute task content.',
              '  Docker build, oracle, nop and agent trials were not performed.']

    if overrides:
        lines += ['', 'HUMAN OVERRIDES']
        for o in overrides:
            lines += [f"  {o['id']}: {o['original_result']} -> {o['final_determination']} "
                      f"by {o['reviewer']} at {o['timestamp']}",
                      f"    reason: {o['reason']}", f"    evidence: {o['evidence']}",
                      f"    original source: {o['original_source']}"]

    lines += ['', 'SUMMARY', review.get('summary', ''), '', 'ALL FINDINGS - UNRESOLVED FIRST']
    items = {i['id']: i for i in checklist.get('items', [])}
    for number, res in enumerate(sorted(review.get('results', []), key=_sort_key), 1):
        item = items.get(res['id'], {})
        lineage = '; '.join(
            f"{x['version']} {x['rule'] or '(no counterpart)'} ({x['relation']})"
            for x in res.get('lineage', [])) or 'none recorded'
        lines += ['',
                  f"{number}. [{_outcome(res).upper()}] {item.get('criterion', res['id'])}",
                  f"ID: {res['id']}",
                  f"Layer: {res.get('layer', 'rubric')}   severity: {item.get('severity', '')}   "
                  f"category: {item.get('category', '')}",
                  f"Assessment source: {res.get('assessment_source', 'unspecified')}",
                  f"Lineage: {lineage}",
                  f"Applies when: {item.get('applies_when', '')}",
                  f"Evidence: {res.get('evidence', '')}",
                  f"Recommendation: {res.get('recommendation', '')}"]
        if res.get('override'):
            o = res['override']
            lines += [f"Override: {o['original_result']} -> {o['final_determination']} by "
                      f"{o['reviewer']} ({o['timestamp']})"]
    lines += ['', 'END OF REPORT',
              'Exported on request. Full ZIP contents and raw model prompts are not included.']
    return '\n'.join(lines) + '\n'


def _safe_stem(name):
    base = str(name).replace('\\', '/').split('/')[-1]
    base = re.sub(r'[\x00-\x1f\x7f]', '', base)[:180] or 'task.zip'
    stem = base[:-4] if base.lower().endswith('.zip') else base
    return base, re.sub(r'[^\w. -]', '_', stem).strip(' .') or 'task'


def attach_report(review, checklist, zip_bytes, zip_name, model, duration):
    name, stem = _safe_stem(zip_name)
    stamp = datetime.now(timezone.utc)
    review['report_metadata'] = dict(
        zip_name=name, zip_sha256=hashlib.sha256(zip_bytes).hexdigest(),
        checker_version=CHECKER_VERSION,
        checklist_sha256=hashlib.sha256(json.dumps(checklist, sort_keys=True).encode()).hexdigest(),
        model=model, completed_at=stamp.isoformat(), duration_sec=round(duration, 2))
    review.setdefault('policy_sha256', review['report_metadata']['checklist_sha256'])
    summarise(review, checklist)
    review['report_text'] = render_report(review, checklist)
    review['report_filename'] = f"{stem}-review-{stamp.strftime('%Y%m%dT%H%M%S%fZ')}.txt"
    return review


def rerender_with_overrides(review, checklist, overrides):
    """Apply reviewer overrides to an existing review and rebuild its report.

    The original review is not mutated; the returned copy records the overrides
    and a fresh filename, so an earlier export is never rewritten.
    """
    profile = review.get('profile') or pm.PROFILE_T3
    base_results = [{k: v for k, v in r.items() if k not in ('override',)}
                    for r in review.get('original_results') or review.get('results', [])]
    results, applied = pm.apply_overrides(profile, checklist.get('items', []), base_results, overrides)
    out = {**review, 'results': results, 'human_overrides': applied,
           'original_results': review.get('original_results') or review.get('results', [])}
    summarise(out, checklist)
    out['report_text'] = render_report(out, checklist)
    _, stem = _safe_stem(out.get('report_metadata', {}).get('zip_name', 'task.zip'))
    out['report_filename'] = (f"{stem}-review-"
                              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-reviewed.txt")
    return out
