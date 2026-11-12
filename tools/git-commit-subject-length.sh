#!/bin/sh
# commit-msg hook: refuse a subject of 72 characters or more, the limit the
# agent instructions set for every commit. Plain POSIX sh with builtins only,
# because GUI clients like Fork run git without Homebrew on PATH.
#
# Subjects that git writes itself (merges, reverts, fixup!, squash!, amend!)
# pass unchecked. Bypass the hook once with `git commit --no-verify`, or in one
# repository with `git config hook.subject-length.enabled false`.

limit=72
# Count characters, not bytes, whatever locale the client runs git in.
LC_ALL=en_US.UTF-8
export LC_ALL

subject=
while IFS= read -r line || [ -n "$line" ]; do
    case $line in
        '' | '#'*) continue ;;
    esac
    subject=$line
    break
done <"$1"

case $subject in
    'Merge '* | 'Revert "'* | 'fixup! '* | 'squash! '* | 'amend! '*) exit 0 ;;
esac

length=${#subject}
if [ "$length" -ge "$limit" ]; then
    printf 'commit-msg: the subject has %s characters, the limit is %s:\n  %s\n' \
        "$length" "$((limit - 1))" "$subject" >&2
    exit 1
fi
