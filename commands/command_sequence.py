from collections import deque

class CommandSequence:
    def __init__(self, commands, name):
        self._commands = deque(commands)
        self._name = name

    def execute(self):
        print('Executing...')
        self.execute_next_step()
    
    def execute_next_step(self):
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
        if self._activeCommand.check_progress():
            if not self._commands: #queue empty
                return True
            else:
                self.execute_next_step()
        return False