# Add to envs/__init__.py in make_env(), alongside the crafter/atari branches.
# config.task = "pigrunner_v0" splits into suite="pigrunner", task="v0".

    elif suite == "pigrunner":
        from envs.pigrunner import PigRunnerEnv

        env = PigRunnerEnv(task, seed=config.seed + id)
        env = wrappers.OneHotAction(env)   # env exposes Discrete(2); wrapper one-hots it
