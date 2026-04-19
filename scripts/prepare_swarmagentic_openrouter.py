"""Patch a cloned SwarmAgentic TravelPlanner workspace for OpenRouter runs."""

from __future__ import annotations

import argparse
from pathlib import Path

PATCH_REVISION = "swarm-openrouter-20260407-monitoring-v1"


MODEL_HELP_BLOCK = """    parser.add_argument('--model', type=str, default='gpt-4o-mini',
                       choices=['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo-2024-04-09', 'gpt-3.5-turbo-0125'],
                       help='LLM model to use')
"""

MODEL_HELP_REPLACEMENT = """    parser.add_argument('--model', type=str, default='openai/gpt-4o',
                       help='LLM model to use (for OpenRouter, prefer fully qualified ids such as openai/gpt-4o)')
    parser.add_argument('--extract_model', type=str, default=None,
                       help='Optional extraction model override; defaults to --model when omitted')
"""

MAIN_CALL_BLOCK = """        particle_idx=args.particle_idx,
        model=args.model,
        save_dir=args.save_dir,
        start_index=args.start_index,
        end_index=args.end_index,
        max_workers=args.max_workers,
        dataset_path=args.dataset,
        ref_info_path=args.ref_info,
        aggregate_folder=args.aggregate_folder
    ))
"""

MAIN_CALL_REPLACEMENT = """        particle_idx=args.particle_idx,
        model=args.model,
        save_dir=args.save_dir,
        start_index=args.start_index,
        end_index=args.end_index,
        max_workers=args.max_workers,
        dataset_path=args.dataset,
        ref_info_path=args.ref_info,
        aggregate_folder=args.aggregate_folder,
        extract_model=args.extract_model
    ))
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch SwarmAgentic TravelPlanner test.py for controlled OpenRouter use"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Path to a cloned SwarmAgenticCode repository",
    )
    return parser.parse_args()


def replace_once(text: str, old: str, new: str, *, path: Path, label: str) -> str:
    """Replace one known code block, warning instead of failing on drift."""
    if new in text:
        return text
    if old not in text:
        print(f"WARNING: could not patch {label} in {path}")
        return text
    return text.replace(old, new, 1)


def patch_test_script(test_path: Path) -> None:
    text = test_path.read_text(encoding="utf-8")

    if "def resolve_model_name(model_name: str) -> str:" not in text:
        anchor = "from eval import evaluate, get_scores\n"
        helper = """

def resolve_model_name(model_name: str) -> str:
    alias_map = {
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-4-turbo-2024-04-09": "openai/gpt-4-turbo",
        "gpt-3.5-turbo-0125": "openai/gpt-3.5-turbo-0125",
    }
    return alias_map.get(model_name, model_name)
"""
        if anchor not in text:
            raise ValueError(f"Unable to locate import anchor in {test_path}")
        text = text.replace(anchor, anchor + helper, 1)

    old_signature = """async def main(particle_idx=-1, model='gpt-4o-mini', save_dir='evaluation/test', 
               start_index=0, end_index=None, max_workers=16,
               dataset_path=r'data/validation.jsonl',
               ref_info_path=r'data/validation_ref_info.jsonl',
               aggregate_folder=None):
"""
    new_signature = """async def main(particle_idx=-1, model='openai/gpt-4o', save_dir='evaluation/test', 
               start_index=0, end_index=None, max_workers=16,
               dataset_path=r'data/validation.jsonl',
               ref_info_path=r'data/validation_ref_info.jsonl',
               aggregate_folder=None, extract_model=None):
