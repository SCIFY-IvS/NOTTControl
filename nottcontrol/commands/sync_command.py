from commands.command import Command

class SyncCommand(Command):
    def is_synchronous(self):
        return True
    
    def check_progress(self):
        return False
