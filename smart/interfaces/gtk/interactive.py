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
from smart.transaction import INSTALL, REMOVE, UPGRADE, REINSTALL, KEEP, FIX
from smart.transaction import Transaction, ChangeSet
from smart.transaction import PolicyInstall, PolicyRemove, PolicyUpgrade
from smart.interfaces.gtk.channels import GtkChannels, GtkChannelSelector
from smart.interfaces.gtk.mirrors import GtkMirrors
from smart.interfaces.gtk.flags import GtkFlags
from smart.interfaces.gtk.priorities import GtkPriorities, GtkSinglePriority
from smart.interfaces.gtk.packageview import GtkPackageView
from smart.interfaces.gtk.packageinfo import GtkPackageInfo
from smart.interfaces.gtk.interface import GtkInterface
from smart.interfaces.gtk import getPixbuf
from smart.const import NEVER, VERSION
from smart import *
import shlex, re
import fnmatch
import gtk

UI = """
<ui>
<menubar>
    <menu action="file">
        <menuitem action="update-selected-channels"/>
        <menuitem action="update-channels"/>
        <separator/>
        <menuitem action="rebuild-cache"/>
        <separator/>
        <menuitem action="exec-changes"/>
        <separator/>
        <menuitem action="quit"/>
    </menu>
    <menu action="edit">
        <menuitem action="undo"/>
        <menuitem action="redo"/>
        <menuitem action="clear-changes"/>
        <separator/>
        <menuitem action="upgrade-all"/>
        <menuitem action="fix-all-problems"/>
        <separator/>
        <menuitem action="find"/>
        <separator/>
        <menuitem action="edit-channels"/>
        <menuitem action="edit-mirrors"/>
        <menuitem action="edit-flags"/>
        <menuitem action="edit-priorities"/>
    </menu>
    <menu action="view">
        <menuitem action="hide-non-upgrades"/>
        <menuitem action="hide-installed"/>
        <menuitem action="hide-uninstalled"/>
        <menuitem action="hide-unmarked"/>
        <menuitem action="hide-old"/>
        <separator/>
        <menuitem action="expand-all"/>
        <menuitem action="collapse-all"/>
        <separator/>
        <menu action="tree-style">
            <menuitem action="tree-style-groups"/>
            <menuitem action="tree-style-channels"/>
            <menuitem action="tree-style-channels-groups"/>
            <menuitem action="tree-style-none"/>
        </menu>
        <separator/>
        <menuitem action="summary-window"/>
        <menuitem action="log-window"/>
    </menu>
</menubar>
<toolbar>
    <toolitem action="update-channels"/>
    <separator/>
    <toolitem action="exec-changes"/>
    <separator/>
    <toolitem action="undo"/>
    <toolitem action="redo"/>
    <toolitem action="clear-changes"/>
    <separator/>
    <toolitem action="upgrade-all"/>
    <separator/>
    <toolitem action="find"/>
</toolbar>
</ui>
"""