"""
    if old_signature in text:
        text = text.replace(old_signature, new_signature, 1)

    text = text.replace(
        "    llm_role = ChatOpenAI(model=model, temperature=0.001)\n"
        '    llm_extract = ChatOpenAI(model="gpt-4o-mini")  # Fixed model for extraction\n',
        "    llm_role = ChatOpenAI(model=resolve_model_name(model), temperature=0.001)\n"
        "    llm_extract = ChatOpenAI(\n"
        "        model=resolve_model_name(extract_model or model),\n"
        "        temperature=0.001,\n"
        "    )\n",
        1,
    )

    if MODEL_HELP_BLOCK in text:
        text = text.replace(MODEL_HELP_BLOCK, MODEL_HELP_REPLACEMENT, 1)
    if MAIN_CALL_BLOCK in text:
        text = text.replace(MAIN_CALL_BLOCK, MAIN_CALL_REPLACEMENT, 1)

    # --- resolve relative dataset paths (imports chdir away from swarm/) ---
    os_anchor = "import os\n"
    cwd_snippet = (
        "\n# -- patch: remember original cwd before transitive imports chdir --\n"
        "_ORIG_CWD = os.path.abspath(os.getcwd())\n"
    )
    if "_ORIG_CWD" not in text and os_anchor in text:
        text = text.replace(os_anchor, os_anchor + cwd_snippet, 1)

    # Resolve paths right before the first load_dataset call inside main()
    old_agg_load = "        testset = load_dataset(path=dataset_path)\n"
    new_agg_load = (
        "        dataset_path = os.path.join(_ORIG_CWD, dataset_path) if not os.path.isabs(dataset_path) else dataset_path\n"
        "        testset = load_dataset(path=dataset_path)\n"
    )
    if old_agg_load in text and "_ORIG_CWD, dataset_path" not in text:
        text = text.replace(old_agg_load, new_agg_load, 1)

    old_main_load = (
        "    testset = load_dataset(path=dataset_path)\n"
        "    infoset = load_ref_info(path=ref_info_path)\n"
    )
    new_main_load = (
        "    dataset_path = os.path.join(_ORIG_CWD, dataset_path) if not os.path.isabs(dataset_path) else dataset_path\n"
        "    ref_info_path = os.path.join(_ORIG_CWD, ref_info_path) if not os.path.isabs(ref_info_path) else ref_info_path\n"
        "    testset = load_dataset(path=dataset_path)\n"
        "    infoset = load_ref_info(path=ref_info_path)\n"
    )
    if old_main_load in text and "    dataset_path = os.path.join(_ORIG_CWD" not in text:
        text = text.replace(old_main_load, new_main_load, 1)

    test_path.write_text(text, encoding="utf-8")


def patch_requirements(repo_root: Path) -> None:
    """Remove packages unnecessary for benchmarking that cause dependency conflicts."""
    req_path = repo_root / "requirements.txt"
    if not req_path.exists():
        return
    import re
    lines = req_path.read_text(encoding="utf-8").splitlines()
    # Packages to drop entirely (unused by pso.py / test.py, cause build or
    # dependency-resolution failures on Python 3.13).
    drop_prefixes = ("gradio",)
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip().lower()
        if any(stripped.startswith(p) for p in drop_prefixes):
            continue
        # Relax all exact pins (==X.Y.Z) to lower bounds (>=X.Y.Z) so uv
        # can resolve versions with pre-built wheels for the current Python.
        line = re.sub(r"==", ">=", line)
        filtered.append(line)
    req_path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    print(f"patched {req_path}")


def patch_gradio_imports(repo_root: Path) -> None:
    """Replace 'import gradio as gr' / 'gr.Error' with plain ValueError."""
    func_path = repo_root / "travelplanner" / "utils" / "func.py"
    if not func_path.exists():
        return
    text = func_path.read_text(encoding="utf-8")
    text = text.replace("import gradio as gr\n", "")
    text = text.replace("gr.Error(", "ValueError(")
    func_path.write_text(text, encoding="utf-8")
    print(f"patched {func_path}")


def patch_evaluation_imports(repo_root: Path) -> None:
    """Fix bare imports in evaluation/eval.py so it works when called from swarm/."""
    eval_path = repo_root / "travelplanner" / "evaluation" / "eval.py"
    if not eval_path.exists():
        return
    text = eval_path.read_text(encoding="utf-8")
    # Add evaluation dir to sys.path so bare imports resolve
    old = 'sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))'
    new = (
        'sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))\n'
        'sys.path.append(os.path.abspath(os.path.dirname(__file__)))'
    )
    if old in text and "os.path.dirname(__file__)" not in text:
        text = text.replace(old, new, 1)
        eval_path.write_text(text, encoding="utf-8")
        print(f"patched {eval_path}")


def patch_pso_resolve_paths(repo_root: Path) -> None:
    """Resolve dataset/ref_info paths to absolute before imports change cwd."""
    pso_path = repo_root / "travelplanner" / "swarm" / "pso.py"
    if not pso_path.exists():
        return
    text = pso_path.read_text(encoding="utf-8")
    # Insert an early cwd snapshot right after the imports, before any chdir
    # happens via transitive imports at module level.
    anchor = "from prompt.team_update import update_team\n"
    snippet = (
        "\n# -- patch: remember original cwd before transitive imports chdir --\n"
        "_ORIG_CWD = os.path.abspath(os.getcwd())\n"
    )
    if "_ORIG_CWD" not in text:
        if anchor not in text:
            print(f"WARNING: could not locate import anchor in {pso_path}, skipping path patch")
            return
        # Insert BEFORE the anchor so it runs before the chdir-causing imports
        # Actually we need it after 'import os' but before eval/role imports.
        # The safest place: right after 'import os' line.
        os_anchor = "import os\n"
        if os_anchor in text:
            text = text.replace(os_anchor, os_anchor + snippet, 1)
        else:
            print(f"WARNING: 'import os' not found in {pso_path}")
            return

    # Resolve relative paths at the start of main()
    old_load = "    # Load dataset\n    train_set = load_dataset(path=dataset_path)\n"
    new_load = (
        "    # Load dataset (resolve relative paths against original cwd)\n"
        "    dataset_path = os.path.join(_ORIG_CWD, dataset_path) if not os.path.isabs(dataset_path) else dataset_path\n"
        "    ref_info_path = os.path.join(_ORIG_CWD, ref_info_path) if not os.path.isabs(ref_info_path) else ref_info_path\n"
        "    train_set = load_dataset(path=dataset_path)\n"
    )
    if old_load in text:
        text = text.replace(old_load, new_load, 1)

    # Also resolve 'save_state.jsonl' in initialize_with_state()
    old_state = "    state = read_jsonl('save_state.jsonl')[idx]\n"
    new_state = "    state = read_jsonl(os.path.join(_ORIG_CWD, 'save_state.jsonl'))[idx]\n"
    if old_state in text:
        text = text.replace(old_state, new_state, 1)

    pso_path.write_text(text, encoding="utf-8")
    print(f"patched {pso_path}")


def patch_structured_output_method(repo_root: Path) -> None:
    """Force method='function_calling' for all with_structured_output calls.

    langchain-openai >=1.1 defaults to method='json_schema', which hangs
    indefinitely (client-side, no HTTP request sent) when the prompt is long
    and the schema is complex on certain providers.  'function_calling' works
    reliably with OpenRouter.
    """
    swarm_dir = repo_root / "travelplanner" / "swarm"
    count = 0
    for py_file in swarm_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if ".with_structured_output(schema)" in text or ".with_structured_output(TASK_OUTPUT_SCHEMA)" in text:
            original = text
            text = text.replace(
                ".with_structured_output(schema)",
                ".with_structured_output(schema, method='function_calling')",
            )
            text = text.replace(
                ".with_structured_output(TASK_OUTPUT_SCHEMA)",
                ".with_structured_output(TASK_OUTPUT_SCHEMA, method='function_calling')",
            )
            if text != original:
                py_file.write_text(text, encoding="utf-8")
                count += 1
    print(f"patched with_structured_output in {count} files under {swarm_dir}")


def patch_pso_resilience(repo_root: Path) -> None:
    """Harden pso.py against transient provider failures and missing outputs."""
    pso_path = repo_root / "travelplanner" / "swarm" / "pso.py"
    if not pso_path.exists():
        return

    text = pso_path.read_text(encoding="utf-8")

    helper_anchor = "from prompt.feedback_summarize import summarize_feedback\n"
    helper_snippet = """

