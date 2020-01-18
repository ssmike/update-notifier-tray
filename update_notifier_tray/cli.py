# Copyright (C) 2014 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GPL v3 or later

import argparse
import signal
import subprocess
import sys
from threading import Event, Lock, Thread
import time

from PyQt5 import QtWidgets, QtCore, QtGui

from update_notifier_tray.notify import notify
from update_notifier_tray.distros.debian import Debian
from update_notifier_tray.distros.gentoo import Gentoo
from update_notifier_tray.distros.ubuntu import Ubuntu


_DISTRO_CLASSES = (
    Debian,
    Gentoo,
    Ubuntu,
)


class _UpdateNotifierTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon, parent, distro):
        super(_UpdateNotifierTrayIcon, self).__init__(icon, parent)

        menu = QtWidgets.QMenu(parent)
        update_action = QtWidgets.QAction(
            distro.describe_update_gui_action(),
            self,
            triggered=distro.start_update_gui,
        )
        menu.addAction(update_action)
        exit_action = QtWidgets.QAction('&Exit', self, triggered=self.handle_exit)
        menu.addAction(exit_action)
        self.setContextMenu(menu)

        self.activated.connect(self.handle_activated)
        self._previous_count = 0
        self._previous_count_lock = Lock()
        self._distro = distro

    def handle_activated(self, reason):
        print('activated', 'reason=', reason)
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick, QtGui.QSystemTrayIcon.MiddleClick):
            self._distro.start_update_gui()

    @QtCore.pyqtSlot(int)
    def handle_count_changed(self, count):
        self._previous_count_lock.acquire()

        unchanged = (count == self._previous_count)
        self._previous_count = count

        self._previous_count_lock.release()

        if unchanged:
            return

        if count > 0:
            title = 'Updates available'

            if count == 1:
                message = 'There is 1 update available'
            else:
                message = 'There are %d updates available' % count

            self.setToolTip(message)
            self.show()

            notify(title, message)
        else:
            self.hide()

    def handle_exit(self):
        self._thread.stop()
        self._thread.join()
        QtGui.qApp.quit()

    def set_thread(self, check_thread):
        self._thread = check_thread


class _UpdateCheckThread(Thread, QtCore.QObject):
    _count_changed = QtCore.pyqtSignal(int)

    def __init__(self, distro):
        Thread.__init__(self)
        QtCore.QObject.__init__(self)
        self._exit_wanted = Event()
        self._distro = distro

    def set_tray_icon(self, tray_icon):
        self._count_changed.connect(tray_icon.handle_count_changed)

    def stop(self):
        self._exit_wanted.set()

    def run(self):
        while not self._exit_wanted.isSet():
            count = self._distro.get_updateable_package_count()
            self._count_changed.emit(count)
            for i in range(self._distro.get_check_interval_seconds()):
                if self._exit_wanted.isSet():
                    break
                time.sleep(1)


def main():
    # To make killable using Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    parser = argparse.ArgumentParser()
    distros = parser.add_mutually_exclusive_group()
    for clazz in _DISTRO_CLASSES:
        name = clazz.get_command_line_name()
        distros.add_argument('--%s' % name, dest='distro_callable', action='store_const',
                             const=clazz, help='force %s mode (default: distribution auto-detected)'
                             % name.title())
    options = parser.parse_args()

    if options.distro_callable is None:
        with open('/dev/null', 'w') as dev_null:
            lsb_release_minus_a_output = str(subprocess.check_output([
                'lsb_release', '-a'], stderr=dev_null))
        for clazz in _DISTRO_CLASSES:
            if clazz.detected(lsb_release_minus_a_output):
                options.distro_callable = clazz
                print('INFO: %s detected for a distribution.'
                      % clazz.get_command_line_name().title())
                break
        else:
            print('No supported distribution was detected, please check --help output.',
                  file=sys.stderr)
            sys.exit(1)
    distro = options.distro_callable()

    app = QtWidgets.QApplication(sys.argv)
    dummy = QtWidgets.QWidget()
    icon = QtGui.QIcon.fromTheme('system-software-update')
    tray_icon = _UpdateNotifierTrayIcon(icon, dummy, distro)
    check_thread = _UpdateCheckThread(distro)

    check_thread.set_tray_icon(tray_icon)
    tray_icon.set_thread(check_thread)

    check_thread.start()
    sys.exit(app.exec())