ACTIONS = [
    ("file", None, "_File"),
    ("update-selected-channels", "gtk-refresh", "Update _Selected Channels...", None,
     "Update given channels", "self.updateChannels(True)"),
    ("update-channels", "gtk-refresh", "_Update Channels", None,
     "Update channels", "self.updateChannels()"),
    ("rebuild-cache", None, "_Rebuild Cache", None,
     "Reload package information", "self.rebuildCache()"),
    ("exec-changes", "gtk-execute", "_Execute Changes...", "<control>c",
     "Apply marked changes", "self.applyChanges()"),
    ("quit", "gtk-quit", "_Quit", "<control>q",
     "Quit application", "gtk.main_quit()"),

    ("edit", None, "_Edit"),
    ("undo", "gtk-undo", "_Undo", "<control>z",
     "Undo last change", "self.undo()"),
    ("redo", "gtk-redo", "_Redo", "<control><shift>z",
     "Redo last undone change", "self.redo()"),
    ("clear-changes", "gtk-clear", "Clear Marked Changes", None,
     "Clear all changes", "self.clearChanges()"),
    ("upgrade-all", "gtk-go-up", "Upgrade _All...", None,
     "Upgrade all packages", "self.upgradeAll()"),
    ("fix-all-problems", None, "Fix All _Problems...", None,
     "Fix all problems", "self.fixAllProblems()"),
    ("find", "gtk-find", "_Find...", "<control>f",
     "Find packages", "self.toggleSearch()"),
    ("edit-channels", None, "_Channels", None,
     "Edit channels", "self.editChannels()"),
    ("edit-mirrors", None, "_Mirrors", None,
     "Edit mirrors", "self.editMirrors()"),
    ("edit-flags", None, "_Flags", None,
     "Edit package flags", "self.editFlags()"),
    ("edit-priorities", None, "_Priorities", None,
     "Edit package priorities", "self.editPriorities()"),

    ("view", None, "_View"),
    ("tree-style", None, "_Tree Style"),
    ("expand-all", "gtk-open", "_Expand All", None,
     "Expand all items in the tree", "self._pv.getTreeView().expand_all()"),
    ("collapse-all", "gtk-close", "_Collapse All", None,
     "Collapse all items in the tree", "self._pv.getTreeView().collapse_all()"),
    ("summary-window", None, "_Summary Window", "<control>s",
     "Show summary window", "self.showChanges()"),
    ("log-window", None, "_Log Window", None,
     "Show log window", "self._log.show()"),
]

def compileActions(actions, globals):
    newactions = []
    for action in actions:
        if len(action) > 5:
            action = list(action)
            code = compile(action[5], "<callback>", "exec")
            def callback(action, code=code, globals=globals):
                globals["action"] = action
                exec code in globals
            action[5] = callback
        newactions.append(tuple(action))
    return newactions

