### Added by Zinit's installer
if [[ ! -f $HOME/.zinit/bin/zinit.zsh ]]; then
    print -P "%F{33}▓▒░ %F{220}Installing DHARMA Initiative Plugin Manager (zdharma/zinit)…%f"
    command mkdir -p "$HOME/.zinit" && command chmod g-rwX "$HOME/.zinit"
    command git clone https://github.com/zdharma/zinit "$HOME/.zinit/bin" && \
        print -P "%F{33}▓▒░ %F{34}Installation successful.%f" || \
        print -P "%F{160}▓▒░ The clone has failed.%f"
fi
source "$HOME/.zinit/bin/zinit.zsh"
autoload -Uz _zinit
(( ${+_comps} )) && _comps[zinit]=_zinit
### End of Zinit installer's chunk

# Setting history length
export HISTSIZE=999999
export SAVEHIST=$HISTSIZE;
# Make some commands not show up in history
export HISTORY_IGNORE='(ls|ll|cd|cd ..|pwd|exit|date|history)'

# Append history list to the history file; this is the default but we make sure
# because it's required for share_history.
setopt append_history

# Save each command's beginning timestamp and the duration to the history file
setopt extended_history

# Import new commands from the history file also in other zsh-session
setopt share_history

# Expire duplicate entries first when trimming history.
setopt HIST_EXPIRE_DUPS_FIRST

# If a new command line being added to the history list duplicates an older
# one, the older command is removed from the list
setopt hist_ignore_all_dups

# Remove command lines from the history list when the first character on the
# line is a space
setopt hist_ignore_space

# Whenever a command completion is attempted, make sure the entire command path
# is hashed first.
setopt hash_list_all

# Don't execute immediately upon history expansion.
setopt hist_verify

# Remove superfluous blanks before recording entry.
setopt hist_reduce_blanks

# not just at the end
setopt completeinword

# In order to use #, ~ and ^ for filename generation grep word
# *~(*.gz|*.bz|*.bz2|*.zip|*.Z) -> searches for word not in compressed files
# don't forget to quote '^', '~' and '#'!
setopt extended_glob

# Lets files beginning with a . be matched without explicitly specifying the dot.
setopt globdots

# Turns on spelling correction for all arguments.
setopt correctall

# If a command is issued that can't be executed as a normal command, and the
# command is the name of a directory, perform the cd command to that directory.
setopt autocd

# Turns on interactive comments; comments begin with a #.
setopt interactivecomments

# Avoid beeps and visual bells.
setopt nobeep

# Display PID when suspending processes as well
setopt longlistjobs

# report the status of backgrounds jobs immediately
setopt notify

# use zsh style word splitting
setopt noshwordsplit


### Install Zsh plugins ###

zinit light zsh-users/zsh-completions

zinit light zsh-users/zsh-autosuggestions

zinit light zdharma/fast-syntax-highlighting

zinit light zdharma/zsh-diff-so-fancy
