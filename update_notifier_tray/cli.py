# Copyright (C) 2014 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GPL v3 or later

from __future__ import print_function
import sys
from PySide import QtGui, QtCore
import apt
import subprocess
import signal
from threading import Event, Thread
import time

def _get_updateable_package_count():
	count = 0
	cache = apt.Cache()
	for package_name in cache.keys():
		if cache[package_name].is_upgradable:
			count += 1
	return count


def _start_update_gui():
	subprocess.Popen(['gpk-update-viewer'])


class _UpdateNotifierTrayIcon(QtGui.QSystemTrayIcon):
	def __init__(self, icon=None, parent=None):
		super(_UpdateNotifierTrayIcon, self).__init__(icon, parent)

		menu = QtGui.QMenu(parent)
		update_action = QtGui.QAction('Run gpk-&update-viewer', self, triggered=_start_update_gui)
		menu.addAction(update_action)
		exit_action = QtGui.QAction('&Exit', self, triggered=self.handle_exit)
		menu.addAction(exit_action)
		self.setContextMenu(menu)

		self.activated.connect(self.handle_activated)

	def handle_activated(self, reason):
		if reason in (QtGui.QSystemTrayIcon.Trigger, QtGui.QSystemTrayIcon.DoubleClick, QtGui.QSystemTrayIcon.MiddleClick):
			_start_update_gui()

	@QtCore.Slot(int)
	def handle_count_changed(self, count):
		if count > 0:
			if count == 1:
				message = 'There is 1 update available'
			else:
				message = 'There are %d updates available' % count

			self.setToolTip(message)
			self.show()
		else:
			self.hide()

	def handle_exit(self):
		self._thread.stop()
		self._thread.join()
		QtGui.qApp.quit()

	def set_thread(self, check_thread):
		self._thread = check_thread


class _UpdateCheckThread(Thread, QtCore.QObject):
	_count_changed = QtCore.Signal(int)

	def __init__(self):
		Thread.__init__(self)
		QtCore.QObject.__init__(self)
		self._exit_wanted = Event()

	def set_tray_icon(self, tray_icon):
		self._count_changed.connect(tray_icon.handle_count_changed)

	def stop(self):
		self._exit_wanted.set()

	def run(self):
		while not self._exit_wanted.isSet():
			count = _get_updateable_package_count()
			self._count_changed.emit(count)
			time.sleep(1)


def main():
	signal.signal(signal.SIGINT, signal.SIG_DFL)  # To make killable using Ctrl+C

	app = QtGui.QApplication(sys.argv)
	dummy_widget = QtGui.QWidget()
	icon = QtGui.QIcon('/usr/share/icons/Tango/scalable/status/software-update-available.svg')
	tray_icon = _UpdateNotifierTrayIcon(icon, dummy_widget)
	check_thread = _UpdateCheckThread()

	check_thread.set_tray_icon(tray_icon)
	tray_icon.set_thread(check_thread)

	check_thread.start()
	sys.exit(app.exec_())