# Force use of Python 3 from Homebrew by default.
PYTHON_LOCAL_BIN="/usr/local/opt/python/libexec/bin"
GNU_COREUTILS_BIN="$(brew --prefix coreutils)/libexec/gnubin"
GNU_TAR_BIN="$(brew --prefix gnu-tar)/libexec/gnubin"
GNU_SED_BIN="$(brew --prefix gnu-sed)/libexec/gnubin"
GNU_GREP_BIN="$(brew --prefix grep)/libexec/gnubin"
GNU_FINDUTILS_BIN="$(brew --prefix findutils)/libexec/gnubin"
BSD_OPENSSH_BIN="/usr/local/opt/openssl/bin"
export PATH="$PYTHON_LOCAL_BIN:$GNU_COREUTILS_BIN:$GNU_TAR_BIN:$GNU_SED_BIN:$GNU_GREP_BIN:$GNU_FINDUTILS_BIN:$BSD_OPENSSH_BIN:/usr/local/bin:/usr/local/sbin:$PATH"

# Prefer US English and use UTF-8
export LANG="en_US"
export LC_ALL="en_US.UTF-8"

# Do not let homebrew send stats to Google Analytics.
# See: https://github.com/Homebrew/brew/blob/master/share/doc/homebrew/Analytics.md#opting-out
export HOMEBREW_NO_ANALYTICS=1

# If possible, add tab completion for many more commands
[ -f /etc/bash_completion ] && source /etc/bash_completion
[ -f "$(brew --prefix)/etc/bash_completion" ] && source "$(brew --prefix)/etc/bash_completion"

# Setting history length
export HISTCONTROL="ignoredups:erasedups"
export HISTTIMEFORMAT="[%F %T] "
export HISTSIZE=999999
export HISTFILESIZE=$HISTSIZE;
# Make some commands not show up in history
export HISTIGNORE="ls:ll:cd:cd -:pwd:exit:date:history"

# Append to the history file, don't overwrite it.
shopt -s histappend
# Allow us to re-edit a failed history substitution.
shopt -s histreedit
# History expansions will be verified before execution.
shopt -s histverify

# Case-insensitive globbing (used in pathname expansion).
shopt -s nocaseglob

# Autocorrect typos in path names when using `cd`.
shopt -s cdspell

# Check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# Enable some Bash 4 features when possible:
# * `autocd`, e.g. `**/qux` will enter `./foo/bar/baz/qux`
# * Recursive globbing, e.g. `echo **/*.txt`
for option in autocd globstar; do
    shopt -s "$option" 2> /dev/null;
done;

# After each command, append to the history file and reread it.
# Source: https://unix.stackexchange.com/a/1292
export PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND$'\n'}history -a; history -c; history -r"

# Set user & root prompt
GIT_PROMPT_THEME="Solarized"
source ~/.bash-git-prompt/gitprompt.sh
export SUDO_PS1='\[\e[31m\]\u\[\e[37m\]:\[\e[33m\]\w\[\e[31m\]\$\[\033[00m\] '

# Make Neovim the default editor
export EDITOR="nvim"

# Set default ls color schemes (source: https://github.com/seebi/dircolors-solarized/issues/10 ).
# macOS/Linux color translations generated with http://geoff.greer.fm/lscolors/
export CLICOLOR=1
export LSCOLORS="gxfxbEaEBxxEhEhBaDaCaD"

# Activate global dir colors if found.
alias dircolors='gdircolors'
if [ -f $HOME/.dircolors ]
then
    eval "$(dircolors -b $HOME/.dircolors)"
else
    eval "$(dircolors -b)"
fi

# Force colored output and good defaults
alias du='du -csh'
alias df='df -h'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias diff="colordiff -ru"
alias dmesg="dmesg --color"
alias tree='tree -Csh'
alias ccat='pygmentize -g'

alias top="htop"
alias gr='grep -RIi --no-messages'
alias vim='nvim'
alias vi='nvim'
alias v="nvim"
alias g="git"
alias h="history"
alias q='exit'
alias how="howdoi --color"

