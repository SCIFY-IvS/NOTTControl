from collections import deque

#TODO does this work properly when finishing on a synchronous step?
class CommandSequence:
    def __init__(self, commands, name):
        self._commands = deque(commands)
        self._name = name

    def execute(self):
        print('Executing...')
        self.execute_next_step()
    
    def execute_next_step(self):
        if not self._commands:
            self._activeCommand = None
            return

        self._activeCommand = self._commands.popleft()
        self._activeCommand.execute()

        #If the next command is synchronous, execute it, then immediately continue
        #Otherwise, we stop execution here, and continue only when check_progress is called
        if self._activeCommand.is_synchronous():
            self.execute_next_step()
    
    def text(self):
        print('text')
        return f'{self._name}: {self._activeCommand.text()}'
    
    def check_progress(self):
        print('check progress')
        if self._activeCommand is None:
            return True
        
        if self._activeCommand.check_progress():
            self.execute_next_step()

        return False