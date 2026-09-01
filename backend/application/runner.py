"""Single outer transaction runner for model-free application commands."""

from application.contracts import CommandContext, CommandResult, CommandSpec
from core.idempotency import UncommittedResponse, execute_idempotent
from core.services import run_in_tenant


def run_command(spec: CommandSpec, context: CommandContext, callback):
    if not isinstance(spec, CommandSpec) or not isinstance(context, CommandContext):
        raise TypeError("run_command requires CommandSpec and CommandContext values.")
    if context.capability != spec.capability:
        raise PermissionError("Command capability does not match the command contract.")
    if spec.requires_idempotency and not context.idempotency_key:
        raise ValueError("This command requires an Idempotency-Key.")
    if context.idempotency_key and not context.fingerprint:
        raise ValueError("An idempotent command requires a request fingerprint.")

    def invoke():
        result = callback(context)
        if isinstance(result, CommandResult) and not 200 <= result.status_code < 300:
            raise UncommittedResponse(result)
        return result

    if not context.idempotency_key:
        result = run_in_tenant(context.organisation_id, invoke)
        return _as_result(result)

    outcome = run_in_tenant(
        context.organisation_id,
        lambda: execute_idempotent(
            organisation=context.organisation_id,
            operation=spec.operation_id,
            key=context.idempotency_key,
            fingerprint=context.fingerprint,
            callback=invoke,
        ),
    )
    if outcome.replay:
        return CommandResult(
            status_code=outcome.status_code,
            body=outcome.body,
            headers=outcome.headers or {},
            result_reference=outcome.result_reference,
            replayed=True,
        )
    return _as_result(outcome.value)


def _as_result(value):
    if isinstance(value, CommandResult):
        return value
    return CommandResult(status_code=200, body=value)
