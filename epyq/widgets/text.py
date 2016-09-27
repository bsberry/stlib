#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import epyq.widgets.abstractwidget
import os
from PyQt5.QtCore import (pyqtSignal, pyqtProperty,
                          QFile, QFileInfo, QTextStream)

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class Text(epyq.widgets.abstractwidget.AbstractWidget):
    def __init__(self, parent=None, in_designer=False):
        ui_file = os.path.join(QFileInfo.absolutePath(QFileInfo(__file__)),
                               'text.ui')

        epyq.widgets.abstractwidget.AbstractWidget.__init__(self,
                ui=ui_file, parent=parent, in_designer=in_designer)

        self._frame = None
        self._signal = None

    def set_value(self, value):
        # TODO: quit hardcoding this and it's better implemented elsewhere
        if value is not None:
            value *= self._conversion_multiplier

        if value is None:
            value = '-'
        else:
            if self.signal_object is None:
                value = '{0:.2f}'.format(value)
            elif len(self.signal_object.enumeration) > 0:
                value = self.signal_object.short_string
            else:
                decimal_places = (None
                                  if self.decimal_places < 0
                                  else self.decimal_places)
                value = self.signal_object.format_float(
                    value=value,
                    decimal_places=decimal_places)

        self.ui.value.setText(value)

    def update_layout(self):
        pass


if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
