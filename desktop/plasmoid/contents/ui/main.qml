pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.workspace.dbus as DBus

PlasmoidItem {
    id: root
    property var state: ({})
    property int lastShowSerial: 0
    property bool popupOpen: false
    property double now: Date.now()
    readonly property bool online: service.registered && !!state.online
    readonly property string stage: online ? (state.status || "Waiting for washer") : "Connection unavailable"
    readonly property string remainingText: timeText(state.remaining)
    readonly property string settingsText: [state.course, state.temperature, state.spin].filter(value => value && value !== "Not selected").join(" · ") || "No programme reported"
    readonly property string warning: !service.registered ? "The background monitor is not running. Open Washer Monitor from the application launcher."
        : state.error ? `Machine error code ${state.error}. Check the washer's display.` : (state.problem || "")
    readonly property bool active: ["Detecting", "Washing", "Rinsing", "Spinning", "Drying", "Cooling down"].includes(state.status)
    readonly property double fraction: state.initial > 0 && typeof state.remaining === "number" ? Math.max(0, Math.min(1, 1 - state.remaining / state.initial)) : 0
    readonly property string reportText: state.reportedAt ? `Updated ${Qt.formatTime(new Date(state.reportedAt), "HH:mm:ss")} · ${Math.max(0, Math.floor((now - Date.parse(state.reportedAt)) / 60000))} min ago` : "Waiting for a machine report"

    function timeText(minutes) {
        if (typeof minutes !== "number" || minutes < 0) return "Not reported";
        const hours = Math.floor(minutes / 60);
        return hours ? `${hours} h ${Math.floor(minutes % 60)} min` : `${Math.floor(minutes)} min`;
    }

    function update() {
        now = Date.now();
        if (service.registered) display.updateAll();
    }

    function syncPopup() {
        if (root.popupOpen && root.Window.window) {
            popup.show();
            popup.requestActivate();
        } else {
            popup.hide();
        }
    }
    onPopupOpenChanged: Qt.callLater(() => root.syncPopup())
    Window.onWindowChanged: Qt.callLater(() => root.syncPopup())

    function call(method, args = []) {
        DBus.SessionBus.asyncCall({service: "io.github.missingfaktor.LGWasherMonitor.Monitor", path: "/Display",
            iface: "io.github.missingfaktor.LGWasherMonitor.Display", member: method, arguments: args});
    }

    function readSnapshot() {
        try {
            const next = JSON.parse(display.properties.Snapshot || "{}");
            state = next;
            if ((next.showSerial || 0) > lastShowSerial) root.popupOpen = true;
            lastShowSerial = next.showSerial || 0;
            call("ReportView", [JSON.stringify({stage: root.stage, expanded: root.popupOpen, visible: popup.visible, font: Kirigami.Theme.defaultFont.pointSize})]);
        } catch (error) { console.warn("Washer Monitor: invalid display snapshot", error); }
    }

    preferredRepresentation: compactRepresentation
    Plasmoid.icon: Qt.resolvedUrl("../images/washer.svg")
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    Plasmoid.contextualActions: [
        PlasmaCore.Action { text: "Refresh status"; icon.name: "view-refresh"; onTriggered: root.call("Refresh") },
        PlasmaCore.Action { text: "Send test notification"; icon.name: "notifications"; onTriggered: root.call("TestNotification") },
        PlasmaCore.Action { text: "Monitor settings…"; icon.name: "configure"; onTriggered: root.call("OpenSettings") },
        PlasmaCore.Action { text: "Quit monitor"; icon.name: "application-exit"; onTriggered: root.call("Quit") }
    ]
    toolTipMainText: `Washer · ${root.stage}`
    toolTipSubText: `${root.settingsText}\nDrying: ${state.drying || "—"}` + (root.active ? `\n${root.remainingText} remaining` : "")

    compactRepresentation: MouseArea {
        Layout.minimumWidth: Kirigami.Units.iconSizes.smallMedium
        Layout.minimumHeight: Kirigami.Units.iconSizes.smallMedium
        onClicked: root.popupOpen = !root.popupOpen
        Image {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height, Kirigami.Units.iconSizes.smallMedium)
            height: width
            source: "../images/washer.svg"
            sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
        }
    }
    fullRepresentation: FullRepresentation { monitor: root }
    PlasmaCore.AppletPopup {
        id: popup
        animated: true
        visualParent: root
        // Match panel applets: join the panel without a facing border/shadow.
        floating: false
        margin: 0
        removeBorderStrategy: PlasmaCore.AppletPopup.AtScreenEdges | PlasmaCore.AppletPopup.AtPanelEdges
        hideOnWindowDeactivate: true
        popupDirection: Plasmoid.location === PlasmaCore.Types.TopEdge ? Qt.BottomEdge
            : Plasmoid.location === PlasmaCore.Types.LeftEdge ? Qt.RightEdge
            : Plasmoid.location === PlasmaCore.Types.RightEdge ? Qt.LeftEdge : Qt.TopEdge
        mainItem: FullRepresentation { monitor: root }
        onVisibleChanged: if (!visible && root.popupOpen) Qt.callLater(() => { if (!popup.visible) root.popupOpen = false; })
    }

    DBus.DBusServiceWatcher {
        id: service
        busType: DBus.BusType.Session
        watchedService: "io.github.missingfaktor.LGWasherMonitor.Monitor"
        onRegisteredChanged: root.update()
    }
    DBus.Properties {
        id: display
        busType: DBus.BusType.Session
        service: "io.github.missingfaktor.LGWasherMonitor.Monitor"
        path: "/Display"
        iface: "io.github.missingfaktor.LGWasherMonitor.Display"
        onRefreshed: root.readSnapshot()
    }
    Timer { interval: 2000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.update() }
}
