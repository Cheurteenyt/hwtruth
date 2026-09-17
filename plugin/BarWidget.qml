import QtQuick
import Quickshell.Io
import qs.Commons

BarWidget {
  id: root
  moduleName: "cheurteen.hwtruth"

  // Inject the shared shell properties into the panel (same pattern as the
  // first-party widgets) so it can anchor to this button.
  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.openFromHotkey) panelLoader.item.openFromHotkey()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  visible: label.text !== ""
  implicitWidth: row.implicitWidth + 12
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    onClicked: root.togglePanel()
  }

  // Live GPU telemetry (temperature + power). Polls nvidia-smi every 3 s.
  Process {
    id: telemetry
    command: ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw", "--format=csv,noheader,nounits"]
    stdout: StdioCollector {
      onStreamFinished: {
        var parts = text.trim().split(",")
        if (parts.length >= 2)
          root.tempText = parts[0].trim() + "°C " + Math.round(parseFloat(parts[1])) + "W"
      }
    }
  }

  property string tempText: ""

  Timer {
    interval: 3000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: telemetry.running = true
  }

  Row {
    id: row
    anchors.centerIn: parent
    spacing: 4

    Text {
      text: "⚙"
      font.pixelSize: 12
      color: root.opened ? "#7dcfff" : "#c0caf5"
      anchors.verticalCenter: parent.verticalCenter
    }

    Text {
      id: label
      text: root.tempText
      font.pixelSize: 12
      color: "#c0caf5"
      anchors.verticalCenter: parent.verticalCenter
    }
  }
}
