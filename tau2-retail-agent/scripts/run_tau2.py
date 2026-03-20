import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if "TAU2_DATA_DIR" not in os.environ:
    os.environ["TAU2_DATA_DIR"] = str(
        Path(__file__).parent.parent.parent / "tau2-bench" / "data"
    )

from tau2.registry import registry
from tau2.run import run_domain
from tau2.data_model.simulation import RunConfig

from agent.tau2_agent import RetailAgent

registry.register_agent(RetailAgent, "retail_agent")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="retail")
    parser.add_argument("--agent", default="retail_agent")
    parser.add_argument("--agent-llm", default="gpt-5-mini")
    parser.add_argument("--user-llm", default="gpt-5-mini")
    parser.add_argument("--num-tasks", type=int, default=None)
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--task-ids", nargs="*", default=None)
    parser.add_argument("--save-to", default=None)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--seed", type=int, default=300)
    parser.add_argument("--task-split-name", default=None)
    args = parser.parse_args()

    config = RunConfig(
        domain=args.domain,
        agent=args.agent,
        llm_agent=args.agent_llm,
        llm_user=args.user_llm,
        llm_args_agent={},
        llm_args_user={},
        num_tasks=args.num_tasks,
        num_trials=args.num_trials,
        task_ids=args.task_ids,
        save_to=args.save_to,
        max_concurrency=args.max_concurrency,
        seed=args.seed,
        task_split_name=args.task_split_name,
    )
    results = run_domain(config)
    df = results.to_df()
    print("\n=== Results ===")
    print(f"Pass rate: {df['reward'].mean():.1%}")
    print(df[["task_id", "reward"]].to_string(index=False))


if __name__ == "__main__":
    main()
