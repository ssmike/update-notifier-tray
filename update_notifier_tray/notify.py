import sys
import gi

gi.require_version("Notify", "0.7")
from gi.repository import Notify  # noqa

__all__ = ['notify']

Notify.init('update notifier')


def notify(title, message):
    Notify.Notification.new(title, message).show()

