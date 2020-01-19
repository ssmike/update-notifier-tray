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
    def __init__(self, icons, parent, distro, checker):
        self._updates_available, self._error = icons

        super(_UpdateNotifierTrayIcon, self).__init__(
            self._updates_available, parent)
        self._thread = checker

        menu = QtWidgets.QMenu(parent)
        update_action = QtWidgets.QAction(
            distro.describe_update_gui_action(),
            self,
            triggered=distro.start_update_gui,
        )
        rescan_action = QtWidgets.QAction(
            'Rescan', self, triggered=self._thread.trigger_rescan)
        exit_action = QtWidgets.QAction(
            '&Exit', self, triggered=self.handle_exit)
        menu.addActions((update_action, rescan_action, exit_action))
        self.setContextMenu(menu)

        self.activated.connect(self.handle_activated)
        self._distro = distro

        checker.count_changed.connect(self.handle_count_changed)
        checker.error.connect(self.handle_error)

    def handle_activated(self, reason):
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick, QtWidgets.QSystemTrayIcon.MiddleClick):
            self._distro.start_update_gui()

    @QtCore.pyqtSlot()
    def handle_error(self):
        self.setToolTip("can't check for updates")
        self.setIcon(self._error)
        self.show()

    @QtCore.pyqtSlot(int)
    def handle_count_changed(self, count):
        self.setIcon(self._updates_available)

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


class _UpdateCheckThread(Thread, QtCore.QObject):
    count_changed = QtCore.pyqtSignal(int)
    error = QtCore.pyqtSignal()

    def __init__(self, distro):
        Thread.__init__(self)
        QtCore.QObject.__init__(self)
        self._exit_wanted = False
        self._event = Event()
        self._distro = distro

    def stop(self):
        self._exit_wanted = True
        self._event.set()

    def trigger_rescan(self):
        self._event.set()

    def run(self):
        while not self._exit_wanted:
            try:
                self._event.clear()
                count = self._distro.get_updateable_package_count()
                print('%d updates' % (count,))
                self.count_changed.emit(count)
            except:
                self.error.emit()
            self._event.wait(self._distro.get_check_interval_seconds())


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
    icons = [QtGui.QIcon.fromTheme(x) for x in (
        'system-software-update', 'emblem-error')]
    check_thread = _UpdateCheckThread(distro)
    tray_icon = _UpdateNotifierTrayIcon(
        icons, dummy, distro, check_thread)

    check_thread.start()
    sys.exit(app.exec())
