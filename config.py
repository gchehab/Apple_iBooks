#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import absolute_import, division, print_function, unicode_literals

__license__   = 'GPL v3'
__copyright__ = '2019, Guilherme Chehab <guilherme.chehab@yahoo.com>'
__docformat__ = 'restructuredtext en'

from os import path
from PyQt5.Qt import QWidget, QVBoxLayout, QLabel, QLineEdit, QFileDialog, QLayout
from PyQt5 import QtCore, QtGui, QtWidgets

from calibre.utils.config import JSONConfig

# This is where all preferences for this plugin will be stored
# Remember that this name (i.e. plugins/interface_demo) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
prefs = JSONConfig('plugins/apple_ibooks')

# Set defaults
prefs.defaults['bookcatalog'] = \
    path.expanduser("~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books/books.plist")
prefs.defaults['dbbookcatalog'] = \
    path.expanduser("~/Library/Containers/com.apple.iBooksX/Data/Documents/BKLibrary/BKLibrary-1-091020131601.sqlite")
prefs.defaults['dbseriescatalog'] = \
    path.expanduser("~/Library/Containers/com.apple.iBooksX/Data/Documents/BKSeriesDatabase/BKSeries-1-012820141020.sqlite")

prefs.defaults['backup'] = False
prefs.defaults['debug'] = False
prefs.defaults['remove_last_synced'] = False

