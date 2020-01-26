# -*- coding: utf-8 -*-

import rlcompleter
import readline
import atexit
import os
import sys
import pprint


# Enable tab completion.
# Source: https://docs.python.org/3/library/rlcompleter.html
readline.parse_and_bind("tab: complete")


# Enable history file.
# Source: https://docs.python.org/3/library/readline.html?highlight=readline#example
history_file = os.environ.get(
    "PYTHON_HISTORY_FILE",
    os.path.join(os.path.expanduser("~"), '.python_history'))
history_size = os.environ.get("PYTHON_HISTORY_SIZE", -1)

try:
    readline.read_history_file(history_file)
    history_length = readline.get_current_history_length()
except FileNotFoundError:
    open(history_file, 'wb').close()
    history_length = 0

def save(previous_length, history):
    new_length = readline.get_current_history_length()
    readline.set_history_length(history_size)
    readline.append_history_file(new_length - previous_length, history)

atexit.register(save, history_length, history_file)


# Enable pretty printing for stdout.
def display_hook(value):
    """ Pretty-print provided value. """
    if value is not None:
        try:
            import __builtin__
            __builtin__._ = value
        except ImportError:
            __builtins__._ = value
        pprint.pprint(value)
sys.displayhook = display_hook


print(
    'Persistent session history, tab completion and pretty printing are'
    ' enabled.')
