from commands.command import Command
import time

class AsyncCommand(Command):
    def is_synchronous(self) -> bool:
        return False
    
    def check_progress(self) -> bool:
        pass

    def execute_sync(self, timeout = 1000):
        self.execute()
        start = time.perf_counter()

        while not self.check_progress():
            current_time = time.perf_counter()
            if current_time - start > timeout:
                raise Exception('Timeout occurred!')
        return True