import json
import argparse
from pathlib import Path


tool_suffix_mapping = {
    'python': '.py',
    'llm': '.jinja2',
}


def dump_json(data, target_file):
    with open(target_file, 'w') as fout:
        json.dump(data, fout, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--req_file', type=str, required=True)
    parser.add_argument('--target_dir', type=str, default=None)
    args = parser.parse_args()

    with open(args.req_file) as fin:
        data = json.load(fin)
    if args.target_dir is None:
        args.target_dir = Path(args.req_file).parent / Path(args.req_file).stem

    target_dir = Path(args.target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    for tool in data['flow']['tools']:
        if 'code' in tool:
            suffix = tool_suffix_mapping[tool['type']]
            source_file = tool['name'] + suffix
            tool['source'] = tool.get('source', source_file)
            with open(target_dir / source_file, 'w') as fout:
                fout.write(tool.pop('code'))

    dump_json(data['flow'], target_dir / 'flow.json')
    dump_json(data['batch_inputs'], target_dir / 'samples.json')
