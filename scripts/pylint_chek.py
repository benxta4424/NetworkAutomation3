import pylint
import sys
print(sys.path)


args = [ '--rcfile=pylintrc', '4_ftd_config.py']
pylint.run_pylint(args)