import pylint
import sys
from configure_ftd_int import aetest
print(sys.path)


args = [ '--rcfile=pylintrc', 'configure_ftd_int.py']
pylint.run_pylint(args)