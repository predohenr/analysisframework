import json
import os
import subprocess
import time
import glob
import shutil
from itertools import combinations
import pandas as pd
from datetime import datetime

CONFIG_PATH = 'config/tools.json'
PATH_PREFIX = os.getcwd() 
SCENARIOS_DIR = os.path.join(PATH_PREFIX, 'scenarios')
OUTPUT_FILE = os.path.join(PATH_PREFIX, 'output', 'results.csv')

# loading

def load_config(path):
    with open(path, 'r') as f:
        return json.load(f)

def find_source_file(root_dir):
    if not os.path.exists(root_dir):
        return None

    files = [f for f in glob.glob(os.path.join(root_dir, '**'), recursive=True) if os.path.isfile(f)]
    files = [f for f in files if not os.path.basename(f).startswith('.')]

    if not files:
        print(f"ERROR: No valid file in: {root_dir}")
        try:
            print(f"Folder content: {os.listdir(root_dir)}")
        except:
            pass
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

def run_tool(tool_config, base_path, left_path, right_path, output_viz_dir):
    tool_name = tool_config['name']
    binary_path = tool_config['binary_path']
    command_template = tool_config['command_template']

    if not os.path.isabs(binary_path):
        binary_path = os.path.abspath(os.path.join(PATH_PREFIX, binary_path))

    if not os.path.exists(binary_path):
        print(f"  ERROR: Tool Binary not found: {binary_path}")
        return -1, False
    
    tool_output_dir = os.path.join(output_viz_dir, tool_name)
    os.makedirs(tool_output_dir, exist_ok=True)

    _, file_extension = os.path.splitext(left_path)
    output_filename = f"merge{file_extension}"
    output_file_path = os.path.join(tool_output_dir, output_filename)
    
    # glob paths
    command = command_template.format(
        binary_path=binary_path,
        base=base_path,
        left=left_path,
        right=right_path,
        output_dir=tool_output_dir,
        output_file=output_file_path,
    )

    start_time = time.time()
    try:
        result = subprocess.run(command, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        execution_time = (time.time() - start_time) * 1000
        execution_time = round(execution_time, 4)

        if result.returncode in [0,1] and os.path.exists(output_file_path):
            success = True
        else:
            print(f"  TOOL ERROR (Exit Code {result.returncode}): {result.stderr.decode().strip()}")
            execution_time = -1
            success = False

    except Exception as e:
        print(f"  PYTHON ERROR: {e}")
        execution_time = -1
        success = False

    return execution_time, success
# analysis

def analyze_scenario(project_name, commit_hash, original_filename, output_viz_dir, tools_config, ref_name, execution_times, file_extension):
    all_results = {}
    tool_names = [t['name'] for t in tools_config]
    
    # try to find repository merge (ground truth)
    ref_filename = f"merge{file_extension}"
    ref_file_path = os.path.join(output_viz_dir, ref_filename)
    
    valid_ref = os.path.exists(ref_file_path)
    num_conflicts_ref, content_ref, conflicts_ref = count_and_extract_conflicts(ref_file_path)
    
    all_results[ref_name] = {
        'conflicts': num_conflicts_ref, 
        'content': content_ref, 
        'conflict_blocks': conflicts_ref,
        'valid': valid_ref
    }
    
    expected_output_name = f"merge{file_extension}"

    for tool_name in tool_names:
        tool_output_path = os.path.join(output_viz_dir, tool_name, expected_output_name)
        
        # check if file exists
        valid_tool = os.path.exists(tool_output_path)
        
        num_conflicts, content, conflicts = count_and_extract_conflicts(tool_output_path)
        all_results[tool_name] = {
            'conflicts': num_conflicts, 
            'content': content, 
            'conflict_blocks': conflicts,
            'valid': valid_tool
        }

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
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_folder = f"run_{timestamp}"

    current_output_root = os.path.join(PATH_PREFIX, 'output', run_folder)
    current_scenarios_viz = os.path.join(current_output_root, 'scenarios')
    current_csv_file = os.path.join(current_output_root, 'results.csv')

    os.makedirs(current_scenarios_viz, exist_ok=True)

    print(f"EXECUTION RESULTS SAVED IN: {current_output_root}")
    
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
            scenario_source_path = os.path.join(project_path, commit_hash)
            if not os.path.isdir(scenario_source_path):
                continue

            print(f"PROCESSING: {project_name}/{commit_hash}...", end=" ", flush=True)

            base_dir = os.path.join(scenario_source_path, 'base')
            left_dir = os.path.join(scenario_source_path, 'left')
            right_dir = os.path.join(scenario_source_path, 'right')
            child_dir = os.path.join(scenario_source_path, 'child')

            base_file = find_source_file(base_dir)
            left_file = find_source_file(left_dir)
            right_file = find_source_file(right_dir)
            child_file = find_source_file(child_dir)

            if not all([base_file, left_file, right_file]):
                missing = []
                if not base_file: missing.append("BASE")
                if not left_file: missing.append("LEFT")
                if not right_file: missing.append("RIGHT")
                print(f"ERROR: {', '.join(missing)} missing")
                continue #skip this commit

            original_filename = os.path.basename(base_file)
            _, file_extension = os.path.splitext(original_filename)

            scenario_viz_path = os.path.join(current_scenarios_viz, project_name, commit_hash, original_filename)
            os.makedirs(scenario_viz_path, exist_ok=True)

            try:
                shutil.copy2(base_file, os.path.join(scenario_viz_path, f"base{file_extension}"))
                shutil.copy2(left_file, os.path.join(scenario_viz_path, f"left{file_extension}"))
                shutil.copy2(right_file, os.path.join(scenario_viz_path, f"right{file_extension}"))
                
                if child_file and os.path.exists(child_file):
                    shutil.copy2(child_file, os.path.join(scenario_viz_path, f"merge{file_extension}"))
            except Exception as e:
                print(f"COPY ERROR: {e}")
                continue

            times = {}
            detected_extension = file_extension

            viz_base = os.path.join(scenario_viz_path, f"base{file_extension}")
            viz_left = os.path.join(scenario_viz_path, f"left{file_extension}")
            viz_right = os.path.join(scenario_viz_path, f"right{file_extension}")
            
            # run tools
            for tool in tools_config:
                tool_name = tool['name']
                valid_runs=[]

                for i in range(10):
                    exec_time, success = run_tool(tool, viz_base, viz_left, viz_right, scenario_viz_path)
                    
                    if success:
                        valid_runs.append(exec_time)
                
                if valid_runs:
                    if len(valid_runs)>1:
                        valid_runs.pop(0)
                    
                    avg_time = sum(valid_runs)/len(valid_runs)
                    times[tool_name] = round(avg_time, 4)
                else:
                    times[tool_name] = -1
                    print(f"[TOOL {tool_name} FAILED 10x]", end=" ")

            # analyse and saves data
            if detected_extension:
                try:
                    row_data = analyze_scenario(
                        project_name, 
                        commit_hash,
                        original_filename,
                        scenario_viz_path, 
                        tools_config, 
                        ref_name, 
                        times, 
                        detected_extension
                    )
                    
                    df_row = pd.DataFrame([row_data])
                    file_exists = os.path.exists(current_csv_file)
                    
                    # write to csv
                    df_row.to_csv(current_csv_file, mode='a', header=not file_exists, index=False)
                    print(f"DONE!")
                    
                except Exception as e:
                    print(f"ANALYSIS ERROR: {e}")
            else:
                print(f"SKIP: INPUT FILES NOT FOUND")

    print("\nFINISHED EXECUTION")

if __name__ == '__main__':
    main()