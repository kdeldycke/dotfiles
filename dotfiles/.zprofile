# Force use of Python 3 from Homebrew by default.
PYTHON_LOCAL_BIN="/usr/local/opt/python/libexec/bin"
GNU_COREUTILS_BIN="$(brew --prefix coreutils)/libexec/gnubin"
GNU_TAR_BIN="$(brew --prefix gnu-tar)/libexec/gnubin"
GNU_SED_BIN="$(brew --prefix gnu-sed)/libexec/gnubin"
GNU_GREP_BIN="$(brew --prefix grep)/libexec/gnubin"
GNU_FINDUTILS_BIN="$(brew --prefix findutils)/libexec/gnubin"
BSD_OPENSSH_BIN="/usr/local/opt/openssl/bin"
CURL_BIN="$(brew --prefix curl)/bin"
export
PATH="$PYTHON_LOCAL_BIN:$GNU_COREUTILS_BIN:$GNU_TAR_BIN:$GNU_SED_BIN:$GNU_GREP_BIN:$GNU_FINDUTILS_BIN:$BSD_OPENSSH_BIN:$CURL_BIN:/usr/local/bin:/usr/local/sbin:$PATH"

# Prefer US English and use UTF-8
export LANG="en_US"
export LC_ALL="en_US.UTF-8"

# Do not let homebrew send stats to Google Analytics.
# See: https://github.com/Homebrew/brew/blob/master/share/doc/homebrew/Analytics.md#opting-out
export HOMEBREW_NO_ANALYTICS=1

# Case-insensitive globbing (used in pathname expansion).
shopt -s nocaseglob

shopt -s checkwinsize

# Add a reminder of shortcuts to move efficiently in the CLI.
# Source: https://news.ycombinator.com/item?id=16242955
function echo_color() {
    local color="$1"
    printf "${color}$2\033[0m\n"
}
echo_color "\033[0;90m" "^f  Move forward"
echo_color "\033[0;90m" "^b  Move backward"
echo_color "\033[0;90m" "^p  Move up"
echo_color "\033[0;90m" "^n  Move down"
echo_color "\033[0;90m" "^a  Jump to beginning of line"
echo_color "\033[0;90m" "^e  Jump to end of line"
echo_color "\033[0;90m" "^d  Delete forward"
echo_color "\033[0;90m" "^h  Delete backward"
echo_color "\033[0;90m" "^k  Delete forward to end of line"
echo_color "\033[0;90m" "^u  Delete entire line"

# Set user & root prompt
GIT_PROMPT_THEME="Solarized"
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
    lsflags="--color"
else # macOS `ls`
    lsflags="-G"
fi
alias ll='ls --human-readable --almost-all -l ${lsflags}'
alias ls='ls --human-readable --almost-all --indicator-style=slash ${lsflags}'

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

# Don't let Python produce .pyc or .pyo. Left-overs can produce strange side-effects.
export PYTHONDONTWRITEBYTECODE=true

# Python shell auto-completion and history.
export PYTHONSTARTUP="$HOME/.python_startup.py"

# Display DeprecationWarning
#export PYTHONWARNINGS=d

# Set virtualenv home.
export WORKON_HOME=$HOME/.virtualenvs

# Add pip completion.
eval "$(pip completion --zsh)"

# Add pipenv-pipes completion.
# Source: https://pipenv-pipes.readthedocs.io/en/latest/completions.html#bash-zsh
autoload bashcompinit && bashcompinit
_pipenv-pipes_completions() {
    COMPREPLY=($(compgen -W "$(pipes --_completion)" -- "${COMP_WORDS[1]}"))
}
complete -F _pipenv-pipes_completions pipes

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
