class DeploymentWorkerError(Exception):
    retryable = False
    code = "deployment_worker_error"


class RetryableDeploymentError(DeploymentWorkerError):
    retryable = True
    code = "retryable_error"


class TerminalDeploymentError(DeploymentWorkerError):
    retryable = False
    code = "terminal_error"


class PolicyBlockedError(TerminalDeploymentError):
    code = "policy_blocked"

