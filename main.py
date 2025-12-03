import json
import os
import subprocess
import time
import glob
from itertools import combinations
import pandas as pd

CONFIG_PATH = 'config/tools.json'
PATH_PREFIX = os.getcwd() 
SCENARIOS_DIR = os.path.join(PATH_PREFIX, 'scenarios')
OUTPUT_FILE = os.path.join(PATH_PREFIX, 'output', 'results.csv')

# loading

def load_config(path):
    with open(path, 'r') as f:
        return json.load(f)

def find_source_file(root_dir):
    files = [f for f in glob.glob(os.path.join(root_dir, '**'), recursive=True) if os.path.isfile(f)]
    files = [f for f in files if not os.path.basename(f).startswith('.')]

    if not files:
        return None
    
    return files[0]

def count_and_extract_conflicts(file_path):
    """counts and extracts conflict blocks"""
    num_conflicts = 0
    conflict_blocks = []
    current_block = []
    in_conflict = False

    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()

        for line in content.splitlines():
            if line.startswith('<<<<<<<'):
                num_conflicts += 1
                in_conflict = True
                current_block = [line]
            elif line.startswith('>>>>>>>'):
                if in_conflict:
                    current_block.append(line)
                    #remove whitespaces
                    conflict_blocks.append('\n'.join(current_block).strip())
                    in_conflict = False
                    current_block = []
            elif in_conflict:
                current_block.append(line)
        
        return num_conflicts, content.strip(), conflict_blocks
    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}")
        return 0, "", []

def run_tool(scenario_path, tool_config):
    tool_name = tool_config['name']
    binary_path = tool_config['binary_path']
    command_template = tool_config['command_template']

    # find revisions file recursively
    base_dir = os.path.join(scenario_path, 'base')
    left_dir = os.path.join(scenario_path, 'left')
    right_dir = os.path.join(scenario_path, 'right')

    base_file = find_source_file(base_dir)
    left_file = find_source_file(left_dir)
    right_file = find_source_file(right_dir)

    # safety check
    if not all([base_file, left_file, right_file]):
        print(f"ERROR: Revisions not found: {scenario_path}")
        return -1, False, None
    
    # get extension
    _, file_extension = os.path.splitext(left_file)

    # define merge file name
    output_filename = f"merge{file_extension}"
    output_dir = os.path.join(scenario_path, tool_name)
    output_file_path = os.path.join(output_dir, output_filename)

    os.makedirs(output_dir, exist_ok=True)
    
    # O comando agora recebe os caminhos completos descobertos pelo glob
    command = command_template.format(
        binary_path=binary_path,
        base=base_file,
        left=left_file,
        right=right_file,
        output_dir=output_dir
    )

    start_time = time.time()
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        execution_time = (time.time() - start_time) * 1000
        success = True
    except subprocess.CalledProcessError:
        execution_time = (time.time() - start_time) * 1000
        success = False
    except Exception:
        execution_time = -1
        success = False

    return execution_time, success, file_extension

# analysis