function cls {
    # Source: https://stackoverflow.com/a/2198403
    osascript -e 'tell application "System Events" to keystroke "k" using command down'
}
alias c='cls'

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
if ls --color > /dev/null 2>&1; then # GNU `ls`
    lsflags="--color --group-directories-first"
else # macOS `ls`
    lsflags="-G"
fi
alias ll='ls -lah ${lsflags}'
alias ls='ls -hFp ${lsflags}'

# Handy aliases for going up in a directory
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias .....="cd ../../../.."

export LESS="-eRX"
export LESSOPEN='| pygmentize -g %s'
# Tip from http://sourceforge.net/apps/trac/qlc/wiki/InstallationSubversionLinux#Optionalhelpers
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

# Remove spurious find error messages on access restrictions. Keeps find's
# output clean, tidy and easier to read.
# Source: https://apple.stackexchange.com/a/353650
find() {
  { LC_ALL=C command find "$@" 3>&2 2>&1 1>&3 | \
    grep -v -e 'Permission denied' -e 'Operation not permitted' >&3; \
    [ $? = 1 ]; \
  } 3>&2 2>&1
}

# Expose diff-so-fancy.
export PATH="$PATH:$HOME/.diff-so-fancy"

# Don't let Python produce .pyc or .pyo. Left-overs can produce strange side-effects.
export PYTHONDONTWRITEBYTECODE=true

# Python shell auto-completion and history.
export PYTHONSTARTUP="$HOME/.python_startup.py"

# Display DeprecationWarning
#export PYTHONWARNINGS=d

# Set virtualenv home.
export WORKON_HOME=$HOME/.virtualenvs

# Add pip completion.
eval "$(pip completion --bash)"

# Add pipenv-pipes completion.
# Source: https://pipenv-pipes.readthedocs.io/en/latest/completions.html#bash-zsh
_pipenv-pipes_completions() {
    COMPREPLY=($(compgen -W "$(pipes --_completion)" -- "${COMP_WORDS[1]}"))
}
complete -F _pipenv-pipes_completions pipes

# Add tab completion for SSH hostnames based on ~/.ssh/config, ignoring wildcards
[ -e "$HOME/.ssh/config" ] && complete -o "default" -o "nospace" -W "$(grep "^Host" ~/.ssh/config | grep -v "[?*]" | cut -d " " -f2- | tr ' ' '\n')" scp sftp ssh

# Extract most know archives with one command
extract () {
    if [ -f "$1" ]; then
        case "$1" in
            *.dmg)   hdiutil mount "$1"                ;;
            *.tar)   tar -xvf "$1"                     ;;
            *.zip)   unzip "$1"                        ;;
            *.ZIP)   unzip "$1"                        ;;
            *.pax)   pax -r < "$1"                     ;;
            *.pax.Z) uncompress "$1" --stdout | pax -r ;;
            *.rar)   unrar x "$1"                      ;;
            *.7z)    7z x "$1"                         ;;
            *.xar)   xar -xvf "$1"                     ;;
            *.pkg)   xar -xvf "$1"                     ;;
            # Rely on GNU's tar autodetection. List of recognized suffixes:
            # https://www.gnu.org/software/tar/manual/html_node/gzip.html#auto_002dcompress
            *)       tar -axvf "$1"                    ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}

# Opens current directory in apps
alias f='open -a Finder ./'

# Replace netstat command on macOS to find ports used by apps
alias netstat="sudo lsof -i -P"

# Add tab completion for `defaults read|write NSGlobalDomain`
# You could just use `-g` instead, but I like being explicit
complete -W "NSGlobalDomain" defaults

# Lock the screen
alias lock='/System/Library/CoreServices/Menu\ Extras/User.menu/Contents/Resources/CGSession -suspend'

# Link pinentry and GPG agent together
if test -f $HOME/.gnupg/.gpg-agent-info -a -n "$(pgrep gpg-agent)"; then
    source $HOME/.gnupg/.gpg-agent-info
    export GPG_AGENT_INFO
else
    eval $(gpg-agent --daemon --write-env-file $HOME/.gnupg/.gpg-agent-info)
fi
