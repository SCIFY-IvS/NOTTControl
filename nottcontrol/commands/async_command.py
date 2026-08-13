from nottcontrol.commands.command import Command
import time

_TERMINAL_FAILURE_TOKENS = ("ERR", "FAULT", "TIMEOUT", "TIME OUT", "TIME-OUT")


def is_axis_move_finished(status, state) -> bool:
    """Return True when a delay-line/motor move has finished successfully or failed.

    Successful completion uses STANDING + OPERATIONAL (including variants such as
    "Motor stopped - STANDING"). Timeout/error/fault/not-operational states also
    count as finished so the GUI can re-enable Absolute/Relative move buttons.
    """
    status_u = str(status or "").upper()
    state_u = str(state or "").upper()

    standing = "STAND" in status_u
    not_operational = (
        "NOT OPERATIONAL" in state_u or "NOT_OPERATIONAL" in state_u
    )
    operational = "OPERATIONAL" in state_u and not not_operational
    if standing and operational:
        return True

    if not_operational:
        return True

    if any(token in status_u for token in _TERMINAL_FAILURE_TOKENS):
        return True
    if any(token in state_u for token in _TERMINAL_FAILURE_TOKENS):
        return True
    return False


class AsyncCommand(Command):
    def is_synchronous(self) -> bool:
        return False

    def check_progress(self) -> bool:
        pass

    def execute_sync(self, timeout=1000):
        self.execute()
        start = time.perf_counter()

        while not self.check_progress():
            current_time = time.perf_counter()
            if current_time - start > timeout:
                raise Exception("Timeout occurred!")
        return True
