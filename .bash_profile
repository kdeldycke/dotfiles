# Force Homebrew binaries to take precedence on OSX default
# XXX Should we use GNU utilities on OSX ? See:
# https://github.com/mxcl/homebrew/blob/master/Library/Formula/coreutils.rb#L41
# https://github.com/mathiasbynens/dotfiles/issues/182#issuecomment-26945081
export PATH="/usr/local/bin:/usr/local/sbin:$PATH:~/.cabal/bin"

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
    [ -f "$(brew --prefix)/etc/bash_completion" ] && source "$(brew --prefix)/etc/bash_completion"
fi

# Setting history length
export HISTCONTROL="erasedups"
export HISTTIMEFORMAT="[%F %T] "
export HISTSIZE=99999
export HISTFILESIZE=$HISTSIZE;
# Make some commands not show up in history
export HISTIGNORE="ls:cd:cd -:pwd:exit:date:* --help:history"

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

bash_prompt_command() {
    ## After each command, save and reload history
    # Source: http://unix.stackexchange.com/a/18443
    history -n
    history -w
    history -c
    history -r
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
    export PROMPT_GIT=$(__git_ps1 "(%s@$(git_sha))")
}

bash_prompt() {
    PS1="\[\033[01;30m\]\u\[\e[m\] \[\e[1;34m\]\${NEW_PWD}\[\e[m\]\${PROMPT_GIT} \$(if [[ \$? == 0
    ]]; then echo \"\[\033[01;32m\]\342\234\224\"; else echo \"\[\033[01;31m\]\342\234\230\"; fi)\[\e[m\] "
}

# Set user & root prompt
export PROMPT_COMMAND=bash_prompt_command
export SUDO_PS1='\[\e[31m\]\u\[\e[37m\]:\[\e[33m\]\w\[\e[31m\]\$\[\033[00m\] '
bash_prompt
unset bash_prompt

# Make vim the default editor
export EDITOR="vim"

# Set default ls color schemes (source: https://github.com/seebi/dircolors-solarized/issues/10 ).
# OSX/Linux color translations generated with http://geoff.greer.fm/lscolors/
if $IS_OSX; then
    export CLICOLOR=1
    export LSCOLORS="gxfxbEaEBxxEhEhBaDaCaD"
else
    export LS_COLORS="di=36;40:ln=35;40:so=31;:pi=0;:ex=1;;40:bd=0;:cd=37;:su=37;:sg=0;:tw=0;:ow=0;:"
fi

# Activate global dir colors if found.
if $IS_OSX; then
    alias dircolors='gdircolors'
fi
if [ -f ~/.dircolors ]
then
    eval "$(dircolors -b ~/.dircolors)"
else
    eval "$(dircolors -b)"
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
GRC=$(which grc)
if [ -n GRC ]; then
    alias colourify='$GRC -es --colour=auto'
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
alias ll='ls -lah ${lsflags}'
alias ls='ls -hFp ${lsflags}'

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

# Don't let Python produce .pyc or .pyo. Left-overs can produce strange side-effects.
export PYTHONDONTWRITEBYTECODE=true

# Python shell auto-completion and history
export PYTHONSTARTUP="$HOME/python-shell-enhancement/pythonstartup.py"
export PYTHON_HISTORY_FILE="$HOME/.python_history"

# Display DeprecationWarning
export PYTHONWARNINGS=d

# Set virtualenv facilities
export WORKON_HOME=$HOME/virtualenvs
# virtualenv should use Distribute instead of legacy setuptools
export VIRTUALENV_DISTRIBUTE=true
export VIRTUALENVWRAPPER_HOOK_DIR=$HOME/.virtualenv
# Use default Python. VIRTUALENVWRAPPER_PYTHON doesn't seems to be used by virtualenvwrapper, so
# force it through venv's args.
# export VIRTUALENVWRAPPER_PYTHON=`which python`
export VIRTUALENVWRAPPER_VIRTUALENV_ARGS="--no-site-packages --python=$(which python)"
# Centralized location for new virtual environments
export PIP_VIRTUALENV_BASE=$WORKON_HOME
# Define a function for automatic virtualenv loading
# Source: https://github.com/kennethreitz/autoenv/wiki/Cookbook
use_env() {
  typeset venv
  venv="$1"
  if [[ "${VIRTUAL_ENV:t}" != "$venv" ]]; then
    if workon | grep -q "$venv"; then
      workon "$venv"
    else
      echo -n "Create virtualenv $venv now? (Yn) "
      read answer
      if [[ "$answer" == "Y" ]]; then
        mkvirtualenv "$venv"
      fi
    fi
  fi
}
# Load shell helpers
source /usr/local/bin/virtualenvwrapper.sh
source /usr/local/bin/activate.sh

eval "$(pip completion --bash)"

# Add tab completion for SSH hostnames based on ~/.ssh/config, ignoring wildcards
[ -e "$HOME/.ssh/config" ] && complete -o "default" -o "nospace" -W "$(grep "^Host" ~/.ssh/config | grep -v "[?*]" | cut -d " " -f2- | tr ' ' '\n')" scp sftp ssh

# Extract most know archives with one command
extract () {
    if [ -f "$1" ]; then
        case $1 in
            *.tar.bz2)  tar xjf "$1"    ;;
            *.tar.gz)   tar xzf "$1"    ;;
            *.bz2)      bunzip2 "$1"    ;;
            *.rar)      unrar e "$1"    ;;
            *.gz)       gunzip "$1"     ;;
            *.tar)      tar xf "$1"     ;;
            *.tbz2)     tar xjf "$1"    ;;
            *.tgz)      tar xzf "$1"    ;;
            *.xz)       tar xJf "$1"    ;;
            *.zip)      unzip "$1"      ;;
            *.Z)        uncompress "$1" ;;
            *.7z)       7z x "$1"       ;;
            *)          echo "'$1' cannot be extracted via extract()";;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}


# Cabal utils. Source: https://gist.github.com/timmytofu/7417408

# Unregister broken GHC packages. Run this a few times to resolve dependency rot in installed
# packages. ghc-pkg-clean -f cabal/dev/packages*.conf also works.
function ghc-pkg-clean() {
    for p in `ghc-pkg check $* 2>&1  | grep problems | awk '{print $6}' | sed -e 's/:$//'`
    do
        echo unregistering $p; ghc-pkg $* unregister $p
    done
}

# Remove all installed GHC/cabal packages, leaving ~/.cabal binaries and docs in place.
# When all else fails, use this to get out of dependency hell and start over.
function ghc-pkg-reset() {
    if [[ $(readlink -f /proc/$$/exe) =~ zsh ]]; then
        read 'ans?Erasing all your user ghc and cabal packages - are you sure (y/N)? '
    else # assume bash/bash compatible otherwise
        read -p 'Erasing all your user ghc and cabal packages - are you sure (y/N)? ' ans
    fi
    [[ x$ans =~ "xy" ]] && ( \
        echo 'erasing directories under ~/.ghc'; command rm -rf `find ~/.ghc/* -maxdepth 1
    -type d`; \
        echo 'erasing ~/.cabal/lib'; command rm -rf ~/.cabal/lib; \
    )
}

alias cabalupgrades="cabal list --installed  | egrep -iv '(synopsis|homepage|license)'"


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

    # Lock the screen
    alias lock='/System/Library/CoreServices/Menu\ Extras/User.menu/Contents/Resources/CGSession -suspend'

fi