LLM_MAX_RETRIES = 6
LLM_TIMEOUT_SECONDS = 180


def build_chat_llm(model, temperature):
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_retries=LLM_MAX_RETRIES,
        timeout=LLM_TIMEOUT_SECONDS,
    )


def debug_stdout(message):
    print(f"[PSO] {message}", flush=True)
"""
    if "def build_chat_llm(" not in text and helper_anchor in text:
        text = text.replace(helper_anchor, helper_anchor + helper_snippet, 1)

    text = replace_once(
        text,
        "        func = set_forward(code)\n",
        """        debug_stdout(f"iter={iter} particle={i_pos} evaluate:start samples={len(dataset)}")\n        try:\n            func = set_forward(code)\n        except Exception as e:\n            debug_stdout(f"iter={iter} particle={i_pos} set_forward:error error={e}")\n            log(self.logger, 'Set Forward Error', str(e))\n            self.fitness = 0.0\n            self.fitness_history.append(self.fitness)\n            if self.best_position is None:\n                self.best_position = (self.position[0].save_into_dict(), self.position[1])\n                self.best_fitness = self.fitness\n            self.evaluation = []\n            return\n""",
        path=pso_path,
        label="set_forward guard",
    )

    text = replace_once(
        text,
        """        def execute(team_with_task, data, evaluations, i, batch_logs):
            logs = [(f'Iter {iter} - Data {i}', '\\n# Roles Message', None)]
            
            task_instance = f'''**Given reference information:**\\n{infoset[i]}\\n\\n**Query:**\\n{data['query']}'''
            team_with_task.reset_task(task_instance)
            times = 0
            while times < 3:
                try:
                    res = func(team_with_task)
                    logs.extend(team_with_task.logs)
                    final_answer, plan_log = extract_plan(self.llm, res)
                    logs.append(plan_log)

                    result = {
                            "idx": i, 
                            "query": data['query'], 
                            "plan": final_answer
                    }
                    # evaluate the result and extract the constraints that are not satisfied
                    false_item, problem = evaluate(data, final_answer)
                    break
                
                except Exception as e:
                    logs = [(f'Iter {iter} - Data {i}', '\\n# Roles Message', None)]
                    team_with_task.reset_task(task_instance)
                    print(f'{e}')
                    times += 1

            logs.append((f'Iter {iter} - Data {i} - False Constraints', json.dumps(false_item, indent=4), None))

            if problem != "":
                evaluation = give_feedback(self.llm, self.logger, task_instance, team_with_task.patch_result_and_workflow(), problem)
                evaluations.append(evaluation)
            batch_logs.append(logs)
            return result
