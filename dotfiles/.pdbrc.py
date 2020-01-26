print "\n.pdbrc.py started"

# Find home.
import os
home = os.curdir
if 'HOME' in os.environ:
    home = os.environ['HOME']
elif os.name == 'posix':
    home = os.path.expanduser("~/")
# Make sure home always ends with a directory separator.
home = os.path.realpath(home) + os.sep
print "Home folder: " + home

# Command line history.
# Source: https://wiki.python.org/moin/PdbRcIdea
import readline
histfile = home + ".pdb_history"
print "Command history: " + histfile
try:
    readline.read_history_file(histfile)
except IOError:
    pass
import atexit
atexit.register(readline.write_history_file, histfile)
del histfile
readline.set_history_length(20000)

# Autocomplete.
import rlcompleter
pdb.Pdb.complete = rlcompleter.Completer(locals()).complete

# Sometimes when you do something funky, you may lose your terminal echo. This
# should restore it when spanwning new pdb.
# Source: https://gist.github.com/epeli/1125049
import termios, sys
termios_fd = sys.stdin.fileno()
termios_echo = termios.tcgetattr(termios_fd)
termios_echo[3] = termios_echo[3] | termios.ECHO
termios_result = termios.tcsetattr(termios_fd, termios.TCSADRAIN, termios_echo)

print ".pdbrc.py finished"
