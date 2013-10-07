# Force Homebrew binaries to take precedence on OSX default
export PATH="/usr/local/bin:/usr/local/sbin:$PATH"

# Prefer US English and use UTF-8
export LANG="en_US"
export LC_ALL="en_US.UTF-8"

# Detect distribution
if [ "$(uname -s)" == "Darwin" ]; then
    IS_OSX=true
else
    IS_OSX=false
fi

# If possible, add tab completion for many more commands
[ -f /etc/bash_completion ] && source /etc/bash_completion
if $IS_OSX; then
    [ -f $(brew --prefix)/etc/bash_completion ] && source $(brew --prefix)/etc/bash_completion
fi

bash_prompt_command() {
    ## Fancy PWD display function, better than PROMPT_DIRTRIM
    # Source: https://wiki.archlinux.org/index.php/Color_Bash_Prompt
    # How many characters of the $PWD should be kept
    local pwdmaxlen=25
    # Indicate that there has been dir truncation
    local trunc_symbol="…"
    local dir=${PWD##*/}
    pwdmaxlen=$(( ( pwdmaxlen < ${#dir} ) ? ${#dir} : pwdmaxlen ))
    NEW_PWD=${PWD/#$HOME/\~}
    local pwdoffset=$(( ${#NEW_PWD} - pwdmaxlen ))
    if [ ${pwdoffset} -gt "0" ]; then
        NEW_PWD=${NEW_PWD:$pwdoffset:$pwdmaxlen}
        NEW_PWD=${trunc_symbol}/${NEW_PWD#*/}
    fi
    ## Set git contextual info
    git_sha() {
        git rev-parse --short HEAD 2>/dev/null
    }
    PROMPT_GIT=$(__git_ps1 "(%s@$(git_sha))")
}

bash_prompt() {
    PS1="\[\033[01;30m\]\u\[\e[m\] \[\e[1;34m\]\${NEW_PWD}\[\e[m\]\${PROMPT_GIT} \$(if [[ \$? == 0
    ]]; then echo \"\[\033[01;32m\]\342\234\224\"; else echo \"\[\033[01;31m\]\342\234\230\"; fi) \[\033[01;32m\]\$\[\e[m\] "
}

# Set user & root prompt
export PROMPT_COMMAND=bash_prompt_command
export SUDO_PS1='\[\e[31m\]\u\[\e[37m\]:\[\e[33m\]\w\[\e[31m\]\$\[\033[00m\] '
bash_prompt
unset bash_prompt

# Make vim the default editor
export EDITOR="vim"

# Setting history length
export HISTCONTROL="ignorespace:erasedups"
export HISTTIMEFORMAT="[%F %T] "
export HISTSIZE=99999
# Make some commands not show up in history
export HISTIGNORE="ls:cd:cd -:pwd:exit:date:* --help"

# append to the history file, don't overwrite it
shopt -s histappend
# Allow use to re-edit a faild history substitution.
shopt -s histreedit
# History expansions will be verified before execution.
shopt -s histverify

# Case-insensitive globbing (used in pathname expansion)
shopt -s nocaseglob

# Autocorrect typos in path names when using `cd`
shopt -s cdspell

# Check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# Activate global dir colors
if $IS_OSX; then
    alias dircolors='gdircolors'
fi
[ -f ~/.dircolors ] && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
# OSX/Linux color translations generated with http://geoff.greer.fm/lscolors/
if $IS_OSX; then
    export CLICOLOR=1
    export LSCOLORS="GxFxCxDxBxegedabagaced"
else
    export LS_COLORS="di=1;;40:ln=1;;40:so=1;;40:pi=1;;40:ex=1;;40:bd=34;46:cd=34;43:su=0;41:sg=0;46:tw=0;42:ow=34;43:"
fi

# Force colored output and good defaults
alias du='du -csh'
alias df='df -Th'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias diff="colordiff -ru"
alias svn="colorsvn"
alias dmesg="dmesg --color"
alias tree='tree -Csh'

alias top="htop"
alias gr='grep -RIi --no-messages'
alias vi='vim'
alias v="vim"
alias g="git"
alias h="history"

alias c='clear'
alias cls='clear'

alias q='exit'

# Use GRC for additionnal colorization
GRC=`which grc`
if [ -n GRC ]; then
    alias colourify="$GRC -es --colour=auto"
    alias as='colourify as'
    #cvs
    alias configure='colourify ./configure'
    alias diff='colourify diff'
    alias dig='colourify dig'
    alias g++='colourify g++'
    alias gas='colourify gas'
    alias gcc='colourify gcc'
    alias head='colourify head'
    alias ifconfig='colourify ifconfig'
    #irclog
    alias ld='colourify ld'
    #ldap
    #log
    alias ls='colourify ls'
    alias make='colourify make'
    alias mount='colourify mount'
    #mtr
    alias netstat='colourify netstat'
    alias ping='colourify ping'
    #proftpd
    alias ps='colourify ps'
    alias tail='colourify tail'
    alias traceroute='colourify traceroute'
    #wdiff
fi

# Detect which `ls` flavor is in use
if $IS_OSX; then
    lsflags="-G"
else
    lsflags="--color --group-directories-first"
fi
alias ll="ls -lah ${lsflags}"
alias ls="ls -hFp ${lsflags}"

# Handy aliases for going up in a directory
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias .....="cd ../../../.."

# Tip from http://sourceforge.net/apps/trac/qlc/wiki/InstallationSubversionLinux#Optionalhelpers
export LESS="-erX"
export LESS_TERMCAP_mb=$(tput bold; tput setaf 2) # green
export LESS_TERMCAP_md=$(tput bold; tput setaf 6) # cyan
export LESS_TERMCAP_me=$(tput sgr0)
export LESS_TERMCAP_so=$(tput bold; tput setaf 3; tput setab 4) # yellow on blue
export LESS_TERMCAP_se=$(tput rmso; tput sgr0)
export LESS_TERMCAP_us=$(tput smul; tput bold; tput setaf 7) # white
export LESS_TERMCAP_ue=$(tput rmul; tput sgr0)
export LESS_TERMCAP_mr=$(tput rev)
export LESS_TERMCAP_mh=$(tput dim)
export LESS_TERMCAP_ZN=$(tput ssubm)
export LESS_TERMCAP_ZV=$(tput rsubm)
export LESS_TERMCAP_ZO=$(tput ssupm)
export LESS_TERMCAP_ZW=$(tput rsupm)

# Python shell auto-completion and history
export PYTHONSTARTUP="$HOME/python-shell-enhancement/pythonstartup.py"
export PYTHON_HISTORY_FILE="$HOME/.python_history"

# Set virtualenv facilities
if $IS_OSX; then
    # Force virtualenv to use homebrew's Python on OSX
    export VIRTUALENVWRAPPER_PYTHON="/usr/local/bin/python"
fi
export WORKON_HOME=$HOME/virtualenvs
export VIRTUALENVWRAPPER_HOOK_DIR=$HOME/.virtualenv
export VIRTUALENVWRAPPER_VIRTUALENV_ARGS='--no-site-packages'
export PIP_VIRTUALENV_BASE=$WORKON_HOME
source /usr/local/bin/virtualenvwrapper.sh
source /usr/local/bin/activate.sh

eval "`pip completion --bash`"

# Add tab completion for SSH hostnames based on ~/.ssh/config, ignoring wildcards
[ -e "$HOME/.ssh/config" ] && complete -o "default" -o "nospace" -W "$(grep "^Host" ~/.ssh/config | grep -v "[?*]" | cut -d " " -f2 | tr ' ' '\n')" scp sftp ssh

# Extract most know archives with one command
extract () {
    if [ -f $1 ]; then
        case $1 in
            *.tar.bz2)  tar xjf $1    ;;
            *.tar.gz)   tar xzf $1    ;;
            *.bz2)      bunzip2 $1    ;;
            *.rar)      unrar e $1    ;;
            *.gz)       gunzip $1     ;;
            *.tar)      tar xf $1     ;;
            *.tbz2)     tar xjf $1    ;;
            *.tgz)      tar xzf $1    ;;
            *.xz)       tar xJf $1    ;;
            *.zip)      unzip $1      ;;
            *.Z)        uncompress $1 ;;
            *.7z)       7z x $1       ;;
            *)          echo "'$1' cannot be extracted via extract()";;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}


# Distribution-specific commands
if $IS_OSX; then

    # Opens current directory in apps
    alias f='open -a Finder ./'
    alias gitx='open -a ~/Applications/GitX.app ./'

    # Replace netstat command on OSX to find ports used by apps
    alias netstat="sudo lsof -i -P"

    # Add tab completion for `defaults read|write NSGlobalDomain`
    # You could just use `-g` instead, but I like being explicit
    complete -W "NSGlobalDomain" defaults

fi
