from commands.command import Command

class SyncCommand(Command):
    def is_synchronous(self):
        return True
