class BuildJobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContainerBuildStatus:
    QUEUED = "queued"
    VALIDATING_CONTEXT = "validating_context"
    BUILDING = "building"
    PUSHING_IMAGE = "pushing_image"
    SCANNING_IMAGE = "scanning_image"
    READY_FOR_DEPLOY = "ready_for_deploy"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DeploymentStatus:
    QUEUED = "queued"
    BUILDING = "building"
    SCANNING = "scanning"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
