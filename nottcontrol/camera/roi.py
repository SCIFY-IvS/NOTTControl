
class Roi():
    #Create a Roi, using the coordinates of the top left, followed by the width and the height
    def __init__(self, x, y, w, h) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h