class GtkInteractiveInterface(GtkInterface):

    def __init__(self, ctrl):
        GtkInterface.__init__(self, ctrl)

        self._changeset = ChangeSet(self._ctrl.getCache())

        self._window = gtk.Window()
        self._window.set_title("Smart Package Manager %s" % VERSION)
        self._window.set_position(gtk.WIN_POS_CENTER)
        self._window.set_geometry_hints(min_width=640, min_height=480)
        self._window.connect("destroy", lambda x: gtk.main_quit())

        self._log.set_transient_for(self._window)
        self._progress.set_transient_for(self._window)
        self._hassubprogress.set_transient_for(self._window)

        self._watch = gtk.gdk.Cursor(gtk.gdk.WATCH)

        self._undo = []
        self._redo = []

        self._topvbox = gtk.VBox()
        self._topvbox.show()
        self._window.add(self._topvbox)

        globals = {"self": self, "gtk": gtk}
        self._actions = gtk.ActionGroup("Actions")
        self._actions.add_actions(compileActions(ACTIONS, globals))

        filters = sysconf.get("package-filters", {})
        for name, label in [("hide-non-upgrades", "Hide Non-upgrades"),
                            ("hide-installed", "Hide Installed"),
                            ("hide-uninstalled", "Hide Uninstalled"),
                            ("hide-unmarked", "Hide Unmarked"),
                            ("hide-old", "Hide Old")]:
            action = gtk.ToggleAction(name, label, "", "")
            if name in filters:
                action.set_active(True)
            action.connect("toggled", lambda x, y: self.toggleFilter(y), name)
            self._actions.add_action(action)

        treestyle = sysconf.get("package-tree", {})
        lastaction = None
        for name, label in [("groups", "Groups"),
                            ("channels", "Channels"),
                            ("channels-groups", "Channels & Groups"),
                            ("none", "None")]:
            action = gtk.RadioAction("tree-style-"+name, label, "", "", 0)
            if name == treestyle:
                action.set_active(True)
            if lastaction:
                action.set_group(lastaction)
            lastaction = action
            action.connect("toggled", lambda x, y: self.setTreeStyle(y), name)
            self._actions.add_action(action)

        self._ui = gtk.UIManager()
        self._ui.insert_action_group(self._actions, 0)
        self._ui.add_ui_from_string(UI)
        self._menubar = self._ui.get_widget("/menubar")
        self._topvbox.pack_start(self._menubar, False)

        self._toolbar = self._ui.get_widget("/toolbar")
        self._toolbar.set_style(gtk.TOOLBAR_ICONS)
        self._topvbox.pack_start(self._toolbar, False)

        self._window.add_accel_group(self._ui.get_accel_group())

        self._execmenuitem = self._ui.get_action("/menubar/file/exec-changes")
        self._execmenuitem.set_property("sensitive", False)
        self._clearmenuitem = self._ui.get_action("/menubar/edit/clear-changes")
        self._clearmenuitem.set_property("sensitive", False)
        self._undomenuitem = self._ui.get_action("/menubar/edit/undo")
        self._undomenuitem.set_property("sensitive", False)
        self._redomenuitem = self._ui.get_action("/menubar/edit/redo")
        self._redomenuitem.set_property("sensitive", False)

        # Search bar

        self._searchbar = gtk.Alignment()
        self._searchbar.set(0, 0, 1, 1)
        self._searchbar.set_padding(3, 3, 0, 0)
        self._topvbox.pack_start(self._searchbar, False)

        searchvp = gtk.Viewport()
        searchvp.set_shadow_type(gtk.SHADOW_OUT)
        searchvp.show()
        self._searchbar.add(searchvp)

        searchtable = gtk.Table(1, 1)
        searchtable.set_row_spacings(5)
        searchtable.set_col_spacings(5)
        searchtable.set_border_width(5)
        searchtable.show()
        searchvp.add(searchtable)

        label = gtk.Label("Search:")
        label.show()
        searchtable.attach(label, 0, 1, 0, 1, 0, 0)

        self._searchentry = gtk.Entry()
        self._searchentry.connect("activate", lambda x: self.refreshPackages())
        self._searchentry.show()
        searchtable.attach(self._searchentry, 1, 2, 0, 1)

        button = gtk.Button()
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", lambda x: self.refreshPackages())
        button.show()
        searchtable.attach(button, 2, 3, 0, 1, 0, 0)
        image = gtk.Image()
        image.set_from_stock("gtk-find", gtk.ICON_SIZE_BUTTON)
        image.show()
        button.add(image)

        align = gtk.Alignment()
        align.set(1, 0, 0, 0)
        align.set_padding(0, 0, 10, 0)
        align.show()
        searchtable.attach(align, 3, 4, 0, 1, gtk.FILL, gtk.FILL)
        button = gtk.Button()
        button.set_size_request(20, 20)
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", lambda x: self.toggleSearch())
        button.show()
        align.add(button)
        image = gtk.Image()
        image.set_from_stock("gtk-close", gtk.ICON_SIZE_MENU)
        image.show()
        button.add(image)

        hbox = gtk.HBox()
        hbox.set_spacing(10)
        hbox.show()
        searchtable.attach(hbox, 1, 2, 1, 2)

        self._searchname = gtk.RadioButton(None, "Name")
        self._searchname.set_active(True)
        self._searchname.connect("clicked", lambda x: self.refreshPackages())
        self._searchname.show()
        hbox.pack_start(self._searchname, False)
        self._searchdesc = gtk.RadioButton(self._searchname, "Description")
        self._searchdesc.connect("clicked", lambda x: self.refreshPackages())
        self._searchdesc.show()
        hbox.pack_start(self._searchdesc, False)
        self._searchpath = gtk.RadioButton(self._searchname, "Content")
        self._searchpath.connect("clicked", lambda x: self.refreshPackages())
        self._searchpath.show()
        hbox.pack_start(self._searchpath, False)

        # Packages and information

        self._vpaned = gtk.VPaned()
        self._vpaned.show()
        self._topvbox.pack_start(self._vpaned)

        self._pv = GtkPackageView()
        self._pv.show()
        self._vpaned.pack1(self._pv, True)

        self._pi = GtkPackageInfo()
        self._pi.setChangeSet(self._changeset)
        self._pi.show()
        self._pv.connect("package_selected",
                         lambda x, y: self._pi.setPackage(y))
        self._pv.connect("package_activated",
                         lambda x, y: self.actOnPackages(y))
        self._pv.connect("package_popup", self.packagePopup)
        self._vpaned.pack2(self._pi, False)

        self._status = gtk.Statusbar()
        self._status.show()
        self._topvbox.pack_start(self._status, False)

    def showStatus(self, msg):
        self._status.pop(0)
        self._status.push(0, msg)

    def hideStatus(self):
        self._status.pop(0)

    def run(self, command=None, argv=None):
        self.setCatchExceptions(True)
        self._window.show()
        self._ctrl.updateCache()
        self._progress.hide()
        self.refreshPackages()
        gtk.main()
        self.setCatchExceptions(False)

    # Non-standard interface methods:

    def getChangeSet(self):
        return self._changeset

    def updateChannels(self, selected=False):
        channels = None
        if selected:
            aliases = GtkChannelSelector().show()
            channels = [channel for channel in self._ctrl.getChannels()
                        if channel.getAlias() in aliases]
            if not channels:
                return
        state = self._changeset.getPersistentState()
        self._ctrl.updateCache(channels, caching=NEVER)
        self._changeset.setPersistentState(state)
        self.refreshPackages()

    def rebuildCache(self):
        state = self._changeset.getPersistentState()
        self._ctrl.updateCache()
        self._changeset.setPersistentState(state)
        self.refreshPackages()

    def applyChanges(self):
        transaction = Transaction(self._ctrl.getCache(),
                                  changeset=self._changeset)
        if self._ctrl.commitTransaction(transaction):
            del self._undo[:]
            del self._redo[:]
            self._redomenuitem.set_property("sensitive", False)
            self._undomenuitem.set_property("sensitive", False)
            self._changeset.clear()
            self._ctrl.updateCache()
            self.refreshPackages()
            self.changedMarks()
        self._progress.hide()

    def clearChanges(self):
        self.saveUndo()
        self._changeset.clear()
        self.changedMarks()

    def showChanges(self):
        return self._changes.showChangeSet(self._changeset)

    def toggleFilter(self, filter):
        filters = sysconf.get("package-filters", {})
        if filter in filters:
            del filters[filter]
        else:
            filters[filter] = True
        sysconf.set("package-filters", filters)
        self.refreshPackages()

    def upgradeAll(self):
        transaction = Transaction(self._ctrl.getCache())
        transaction.setState(self._changeset)
        for pkg in self._ctrl.getCache().getPackages():
            if pkg.installed:
                transaction.enqueue(pkg, UPGRADE)
        transaction.setPolicy(PolicyUpgrade)
        transaction.run()
        changeset = transaction.getChangeSet()
        if changeset != self._changeset:
            if self.confirmChange(self._changeset, changeset):
                self.saveUndo()
                self._changeset.setState(changeset)
                self.changedMarks()
                if self.askYesNo("Apply marked changes now", True):
                    self.applyChanges()
        else:
            self.showStatus("No interesting upgrades available!")

    def actOnPackages(self, pkgs, op=None):
        transaction = Transaction(self._ctrl.getCache(), policy=PolicyInstall)
        transaction.setState(self._changeset)
        changeset = transaction.getChangeSet()
        if op is None:
            if not [pkg for pkg in pkgs if pkg not in changeset]:
                op = KEEP
            else:
                for pkg in pkgs:
                    if not pkg.installed:
                        op = INSTALL
                        break
                else:
                    op = REMOVE
        for pkg in pkgs:
            if op is KEEP:
                transaction.enqueue(pkg, op)
            elif op in (REMOVE, REINSTALL, FIX):
                if pkg.installed:
                    transaction.enqueue(pkg, op)
            elif op is INSTALL:
                if not pkg.installed:
                    transaction.enqueue(pkg, op)
        transaction.run()
        if op is FIX:
            expected = 0
        else:
            expected = 1
        if self.confirmChange(self._changeset, changeset, expected):
            self.saveUndo()
            self._changeset.setState(changeset)
            self.changedMarks()

    def packagePopup(self, packageview, pkgs, event):

        menu = gtk.Menu()

        hasinstalled = bool([pkg for pkg in pkgs if pkg.installed
                             and self._changeset.get(pkg) is not REMOVE])
        hasnoninstalled = bool([pkg for pkg in pkgs if not pkg.installed
                                and self._changeset.get(pkg) is not INSTALL])

        image = gtk.Image()
        image.set_from_pixbuf(getPixbuf("package-install"))
        item = gtk.ImageMenuItem("Install")
        item.set_image(image)
        item.connect("activate", lambda x: self.actOnPackages(pkgs, INSTALL))
        if not hasnoninstalled:
            item.set_sensitive(False)
        menu.append(item)

        image = gtk.Image()
        image.set_from_pixbuf(getPixbuf("package-reinstall"))
        item = gtk.ImageMenuItem("Reinstall")
        item.set_image(image)
        item.connect("activate", lambda x: self.actOnPackages(pkgs, INSTALL))
        if not hasinstalled:
            item.set_sensitive(False)
        menu.append(item)


        image = gtk.Image()
        image.set_from_pixbuf(getPixbuf("package-remove"))
        item = gtk.ImageMenuItem("Remove")
        item.set_image(image)
        item.connect("activate", lambda x: self.actOnPackages(pkgs, REMOVE))
        if not hasinstalled:
            item.set_sensitive(False)
        menu.append(item)

        image = gtk.Image()
        if not hasinstalled:
            image.set_from_pixbuf(getPixbuf("package-available"))
        else:
            image.set_from_pixbuf(getPixbuf("package-installed"))
        item = gtk.ImageMenuItem("Keep")
        item.set_image(image)
        item.connect("activate", lambda x: self.actOnPackages(pkgs, KEEP))
        if not [pkg for pkg in pkgs if pkg in self._changeset]:
            item.set_sensitive(False)
        menu.append(item)

        image = gtk.Image()
        image.set_from_pixbuf(getPixbuf("package-broken"))
        item = gtk.ImageMenuItem("Fix problems")
        item.set_image(image)
        item.connect("activate", lambda x: self.actOnPackages(pkgs, FIX))
        if not hasinstalled:
            item.set_sensitive(False)
        menu.append(item)

        inconsistent = False
        thislocked = None
        alllocked = None
        names = sysconf.get("package-flags", setdefault={}) \
                                    .setdefault("lock", {})
        if [pkg for pkg in pkgs if pkg in self._changeset]:
            inconsistent = True
        else:
            for pkg in pkgs:
                if (names and pkg.name in names and 
                    ("=", pkg.version) in names[pkg.name]):
                    newthislocked = True
                    newalllocked = len(names[pkg.name]) > 1
                else:
                    newthislocked = False
                    newalllocked = sysconf.testFlag("lock", pkg)
                if (thislocked is not None and thislocked != newthislocked or
                    alllocked is not None and alllocked != newalllocked):
                    inconsistent = True
                    break
                thislocked = newthislocked
                alllocked = newalllocked

        image = gtk.Image()
        if thislocked:
            item = gtk.ImageMenuItem("Unlock this version")
            if not hasnoninstalled:
                image.set_from_pixbuf(getPixbuf("package-installed"))
            else:
                image.set_from_pixbuf(getPixbuf("package-available"))
            def unlock_this(x):
                for pkg in pkgs:
                    names[pkg.name].remove(("=", pkg.version))
                self._pv.queue_draw()
                self._pi.setPackage(pkgs[0])
            item.connect("activate", unlock_this)
        else:
            item = gtk.ImageMenuItem("Lock this version")
            if not hasnoninstalled:
                image.set_from_pixbuf(getPixbuf("package-installed-locked"))
            else:
                image.set_from_pixbuf(getPixbuf("package-available-locked"))
            def lock_this(x):
                for pkg in pkgs:
                    names.setdefault(pkg.name, []).append(("=", pkg.version))
                self._pv.queue_draw()
                self._pi.setPackage(pkgs[0])
            item.connect("activate", lock_this)
        item.set_image(image)
        if inconsistent:
            item.set_sensitive(False)
        menu.append(item)

        image = gtk.Image()
        if alllocked:
            item = gtk.ImageMenuItem("Unlock all versions")
            if not hasnoninstalled:
                image.set_from_pixbuf(getPixbuf("package-installed"))
            else:
                image.set_from_pixbuf(getPixbuf("package-available"))
            def unlock_all(x):
                for pkg in pkgs:
                    del names[pkg.name]
                self._pv.queue_draw()
                self._pi.setPackage(pkgs[0])
            item.connect("activate", unlock_all)
        else:
            item = gtk.ImageMenuItem("Lock all versions")
            if not hasnoninstalled:
                image.set_from_pixbuf(getPixbuf("package-installed-locked"))
            else:
                image.set_from_pixbuf(getPixbuf("package-available-locked"))
            def lock_all(x):
                for pkg in pkgs:
                    names.setdefault(pkg.name, []).append((None, None))
                self._pv.queue_draw()
                self._pi.setPackage(pkgs[0])
            item.connect("activate", lock_all)
        item.set_image(image)
        if inconsistent:
            item.set_sensitive(False)
        menu.append(item)

        item = gtk.MenuItem("Priority")
        def priority(x):
            GtkSinglePriority(self._window).show(pkgs[0])
            self._pi.setPackage(pkgs[0])
        item.connect("activate", priority)
        if len(pkgs) != 1:
            item.set_sensitive(False)
        menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, event.button, event.time)

    def fixAllProblems(self):
        self.actOnPackages([pkg for pkg in self._ctrl.getCache().getPackages()
                            if pkg.installed], FIX)

    def undo(self):
        if self._undo:
            state = self._undo.pop(0)
            if not self._undo:
                self._undomenuitem.set_property("sensitive", False)
            self._redo.insert(0, self._changeset.getPersistentState())
            self._redomenuitem.set_property("sensitive", True)
            self._changeset.setPersistentState(state)
            self.changedMarks()

    def redo(self):
        if self._redo:
            state = self._redo.pop(0)
            if not self._redo:
                self._redomenuitem.set_property("sensitive", False)
            self._undo.insert(0, self._changeset.getPersistentState())
            self._undomenuitem.set_property("sensitive", True)
            self._changeset.setPersistentState(state)
            self.changedMarks()

    def saveUndo(self):
        self._undo.insert(0, self._changeset.getPersistentState())
        del self._redo[:]
        del self._undo[20:]
        self._undomenuitem.set_property("sensitive", True)
        self._redomenuitem.set_property("sensitive", False)

    def setTreeStyle(self, mode):
        if mode != sysconf.get("package-tree"):
            sysconf.set("package-tree", mode)
            self.refreshPackages()

    def editChannels(self):
        if GtkChannels(self._window).show():
            self.rebuildCache()

    def editMirrors(self):
        GtkMirrors(self._window).show()

    def editFlags(self):
        GtkFlags(self._window).show()

    def editPriorities(self):
        GtkPriorities(self._window).show()

    def setBusy(self, flag):
        if flag:
            self._window.window.set_cursor(self._watch)
            while gtk.events_pending():
                gtk.main_iteration()
        else:
            self._window.window.set_cursor(None)

    def changedMarks(self):
        if "hide-unmarked" in sysconf.get("package-filters", {}):
            self.refreshPackages()
        else:
            self._pv.queue_draw()
        self._execmenuitem.set_property("sensitive", bool(self._changeset))
        self._clearmenuitem.set_property("sensitive", bool(self._changeset))

    def toggleSearch(self):
        visible = not self._searchbar.get_property('visible')
        self._searchbar.set_property('visible', visible)
        self.refreshPackages()
        if visible:
            self._searchentry.grab_focus()

    def refreshPackages(self):
        if not self._ctrl:
            return

        self.setBusy(True)

        tree = sysconf.get("package-tree", "groups")
        ctrl = self._ctrl
        packages = ctrl.getCache().getPackages()

        filters = sysconf.get("package-filters", {})

        changeset = self._changeset

        if filters:
            if "hide-non-upgrades" in filters:
                newpackages = {}
                for pkg in packages:
                    if pkg.installed:
                        upgpkgs = {}
                        try:
                            for prv in pkg.provides:
                                for upg in prv.upgradedby:
                                    for upgpkg in upg.packages:
                                        if upgpkg.installed:
                                            raise StopIteration
                                        upgpkgs[upgpkg] = True
                        except StopIteration:
                            pass
                        else:
                            newpackages.update(upgpkgs)
                packages = newpackages.keys()
            if "hide-uninstalled" in filters:
                packages = [x for x in packages if x.installed]
            if "hide-unmarked" in filters:
                packages = [x for x in packages if x in changeset]
            if "hide-installed" in filters:
                packages = [x for x in packages if not x.installed]
            if "hide-old" in filters:
                packages = sysconf.filterByFlag("new", packages)

        if self._searchbar.get_property("visible"):
            search = []
            for tok in shlex.split(self._searchentry.get_text()):
                tok = fnmatch.translate(tok)[:-1].replace(r"\ ", " ")
                tok = r"\s+".join(tok.split())
                search.append(re.compile(tok))
            if not search:
                packages = []
            else:
                desc = self._searchdesc.get_active()
                path = self._searchpath.get_active()
                newpackages = []
                for pkg in packages:
                    for pat in search:
                        if desc:
                            info = pkg.loaders.keys()[0].getInfo(pkg)
                            if pat.search(info.getDescription()):
                                newpackages.append(pkg)
                                break
                        elif path:
                            info = pkg.loaders.keys()[0].getInfo(pkg)
                            for path in info.getPathList():
                                if pat.search(path):
                                   newpackages.append(pkg)
                                   break
                            else:
                                continue
                            break
                        elif pat.search(pkg.name):
                            newpackages.append(pkg)
                            break
                packages = newpackages

        if tree == "groups":
            groups = {}
            done = {}
            for pkg in packages:
                lastgroup = None
                for loader in pkg.loaders:
                    info = loader.getInfo(pkg)
                    group = info.getGroup()
                    donetuple = (group, pkg)
                    if donetuple not in done:
                        done[donetuple] = True
                        if group in groups:
                            groups[group].append(pkg)
                        else:
                            groups[group] = [pkg]

        elif tree == "channels":
            groups = {}
            done = {}
            for pkg in packages:
                for loader in pkg.loaders:
                    channel = loader.getChannel()
                    group = channel.getName() or channel.getAlias()
                    donetuple = (group, pkg)
                    if donetuple not in done:
                        done[donetuple] = True
                        if group in groups:
                            groups[group].append(pkg)
                        else:
                            groups[group] = [pkg]

        elif tree == "channels-groups":
            groups = {}
            done = {}
            for pkg in packages:
                for loader in pkg.loaders:
                    channel = loader.getChannel()
                    group = channel.getName() or channel.getAlias()
                    subgroup = loader.getInfo(pkg).getGroup()
                    donetuple = (group, subgroup, pkg)
                    if donetuple not in done:
                        done[donetuple] = True
                        if group in groups:
                            if subgroup in groups[group]:
                                groups[group][subgroup].append(pkg)
                            else:
                                groups[group][subgroup] = [pkg]
                        else:
                            groups[group] = {subgroup: [pkg]}

        else:
            groups = packages

        self._pv.setPackages(groups, changeset, keepstate=True)

        if filters:
            self.showStatus("There are filters being applied!")
        else:
            self.hideStatus()

        self.setBusy(False)


# vim:ts=4:sw=4:et