""",
        """        def execute(team_with_task, data, evaluations, i, batch_logs):
            logs = [(f'Iter {iter} - Data {i}', '\\n# Roles Message', None)]

            task_instance = f'''**Given reference information:**\\n{infoset[i]}\\n\\n**Query:**\\n{data['query']}'''
            team_with_task.reset_task(task_instance)
            times = 0
            false_item = []
            problem = ""
            result = {
                "idx": i,
                "query": data['query'],
                "plan": [],
            }
            last_error = None
            while times < 3:
                try:
                    debug_stdout(f"iter={iter} particle={i_pos} sample={i} attempt={times + 1} start")
                    res = func(team_with_task)
                    logs.extend(team_with_task.logs)
                    final_answer, plan_log = extract_plan(self.llm, res)
                    logs.append(plan_log)

                    result = {
                        "idx": i,
                        "query": data['query'],
                        "plan": final_answer,
                    }
                    # Evaluate the result and extract the constraints that are not satisfied.
                    false_item, problem = evaluate(data, final_answer)
                    debug_stdout(
                        f"iter={iter} particle={i_pos} sample={i} attempt={times + 1} done "
                        f"false_constraints={len(false_item)} problem={'yes' if problem != '' else 'no'}"
                    )
                    break

                except Exception as e:
                    last_error = e
                    logs = [(f'Iter {iter} - Data {i}', '\\n# Roles Message', None)]
                    team_with_task.reset_task(task_instance)
                    debug_stdout(f"iter={iter} particle={i_pos} sample={i} retry={times + 1} error={e}")
                    print(f'{e}')
                    times += 1
            else:
                problem = f'Execution failed after retries: {last_error}'
                debug_stdout(f"iter={iter} particle={i_pos} sample={i} failed_after_retries error={last_error}")
                logs.append((f'Iter {iter} - Data {i} - Runtime Error', str(last_error), None))

            logs.append((f'Iter {iter} - Data {i} - False Constraints', json.dumps(false_item, indent=4), None))

            if problem != "":
                try:
                    evaluation = give_feedback(
                        self.llm,
                        self.logger,
                        task_instance,
                        team_with_task.patch_result_and_workflow(),
                        problem,
                    )
                except Exception as e:
                    evaluation = f'Feedback unavailable due to provider/runtime error: {e}'
                    debug_stdout(f"iter={iter} particle={i_pos} sample={i} feedback_error={e}")
                    logs.append((f'Iter {iter} - Data {i} - Feedback Error', str(e), None))
                evaluations.append(evaluation)
            batch_logs.append(logs)
            return result
""",
        path=pso_path,
        label="execute retry fallback",
    )

    text = replace_once(
        text,
        """            results = await asyncio.gather(*tasks)
            for logs in batch_logs:
                log_all(self.logger, logs)
