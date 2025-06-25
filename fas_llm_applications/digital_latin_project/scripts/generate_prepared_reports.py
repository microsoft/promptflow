#!/usr/bin/env python3

import os
import json
import sys
import re
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
input_dir = os.path.join(parent_dir, 'results')
output_dir = os.path.join(parent_dir, 'prepared_reports')
os.makedirs(output_dir, exist_ok=True)

def parse_ids(args):
    ids = set()
    for arg in args:
        if re.match(r'^\d+$', arg):
            ids.add(int(arg))
        elif re.match(r'^\d+-\d+$', arg):
            lo, hi = map(int, arg.split('-'))
            ids.update(range(lo, hi + 1))
    return sorted(ids)

def get_prompt_ids(data):
    prompt_id = data.get("prompt_id")
    system_prompt_id = ''
    user_prompt_id = ''
    if prompt_id and '__' in prompt_id:
        system_prompt_id, user_prompt_id = prompt_id.split('__', 1)
    else:
        system_prompt_id = data.get('system_prompt_id', '')
        user_prompt_id = data.get('user_prompt_id', '')
    return system_prompt_id, user_prompt_id

def extract_content(data):
    llm_output = data.get("llm_invocation_output", {})
    content = ''
    candidates = llm_output.get("candidates")
    if candidates and isinstance(candidates, list):
        c0 = candidates[0].get("content", {})
        if "parts" in c0:
            content = c0.get("parts", [{}])[0].get("text", "")
        else:
            content = c0.get("text", "")
    if not content and llm_output.get("choices"):
        message = llm_output["choices"][0].get("message", {})
        content = message.get("content", "")
        reasoning_content = message.get("reasoning_content", "")
        
        # Append reasoning_content if not empty
        if reasoning_content:
            if content:
                content = f"{content.strip()}\n\nReasoning Content:\n\n{reasoning_content.strip()}"
            else:
                content = reasoning_content.strip()
        else:
            reasoning_content = ""
            if content:
                content = f"{content.strip()}]"
            else:
                content = ""

    if not content:
        content = llm_output.get("content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
    return content

def usage_token(data, key1, key2):
    llm_output = data.get("llm_invocation_output", {})
    usage = llm_output.get("usageMetadata", {}) if "usageMetadata" in llm_output else llm_output.get("usage", {})
    return usage.get(key1, usage.get(key2, ""))

def get_test_batch_id(data):
    test_batch_id = data.get("test_batch_id", "")
    flow_batch_id = data.get("flow_metadata", {}).get("flow_batch_id", "")
    batch_id = data.get("batch_id", "")
    return batch_id or flow_batch_id or test_batch_id

def get_test_case_no(data):
    test_case_no = data.get("test_case_no", "") or data.get("flow_metadata", {}).get("test_case_no", "")
    return test_case_no

def process_report(report_id, verbose=True):
    json_fname = f"llm_report_{report_id:05}.json"
    json_path = os.path.join(input_dir, json_fname)

    try:
        with open(json_path, encoding='utf8') as f:
            data = json.load(f)
    except Exception as e:
        reason = f"corrupted or unreadable: {e}"
        if verbose: print(f"[SKIP] {json_fname:30} ... {reason}")
        return ("skipped", report_id, json_fname, reason)   

    md_fname = f"llm_report_{get_test_batch_id(data)}_test_case_{get_test_case_no(data)}.md"
    md_path = os.path.join(output_dir, md_fname) 

    if not os.path.exists(json_path):
        reason = "not found"
        if verbose: print(f"[SKIP] {json_fname:30} ... {reason}")
        return ("skipped", report_id, json_fname, md_fname, reason)
    
    if os.path.exists(md_path):
        reason = "already exists in prepared_reports"
        if verbose: print(f"[SKIP] {md_fname:30} ... {reason}")
        return ("skipped", report_id, json_fname, md_fname, reason)

    try:
        sys_id, user_id = get_prompt_ids(data)
        content = extract_content(data)
        input_tokens = usage_token(data, "promptTokenCount", "input_tokens")
        output_tokens = usage_token(data, "candidatesTokenCount", "output_tokens")
        thought_tokens = usage_token(data, "thoughtsTokenCount", "")
        total_token_reported = usage_token(data, "totalTokenCount", "")
        total_tokens = int(total_token_reported) if total_token_reported else input_tokens + output_tokens
        md = f"""\
Timestamp: {data.get("timestamp", "")}
Report ID: {data.get("report_id", "")}
Test Batch ID: {get_test_batch_id(data)}
Test Case No: {get_test_case_no(data)}

Model Used: {data.get("model_used", "")}
System Prompt ID: {sys_id}
User Prompt ID: {user_id}

Input Tokens: {input_tokens}
Output Tokens: {output_tokens}
Reasoning Tokens: {thought_tokens}
Total Tokens: {total_tokens}

LLM Latency (in seconds): {data.get("llm_latency_in_sec", "")}

Flow Name: {data.get("flow_metadata", {}).get("flow_name", "")}
Flow Run ID: {data.get("flow_metadata", {}).get("flow_run_id", "")}
Is RAG Flow: {data.get("flow_metadata", {}).get("is_rag_flow", "")}

Content:

{content.strip()}
"""
        with open(md_path, "w", encoding="utf8") as f:
            f.write(md)
        if verbose: print(f"[OK]   {md_fname:30} ... written successfully")
        return ("written", report_id, json_fname, md_fname, "written successfully")
    except Exception as e:
        reason = f"EXTRACT ERROR: {e}"
        if verbose: print(f"[SKIP] {json_fname:30} ... {reason}")
        return ("skipped", report_id, json_fname, md_fname, reason)

def main():
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    manifest_filename = f"prepared_report_manifest_{timestamp_str}.md"
    manifest_path = os.path.join(output_dir, manifest_filename)

    all_ids = []
    if len(sys.argv) > 1:
        all_ids = parse_ids(sys.argv[1:])
        print(f"Processing report IDs: {all_ids}")
    else:
        print("No report IDs/range specified.")
        answer = input("Do you want to enter a range of reports to process? (y/n): ").strip().lower()
        if answer.startswith('y'):
            s = input("Enter report IDs or ranges, e.g. 28 29 32-34: ").strip()
            if s:
                all_ids = parse_ids(s.split())
        if not all_ids:
            print("No range entered. Will process all new (not yet prepared) reports in results/")
            all_jsons = [f for f in os.listdir(input_dir) if f.startswith('llm_report_') and f.endswith('.json')]
            for js in all_jsons:
                rid = js.replace('llm_report_', '').replace('.json','')
                try:
                    rid_int = int(rid)
                    md_fname = f"llm_report_{rid_int:05}.md"
                    if not os.path.exists(os.path.join(output_dir, md_fname)):
                        all_ids.append(rid_int)
                except Exception:
                    continue
            all_ids = sorted(set(all_ids))
            print(f"Discovered {len(all_ids)} new reports to process.")

    written, skipped = [], []

    print(f"\n===[ Generating prepared reports at {timestamp_str} ]===\n")
    for rid in all_ids:
        res = process_report(rid, verbose=True)
        if res[0] == 'written':
            written.append(res)
        else:
            skipped.append(res)

    # Write manifest (timestamped filename and timestamp in content)
    with open(manifest_path, "w", encoding="utf8") as f:
        f.write(f"# Prepared Report Manifest\n")
        f.write(f"Generated at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*45 + "\n")
        if len(sys.argv) > 1 or all_ids:
            f.write(f"Processed report IDs: {all_ids}\n\n")
        else:
            f.write("Processed all discovered new reports in results/\n\n")

        f.write("FILES WRITTEN:\n")
        for _, rid, json_fn, md_fn, msg in written:
            f.write(f"- {md_fn:30} (from {json_fn})\n")
        f.write("\nFILES SKIPPED:\n")
        for _, rid, json_fn, md_fn, reason in skipped:
            f.write(f"- {json_fn:30} : {reason}\n")
        f.write("\n")

    # Print summary in terminal too
    print("\n======== SUMMARY ========")
    print("FILES WRITTEN:")
    for _, _, _, md_fn, _ in written:
        print(f"  - {md_fn}")
    print("FILES SKIPPED:")
    for _, _, json_fn, _, reason in skipped:
        print(f"  - {json_fn}: {reason}")
    print(f"\nManifest written to: {manifest_path}")

if __name__ == '__main__':
    main()