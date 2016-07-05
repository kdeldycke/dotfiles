#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <bitbar.title>PackageManager</bitbar.title>
# <bitbar.version>v1.0.0</bitbar.version>
# <bitbar.author>Kevin Deldycke</bitbar.author>
# <bitbar.author.github>kdeldycke</bitbar.author.github>
# <bitbar.desc>List available updates and allows individual or full upgrades.
# </bitbar.desc>
# <bitbar.dependencies>python,homebrew</bitbar.dependencies>
# <bitbar.image></bitbar.image>

from __future__ import print_function, unicode_literals

from subprocess import Popen, PIPE
import sys
import json


BREW_CLI = '/usr/local/bin/brew'


def repo_sync():
    """ Sync reporitories, exits right away on error. """
    _, error = Popen(
        [BREW_CLI, 'update'],
        stdout=PIPE).communicate()

    if error:
        print("Error | color=red")
        sys.exit(error)


def list_updates():
    """ List available updates. """
    output, error = Popen(
        [BREW_CLI, 'outdated', '--json=v1'],
        stdout=PIPE).communicate()

    if error:
        return

    updates = json.loads(output)

    # Only keeps the highest installed version.
    for package in updates:
        yield {
            'name': package['name'],
            'installed_version': max(package['installed_versions']),
            'latest_version': package['current_version']}


def print_menu():
    """ Print menu structure using BitBar's plugin API.

    See: https://github.com/matryer/bitbar#plugin-api
    """
    # Update repositories.
    repo_sync()

    # List available updates.
    updates = list(list_updates())

    # Print menu bar icon with number of available updates.
    print(("↑{} | dropdown=false".format(len(updates))).encode('utf-8'))

    # Print the dropdown menu's content.
    print("---")

    print("{} Homebrew packages".format(len(updates)))

    if updates:
        print(
            "Upgrade all | "
            "bash={} param1=upgrade param2=--cleanup "
            "terminal=false refresh=true".format(
                BREW_CLI))

    for package in updates:
        print((
            "{name} {installed_version} → {latest_version} | "
            "bash={cli} param1=upgrade param2=--cleanup param3={name} "
            "terminal=false refresh=true".format(
                cli=BREW_CLI, **package)).encode('utf-8'))

print_menu()
