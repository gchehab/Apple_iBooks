#!/usr/bin/python
# -*- coding=utf-8 -*-
import sys
import os
import zipfile
import tempfile

from calibre_plugins.apple_ibooks.config import prefs


# Ugly hack to manipulate sys path to add allow import of complex packages, needed for pslist and sqlalchemy so far
packages_path = os.path.join(tempfile.gettempdir(), 'calibre_ibooks_plugin')

# Extract packges to temp dir if it does not exist
if not os.path.isdir(packages_path) or prefs['debug']:
    with zipfile.ZipFile(os.path.expanduser("~/Library/Preferences/calibre/plugins/Apple_iBooks.zip"), 'r') as packages:
        packages.extractall(packages_path)

packages_path = os.path.join(packages_path)
sys.path.insert(0, os.path.join(packages_path, 'packages'))

from .ibooks_api import IbooksApi

# Recover os.path
sys.path.pop(0)


