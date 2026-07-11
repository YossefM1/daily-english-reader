#!/usr/bin/env python3
"""Validate public reading-comprehension task metadata files."""
import json, sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_TASK_COUNT=10
ALLOWED_CATEGORIES={"main_idea","factual_details","inference","vocabulary_context","summary","written_expression"}
ALLOWED_TYPES={"multiple_choice","short_answer","summary","written_response"}
BBC_HOSTS={"bbc.com","www.bbc.com","bbc.co.uk","www.bbc.co.uk"}
PLACEHOLDER_STRINGS={
 "The article’s central event or claim","A minor background detail only","A topic not discussed in the article",
 "A conclusion supported by details in the article","An unrelated opinion not supported by the article",
 "A direct quotation only","A personal preference unrelated to the report",
}
TEXT_FIELDS={"text","article_text","full_text","content","body"}
SKILLS=ALLOWED_CATEGORIES

def fail(msg): raise ValueError(msg)
def assert_bbc(url, ctx):
    host=urlparse(str(url)).netloc.lower()
    if host not in BBC_HOSTS: fail(f"Non-BBC URL in {ctx}: {url!r}")
def scan_placeholders(obj, ctx):
    if isinstance(obj, str):
        if obj in PLACEHOLDER_STRINGS: fail(f"Placeholder task text in {ctx}: {obj!r}")
    elif isinstance(obj, list):
        for i,v in enumerate(obj): scan_placeholders(v, f"{ctx}[{i}]")
    elif isinstance(obj, dict):
        for k,v in obj.items(): scan_placeholders(v, f"{ctx}.{k}")
def validate_task_file(path: Path):
    data=json.loads(path.read_text(encoding='utf-8'))
    scan_placeholders(data, str(path))
    for f in ["date","article_id","article_title","article_url","article_level","profile_version_used","adaptation_summary","tasks"]:
        if f not in data: fail(f"{path} missing {f}")
    aid=data["article_id"]
    if aid not in {"A","B","C"} or data["article_level"]!=aid: fail(f"{path} has invalid article id/level")
    assert_bbc(data["article_url"], str(path))
    tasks=data["tasks"]
    if not isinstance(tasks,list) or len(tasks)!=EXPECTED_TASK_COUNT: fail(f"{path} must contain exactly {EXPECTED_TASK_COUNT} tasks")
    ids=set(); positions=[]; option_sets=[]
    for i,t in enumerate(tasks):
        if TEXT_FIELDS & set(t): fail(f"{path} task {t.get('id')} publishes article text fields")
        for f in ["id","category","type","prompt","difficulty"]:
            if f not in t: fail(f"{path} task #{i} missing {f}")
        if t["id"] in ids: fail(f"{path} duplicate task id {t['id']}")
        ids.add(t["id"])
        if t["category"] not in ALLOWED_CATEGORIES: fail(f"{path} invalid category {t['category']}")
        if t["type"] not in ALLOWED_TYPES: fail(f"{path} invalid type {t['type']}")
        if t["difficulty"] != aid: fail(f"{path} task {t['id']} difficulty mismatch")
        if not str(t["prompt"]).strip(): fail(f"{path} task {t['id']} empty prompt")
        if t["type"]=="multiple_choice":
            opts=t.get("options")
            if not isinstance(opts,list) or len(opts)!=4 or len(set(opts))!=4: fail(f"{path} task {t['id']} needs four unique options")
            if t.get("correct_answer") not in opts: fail(f"{path} task {t['id']} correct answer not in options")
            option_tuple=tuple(opts)
            if option_tuple in option_sets: fail(f"{path} reuses identical MCQ options")
            option_sets.append(option_tuple); positions.append(opts.index(t["correct_answer"]))
            if not str(t.get("explanation_hebrew","")).strip(): fail(f"{path} task {t['id']} missing explanation_hebrew")
        else:
            if not str(t.get("rubric_hebrew","")).strip(): fail(f"{path} task {t['id']} missing rubric_hebrew")
            pts=t.get("expected_points")
            if not isinstance(pts,list) or not pts or not all(isinstance(x,str) and x.strip() for x in pts): fail(f"{path} task {t['id']} needs expected_points")
    if len(set(positions)) < 2: fail(f"{path} MCQ correct-answer positions are not mixed: {Counter(positions)}")

def main():
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/data/tasks')
    index=json.loads((root/'task-index.json').read_text(encoding='utf-8'))
    seen=[]
    for entry in index.get('articles',[]):
        assert_bbc(entry.get('article_url',''), 'task-index.json')
        if entry.get('task_count')!=EXPECTED_TASK_COUNT: fail('task-index entry has wrong task_count')
        rel=entry['task_data_url'].replace('data/tasks/','')
        validate_task_file(root/rel); seen.append(entry['id'])
    if sorted(seen)!=['A','B','C']: fail(f'task-index must reference A/B/C, got {seen}')
    print(f'Validated {len(seen)} task files in {root}')
if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr); raise SystemExit(1)