""",
        """            results = await asyncio.gather(*tasks, return_exceptions=True)
            normalized_results = []
            for i_data, item in enumerate(results):
                if isinstance(item, Exception):
                    log(self.logger, 'Execute Error', str(item))
                    normalized_results.append({
                        "idx": i_data,
                        "query": dataset[i_data]['query'],
                        "plan": [],
                    })
                else:
                    normalized_results.append(item)
            results = normalized_results
            for logs in batch_logs:
                log_all(self.logger, logs)
""",
        path=pso_path,
        label="gather return_exceptions",
    )

    text = replace_once(
        text,
        """        scores, _ = get_scores(dataset, f'{self.save_dir}/results-{iter}-{i_pos}.jsonl')
        self.fitness = scores['Commonsense Constraint Micro Pass Rate'] + scores['Hard Constraint Micro Pass Rate']
        log(self.logger, 'Pass Rate', f'''Commonsense Constraint: {scores['Commonsense Constraint Micro Pass Rate']}\\nHard Constraint:{scores['Hard Constraint Micro Pass Rate']}''')
""",
        """        try:
            scores, _ = get_scores(dataset, f'{self.save_dir}/results-{iter}-{i_pos}.jsonl')
            self.fitness = scores['Commonsense Constraint Micro Pass Rate'] + scores['Hard Constraint Micro Pass Rate']
            log(self.logger, 'Pass Rate', f'''Commonsense Constraint: {scores['Commonsense Constraint Micro Pass Rate']}\\nHard Constraint:{scores['Hard Constraint Micro Pass Rate']}''')
            debug_stdout(
                f"iter={iter} particle={i_pos} evaluate:scored fitness={self.fitness:.4f} "
                f"commonsense={scores['Commonsense Constraint Micro Pass Rate']:.4f} "
                f"hard={scores['Hard Constraint Micro Pass Rate']:.4f}"
            )
        except Exception as e:
            log(self.logger, 'Score Error', str(e))
            debug_stdout(f"iter={iter} particle={i_pos} evaluate:score_error error={e}")
            self.fitness = 0.0
""",
        path=pso_path,
        label="score fallback",
    )

    text = replace_once(
        text,
        """        evaluations = '\\n'.join(f"**Feedback {i+1}:**\\n{item}\\n" for i, item in enumerate(evaluations))
        self.evaluation = summarize_feedback(self.llm, self.logger, evaluations, json.dumps(team.save_into_dict(), indent=4))
""",
        """        evaluations = '\\n'.join(f"**Feedback {i+1}:**\\n{item}\\n" for i, item in enumerate(evaluations))
        try:
            self.evaluation = summarize_feedback(self.llm, self.logger, evaluations, json.dumps(team.save_into_dict(), indent=4))
            debug_stdout(f"iter={iter} particle={i_pos} evaluate:feedback_summary status=ok items={len(self.evaluation)}")
        except Exception as e:
            log(self.logger, 'Summarize Feedback Error', str(e))
            debug_stdout(f"iter={iter} particle={i_pos} evaluate:feedback_summary status=fallback error={e}")
            self.evaluation = []
""",
        path=pso_path,
        label="summarize_feedback fallback",
    )

    text = replace_once(
        text,
        """    def update_velocity(self, global_best_position):
        team = json.dumps(self.position[0].save_into_dict(), indent=4)
        global_best_team = json.dumps(global_best_position[0], indent=4)
        personal_best_team = json.dumps(self.best_position[0], indent=4)
        
        evaluation = self.evaluation

        if team == personal_best_team:
            p_best = None
        else:
            p_best = reflect_from_personal_best(self.llm, self.logger, team, evaluation, personal_best_team)
            
        if team == global_best_team:
            g_best = None
        else:
            g_best = reflect_from_global_best(self.llm, self.logger, team, evaluation, global_best_team)
        
        if self.velocity is None:
            velocity = initialize_velocity(self.llm, self.logger, team, evaluation)
            if team == personal_best_team and team == global_best_team:
                self.velocity = velocity
            else:
                self.velocity = update_velocity(self.llm, self.logger, team, velocity, g_best, p_best)
        else:
            failures = identify_failure(self.llm, self.logger, evaluation, self.velocity)
            velocity = improve_failure(self.llm, self.logger, team, failures)
            if team == personal_best_team and team == global_best_team:
                clean_velocity = [{k: v for k, v in item.items() if k != "Failed Adjustment"} for item in velocity]
                self.velocity = clean_velocity
            else:
                self.velocity = update_velocity(self.llm, self.logger, team, velocity, g_best, p_best)
