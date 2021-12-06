import shutil
import subprocess
import signal


def wrap_sudo(cmd):
    return '(set -x; sudo %s) ; cd ~; bash -i' % ' '.join(cmd)


def run_in_term(command):
    for cmd in ['konsole', 'xterm']:
        if shutil.which(cmd):
            subprocess.Popen([
                cmd, '-e', 'bash', '-c', wrap_sudo(command),
            ])
            break
    # So the kernel takes care of the zombie
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
