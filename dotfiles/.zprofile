###############################################################################
# Login shell environment
###############################################################################
# Sourced by every login shell, interactive or not, before .zshrc. The PATH is
# built here rather than in .zshrc because GUI hosts run their helpers through
# a non-interactive login shell: SwiftBar spawns each plugin as `$SHELL -l -c`,
# which reads this file and skips .zshrc.

# Do not let homebrew send stats to Google Analytics.
# See: https://github.com/Homebrew/brew/blob/master/share/doc/homebrew/Analytics.md#opting-out
export HOMEBREW_NO_ANALYTICS=1

# Homebrew's PATH, prefix variables and completions. First, because the
# `brew --prefix` calls below need `brew` on the PATH.
eval "$(/opt/homebrew/bin/brew shellenv)"

# Global bin directory of pnpm-installed packages.
export PNPM_HOME="${HOME}/Library/pnpm"

# File where the list of path is cached.
PATH_CACHE="${HOME}/.path-env-cache"

# Force a cache refresh if file doesn't exist or older than 7 days.
# Source: https://gist.github.com/ctechols/ca1035271ad134841284#gistcomment-3109177
() {
    setopt extendedglob local_options
    if [[ ! -e ${PATH_CACHE} || -n ${PATH_CACHE}(#qN.md+7) ]]; then
        # Ordered list of path.
        PATH_LIST=(
            /usr/local/sbin
            $(brew --prefix eza)/bin
            $(brew --prefix uutils-coreutils)/libexec/uubin
            $(brew --prefix grep)/libexec/gnubin
            $(brew --prefix uutils-findutils)/libexec/uubin
            $(brew --prefix gnu-sed)/libexec/gnubin
            $(brew --prefix gnu-tar)/libexec/gnubin
            $(brew --prefix openssh)/bin
            # Keg-only (provided_by_macos): the openssh formula does not ship
            # ssh-copy-id, so it needs its own entry to shadow /usr/bin.
            $(brew --prefix ssh-copy-id)/bin
            $(brew --prefix curl)/bin
            $(brew --prefix python)/libexec/bin
            ${HOME}/.cargo/bin
            ${HOME}/.local/bin
            ${PNPM_HOME}/bin
            /Applications/Visual\ Studio\ Code.app/Contents/Resources/app/bin
        )
        print -rl -- ${PATH_LIST} > ${PATH_CACHE}
    fi
}

# Cache exists and has been refreshed in the last 7 days: load it.
# Source: https://stackoverflow.com/a/41212803
for line in "${(@f)"$(<${PATH_CACHE})"}"
{
    # Prepend paths. Source: https://stackoverflow.com/a/9352979
    path[1,0]=${line}
}
