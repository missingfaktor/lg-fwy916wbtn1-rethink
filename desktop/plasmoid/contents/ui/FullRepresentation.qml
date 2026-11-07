import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

Item {
    id: view
    required property var monitor
    implicitWidth: Layout.minimumWidth
    implicitHeight: Layout.minimumHeight
    Layout.minimumWidth: Kirigami.Units.gridUnit * 23
    Layout.preferredWidth: Layout.minimumWidth
    Layout.minimumHeight: content.implicitHeight + 2 * Kirigami.Units.largeSpacing
    Layout.maximumHeight: Layout.minimumHeight
    Shortcut { sequence: "Escape"; enabled: view.monitor.popupOpen; onActivated: view.monitor.popupOpen = false }

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Kirigami.Units.largeSpacing }
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Heading { level: 1; text: view.monitor.stage }
        PlasmaComponents.Label { text: view.monitor.settingsText; opacity: 0.7 }
        PlasmaComponents.Label { text: `Drying: ${view.monitor.state.drying || "—"}` }

        PlasmaComponents.ProgressBar {
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            visible: view.monitor.online && view.monitor.active
            from: 0; to: 1; value: view.monitor.fraction
        }
        PlasmaComponents.Label {
            Layout.alignment: Qt.AlignRight
            visible: view.monitor.active
            text: `${view.monitor.remainingText} remaining · machine estimate`
            font: Kirigami.Theme.smallFont
            opacity: 0.7
        }
        PlasmaComponents.Label {
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.fillWidth: true
            visible: !!view.monitor.warning
            text: view.monitor.warning
            wrapMode: Text.Wrap
            color: Kirigami.Theme.negativeTextColor
        }
        PlasmaComponents.Label { text: view.monitor.reportText; opacity: 0.7 }

        RowLayout {
            Layout.topMargin: Kirigami.Units.smallSpacing
            PlasmaComponents.Button { text: "Open washer page"; onClicked: { view.monitor.popupOpen = false; Qt.openUrlExternally(view.monitor.state.base + "/washer"); } }
            PlasmaComponents.Button { text: "Recent alerts"; checkable: true; checked: events.visible; onClicked: events.visible = !events.visible }
            PlasmaComponents.ToolButton { icon.name: "configure"; text: "Settings"; onClicked: { view.monitor.popupOpen = false; view.monitor.call("OpenSettings"); } }
        }
        ColumnLayout {
            id: events
            visible: false
            Layout.fillWidth: true
            PlasmaComponents.Label { visible: !(view.monitor.state.history || []).length; text: "No alerts yet."; opacity: 0.7 }
            Repeater {
                model: (view.monitor.state.history || []).slice(-5).reverse()
                PlasmaComponents.Label {
                    required property var modelData
                    Layout.fillWidth: true
                    text: `${modelData.time.substring(11, 19)} · ${modelData.title}\n${modelData.body}`
                    wrapMode: Text.Wrap
                }
            }
        }
        PlasmaComponents.CheckBox {
            text: "Notifications enabled"
            checked: view.monitor.state.notifications !== false
            onClicked: view.monitor.call("SetNotifications", [checked])
        }
    }
}