""",
        """    def update_velocity(self, global_best_position):
        try:
            team = json.dumps(self.position[0].save_into_dict(), indent=4)
            global_best_team = json.dumps(global_best_position[0], indent=4)
            personal_best_team = json.dumps(self.best_position[0], indent=4)

            evaluation = self.evaluation

            if team == personal_best_team:
                p_best = None
            else:
                p_best = reflect_from_personal_best(self.llm, self.logger, team, evaluation, personal_best_team)

            if team == global_best_team:
                g_best = None
            else:
                g_best = reflect_from_global_best(self.llm, self.logger, team, evaluation, global_best_team)

            if self.velocity is None:
                velocity = initialize_velocity(self.llm, self.logger, team, evaluation)
                if team == personal_best_team and team == global_best_team:
                    self.velocity = velocity
                else:
                    self.velocity = update_velocity(self.llm, self.logger, team, velocity, g_best, p_best)
            else:
                failures = identify_failure(self.llm, self.logger, evaluation, self.velocity)
                velocity = improve_failure(self.llm, self.logger, team, failures)
                if team == personal_best_team and team == global_best_team:
                    clean_velocity = [{k: v for k, v in item.items() if k != "Failed Adjustment"} for item in velocity]
                    self.velocity = clean_velocity
                else:
                    self.velocity = update_velocity(self.llm, self.logger, team, velocity, g_best, p_best)
        except Exception as e:
            log(self.logger, 'Update Velocity Error', str(e))
            debug_stdout(f"particle_velocity:update_error error={e}")
            if self.velocity is None:
                self.velocity = []
""",
        path=pso_path,
        label="update_velocity fallback",
    )

    text = replace_once(
        text,
        """    def update_position(self):
        team = self.position[0]
        new_team = update_team(self.llm, self.logger, team.to_str(), team.workflow, self.velocity)
        team.update(new_team)
        new_code = get_forward(self.llm, self.logger, team.to_str(), team.workflow)
        self.position = (team, new_code)
""",
        """    def update_position(self):
        try:
            team = self.position[0]
            new_team = update_team(self.llm, self.logger, team.to_str(), team.workflow, self.velocity)
            team.update(new_team)
            new_code = get_forward(self.llm, self.logger, team.to_str(), team.workflow)
            self.position = (team, new_code)
        except Exception as e:
            log(self.logger, 'Update Position Error', str(e))
""",
        path=pso_path,
        label="update_position fallback",
    )

    text = text.replace("ChatOpenAI(model=model, temperature=item)", "build_chat_llm(model=model, temperature=item)")
    text = text.replace("ChatOpenAI(model=model, temperature=0.001)", "build_chat_llm(model=model, temperature=0.001)")

    text = replace_once(
        text,
        """            awaitables = asyncio.as_completed(evaluate_tasks)
            for _ in tqdm(awaitables, desc="Particles Evaluate", total=len(particles), position=1):
                await _

            global_best_position, global_best_fitness = update_global_best(particles, global_best_position, global_best_fitness)
            global_best_trend.append(global_best_fitness)
""",
        """            debug_stdout(f"iter={iter} particle_batch:start count={len(particles)}")\n            awaitables = asyncio.as_completed(evaluate_tasks)
            for pending in tqdm(awaitables, desc="Particles Evaluate", total=len(particles), position=1):
                try:
                    await pending
                except Exception as e:
                    debug_stdout(f"iter={iter} particle_batch:error error={e}")
                    print(f'Particle evaluation failed: {e}')

            global_best_position, global_best_fitness = update_global_best(particles, global_best_position, global_best_fitness)
            global_best_trend.append(global_best_fitness)
            debug_stdout(
                f"iter={iter} global_best:update fitness={global_best_fitness:.4f} "
                f"has_position={'yes' if global_best_position is not None else 'no'}"
            )
            debug_stdout(f"iter={iter} checkpoint:start")
            save_state(particles, global_best_position, global_best_fitness, global_best_trend)
            debug_stdout(f"iter={iter} checkpoint:done")
""",
        path=pso_path,
        label="per-iteration checkpoint",
    )

    text = replace_once(
        text,
        """def update_global_best(particles, global_best_position, global_best_fitness):
    g_best_position = global_best_position
    g_best_fitness = global_best_fitness
    
    for p in particles:
        if p.fitness >= g_best_fitness:
            g_best_position = p.best_position
            g_best_fitness = p.fitness
    
    return g_best_position, g_best_fitness
