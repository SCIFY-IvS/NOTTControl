from commands.command import Command

class AsyncCommand(Command):
    def is_synchronous(self):
        return False

    
    def check_progress(self):
        pass