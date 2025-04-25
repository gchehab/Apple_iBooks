#!/usr/bin/python
# -*- coding=utf-8 -*-
import sys
import hashlib
from os import path, getuid, remove
from shutil import copy2, rmtree, move
import zipfile
import zlib
import re
from time import time
from datetime import datetime

import pypsutil as psutil
#from biplist import readPlist, writePlist, InvalidPlistException, NotBinaryPlistException
from plistlib import load, dump, FMT_BINARY
from calibre_plugins.apple_ibooks.ibooks_api.ibooks_sql import BkLibraryDb, BkSeriesDb
from pprint import pprint
# from fsevents import Observer, Stream
from profilehooks import profile

from calibre_plugins.apple_ibooks.config import prefs

def my_profile(func):
    def profile_it(*args, **kwargs):
        if prefs['debug']:
            profile(func)(*args, **kwargs)
        else:
            func(*args, **kwargs)
    return profile_it

class IbooksApi:
    catalog = {}
    IBOOKS_BKAGENT_PATH = path.dirname(prefs['bookcatalog'])
    IBOOKS_BKAGENT_CATALOG_FILE = prefs['bookcatalog']
    
    @staticmethod
    def __file_as_bytes(file_to_read, size=None):
        with file_to_read:
            return file_to_read.read(size) if size is not None else file_to_read.read()

    @staticmethod
    def __kill_ibooks():
        ps_util_fail = False

        try:
            processes = psutil.process_iter(attrs=['pid', 'name'])
        except:
            ps_util_fail = True
            pass

        try:
            if not ps_util_fail:
                # Kill any running ibooks process from the current user using pslist
                for process in processes:
                    if getuid() == process.uids()[1]:
                        if 'Books' in process.info['name']:
                            if 'Books.app' in process.cmdline()[0]:
                                try:
                                    if prefs['debug']:
                                        print (str(datetime.now()) + ": Killing (i)Books.app")

                                    process.terminate()
                                    process.wait(5)
                                except Exception:
                                    process.kill()
                                    pass
                        if 'BKAgentService' in process.info['name']:
                            try:
                                if prefs['debug']:
                                    print (str(datetime.now()) + ": Killing BKAgentService")
                                process.terminate()
                                process.wait(5)
                            except Exception:
                                process.kill()
                                pass
            else:
                # Kill any running ibooks process from the current user using ps -Au and os.kill
                from os import kill, waitpid, WNOHANG
                from re import split
                from errno import ESRCH
                from subprocess import Popen, PIPE
                from time import sleep
                from signal import SIGTERM, SIGKILL
                p = Popen(['ps', '-Au', str(getuid())], stdout=PIPE)
                out, err = p.communicate()
                for line in out.splitlines():
                    print (type(line))
                    if 'Books.app' in line or 'BKAgentService' in line:
                        pid = int(split(r"\s+", line)[2])
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Killing " + str(pid)) #split(r"\t+", line)[4])

                        tries = 0
                        try:
                            while (kill(pid, SIGTERM) and tries < 3):
                                sleep(0.5)
                                tries += 1
                        except OSError as err:
                            if err.errno == ESRCH:
                                return False
                            return True


                        tries = 0
                        try:
                            while (kill(pid, SIGKILL) and tries < 3):
                                sleep(0.5)
                                tries += 1
                        except OSError as err:
                            if err.errno == ESRCH:
                                return False

        except Exception:
            raise


    def __init__(self):

        # # Start file watcher to ensure no one else opens database files -- maybe add something to lock them
        # self.observer = Observer()
        # self.observer.start()

        # self.stream = Stream(self.ObserverCallback, IBOOKS_BKAGENT_CATALOG_FILE, file_events=True )
        # self.observer.schedule(self.stream)

        try:
            self.__kill_ibooks()
        except Exception:
            raise

        try:
            self.__library_db = BkLibraryDb()
            self.__series_db = BkSeriesDb()
            self.has_changed = 0
            self.has_backup = False
            #self.catalog = readPlist(self.IBOOKS_BKAGENT_CATALOG_FILE)
            self.catalog = None
            with open(self.IBOOKS_BKAGENT_CATALOG_FILE, 'rb') as fp:
                self.catalog = load(fp)

        # except InvalidPlistException:
        #     if prefs['debug']:
        #         print (str(datetime.now()) + ": " + self.IBOOKS_BKAGENT_CATALOG_FILE + "is not a valid plist file")
        #     raise

        # except NotBinaryPlistException:
        #     if prefs['debug']:
        #         print (str(datetime.now()) + ": " + self.IBOOKS_BKAGENT_CATALOG_FILE + "is not a valid plist file")
        #     raise
    
        except Exception:
            print (sys.exc_info()[0])
            raise

    def rollback(self):
        try:
            if self.has_changed > 0:
                self.__kill_ibooks()

                if prefs['debug']:
                    print (str(datetime.now()) + ": Rolling back library DB")
                self.__library_db.rollback()

                if prefs['debug']:
                    print (str(datetime.now()) + ": Rolling back Series DB")
                self.__series_db.rollback()

                if prefs['backup'] and self.has_backup:
                    if prefs['debug']:
                        print (str(datetime.now()) + ": Rolling back plist catalog")

                    for filename in ['bookcatalog']:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Rolling back " + filename)
                        move(prefs[filename] + ".bkp", prefs[filename])
                    self.has_backup = False
                if prefs['debug']:
                    print (str(datetime.now()) + ": Roll back finished")
                self.has_changed = 0

        except Exception:
            print (sys.exc_info()[0])
            raise

    #@profile
    def commit(self):
        try:
            if self.has_changed > 0:
                if prefs['backup'] and not self.has_backup:
                    for filename in ['bookcatalog']:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Backing up " + filename)
                        copy2(prefs[filename], prefs[filename] + ".bkp")
                    self.has_backup = True
                self.__kill_ibooks()
                if prefs['debug']:
                    print (str(datetime.now()) + ": Commmiting library DB")
                self.__library_db.commit()
                if prefs['debug']:
                    print (str(datetime.now()) + ": Commmiting series DB")
                self.__series_db.commit()
                if prefs['debug']:
                    print (str(datetime.now()) + ": Commmiting plist catalog")
                
                #writePlist(self.catalog, self.IBOOKS_BKAGENT_CATALOG_FILE + ".tmp", binary=False)
                with open(self.IBOOKS_BKAGENT_CATALOG_FILE + ".tmp", 'wb') as fp:
                    dump(self.catalog, fp, fmt=FMT_BINARY)
                move(self.IBOOKS_BKAGENT_CATALOG_FILE + ".tmp", self.IBOOKS_BKAGENT_CATALOG_FILE)

                if prefs['debug']:
                    print (str(datetime.now()) + ": Commmit finished")
                self.has_changed = 0
        except Exception:
            print (sys.exc_info()[0])
            raise


    def __del__(self):
    #     self.observer.unschedule(self.stream)
    #     self.observer.stop()
    #     self.observer.join()
    #     self.commit()
        del self.__series_db
        del self.__library_db
        del self.catalog

    #@profile
    def add_book(self, book_id=None, title=None, collection=None, genre=None, is_explicit=None,
                 series_name=None, series_number=0, sequence_display_name=None,
                 input_path=None, author=None):

        try:
            # Calculate fields and file stats, including destination collection
            size = 0

            # Check if file already exists on destination
            if input_path is not None:
                if prefs['debug']:
                    print (str(datetime.now()) + ": Adding " + title + " to calibre")

                if path.isfile(path.expanduser(input_path)):
                    asset_id = str(hashlib.md5(
                        self.__file_as_bytes(open(path.expanduser(input_path), 'rb'), size=32768)).
                                   hexdigest()).upper()
                    book_hash = asset_id

                    if ".epub" in input_path.lower():
                        output_path = path.join(self.IBOOKS_BKAGENT_PATH, asset_id)
                        output_path = output_path + '.epub'
                    else:
                        output_path = path.join(self.IBOOKS_BKAGENT_PATH,
                                                # path.splitext(path.basename(path.expanduser(input_path)))[0],
                                                path.basename(path.expanduser(input_path)))

                    if not path.exists(output_path):
                        if ".epub" in input_path.lower():
                            try:
                                if prefs['debug']:
                                    print (str(datetime.now()) + ": Extracting epub file")

                                with zipfile.ZipFile(path.expanduser(input_path), 'r') as epub_file:
                                    zip_info = epub_file.infolist()
                                    for member in zip_info:
                                        size += member.file_size

                                    epub_file.extractall(path.expanduser(output_path))
                            except Exception:
                                if prefs['debug']:
                                    print (str(datetime.now()) + ": Cannot extract file to destination")
                                print (sys.exc_info()[0])
                                raise
                        else:
                            size = path.getsize(path.expanduser(input_path))
                            try:
                                if prefs['debug']:
                                   print (str(datetime.now()) + ": Copying pdf file")
                                copy2(path.expanduser(input_path), path.expanduser(output_path))
                            except Exception:
                                if prefs['debug']:
                                    print (str(datetime.now()) + ": Cannot copy file to destination")
                                print (sys.exc_info()[0])
                                raise
                    else:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Will not copy/extract file as it already exists -- update metadata only")

                    # Add book to database
                    series_adam_id = None

                    if series_name is not None:
                        # series_number *= 100
                        adam_id = zlib.crc32(asset_id.encode('utf-8'))
                        adam_id = adam_id % (1<<32) if adam_id < 0 else adam_id
                        series_adam_id = zlib.crc32(series_name.encode('utf-8'))
                        series_adam_id = series_adam_id % (1 << 32) if series_adam_id < 0 else series_adam_id

                        sequence_display_name = str(series_number/100) \
                            if sequence_display_name is None else sequence_display_name

                        if prefs['debug']:
                            print (str(datetime.now()) + ": Adding to series DB")

                        self.__series_db.add_book_to_series(series_name=series_name, series_id=series_adam_id,
                                                            series_number=series_number, author=author,
                                                            genre=genre, adam_id=asset_id, title=title)
                    if prefs['debug']:
                        print (str(datetime.now()) + ": Adding to asset DB")

                    self.__library_db.add_book(book_id=book_id, title=title, collection_name=collection,
                                               filepath=output_path, asset_id=asset_id, series_name=series_name,
                                               series_id=series_adam_id, series_number=series_number, genre=genre,
                                               author=author, size=size)

                    # Add asset to plist file
                    if prefs['debug']:
                        print (str(datetime.now()) + ": Checking if exists on Books.plist")

                    if asset_id not in [book['BKGeneratedItemId'] for book in self.catalog['Books']]:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Adding new entry to Books.plist")

                        new_plist = {
                            'BKGeneratedItemId': asset_id,
                            'BKAllocatedSize': size,
                            'BKBookType': u'epub' if ".epub" in input_path.lower() else u'pdf',
                            'BKDisplayName': path.basename(path.expanduser(input_path)),
                            'BKGenerationCount': 1,
                            'BKInsertionDate': int(time()),
                            'BKIsLocked': False,
                            # 'BKPercentComplete': 1.0,
                            'comment': 'Calibre #' + str(book_id),
                            'artistName': author,
                            # 'book-info': {'package-file-hash': book_hash,
                            #               'cover-image-path': u'file:/tmp/cover.jpg'},
                            # 'cover-writing-mqode': 'horizontal',
                            # 'cover-url': 'file:/tmp/cover.jpg',
                            # 'explicit': False if is_explicit is None else bool(is_explicit),
                            # 'genre': genre,
                            # 'isPreview': False,
                            'itemName': title,
                            'path': path.expanduser(output_path),
                            'sourcePath': path.expanduser(input_path),
                        }

                        # Add to series if needed
                        if series_name is not None:
                            new_plist['seriesAdamId'] = series_adam_id
                            new_plist['seriesTitle'] = series_name
                            new_plist['seriesSequenceNumber'] = str(series_number)
                            new_plist['playlistName'] = series_name
                            new_plist['itemId'] = asset_id

                        self.catalog['Books'].append(new_plist)

                    else:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Modifying entry to Books.plist")

                        new_plist = self.catalog['Books'][
                            next((i for i, book in enumerate(self.catalog['Books'])
                                  if book['BKGeneratedItemId'] == asset_id), -1)
                        ]
                        new_plist['BKAllocatedSize'] = size
                        new_plist['BKDisplayName'] = path.basename(path.expanduser(input_path)),
                        new_plist['BKBookType'] = u'epub' if ".epub" in input_path.lower() else u'pdf',
                        new_plist['BKGenerationCount'] += 1
                        new_plist['BKInsertionDate'] = int(time())
                        new_plist['comment'] = 'Calibre #' + str(book_id)
                        new_plist['artistName'] = author
                        # new_plist['book-info'] = {'package-file-hash': book_hash}
                        # new_plist['explicit'] = False if is_explicit is None else bool(is_explicit),
                        # new_plist['genre'] = genre
                        new_plist['itemName'] = title
                        new_plist['path'] = path.expanduser(output_path)
                        new_plist['sourcePath'] = path.expanduser(input_path)

                        # Add to series if needed
                        if series_name is not None:
                            new_plist['seriesAdamId'] = series_adam_id
                            new_plist['seriesTitle'] = series_name
                            new_plist['seriesSequenceNumber'] = str(series_number)
                            new_plist['playlistName'] = series_name
                            new_plist['itemId'] = asset_id

                    self.has_changed += 1

                else:
                    if prefs['debug']:
                        print (str(datetime.now()) + ": File not found!")
                    print (sys.exc_info()[0])
                    return -1

            else:
                if prefs['debug']:
                    print (str(datetime.now()) + ": Path is invalid")
                return -1

            if prefs['debug']:
                print (str(datetime.now()) + ": Done adding new book\n")

            # Todo: add batch size as a configuration option
            if (self.has_changed % 1000 == 0):
                self.commit()
            return 0

        except Exception:
            print (sys.exc_info()[0])
            raise

    def del_all_books_from_calibre(self):
        deleted = 0
        self.__library_db.del_all_books_from_calibre()

        count = len(self.catalog['Books'])

        if prefs['debug']:
                    print (str(datetime.now()) + ": Deletting all books from calibre")

        for i in range(len(self.catalog['Books']) - 1, -1, -1):
            book = self.catalog['Books'][i]

            if 'comment' not in book:
                if prefs['debug']:
                    print (str(datetime.now()) + ": Not deleting " + str(i) + ': Book not added by calibre, skipping')
                continue

            if prefs['debug']:
                print (str(datetime.now()) + ": Deleting " + str(i) + ": " + book['comment'])

            if "Calibre #" in book['comment']:
                file_path = book['path']
                if (path.isdir(file_path)):
                    try:
                        rmtree(file_path)
                    except OSError:
                        pass
                else:
                    try:
                        remove(file_path)
                    except OSError:
                        pass

                if 'seriesAdamId' in book:
                    adam_id = book['itemId']
                    if prefs['debug']:
                        print (str(datetime.now()) + ": Removed " +str(adam_id) + " from series table")
                    self.__series_db.del_book_from_series(adam_id=adam_id)

                del (self.catalog['Books'][i])
                self.has_changed=1
                deleted += 1

        if prefs['debug']:
            print (str(datetime.now()) + ": Deleted " + str(deleted) + "/" + str(count) + " books from plist, kept " +\
              str(len(self.catalog['Books'])) + " books")
        # if deleted > 0:
        #     writePlist(self.catalog, self.IBOOKS_BKAGENT_CATALOG_FILE)

        return deleted


    def add_collection(self, title):
        return self.__library_db.create_collection(title)

    def list_collection(self):
        return self.__library_db.list_colections()

    def list_books(self):
        return self.__library_db.list_books()

    @staticmethod
    def observer_callback(file_event):
        if prefs['debug']:
            pprint(file_event)