""",
        """def update_global_best(particles, global_best_position, global_best_fitness):
    g_best_position = global_best_position
    g_best_fitness = global_best_fitness

    for idx, p in enumerate(particles):
        if p.best_position is None:
            debug_stdout(f"particle={idx} global_best:skip reason=missing_best_position fitness={p.fitness:.4f}")
            continue
        if p.fitness >= g_best_fitness:
            g_best_position = p.best_position
            g_best_fitness = p.fitness
            debug_stdout(f"particle={idx} global_best:new fitness={g_best_fitness:.4f}")

    if g_best_position is None:
        for idx, p in enumerate(particles):
            if p.best_position is None:
                continue
            g_best_position = p.best_position
            g_best_fitness = max(g_best_fitness, p.best_fitness)
            debug_stdout(f"global_best:fallback particle={idx} fitness={g_best_fitness:.4f}")
            break

    return g_best_position, g_best_fitness
""",
        path=pso_path,
        label="global_best guard",
    )

    text = replace_once(
        text,
        """    print(f"Loaded {len(dataset)} examples (sampled every {sample_step} items)")
""",
        """    print(f"Loaded {len(dataset)} examples (sampled every {sample_step} items)")
    debug_stdout(
        f"dataset:loaded count={len(dataset)} sample_step={sample_step} "
        f"dataset_path={dataset_path} ref_info_path={ref_info_path}"
    )
""",
        path=pso_path,
        label="dataset load debug",
    )

    pso_path.write_text(text, encoding="utf-8")
    print(f"patched {pso_path}")


def patch_test_resilience(repo_root: Path) -> None:
    """Harden test.py against transient provider failures and missing outputs."""
    test_path = repo_root / "travelplanner" / "swarm" / "test.py"
    if not test_path.exists():
        return

    text = test_path.read_text(encoding="utf-8")

    helper_anchor = """def resolve_model_name(model_name: str) -> str:
    alias_map = {
        "gpt-4o": "openai/gpt-4o",
        "gpt-4o-mini": "openai/gpt-4o-mini",
        "gpt-4-turbo-2024-04-09": "openai/gpt-4-turbo",
        "gpt-3.5-turbo-0125": "openai/gpt-3.5-turbo-0125",
    }
    return alias_map.get(model_name, model_name)
"""
    helper_snippet = """


def build_chat_llm(model_name: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=resolve_model_name(model_name),
        temperature=temperature,
        max_retries=6,
        timeout=180,
    )


def debug_stdout(message: str) -> None:
    print(f"[SWARM-TEST] {message}", flush=True)
"""
    if "def build_chat_llm(" not in text and helper_anchor in text:
        text = text.replace(helper_anchor, helper_anchor + helper_snippet, 1)

    text = replace_once(
        text,
        """def execute(team_with_task, data, ref_info, i, func, llm_extract):
    \"\"\"Execute a single task and evaluate the result.\"\"\"
    task_description = f'''Given reference information: {ref_info}\\n\\nQuery: {data['query']}\\n'''
    team_with_task.reset_task(task_description)
    
    res = func(team_with_task)
    final_answer, plan_log = extract_plan(llm_extract, res)
    
    # Evaluation 
    try:
        false_item, problem = evaluate(data, final_answer)
        
        if problem != '': 
            score = 0.0
        else:
            score = 1.0
    except:
        score = 0.0
    
    result = {
        \"idx\": i,
        \"query\": data['query'],
        \"plan\": final_answer,
        \"score\": score
    }
    return result
""",
        """def execute(team_with_task, data, ref_info, i, func, llm_extract):
    \"\"\"Execute a single task and evaluate the result.\"\"\"
    task_description = f'''Given reference information: {ref_info}\\n\\nQuery: {data['query']}\\n'''
    team_with_task.reset_task(task_description)
    debug_stdout(f"query={i} execute:start")

    res = func(team_with_task)
    final_answer, plan_log = extract_plan(llm_extract, res)

    # Evaluation
    try:
        false_item, problem = evaluate(data, final_answer)

        if problem != '':
            score = 0.0
        else:
            score = 1.0
        debug_stdout(
            f"query={i} execute:done score={score:.1f} "
            f"false_constraints={len(false_item)} problem={'yes' if problem != '' else 'no'}"
        )
    except Exception as e:
        debug_stdout(f"query={i} execute:evaluation_error error={e}")
        score = 0.0

    result = {
        \"idx\": i,
        \"query\": data['query'],
        \"plan\": final_answer,
        \"score\": score
    }
    return result
