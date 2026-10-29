"""Clamp candidate Docker work to the remaining aggregate attempt time."""

from dataclasses import replace


class BudgetRunner:
    def __init__(self, runner, budget):
        self.runner, self.budget = runner, budget

    def __getattr__(self, name):
        return getattr(self.runner, name)

    def run(self, source, command, *, artifact_root=None):
        # The initial public baseline is prepared outside attempt accounting.
        if artifact_root and "regression-baseline" in str(artifact_root):
            with self.budget.exclude_baseline():
                return self.runner.run(source, command, artifact_root=artifact_root)
        self.budget.start()
        self.budget.check()
        command = replace(
            command, timeout_seconds=min(command.timeout_seconds, self.budget.remaining)
        )
        docker = getattr(self.runner, "_docker", None)

        def bounded(*args, **kwargs):
            if args and args[0] == "rm":
                return docker(*args, **kwargs)
            self.budget.check()
            kwargs["timeout"] = min(kwargs.get("timeout", 30), self.budget.remaining)
            return docker(*args, **kwargs)

        if docker is not None:
            self.runner._docker = bounded
        try:
            result = self.runner.run(source, command, artifact_root=artifact_root)
            self.budget.check()
            return result
        finally:
            if docker is not None:
                self.runner._docker = docker
