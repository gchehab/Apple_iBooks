#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import absolute_import, division, print_function, unicode_literals

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

if False:
    # This is here to keep my python error checker from complaining about
    # the builtin functions that will be defined by the plugin loading system
    # You do not need this code in your plugins
    get_icons = get_resources = None

import re
from datetime import datetime
from PyQt5.Qt import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QLabel, QApplication, QEventLoop
from PyQt5 import QtCore, QtGui, QtWidgets

from calibre_plugins.apple_ibooks import InterfacePluginAppleBooks
from calibre_plugins.apple_ibooks.config import prefs
from calibre_plugins.apple_ibooks.ibooks_api import IbooksApi
from pprint import pprint


class MainDialog(QDialog):
    def __init__(self, gui, icon, do_user_config, selected_book_ids, is_sync_selected):
        QDialog.__init__(self, gui)
        self.qDialog = QDialog
        self.gui = gui
        self.db = gui.current_db.new_api
        self.do_user_config = do_user_config
        self.is_sync_selected = is_sync_selected
        self.selected_book_ids = selected_book_ids if is_sync_selected else self.db.all_book_ids()

        # The current database shown in the GUI
        # db is an instance of the class LibraryDatabase from db/legacy.py
        # This class has many, many methods that allow you to do a lot of
        # things. For most purposes you should use db.new_api, which has
        # a much nicer interface from db/cache.py
        #self.db = gui.current_db
        self.setMinimumSize(586, 586)
        self.setMaximumSize(586, 586)

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        #QDialog.setObjectName("Dialog")
        #QDialog.resize(591, 409)


        self.setWindowTitle('Apple iBooks/Books sync')
        self.setWindowIcon(icon)

        self.fr_header = QtWidgets.QFrame(self)
        self.fr_header.setMinimumSize(546, 100)
        self.h = QHBoxLayout()
        self.fr_header.setLayout(self.h)
        self.fr_info = QtWidgets.QFrame(self)
        #self.fr_info.setGeometry(QtCore.QRect(10, 20, 311, 81))
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
        self.lb_product_name.setGeometry(QtCore.QRect(120, 20, 120, 61))
        self.lb_product_name.setTextFormat(QtCore.Qt.RichText)
        self.lb_product_name.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.lb_product_name.setObjectName("lb_product_name")
        self.h.addWidget(self.fr_info)

        # self.gb_generalsettings = QtWidgets.QGroupBox(self)
        # self.gb_generalsettings.setGeometry(QtCore.QRect(320, 20, 261, 81))
        # self.gb_generalsettings.setObjectName("gb_generalsettings")
        # self.gb_generalsettings.setEnabled(False)
        # self.ck_backup = QtWidgets.QCheckBox(self.gb_generalsettings)
        # self.ck_backup.setGeometry(QtCore.QRect(20, 20, 241, 17))
        # self.ck_backup.setObjectName("ck_backup")
        # self.ck_backup.setEnabled(False)
        # self.ck_cleanlast = QtWidgets.QCheckBox(self.gb_generalsettings)
        # self.ck_cleanlast.setObjectName("ch_cleanlast")
        # self.ck_cleanlast.setGeometry(QtCore.QRect(20, 40, 241, 17))
        # self.ck_cleanlast.setEnabled(False)
        # self.ck_debug = QtWidgets.QCheckBox(self.gb_generalsettings)
        # self.ck_debug.setGeometry(QtCore.QRect(20, 60, 241, 17))
        # self.ck_debug.setObjectName("ck_debug")
        # self.ck_debug.setEnabled(False)

        # self.h.addWidget(self.gb_generalsettings)

        self.l.addWidget(self.fr_header)

        self.gb_progress = QtWidgets.QGroupBox(self)
        self.gb_progress.setGeometry(QtCore.QRect(10, 110, 571, 171))
        self.gb_progress.setMinimumSize(562, 80)
        self.gb_progress.setObjectName("gb_progress")
        self.lb_progress = QtWidgets.QLabel(self.gb_progress)
        self.lb_progress.setGeometry(QtCore.QRect(20, 20, 331, 16))
        self.lb_progress.setObjectName("lb_progress")
        self.pb_progressBar = QtWidgets.QProgressBar(self.gb_progress)
        self.pb_progressBar.setEnabled(True)
        self.pb_progressBar.setGeometry(QtCore.QRect(10, 40, 541, 23))
        self.pb_progressBar.setProperty("value", 0)
        self.pb_progressBar.setObjectName("pb_progressBar")
        self.l.addWidget(self.gb_progress)

        self.gb_log = QtWidgets.QGroupBox(self)
        self.gb_log.setMinimumSize(562, 260)
        # self.gb_log.setGeometry(QtCore.QRect(10, 190, 571, 421))
        self.gb_log.setObjectName("gb_log")
        self.lw_log = QtWidgets.QListWidget(self.gb_log)
        self.lw_log.setGeometry(QtCore.QRect(10, 30, 541, 220))
        # self.lw_log.setMinimumSize(522, 210)
        self.lw_log.setObjectName("lw_log")
        self.l.addWidget(self.gb_log)

        self.fr_url = QtWidgets.QFrame(self)
        #self.fr_url.setGeometry(QtCore.QRect(10, 428, 571, 41))
        self.fr_url.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.fr_url.setFrameShadow(QtWidgets.QFrame.Raised)
        self.fr_url.setLineWidth(0)
        self.fr_url.setObjectName("fr_url")
        self.lb_url = QtWidgets.QLabel(self.fr_url)
        self.lb_url.setGeometry(QtCore.QRect(10, 10, 571, 16))
        self.lb_url.setTextFormat(QtCore.Qt.RichText)

        self.l.addWidget(self.fr_url)

        self.ck_syncSelected = QtWidgets.QCheckBox(self)
        self.ck_syncSelected.setChecked(is_sync_selected)
        self.ck_syncSelected.setObjectName("ck_syncSelected")
        self.ck_syncSelected.setEnabled(False)
        self.l.addWidget(self.ck_syncSelected)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.setGeometry(QtCore.QRect(10, 370, 571, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).clicked.connect(self.sync)
        self.buttonBox.button(QtWidgets.QDialogButtonBox.Cancel).clicked.connect(self.close)
        self.buttonBox.setObjectName("buttonBox")
        self.l.addWidget(self.buttonBox)

        self.about_button = QPushButton('About', self)
        self.about_button.clicked.connect(self.about)
        self.l.addWidget(self.about_button)

        self.conf_button = QPushButton(
                'Configure this plugin', self)
        self.conf_button.clicked.connect(self.config)
        self.l.addWidget(self.conf_button)

        #self.l.setContentsMargins(0, 0, 0, 0)
        self.resize(self.sizeHint())
        self.adjustSize()

        self.retranslateUi(QDialog)
        # QtCore.QMetaObject.connectSlotsByName(QDialog)

    def retranslateUi(self, QDialog):
        _translate = QtCore.QCoreApplication.translate
        # QDialog.setWindowTitle(_translate("QDialog", "Dialog"))
        self.lb_url.setText(_translate("QDialog", "<a href=\"" +
                                       InterfacePluginAppleBooks.url + "\">" +
                                       InterfacePluginAppleBooks.url + "</a>"))
        self.gb_progress.setTitle(_translate("QDialog", "Apple Book Agent"))
        self.lb_progress.setText(_translate("QDialog", "Progress:"))
        self.gb_log.setTitle(_translate("QDialog", "Log"))
        self.lb_product_name.setText(_translate("QDialog", "Apple iBooks / Books<br>sync plugin<br>" +
                                                   str(InterfacePluginAppleBooks.version[0]) + "." +
                                                   str(InterfacePluginAppleBooks.version[1]) + "." +
                                                   str(InterfacePluginAppleBooks.version[2]) + "."))
        # self.gb_generalsettings.setTitle(_translate("qWidget", "General Settings"))
        # self.ck_backup.setChecked(prefs['backup'])
        # self.ck_backup.setText(_translate("qWidget", "Backup on database on sync"))
        # self.ck_cleanlast.setChecked(prefs['remove_last_synced'])
        # self.ck_cleanlast.setText(_translate("qWidget", "Remove last synced books"))
        # self.ck_debug.setChecked(prefs['debug'])
        # self.ck_debug.setText(_translate("qWidget", "Debug information on log"))
        if (self.is_sync_selected):
            self.ck_syncSelected.setText(_translate("qWidget", "Sync selected books only (" +
                                                str(len(self.selected_book_ids)) + " books)"))
        else:
            self.ck_syncSelected.setText(_translate("qWidget", "Sync selected books only (all collection = " +
                                                    str(len(self.selected_book_ids)) + " books)"))

    def about(self):
        # Get the about text from a file inside the plugin zip file
        # The get_resources function is a builtin function defined for all your
        # plugin code. It loads files from the plugin zip file. It returns
        # the bytes from the specified file.
        #
        # Note that if you are loading more than one file, for performance, you
        # should pass a list of names to get_resources. In this case,
        # get_resources will return a dictionary mapping names to bytes. Names that
        # are not found in the zip file will not be in the returned dictionary.
        text = get_resources('about.txt')
        QMessageBox.about(self, 'About the Interface Plugin Demo',
                text.decode('utf-8'))

    def config(self):
        self.do_user_config(parent=self)
        # Apply the changes
        self.retranslateUi(self)
        # self.gui.refresh()
        # prefs['backup'] = self.ck_backup.isChecked()
        # prefs['debug'] = self.ck_debug.isChecked()
        # prefs['remove_last_synced'] = self.ck_cleanlast.isChecked()

    def sync(self):
        if (self.pb_progressBar.value() == 100):
            self.buttonBox.setEnabled(True)
            self.close()
        else:
            self.buttonBox.setEnabled(False)
            self.pb_progressBar.setProperty("value", 1)
            self.lw_log.insertItem(0, str(datetime.now()) + ": Starting Sync")
            self.lw_log.insertItem(0, str(datetime.now()) + ": Finishing iBooks and its agent processes")
            ibooks = IbooksApi()

            if prefs['remove_last_synced']:
                self.lw_log.insertItem(0, str(datetime.now()) + ": Removing calibre books from iBooks")
                count=ibooks.del_all_books_from_calibre()
                self.lw_log.insertItem(0, str(datetime.now()) + ": Removed " + str (count) + " calibre books from iBooks")

            for i, book_id in enumerate(list(self.selected_book_ids)):
                self.lw_log.insertItem(0, str(datetime.now()) + ": Syncing book id " +
                                       str(book_id) + ": " + str(i + 1) + "/" + str(len(self.selected_book_ids)))

                fmts = self.db.formats(book_id)
                if fmts is not None:
                    if 'EPUB' in fmts or 'PDF' in fmts:
                        mi = self.db.get_metadata(book_id, get_cover=False, cover_as_data=False)
                        fmt = 'EPUB' if 'EPUB' in fmts else 'PDF'
                        file_path = self.db.format_abspath(book_id, fmt)

                        ibooks.add_book(
                            book_id=book_id,
                            title=mi.title,
                            author=', '.join(map(str,mi.authors)),
                            input_path=file_path,
                            collection=mi.series if mi.series is not None else
                                (u"Books" if fmt == "EPUB" else u"PDFs"),
                            # genre=mi.genre,
                            series_name=mi.series,
                            series_number=mi.series_index
                        )

                        self.lw_log.insertItem(0, str(datetime.now()) + ": Done syncing book id " +
                                               str(book_id) + ": " + str(i + 1) + "/" + str(len(self.selected_book_ids)) +
                                               " - " + mi.title)
                    else:
                        self.lw_log.insertItem(0, str(datetime.now()) + ": Book id " +
                                               str(book_id) + ": " + str(i + 1) + "/" + str(len(self.selected_book_ids)) +
                                               " - " + mi.title + " - has no compatible formats, skipping")
                else:
                    self.lw_log.insertItem(0, str(datetime.now()) + ": Book id " +
                                           str(book_id) + ": " + str(i + 1) + "/" + str(len(self.selected_book_ids)) +
                                           " - " + mi.title + " - has no compatible formats, skipping")

                self.pb_progressBar.setProperty("value", 1 + 99 * (i + 1) / len(self.selected_book_ids))
                self.pb_progressBar.repaint()
                self.lw_log.repaint()
                QtCore.QCoreApplication.instance().processEvents()

            # End sync
            del ibooks

            self.pb_progressBar.setProperty("value", 100)
            self.lw_log.insertItem(0, str(datetime.now()) + ": Finished Sync")
            self.buttonBox.setEnabled(True)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            if 0 < self.pb_progressBar.value() < 100:
                if prefs['debug']:
                    print("Sync in progress, cannot close")
            else:
                event.accept()

    def closeEvent(self, event):
        if 0 < self.pb_progressBar.value() < 100:
            if prefs['debug']:
                print ("Sync in progress, cannot close")
        else:
            event.accept()