class Ui_qWidget(object):

    def setupUi(self, qWidget):

        # Hard code some preferences for now
        prefs.defaults['backup'] = False
        prefs.defaults['debug'] = False
        prefs.defaults['remove_last_synced'] = False

        qWidget.setObjectName("qWidget")
        qWidget.resize(586, 409)
        self.fr_info = QtWidgets.QFrame(qWidget)
        self.fr_info.setGeometry(QtCore.QRect(10, 20, 311, 81))
        self.fr_info.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.fr_info.setFrameShadow(QtWidgets.QFrame.Raised)
        self.fr_info.setLineWidth(0)
        self.fr_info.setObjectName("fr_info")
        self.lb_icon = QtWidgets.QLabel(self.fr_info)
        self.lb_icon.setGeometry(QtCore.QRect(10, 0, 81, 81))
        self.lb_icon.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.lb_icon.setText("")
        self.lb_icon.setPixmap(QtGui.QPixmap("images/icon.svg"))
        self.lb_icon.setScaledContents(True)
        self.lb_icon.setObjectName("lb_icon")
        self.lb_product_name = QtWidgets.QLabel(self.fr_info)
        self.lb_product_name.setGeometry(QtCore.QRect(120, 20, 161, 41))
        self.lb_product_name.setTextFormat(QtCore.Qt.RichText)
        self.lb_product_name.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lb_product_name.setObjectName("lb_product_name")
        self.lb_product_version = QtWidgets.QLabel(self.fr_info)
        self.lb_product_version.setGeometry(QtCore.QRect(120, 60, 161, 20))
        self.lb_product_version.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lb_product_version.setObjectName("lb_product_version")
        self.gb_bookagent = QtWidgets.QGroupBox(qWidget)
        self.gb_bookagent.setGeometry(QtCore.QRect(10, 110, 571, 71))
        self.gb_bookagent.setObjectName("gb_bookagent")
        self.lb_bookcatalog = QtWidgets.QLabel(self.gb_bookagent)
        self.lb_bookcatalog.setGeometry(QtCore.QRect(20, 20, 331, 16))
        self.lb_bookcatalog.setObjectName("lb_bookcataloglocation")
        self.ln_bookcatalog = QtWidgets.QLineEdit(self.gb_bookagent)
        self.ln_bookcatalog.setGeometry(QtCore.QRect(20, 40, 511, 20))
        self.ln_bookcatalog.setMaxLength(1023)
        self.ln_bookcatalog.setPlaceholderText("")
        self.ln_bookcatalog.setObjectName("ln_bookcataloglocation")
        self.tb_findbookcatalog = QtWidgets.QToolButton(self.gb_bookagent)
        self.tb_findbookcatalog.setGeometry(QtCore.QRect(540, 40, 25, 19))
        self.tb_findbookcatalog.setObjectName("tb_findbookcatalog")
        self.gb_databases = QtWidgets.QGroupBox(qWidget)
        self.gb_databases.setGeometry(QtCore.QRect(10, 190, 571, 111))
        self.gb_databases.setObjectName("gb_databases")
        self.lb_dbbookcatalog = QtWidgets.QLabel(self.gb_databases)
        self.lb_dbbookcatalog.setGeometry(QtCore.QRect(20, 20, 331, 16))
        self.lb_dbbookcatalog.setObjectName("lb_dbbookcatalog")
        self.lb_dbseriescatalog = QtWidgets.QLabel(self.gb_databases)
        self.lb_dbseriescatalog.setGeometry(QtCore.QRect(20, 60, 331, 16))
        self.lb_dbseriescatalog.setObjectName("lb_dbseriescataloglocation")
        self.ln_dbbookcatalog = QtWidgets.QLineEdit(self.gb_databases)
        self.ln_dbbookcatalog.setGeometry(QtCore.QRect(20, 40, 511, 20))
        self.ln_dbbookcatalog.setObjectName("ln_dbbookcatalog")
        self.ln_dbseriescatalog = QtWidgets.QLineEdit(self.gb_databases)
        self.ln_dbseriescatalog.setGeometry(QtCore.QRect(20, 80, 511, 20))
        self.ln_dbseriescatalog.setObjectName("ln_dbseriescataloglocation")
        self.tb_finddbbookcatalog = QtWidgets.QToolButton(self.gb_databases)
        self.tb_finddbbookcatalog.setGeometry(QtCore.QRect(540, 40, 25, 19))
        self.tb_finddbbookcatalog.setObjectName("tb_finddbbookcatalog")
        self.tb_finddbseriescatalog = QtWidgets.QToolButton(self.gb_databases)
        self.tb_finddbseriescatalog.setGeometry(QtCore.QRect(540, 80, 25, 19))
        self.tb_finddbseriescatalog.setObjectName("tb_finddbseriescatalog")
        self.fr_url = QtWidgets.QFrame(qWidget)
        self.fr_url.setGeometry(QtCore.QRect(10, 310, 571, 41))
        self.fr_url.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.fr_url.setFrameShadow(QtWidgets.QFrame.Raised)
        self.fr_url.setLineWidth(0)
        self.fr_url.setObjectName("fr_url")
        self.lb_url = QtWidgets.QLabel(self.fr_url)
        self.lb_url.setGeometry(QtCore.QRect(10, 10, 551, 16))
        self.lb_url.setTextFormat(QtCore.Qt.RichText)
        self.lb_url.setOpenExternalLinks(True)
        self.lb_url.setObjectName("lb_url")
        # self.gb_generalsettings = QtWidgets.QGroupBox(qWidget)
        # self.gb_generalsettings.setGeometry(QtCore.QRect(320, 20, 261, 81))
        # self.gb_generalsettings.setObjectName("gb_generalsettings")
        # self.ck_backup = QtWidgets.QCheckBox(self.gb_generalsettings)
        # self.ck_backup.setGeometry(QtCore.QRect(20, 20, 241, 17))
        # self.ck_backup.setChecked(prefs['backup'])
        # self.ck_backup.setObjectName("ck_backup")
        # self.ck_cleanlast = QtWidgets.QCheckBox(self.gb_generalsettings)
        # self.ck_cleanlast.setGeometry(QtCore.QRect(20, 40, 241, 17))
        # self.ck_cleanlast.setChecked(prefs['remove_last_synced'])
        # self.ck_cleanlast.setObjectName("ch_cleanlast")
        # self.ck_debug = QtWidgets.QCheckBox(self.gb_generalsettings)
        # self.ck_debug.setGeometry(QtCore.QRect(20, 60, 241, 17))
        # self.ck_debug.setChecked(prefs['debug'])
        # self.ck_debug.setObjectName("ck_debug")

        self.retranslateUi(qWidget)
        QtCore.QMetaObject.connectSlotsByName(qWidget)
        # qWidget.setTabOrder(self.ck_backup, self.ck_cleanlast)
        # qWidget.setTabOrder(self.ck_cleanlast, self.ck_debug)
        # qWidget.setTabOrder(self.ck_debug, self.ln_bookcatalog)
        qWidget.setTabOrder(self.ln_bookcatalog, self.tb_findbookcatalog)
        qWidget.setTabOrder(self.tb_findbookcatalog, self.ln_dbbookcatalog)
        qWidget.setTabOrder(self.ln_dbbookcatalog, self.tb_finddbbookcatalog)
        qWidget.setTabOrder(self.tb_finddbbookcatalog, self.ln_dbseriescatalog)
        qWidget.setTabOrder(self.ln_dbseriescatalog, self.tb_finddbseriescatalog)

        self.tb_findbookcatalog.clicked.connect(self.selectFile_bookcatalog)
        self.tb_finddbbookcatalog.clicked.connect(self.selectFile_dbbookcatalog)
        self.tb_finddbseriescatalog.clicked.connect(self.selectFile_dbseriescatalog)

    def retranslateUi(self, qWidget):
        _translate = QtCore.QCoreApplication.translate
        qWidget.setWindowTitle(_translate("qWidget", "Configure Apple iBooks/Books Plugin"))
        self.lb_product_name.setText(_translate("qWidget", "Apple iBooks / Books<br>sync plugin"))
        self.lb_product_version.setText(_translate("qWidget", "1.0.0"))
        self.gb_bookagent.setTitle(_translate("qWidget", "Apple Book Agent"))
        self.lb_bookcatalog.setText(_translate("qWidget", "Catalog (books.plist) location:"))
        self.ln_bookcatalog.setText(_translate("qWidget", prefs['bookcatalog']))
        self.tb_findbookcatalog.setText(_translate("qWidget", "..."))
        self.gb_databases.setTitle(_translate("qWidget", "Apple Books Databases"))
        self.lb_dbbookcatalog.setText(_translate("qWidget", "Book Library catalog (BKLibrary-1-091020131601.sqlite)"))
        self.lb_dbseriescatalog.setText(_translate("qWidget", "Book Series catalog (BKSeries-1-012820141020.sqlite)"))
        self.ln_dbbookcatalog.setText(_translate("qWidget", prefs['dbbookcatalog']))
        self.ln_dbseriescatalog.setText(_translate("qWidget", prefs['dbseriescatalog']))
        self.tb_finddbbookcatalog.setText(_translate("qWidget", "..."))
        self.tb_finddbseriescatalog.setText(_translate("qWidget", "..."))
        self.lb_url.setText(_translate("qWidget", "<a href=\"https://github.com/gchehab/apple_ibooks\">https://github.com/gchehab/apple_ibooks</a>"))
        # self.gb_generalsettings.setTitle(_translate("qWidget", "General Settings"))
        # self.ck_backup.setText(_translate("qWidget", "Backup on database on sync"))
        # self.ck_cleanlast.setText(_translate("qWidget", "Remove last synced books"))
        # self.ck_debug.setText(_translate("qWidget", "Debug information on log"))

        # Check if files are there and disable searching if they are
        if path.isfile(prefs['bookcatalog']):
            self.ln_bookcatalog.setEnabled(False)
            self.tb_findbookcatalog.setEnabled(False)
        if path.isfile(prefs['dbbookcatalog']):
            self.ln_dbbookcatalog.setEnabled(False)
            self.tb_finddbbookcatalog.setEnabled(False)
        if path.isfile(prefs['dbseriescatalog']):
            self.ln_dbseriescatalog.setEnabled(False)
            self.tb_finddbseriescatalog.setEnabled(False)

    def selectFile_bookcatalog(self):
        self.ln_bookcatalog.setText(
            QFileDialog.getOpenFileName(None, u'Book Catalog plist', prefs['bookcatalog'], '(*.plist)')[0])

    def selectFile_dbbookcatalog(self):
        self.ln_dbbookcatalog.setText(
            QFileDialog.getOpenFileName(None, u'Books sqlite database', prefs['dbbookcatalog'], '(*.sqlite)')[0])

    def selectFile_dbseriescatalog(self):
        self.ln_dbseriescatalog.setText(
            QFileDialog.getOpenFileName(None, u'Series sqlite database', prefs['dbseriescatalog'], '(*.sqlite)')[0])


class ConfigWidget(QWidget):
    qWidget = None
    def __init__(self):
        QWidget.__init__(self)

        self.setMinimumSize(586, 420)
        self.setMaximumSize(586, 420)

        self.ui = Ui_qWidget()
        self.qWidget = QtWidgets.QWidget()
        self.ui.setupUi(self.qWidget)

        self.l = QVBoxLayout()
        #self.l.setSizeConstraint(QLayout.SetFixedSize)
        self.l.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.l)

        self.l.addWidget(self.qWidget)
        self.adjustSize()

        # from PyQt5.QtCore import pyqtRemoveInputHook
        # from pdb import set_trace
        # pyqtRemoveInputHook()
        # set_trace()

    def save_settings(self):
        prefs['bookcatalog'] = self.ui.ln_bookcatalog.text()
        prefs['dbbookcatalog'] = self.ui.ln_dbbookcatalog.text()
        prefs['dbseriescatalog'] = self.ui.ln_dbseriescatalog.text()
        # prefs['backup'] = self.ui.ck_backup.isChecked()
        # prefs['debug'] = self.ui.ck_debug.isChecked()
        # prefs['remove_last_synced'] = self.ui.ck_cleanlast.isChecked()
        if prefs['debug']:
            print ('update settings')
