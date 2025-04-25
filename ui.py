#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import absolute_import, division, print_function, unicode_literals

__license__   = 'GPL v3'
__copyright__ = '2019, Guilherme Chehab <guilherme.chehab@yahoo.com>'
__docformat__ = 'restructuredtext en'

if False:
    # This is here to keep my python error checker from complaining about
    # the builtin functions that will be defined by the plugin loading system
    # You do not need this code in your plugins
    get_icons = get_resources = None

from PyQt5.Qt import QMenu

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction
from calibre_plugins.apple_ibooks.main import MainDialog

class InterfacePlugin(InterfaceAction):

    name = 'Apple iBooks plugin'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    action_spec = (u'Apple iBooks', None,
            u'Run the Apple iBooks sync', 'Ctrl+Shift+F1')
    action_add_menu = True

    def genesis(self):
        # This method is called once per plugin, do initial setup here

        # Set the icon for this interface action
        # The get_icons function is a builtin function defined for all your
        # plugin code. It loads icons from the plugin zip file. It returns
        # QIcon objects, if you want the actual data, use the analogous
        # get_resources builtin function.
        #
        # Note that if you are loading more than one icon, for performance, you
        # should pass a list of names to get_icons. In this case, get_icons
        # will return a dictionary mapping names to QIcons. Names that
        # are not found in the zip file will result in null QIcons.
        self.sync_selected_action = self.create_action(
            spec=('Sync selected books', None, None, None),
            attr='Sync selected books'
        )
        self.sync_selected_action.triggered.connect(self.sync_selected)

        self.sync_all_action = self.create_action(
            spec=('Sync all books', None, None, None),
            attr='Sync all books'
        )
        self.sync_all_action.triggered.connect(self.sync_all)

        self.remove_all_action = self.create_action(
            spec=(Remove all calibre books', None, None, None),
            attr='Remove all calibre books'
        )
        self.remove_all_action.triggered.connect(self.remove_all)


        self.menu = QMenu(self.gui)
        self.menu.addAction(self.sync_selected_action)
        self.menu.addAction(self.sync_all_action)
        self.menu.addAction(self.remove_all_action)
        self.menu.aboutToShow.connect(self.update_menu)

        # The qaction is automatically created from the action_spec defined
        # above
        #self.qaction.triggered.connect(self.show_dialog)
        icon = get_icons('images/icon.svg')
        self.qaction.setMenu(self.menu)
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.sync_selected)

    def sync_all(self):
        self.show_dialog(is_sync_selected=False)

    def sync_selected(self):
        self.show_dialog()

    def show_dialog(self, is_sync_selected=True):
        # The base plugin object defined in __init__.py
        base_plugin_object = self.interface_action_base_plugin
        # Show the config dialog
        # The config dialog can also be shown from within
        # Preferences->Plugins, which is why the do_user_config
        # method is defined on the base plugin class
        do_user_config = base_plugin_object.do_user_config

        # self.gui is the main calibre GUI. It acts as the gateway to access
        # all the elements of the calibre user interface, it should also be the
        # parent of the dialog

        rows = self.gui.library_view.selectionModel().selectedRows()
        selected_book_ids = []
        for row in rows:
            selected_book_ids.append(self.gui.library_view.model().db.id(row.row()))

        MainDialog(self.gui, self.qaction.icon(), do_user_config, selected_book_ids, is_sync_selected).show()

    def update_menu(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        self.sync_selected_action.setEnabled(len(rows) > 0)

    def apply_settings(self):
        from calibre_plugins.apple_ibooks.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        None

