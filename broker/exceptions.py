
class ConnectError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class BeginTracking(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class EndTracking(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message