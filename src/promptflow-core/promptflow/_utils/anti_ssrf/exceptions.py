class AntiSSRFException(Exception):
    def __init__(self, message=None, inner=None):
        if inner is not None:
            super().__init__(message, inner)
        elif message is not None:
            super().__init__(message)
        else:
            super().__init__()
