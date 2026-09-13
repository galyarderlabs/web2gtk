import gi

gi.require_version('Gio', '2.0')
gi.require_version('GLib', '2.0')
gi.require_version('Dbusmenu', '0.4')

from gi.repository import Gio, GLib, Dbusmenu

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""


class StatusNotifierTray:
    def __init__(self, app, window, manifest):
        self.app = app
        self.window = window
        self.manifest = manifest
        self._status = "Active"
        self._title = self.manifest.name
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.node_info = Gio.DBusNodeInfo.new_for_xml(SNI_XML)

        safe_slug = self.manifest.slug.replace("-", "_")
        self.object_path = f"/StatusNotifierItem/{safe_slug}"
        self.menu_path = f"/MenuBar/{safe_slug}"

        # Setup Dbusmenu Server for right-click context menu
        self.setup_menu()

        # Register D-Bus Object
        self.reg_id = self.bus.register_object(
            self.object_path,
            self.node_info.interfaces[0],
            self.on_method_call,
            self.on_get_property,
            None
        )

        # Register with StatusNotifierWatcher
        self.register_watcher()

    def set_attention(self, needs_attention=True, title=None):
        new_status = "NeedsAttention" if needs_attention else "Active"
        if self._status != new_status or (title and title != self._title):
            self._status = new_status
            if title:
                self._title = title
            elif not needs_attention:
                self._title = self.manifest.name

            try:
                self.bus.emit_signal(
                    None,
                    self.object_path,
                    "org.kde.StatusNotifierItem",
                    "NewStatus",
                    GLib.Variant("(s)", (self._status,))
                )
                self.bus.emit_signal(
                    None,
                    self.object_path,
                    "org.kde.StatusNotifierItem",
                    "NewTitle",
                    None
                )
            except Exception as e:
                print(f"[{self.manifest.slug}] Tray signal error: {e}")

    def setup_menu(self):
        self.menu_server = Dbusmenu.Server.new(self.menu_path)
        self.root_menu = Dbusmenu.Menuitem.new()

        # Toggle Show / Hide
        self.item_toggle = Dbusmenu.Menuitem.new()
        self.item_toggle.property_set("label", "Show / Hide")
        self.item_toggle.connect("item-activated", lambda *_: self.toggle_window())
        self.root_menu.child_append(self.item_toggle)

        # Home URL
        self.item_home = Dbusmenu.Menuitem.new()
        self.item_home.property_set("label", f"Open {self.manifest.name}")
        self.item_home.connect("item-activated", lambda *_: self.open_home())
        self.root_menu.child_append(self.item_home)

        # Separator
        sep = Dbusmenu.Menuitem.new()
        sep.property_set("type", "separator")
        self.root_menu.child_append(sep)

        # Quit
        self.item_quit = Dbusmenu.Menuitem.new()
        self.item_quit.property_set("label", "Quit")
        self.item_quit.connect("item-activated", lambda *_: self.app.quit())
        self.root_menu.child_append(self.item_quit)

        self.menu_server.set_root(self.root_menu)

    def register_watcher(self):
        try:
            watcher = Gio.DBusProxy.new_sync(
                self.bus,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                None
            )
            watcher.call_sync(
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", [self.object_path]),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
        except Exception:
            pass

    def on_method_call(self, connection, sender, object_path, interface_name, method_name, parameters, invocation):
        if method_name in ("Activate", "SecondaryActivate"):
            self.toggle_window()
        invocation.return_value(None)

    def on_get_property(self, connection, sender, object_path, interface_name, property_name):
        props = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", self.manifest.slug),
            "Title": GLib.Variant("s", self._title),
            "Status": GLib.Variant("s", self._status),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self.manifest.icon),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", self.manifest.icon),
            "AttentionMovieName": GLib.Variant("s", ""),
            "IconThemePath": GLib.Variant("s", ""),
            "Menu": GLib.Variant("o", self.menu_path),
            "ItemIsMenu": GLib.Variant("b", False),
        }
        return props.get(property_name, None)

    def toggle_window(self):
        if self.window.is_visible() and self.window.is_active():
            self.window.set_visible(False)
        else:
            self.set_attention(False)
            self.window.set_visible(True)
            self.window.present()
            self.window.web_view.grab_focus()

    def open_home(self):
        self.set_attention(False)
        self.window.set_visible(True)
        self.window.present()
        self.window.web_view.grab_focus()
        self.window.web_view.load_uri(self.manifest.url)
