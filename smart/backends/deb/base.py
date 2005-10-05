#
# Copyright (c) 2004 Conectiva, Inc.
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Smart Package Manager.
#
# Smart Package Manager is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# Smart Package Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Smart Package Manager; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from smart.backends.deb.debver import vercmp, checkdep, splitrelease
from smart.backends.deb.pm import DebPackageManager
from smart.util.strtools import isGlob
from smart.cache import *
import fnmatch
import string
import os, re

__all__ = ["DebPackage", "DebProvides", "DebNameProvides", "DebPreRequires",
           "DebRequires", "DebUpgrades", "DebConflicts", "DebOrRequires",
           "DebOrPreRequires"]

def getArchitecture():
    arch = os.uname()[-1]
    result = {"pentium": "i386",
              "sparc64": "sparc",
              "ppc": "powerpc",
              "mipseb":	"mips",
              "shel": "sh",
              "x86_64": "amd64"}.get(arch)
    if result:
        return result
    elif len(arch) == 4 and arch[0] == "i" and arch.endswith("86"):
        return "i386"
    elif arch.startswith("arm"):
        return "arm"
    elif arch.startswith("hppa"):
        return "hppa"
    elif arch.startswith("alpha"):
        return "alpha"
    else:
        return arch

DEBARCH = sysconf.get("deb-arch", getArchitecture())

class DebPackage(Package):

    __slots__ = ()

    packagemanager = DebPackageManager
    
    def coexists(self, other):
        if not isinstance(other, DebPackage):
            return True
        return False

    def matches(self, relation, version):
        if not relation:
            return True
        return checkdep(self.version, relation, version)

    def search(self, searcher):
        myname = self.name
        myversion = self.version
        ratio = 0
        ic = searcher.ignorecase
        for nameversion, cutoff in searcher.nameversion:
            _, ratio1 = globdistance(nameversion, myname, cutoff, ic)
            _, ratio2 = globdistance(nameversion,
                                     "%s_%s" % (myname, myversion), cutoff, ic)
            _, ratio3 = globdistance(nameversion, "%s_%s" %
                                     (myname, splitrelease(myversion)[0]),
                                     cutoff, ic)
            ratio = max(ratio, ratio1, ratio2, ratio3)
        if ratio:
            searcher.addResult(self, ratio)

    def __lt__(self, other):
        rc = cmp(self.name, other.name)
        if type(other) is DebPackage:
            if rc == 0 and self.version != other.version:
                rc = vercmp(self.version, other.version)
        return rc == -1

    def __str__(self):
        return "%s_%s" % (self.name, self.version)

class DebProvides(Provides):        __slots__ = ()
class DebNameProvides(DebProvides): __slots__ = ()

class DebDepends(Depends):

    __slots__ = ()

    def matches(self, prv):
        if not isinstance(prv, DebProvides) and type(prv) is not Provides:
            return False
        if not self.version:
            return True
        if not prv.version:
            return False
        return checkdep(prv.version, self.relation, self.version)

class DebPreRequires(DebDepends,PreRequires): __slots__ = ()
class DebRequires(DebDepends,Requires):       __slots__ = ()

class DebOrDepends(Depends):

    __slots__ = ("_nrv",)

    def __init__(self, nrv):
        name = " | ".join([(x[2] and " ".join(x) or x[0]) for x in nrv])
        Depends.__init__(self, name, None, None)
        self._nrv = nrv

    def getInitArgs(self):
        return (self.__class__, self._nrv)

    def getMatchNames(self):
        return [x[0] for x in self._nrv]

    def matches(self, prv):
        if not isinstance(prv, DebProvides) and type(prv) is not Provides:
            return False
        for name, relation, version in self._nrv:
            if name == prv.name:
                if not version:
                    return True
                if not prv.version:
                    continue
                if checkdep(prv.version, relation, version):
                    return True
        return False

    def __reduce__(self):
        return (self.__class__, (self._nrv,))

class DebOrRequires(DebOrDepends,Requires):       __slots__ = ()
class DebOrPreRequires(DebOrDepends,PreRequires): __slots__ = ()

class DebUpgrades(DebDepends,Upgrades):

    __slots__ = ()

    def matches(self, prv):
        if not isinstance(prv, DebNameProvides) and type(prv) is not Provides:
            return False
        if not self.version or not prv.version:
            return True
        return checkdep(prv.version, self.relation, self.version)

class DebConflicts(DebDepends,Conflicts): __slots__ = ()

def enablePsyco(psyco):
    psyco.bind(DebPackage.coexists)
    psyco.bind(DebPackage.matches)
    psyco.bind(DebPackage.search)
    psyco.bind(DebPackage.__lt__)
    psyco.bind(DebDepends.matches)
    psyco.bind(DebOrDepends.matches)
    psyco.bind(DebUpgrades.matches)

hooks.register("enable-psyco", enablePsyco)

# vim:ts=4:sw=4:et