""",
        path=test_path,
        label="test execute debug",
    )

    text = replace_once(
        text,
        """        results = await asyncio.gather(*tasks)
""",
        """        results = await asyncio.gather(*tasks, return_exceptions=True)
        normalized_results = []
        for i, item in enumerate(results):
            if isinstance(item, Exception):
                log(logger, 'Evaluation Task Error', str(item))
                normalized_results.append({
                    "idx": i + start_index,
                    "query": dataset[i]['query'],
                    "plan": [],
                    "score": 0.0,
                })
            else:
                normalized_results.append(item)
        results = normalized_results
""",
        path=test_path,
        label="test gather return_exceptions",
    )

    text = replace_once(
        text,
        """    llm_role = ChatOpenAI(model=resolve_model_name(model), temperature=0.001)
    llm_extract = ChatOpenAI(
        model=resolve_model_name(extract_model or model),
        temperature=0.001,
    )
""",
        """    llm_role = build_chat_llm(model, temperature=0.001)
    llm_extract = build_chat_llm(extract_model or model, temperature=0.001)
""",
        path=test_path,
        label="test llm retry config",
    )

    text = replace_once(
        text,
        """    result_path = os.path.join(save_dir, 'results.jsonl')
    write_jsonl(result_path, results, 'w')
    
    # Calculate fitness
    scores = [result['score'] for result in results]
""",
        """    result_path = os.path.join(save_dir, 'results.jsonl')
    write_jsonl(result_path, results, 'w')
    debug_stdout(f"save_dir={save_dir} results_written count={len(results)} path={result_path}")
    
    # Calculate fitness
    scores = [result['score'] for result in results]
""",
        path=test_path,
        label="test results write debug",
    )

    text = replace_once(
        text,
        """        aggregated_path = aggregate_results(aggregate_folder)
        
        # Load dataset for score calculation
""",
        """        aggregated_path = aggregate_results(aggregate_folder)
        debug_stdout(f"aggregate:start folder={aggregate_folder} aggregated_path={aggregated_path}")
        
        # Load dataset for score calculation
""",
        path=test_path,
        label="test aggregate debug",
    )

    text = replace_once(
        text,
        """    # Setup logger
    logger = setup_logger(particle_idx)
    
    # Initialize LLMs
""",
        """    debug_stdout(
        f"main:start particle_idx={particle_idx} model={model} extract_model={extract_model or model} "
        f"range={start_index}:{end_index} max_workers={max_workers}"
    )
    # Setup logger
    logger = setup_logger(particle_idx)
    
    # Initialize LLMs
""",
        path=test_path,
        label="test main debug start",
    )

    test_path.write_text(text, encoding="utf-8")
    print(f"patched {test_path}")


def link_database(repo_root: Path, stigmergi_root: Path) -> None:
    """Symlink the TravelPlanner database into the SwarmAgentic clone."""
    target = stigmergi_root / "data" / "travelplanner" / "database"
    link = repo_root / "travelplanner" / "database"
    if link.exists() or link.is_symlink():
        return
    if not target.exists():
        raise FileNotFoundError(f"TravelPlanner database not found at {target}")
    link.symlink_to(target)
    print(f"symlinked {link} -> {target}")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    test_path = repo_root / "travelplanner" / "swarm" / "test.py"
    if not test_path.exists():
        raise FileNotFoundError(f"SwarmAgentic TravelPlanner test.py not found: {test_path}")

    # Detect the StigmergiAgentic repo root (this script lives in scripts/)
    stigmergi_root = Path(__file__).resolve().parent.parent

    patch_test_script(test_path)
    print(f"patched {test_path}")
    patch_requirements(repo_root)
    patch_gradio_imports(repo_root)
    patch_evaluation_imports(repo_root)
    patch_pso_resolve_paths(repo_root)
    patch_structured_output_method(repo_root)
    patch_pso_resilience(repo_root)
    patch_test_resilience(repo_root)
    link_database(repo_root, stigmergi_root)
    (repo_root / ".stig_patch_revision").write_text(PATCH_REVISION + "\n", encoding="utf-8")
    print(f"wrote patch revision {PATCH_REVISION} to {repo_root / '.stig_patch_revision'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