def analyze_scenario(project_name, commit_hash, scenario_path, tools_config, ref_name, execution_times, file_extension):
    all_results = {}
    tool_names = [t['name'] for t in tools_config]
    
    # try to find repository merge (ground truth)
    child_dir = os.path.join(scenario_path, 'child')
    ref_file_path = find_source_file(child_dir)
    
    valid_ref = (ref_file_path is not None and os.path.exists(ref_file_path))
    num_conflicts_ref, content_ref, conflicts_ref = count_and_extract_conflicts(ref_file_path)
    
    all_results[ref_name] = {
        'conflicts': num_conflicts_ref, 
        'content': content_ref, 
        'conflict_blocks': conflicts_ref,
        'valid': valid_ref
    }
    
    expected_output_name = f"merge{file_extension}"

    for tool_name in tool_names:
        tool_output_path = os.path.join(scenario_path, tool_name, expected_output_name)
        
        # check if file exists
        valid_tool = os.path.exists(tool_output_path)
        
        num_conflicts, content, conflicts = count_and_extract_conflicts(tool_output_path)
        all_results[tool_name] = {
            'conflicts': num_conflicts, 
            'content': content, 
            'conflict_blocks': conflicts,
            'valid': valid_tool
        }

    # csv
    base_file_found = find_source_file(os.path.join(scenario_path, 'base'))
    original_filename = os.path.basename(base_file_found) if base_file_found else "unknown"

    results_row = {
        'project': project_name,
        'merge commit': commit_hash,
        'file': original_filename
    }

    # conflict metrics
    for tool_name in tool_names:
        if all_results[tool_name]['valid']:
            results_row[f'number of {tool_name} conflicts'] = all_results[tool_name]['conflicts']
        else:
            results_row[f'number of {tool_name} conflicts'] = -1 # crash or missing file

    # reference
    if all_results[ref_name]['valid']:
        results_row[f'number of {ref_name} conflicts'] = all_results[ref_name]['conflicts']
    else:
        results_row[f'number of {ref_name} conflicts'] = -1

    # comparison metrics
    all_sources = tool_names + [ref_name]
    for src1, src2 in combinations(all_sources, 2):
        data1 = all_results[src1]
        data2 = all_results[src2]
        
        # only compares if both are valid
        if data1['valid'] and data2['valid']:
            content_eq = (data1['content'] == data2['content'])
            conflicts_eq = (data1['conflict_blocks'] == data2['conflict_blocks'])
        else:
            # if not valid, different
            content_eq = False
            conflicts_eq = False
            
        results_row[f'{src1} content = {src2} content'] = content_eq
        results_row[f'{src1} conflicts = {src2} conflicts'] = conflicts_eq

    # time
    for tool_name in tool_names:
        results_row[f'{tool_name} time'] = execution_times.get(tool_name, -1)

    return results_row

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    try:
        config = load_config(CONFIG_PATH)
        tools_config = config['tools']
        ref_name = config.get('reference_name', 'actual')
    except Exception as e:
        print(f"ERROR Config: {e}")
        return

    if not os.path.exists(SCENARIOS_DIR):
        print(f"Directory {SCENARIOS_DIR} not found.")
        return

    # loop
    projects_list = sorted(os.listdir(SCENARIOS_DIR))
    
    for project_name in projects_list:
        project_path = os.path.join(SCENARIOS_DIR, project_name)
        if not os.path.isdir(project_path):
            continue

        commits_list = sorted(os.listdir(project_path))
        
        # loop commits
        for commit_hash in commits_list:
            scenario_path = os.path.join(project_path, commit_hash)
            if not os.path.isdir(scenario_path):
                continue

            print(f"PROCESSING: {project_name}/{commit_hash}...", end=" ", flush=True)

            times = {}
            detected_extension = ""
            
            # run tools
            for tool in tools_config:
                exec_time, success, ext = run_tool(scenario_path, tool)
                times[tool['name']] = exec_time
                if success and ext:
                    detected_extension = ext
                
                if not success:
                    print(f"[TOOL {tool['name']} FAILED]", end=" ")

            # analyse and saves data
            if detected_extension:
                try:
                    row_data = analyze_scenario(
                        project_name, 
                        commit_hash, 
                        scenario_path, 
                        tools_config, 
                        ref_name, 
                        times, 
                        detected_extension
                    )
                    
                    df_row = pd.DataFrame([row_data])
                    file_exists = os.path.exists(OUTPUT_FILE)
                    
                    # write to csv
                    df_row.to_csv(OUTPUT_FILE, mode='a', header=not file_exists, index=False)
                    print(f"ok!")
                    
                except Exception as e:
                    print(f"ANALYSIS ERROR: {e}")
            else:
                print(f"SKIP: INPUT FILES NOT FOUND")

    print("\nFINISHED EXECUTION")

if __name__ == '__main__':
    main()