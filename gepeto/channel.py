#
# Copyright (c) 2004 Conectiva, Inc.
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Gepeto.
#
# Gepeto is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Gepeto is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gepeto; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from gepeto import *
import os

DEFAULTFIELDS = [("alias", "Alias",
                  "Unique identification for the channel."),
                 ("type", "Type", "Channel type"),
                 ("name", "Name", "Channel name"),
                 ("description", "Description",
                  "Channel description"),
                 ("priority", "Priority",
                  "Default priority assigned to all packages "
                  "available in this channel (0 if not set). If "
                  "the exact same package is available in more "
                  "than one channel, the highest priority is used."),
                 ("manual", "Manual updates",
                  "If set to a true value ('yes', 'true', etc), "
                  "the given channel will only be updated when "
                  "manually selected."),
                 ("disabled", "Disabled",
                  "If set to a true value ('yes', 'true', etc), "
                  "the given channel won't be used."),
                 ("removable", "Removable",
                  "If set to a true value ('yes', 'true', etc), "
                  "the given channel will be considered as being "
                  "available in a removable media (cdrom, etc).")]

class Channel(object):

    def __init__(self, type, alias, name=None, description=None,
                 priority=0, manualupdate=False, removable=False):
        self._type = type
        self._alias = alias
        self._name = name
        self._description = description
        self._priority = priority
        self._loader = None
        self._loadorder = 1000
        self._manualupdate = manualupdate
        self._removable = removable

    def getType(self):
        return self._type

    def getAlias(self):
        return self._alias

    def getName(self):
        return self._name

    def getDescription(self):
        return self._description

    def getPriority(self):
        return self._priority

    def hasManualUpdate(self):
        return self._removable or self._manualupdate

    def isRemovable(self):
        return self._removable

    def getLoader(self):
        return self._loader

    def getLoadOrder(self):
        return self._loadorder

    def __cmp__(self, other):
        if isinstance(other, Channel):
            return cmp(self._loadorder, other._loadorder)
        return -1

    def getFetchSteps(self):
        return 0

    def getCacheCompareURLs(self):
        """
        URLs returned by this method are used to check if a
        repository is currently available by comparing fetched
        information with cached information.
        """
        return []

    def fetch(self, fetcher, progress):
        """
        Fetch metafiles and set loader. This method implements a
        scheme that allows one to use a single logic to fetch remote
        files and also to load local cached information, depending
        on the caching mode of the fetcher.
        """
        pass

class FileChannel(Channel):
    def __init__(self, filename, name=None, description=None, priority=0):
        alias = os.path.abspath(filename)
        if name is None:
            name = os.path.basename(filename)
        if not os.path.isfile(filename):
            raise Error, "File not found: %s" % filename
        super(FileChannel, self).__init__("file", alias, name, description,
                                          priority, manualupdate=True)
        loaders = filter(None, hooks.call("FileChannel.getLoader", filename))
        if not loaders:
            raise Error, "Unable to find loader for file: %s" % filename
        self._loader = loaders[0]


class ChannelDataError(Error): pass

def createChannel(type, alias, data):
    try:
        xtype = type.replace('-', '_').lower()
        gepeto = __import__("gepeto.channels."+xtype)
        channels = getattr(gepeto, "channels")
        channel = getattr(channels, xtype)
    except (ImportError, AttributeError):
        from gepeto.const import DEBUG
        if sysconf.get("log-level") == DEBUG:
            import traceback
            traceback.print_exc()
        raise Error, "Invalid channel type '%s'" % type
    try:
        return channel.create(type, alias, data)
    except ChannelDataError:
        raise Error, "Channel type %s doesn't support %s" % (type, `data`)

def createChannelDescription(type, alias, data):
    lines = []
    lines.append("[%s]" % alias)
    lines.append("type = %s" % type)
    first = ("name", "description")
    for key in first:
        if key in ("type", "alias"):
            continue
        if key in data:
            lines.append("%s = %s" % (key, data[key]))
    keys = data.keys()
    keys.sort()
    for key in keys:
        if key in ("type", "alias"):
            continue
        if key not in first:
            lines.append("%s = %s" % (key, data[key]))
    return "\n".join(lines)

def parseChannelDescription(data):
    channels = {}
    current = None
    alias = None
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) > 2 and line[0] == "[" and line[-1] == "]":
            if current and "type" not in current:
                raise Error, "Channel '%s' has no type" % alias
            alias = line[1:-1].strip()
            current = {}
            channels[alias] = current
        elif current is not None and not line[0] == "#" and "=" in line:
            key, value = line.split("=")
            current[key.strip().lower()] = value.strip()
    return channels

def getChannelInfo(type):
    try:
        infoname = type.replace('-', '_').lower()+"_info"
        gepeto = __import__("gepeto.channels."+infoname)
        channels = getattr(gepeto, "channels")
        info = getattr(channels, infoname)
    except (ImportError, AttributeError):
        from gepeto.const import DEBUG
        if sysconf.get("log-level") == DEBUG:
            import traceback
            traceback.print_exc()
        raise Error, "Invalid channel type '%s'" % type
    return info

def getAllChannelInfos():
    from gepeto import channels
    filenames = os.listdir(os.path.dirname(channels.__file__))
    infos = {}
    for filename in filenames:
        if filename.endswith("_info.py"):
            type = filename[:-8].replace("_", "-")
            infos[type] = getChannelInfo(type)
    return infos

# vim:ts=4:sw=4:et
