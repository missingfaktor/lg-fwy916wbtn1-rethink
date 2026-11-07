import QtQuick
import QtQuick.Window
import QtTest
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import "../plasmoid/contents/ui" as Washer

Item {
    id: fixture
    width: 800; height: 600
    property bool popupOpen: false
    property var state: ({drying: "Off", notifications: true, history: []})
    property string stage: "Washing"
    property string settingsText: "Cotton · 30 °C · 800 rpm"
    property string remainingText: "42 min"
    property string warning: ""
    property string reportText: "Updated just now"
    property bool online: true
    property bool active: true
    property double fraction: 0.2
    function call(method, args) {}

    PlasmaCore.AppletPopup {
        id: popup
        animated: true
        visualParent: anchor
        popupDirection: Qt.TopEdge
        hideOnWindowDeactivate: true
        visible: fixture.popupOpen
        onVisibleChanged: if (!visible && fixture.popupOpen) Qt.callLater(() => { if (!popup.visible) fixture.popupOpen = false; })
        mainItem: Washer.FullRepresentation { monitor: fixture }
    }
    Item { id: anchor; x: 400; y: 550; width: 24; height: 24 }

    TestCase {
        name: "NativeWasherPopup"
        when: windowShown
        function test_native_surface_and_dismissal() {
            fixture.popupOpen = true;
            tryCompare(popup, "visible", true);
            verify(popup.animated);
            verify(popup.hideOnWindowDeactivate);
            compare(popup.visualParent, anchor);
            verify(popup.mainItem.implicitHeight < Kirigami.Units.gridUnit * 22);
            verify(popup.mainItem.implicitWidth > 0);
            wait(250);
            keyClick(Qt.Key_Escape);
            tryCompare(fixture, "popupOpen", false);
            tryCompare(popup, "visible", false);
            fixture.popupOpen = true;
            tryCompare(popup, "visible", true);
            wait(250);
            popup.close();
            tryCompare(popup, "visible", false);
            tryCompare(fixture, "popupOpen", false);
        }
    }
}
