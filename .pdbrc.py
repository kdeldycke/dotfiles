# Autocomplete
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
