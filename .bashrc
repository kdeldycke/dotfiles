# .bashrc

# User specific aliases and functions

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

# enable programmable completion features
if [ -f /etc/bash_completion ]; then
	. /etc/bash_completion
fi

# setting history length
HISTCONTROL="ignorespace:erasedups"
HISTTIMEFORMAT="[%F %T] "
HISTSIZE=99999

# Case-insensitive globbing (used in pathname expansion)
shopt -s nocaseglob

# append to the history file, don't overwrite it
shopt -s histappend
# Allow use to re-edit a faild history substitution.
shopt -s histreedit
# History expansions will be verified before execution.
shopt -s histverify

# Check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# Ubuntu stuff
alias du='du -csh'
alias df='df -Th'
alias ll='ls -lah --group-directories-first'
alias ls='ls -hFp --color'
# TODO: activate this OSX version
# alias ls='ls -hFp -G'
alias vi='vim'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Handy aliases for going up in a directory
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias .....="cd ../../../.."

# Python shell auto-completion and history
export PYTHONSTARTUP="$HOME/python-shell-enhancement/pythonstartup.py"
export PYTHON_HISTORY_FILE="$HOME/.python_history"

