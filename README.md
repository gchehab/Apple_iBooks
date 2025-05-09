# Apple iBooks/Books plugin

### Disclaimer

This software is on initial development stage and should be considered highly unstable. It messes directly with 
the undocumented files Apple application files, and that may cause their corruption, rendering the applications unusable.

**In the present state it can create database inconsistences rendering Apple iBooks/Books unusable (only recoverable through working backup - USE AT YOUR OWN RISK**

It only has been tested with Apple iBooks 1.15 (Macos 10.13) and Apple Books 2.2 (Macos 10.15). 

## License

This piece of software is licensed under GPLv3


## Introduction

Plugin to allow book collection synchronization between Calibre library and Apple iBooks (high sierra) / Books
 (catalina and beyond) Mac OS aplications
 
As Apple has progressively discontinued iTunes API and iTunes itself it became much harder to use 3rd ebooks 
management software.  At the same time, Apple's own solution does not give the same amount of flexibility and 
functionality, giving their users what it seems to be only a half-done ebook manager.

This project goals to fill the gap. When complete will give back users the ability to use Calibre as their main 
ebook management system and synchronize it with their Apple mobile devices.

The lack of documentation and APIs to the newer Apple ebook management applications obligated to understand the way
that Apple maintain its book catalog and books metadata. 

This plugin interacts directly with the backend files used by Apple own applications, emulating the native process
of adding new ebook to the library.

It has the advantage of very quick synchronization routines. On the other hand, as Apple did not made their 
documentation public, it is expected that this files change their layouts without notice, and this could break the 
current integration or, even worse, create hard to fix issues on iBooks/Books catalogs.

That way the integration plugin should implement safeguards to verify the layouts and versions of the running Apple
software. Also it should **never** be used while iBooks/Books and its agent (background service) are running. 

The plugin does try to stop them once activated, however it has no way (as of yet) to detect if iBooks is launched
during synchronization.  
      
## Building
Requirements:
``` shell
make requirements
```

Debug:

``` shell
make debug
```

Package:

``` shell
make dist
```

(creates `dist/Apple_iBooks.zip`)

## Installing

<TODO>

## Todo list
- [ ] Remove psutil dependency as it distributes binary that may not work on all mac os versions
- [ ] Figure a way to transfer calibre covers that are not embeded in the book file
- [X] Tune performance to be able to sync some few thousand books in a single shot
- [X] ~Update Z_PRIMARYKEY -- if not, native adding new books break~
- [X] ~Add book to library and default collections -- need from books 2.X upwards~
- [ ] Create installation instructions
- [ ] Create safeguards against layout changes
- [ ] Properly lock the Apple Books files during use
- [ ] Add option to not uncompress ePub files (have to investigate its support)?
- [ ] Add option to not create copy of all ebooks (depends on compressed epub)?
- [X] Implement backup option
- [ ] Create undo, backup restore
- [X] Allow interrupt during sync
- [X] ~Remove empty collections and series from ibooks (hard to figure the ones created from calibre)~
- [X] ~Review series book grouping (disabled for now), as it seems to use storeID, iBooks thinks that all 
    grouped books were bought from apple store and has issues deleting them. Besides, it does not seem
     to be working consistently~
- [X] ~Figure out how to treat series entries added by BKAgent to series collections~
- [ ] Add paypal information on the plugin and its document should anyone find it useful
- [ ] Better management of unziped packages on temporary file -- add version controlled mechanism
- [ ] Change make dist to add version and release on the zip file


## Help the developer

If you like this and want to help the effort by donating time or money feel free to reach me.   


## Credits

This plugin was developed to be used to extend the functionality of Calibre, the best opensource ebook
management software by Kovid Goyal, https://github.com/kovidgoyal/calibre, who gracefully provided all needed support.

To integrate with Calibre I used as a example the plugin for BookFusion x Calibre synchronization that is available
at https://github.com/BookFusion/calibre-plugin.
