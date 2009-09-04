#!/usr/bin/env python
#
# Download images from Google Maps for use with Maemo Mapper.
#
# This script may corrupt your database. And the Google attorneys may
# show up at your doorstep as downloading maps for use outside of
# Google Maps is most probably illegal. Use at your own risk!
#
# Do whatever you like with this script. If you can improve it, please
# do so and consider to make your changes available so that others can
# benefit from your work.

import sqlite3, urllib

from math import *
from optparse import OptionParser


# Google Maps URL (street maps)
URL="http://mt0.google.com/mt/v=w2.95&hl=en&x=%d&y=%d&zoom=%d"


# some defines
MERCATOR_SPAN=(-6.28318377773622)
MERCATOR_TOP=(3.14159188886811)
WORLD_SIZE_UNITS=(1 << 26)


# not actually used here, but may come in handy for other map sources
def convert_coords_to_quadtree_string(x, y, zoomlevel):
    string = ""
    quadrant = "0123"
    for n in range (16 - zoomlevel, -1, -1):
        xbit = (x >> n) & 1;
        ybit = (y >> n) & 1;
        string += quadrant[xbit + 2 * ybit];
    return string

def latlon2unit(lat, lon):
    unitx = (lon + 180.0) * (WORLD_SIZE_UNITS / 360.0) + 0.5
    tmp = sin (lat * (pi / 180.0))
    unity = (0.5 + (WORLD_SIZE_UNITS / MERCATOR_SPAN) *
             (log ((1.0 + tmp) / (1.0 - tmp)) * 0.50 - MERCATOR_TOP));
    return (unitx, unity)

def tile2zunit(tile, zoom):
    return ((tile) << (5 + zoom))

def unit2ztile(munit, zoom):
    return ((int)(munit) >> (5 + zoom))


# get tile ranges
def getTiles(startlat, endlat, startlong, endlong, zoom):
    (sux, suy) = latlon2unit (startlat, startlong)
    (eux, euy) = latlon2unit (endlat, endlong)
    
    if eux < sux:
        x = eux
        eux = sux
        sux = x
    
    if euy < suy:
        y = euy
        euy = suy
        suy = y
    
    return (range (unit2ztile (sux, zoom), unit2ztile (eux, zoom) + 1),
            range (unit2ztile (suy, zoom), unit2ztile (euy, zoom) + 1))


# check if the tile is already in the database
def tileExists(db, x, y, zoom):
    db.execute ("select count(*) from maps where zoom = %d and tilex = %d and tiley = %d;"
                % (zoom, x, y))
    return (int(db.fetchone()[0]) > 0)

# add the tile to the database
def tileAdd(db, pixbuf, x, y, zoom):
    db.execute ("insert or replace into maps (pixbuf, zoom, tilex, tiley) values (?, ?, ?, ?);",
                (sqlite3.Binary (pixbuf.read()), zoom, x, y))


# This is the central function.
# It first checks if the tile needs to be downloaded at all,
# then downloads it and inserts it into the database.
def loadTile(db, x, y, zoom, num, total):
    if (tileExists (db, x, y, zoom)):
        return
    
    url = URL % (x, y, zoom - 4)
    
    print "Downloading tile %d of %d" % (num, total)
    
    while True:
        try:
            tileAdd (db, urllib.urlopen(url), x, y, zoom)
            break
        except e:
            print "Oops! something went wrong downloading '%s': %s" % (url, e.message)
            print "Trying again..."


def main():
    # parse the command-line
    usage = '''%prog [options] <dbfile>
    
Download images from Google Maps for use with Maemo Mapper.
Try '%prog --help' for a description of all options.'''
    
    parser = OptionParser (usage=usage)
    parser.add_option ("-t", "--start-lat",
                       dest="startlat",  help="start latitude (x)",
                       type="float")
    parser.add_option ("-l", "--start-long",
                       dest="startlong", help="start longitude (y)",
                       type="float")
    parser.add_option ("-b", "--end-lat",
                       dest="endlat",    help="end latitude (x)",
                       type="float")
    parser.add_option ("-r", "--end-long",
                       dest="endlong",   help="end longitude (y)",
                       type="float")
    parser.add_option ("-z", "--zoom",
                       dest="zoom",      help="zoom level (may be used multiple times)",
                       type="int", action="append")
    
    (options, args) = parser.parse_args ()
    
    if len (args) != 1:
        parser.error ("incorrect number of arguments")
    
    # open a connection to the database
    dbConnection = sqlite3.connect (args[0])
    db = dbConnection.cursor ()
    
    # create the table, failing silently if it already exists
    try:
        db.execute ('''create table maps (
            zoom integer,
            tilex integer,
            tiley integer,
            pixbuf blob,
            primary key (zoom, tilex, tiley));''')
    except:
        pass
    
    # calculate the number of requested tiles beforehand
    numTiles = 0
    for zoom in options.zoom:
        (rangex, rangey) = getTiles (options.startlat, options.endlat,
                                     options.startlong, options.endlong,
                                     zoom)
        numTiles += len(rangex) * len(rangey)
    
    print "You asked for %d tiles" % (numTiles)
    
    # loop over all zoom levels and retrieve all tiles
    i = 0
    for zoom in options.zoom:
        (rangex, rangey) = getTiles (options.startlat, options.endlat,
                                     options.startlong, options.endlong,
                                     zoom)
        for x in rangex:
            for y in rangey:
                i = i + 1
                loadTile (db, x, y, zoom, i, numTiles)
                # force a commit every once in a while
                if i % 100 == 0:
                    dbConnection.commit ()
    
    # close the connection to the database and trigger a final commit
    db.close ()
    dbConnection.commit ()


if __name__ == "__main__":
    main()
