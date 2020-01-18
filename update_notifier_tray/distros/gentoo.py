# Copyright (C) 2015 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GPL v3 or later

import signal
import subprocess
import shutil

from update_notifier_tray.distro import Distro


_CHECK_FOR_UPDATES_COMMAND = (
    'emerge',
    '--ignore-default-opts',
    '--pretend',
    '--verbose', '--color', 'n',
    '--complete-graph', '--deep', '--update',
    '@world',
)

_UPDATE_COMMAND = (
    'emerge',
    '--ask',
    '--verbose', '--tree', '--quiet',
    '--complete-graph', '--deep', '--update',
    '--keep-going',
    '@world',
)


def subprocess_nocheck_output(argv, **kvargs):
    kvargs['stdout'] = subprocess.PIPE
    p = subprocess.Popen(argv, **kvargs)
    p.wait()
    return p.stdout.read().decode('utf8')


class Gentoo(Distro):
    def describe_update_gui_action(self):
        return 'Run "emerge --ask --&update ..."'

    @staticmethod
    def detected(lsb_release_minus_a_output):
        return 'Gentoo' in lsb_release_minus_a_output

    @staticmethod
    def get_command_line_name():
        return 'gentoo'

    def get_updateable_package_count(self):
        with open('/dev/null', 'w') as dev_null:
            output = subprocess_nocheck_output(
                _CHECK_FOR_UPDATES_COMMAND, stderr=dev_null)
            return len([0
                        for line in output.split('\n')
                        if line.startswith('[ebuild')
                        ])

    def get_check_interval_seconds(self):
        return 60 * 60 * 12

    def _get_update_command(self):
        return '(set -x; sudo %s) ; cd ~; bash -i' % ' '.join(_UPDATE_COMMAND)

    def start_update_gui(self):
        for cmd in ['konsole', 'xterm']:
            if shutil.which(cmd):
                subprocess.Popen([
                    cmd, '-e', 'bash', '-c', self._get_update_command(),
                ])
                break
        # So the kernel takes care of the zombie
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
