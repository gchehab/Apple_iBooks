#!/usr/bin/python
# -*- coding=utf-8 -*-
import sys
import hashlib
from os import path, getuid, remove
from shutil import copy2, rmtree
import zipfile
import zlib
import re
from time import time

import psutil
from biplist import readPlist, writePlist, InvalidPlistException, NotBinaryPlistException
from calibre_plugins.apple_ibooks.ibooks_api.ibooks_sql import BkLibraryDb, BkSeriesDb
from pprint import pprint
# from fsevents import Observer, Stream

# from profilehooks import profile


from calibre_plugins.apple_ibooks.config import prefs


class IbooksApi:
    catalog = {}
    #IBOOKS_BKAGENT_PATH = path.expanduser("~/Library/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books")
    IBOOKS_BKAGENT_PATH = path.dirname(prefs['bookcatalog'])

    #IBOOKS_BKAGENT_CATALOG = "books.plist"
    #IBOOKS_BKAGENT_CATALOG_FILE = path.join(IBOOKS_BKAGENT_PATH, IBOOKS_BKAGENT_CATALOG)
    IBOOKS_BKAGENT_CATALOG_FILE = prefs['bookcatalog']

    @staticmethod
    def __file_as_bytes(file_to_read):
        with file_to_read:
            return file_to_read.read()

    @staticmethod
    def __kill_ibooks():
        try:
            # Kill any running ibooks process from the current user
            for process in psutil.process_iter(attrs=['pid', 'name']):
                if getuid() == process. uids()[1]:
                    if 'Books' in process.info['name']:
                        if 'Books.app' in process.cmdline()[0]:
                            try:
                                process.terminate()
                                process.wait(5)
                            except Exception:
                                process.kill()
                                pass
                    if 'BKAgentService' in process.info['name']:
                        try:
                            process.terminate()
                            process.wait(5)
                        except Exception:
                            process.kill()
                            pass
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
            self.catalog = readPlist(self.IBOOKS_BKAGENT_CATALOG_FILE)

        except (InvalidPlistException, NotBinaryPlistException), e:
            if prefs['debug']:
                print "Not a plist:", e
            raise

        except Exception:
            print (sys.exc_info()[0])
            raise

    def commit(self):
        try:
            if self.has_changed > 0:
                self.__kill_ibooks()
                self.__library_db.commit()
                self.__series_db.commit()
                writePlist(self.catalog, self.IBOOKS_BKAGENT_CATALOG_FILE)
        except Exception:
            print (sys.exc_info()[0])
            raise


    def __del__(self):
    #     self.observer.unschedule(self.stream)
    #     self.observer.stop()
    #     self.observer.join()
        self.commit()

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
                    print ("Adding " + title + " to calibre")

                if path.isfile(path.expanduser(input_path)):
                    asset_id = str(hashlib.md5(
                        self.__file_as_bytes(open(path.expanduser(input_path), 'rb'))).
                                   hexdigest()).upper()
                    book_hash = asset_id


                    if ".epub" in input_path.lower():
                        output_path = path.join(self.IBOOKS_BKAGENT_PATH, asset_id)
                        output_path = output_path + '.epub'
                        try:
                            if prefs['debug']:
                                print ("Extracting epub file")

                            with zipfile.ZipFile(path.expanduser(input_path), 'r') as epub_file:
                                zip_info = epub_file.infolist()
                                for member in zip_info:
                                    size += member.file_size

                                epub_file.extractall(path.expanduser(output_path))
                        except Exception:
                            if prefs['debug']:
                                print ("Cannot extract file to destination")
                            print (sys.exc_info()[0])
                            raise
                    else:
                        output_path = path.join(self.IBOOKS_BKAGENT_PATH,
                                                # path.splitext(path.basename(path.expanduser(input_path)))[0],
                                                path.basename(path.expanduser(input_path)))

                        size = path.getsize(path.expanduser(input_path))
                        try:
                            if prefs['debug']:
                               print ("Copying pdf file")
                            copy2(path.expanduser(input_path), path.expanduser(output_path))
                        except Exception:
                            if prefs['debug']:
                                print ("Cannot copy file to destination")
                            print (sys.exc_info()[0])
                            raise

                    # Add book to database
                    series_adam_id = None

                    if series_name is not None:
                        # series_number *= 100
                        adam_id = zlib.crc32(asset_id)
                        adam_id = adam_id % (1<<32) if adam_id < 0 else adam_id
                        series_adam_id = zlib.crc32(series_name)
                        series_adam_id = series_adam_id % (1 << 32) if series_adam_id < 0 else series_adam_id

                        sequence_display_name = str(series_number/100) \
                            if sequence_display_name is None else sequence_display_name

                        if prefs['debug']:
                            print ("Adding to series DB")

                        self.__series_db.add_book_to_series(series_name=series_name, series_id=series_adam_id,
                                                            series_number=series_number, author=author,
                                                            genre=genre, adam_id=asset_id, title=title)
                    if prefs['debug']:
                        print ("Adding to asset DB")

                    self.__library_db.add_book(book_id=book_id, title=title, collection_name=collection,
                                               filepath=output_path, asset_id=asset_id, series_name=series_name,
                                               series_id=series_adam_id, series_number=series_number, genre=genre,
                                               author=author, size=size)

                    # Add asset to plist file
                    if prefs['debug']:
                        print ("Checking if exists on Books.plist")

                    if asset_id not in [book['BKGeneratedItemId'] for book in self.catalog['Books']]:
                        if prefs['debug']:
                            print ("Adding new entry to Books.plist")

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
                            print ("Modifying entry to Books.plist")

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

                    # Todo: add batch size as a configuration option
                    if (self.has_changed % 250 == 0):
                        self.commit()

                else:
                    if prefs['debug']:
                        print ("File not found!")
                    print (sys.exc_info()[0])
                    return -1

            else:
                if prefs['debug']:
                    print ("Path is invalid")
                return -1

            if prefs['debug']:
                print ("Done adding new book\n")

            return 0

        except Exception:
            print (sys.exc_info()[0])
            raise

    def del_all_books_from_calibre(self):
        deleted = 0
        self.__library_db.del_all_books_from_calibre()

        count = len(self.catalog['Books'])

        for i in range(len(self.catalog['Books']) - 1, -1, -1):
            book = self.catalog['Books'][i]

            if 'comment' not in book:
                if prefs['debug']:
                    print str(i) + 'Book not added by calibre, skipping'
                continue

            if prefs['debug']:
                print str(i) + ": " + book['comment']

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
                        print "Removed " +str(adam_id) + " from series table"
                    self.__series_db.del_book_from_series(adam_id=adam_id)

                del (self.catalog['Books'][i])
                self.has_changed=1
                deleted += 1

        if prefs['debug']:
            print "Deleted " + str(deleted) + "/" + str(count) + " books from plist, kept " +\
              str(len(self.catalog['Books'])) + " books"
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
