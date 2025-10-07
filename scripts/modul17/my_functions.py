from astroid import Raise


def area(length, width):
    if length < 0 or width < 0:
        raise ValueError('length and width must be positive')

    return length*width