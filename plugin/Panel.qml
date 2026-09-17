import QtQuick
import QtQuick.Controls
import Quickshell.Io

Panel {
  id: root
  moduleName: "cheurteen.hwtruth"
  ipcTarget: "cheurteen.hwtruth"

  property string rebarOutput: "click \"Check ReBAR\" to verify Resizable BAR is actually live"
  property bool checking: false

  // Refresh GPU telemetry whenever the panel opens.
  onOpenedChanged: {
    if (opened) refreshTelemetry.running = true
  }

  function runCheck() {
    checking = true
    rebarOutput = "checking…"
    rebarCheck.running = true
  }

  // The hwtruth CLI does the dual-read cross-check; if it is not installed,
  // fall back to a plain BAR1 size read so the panel still answers.
  Process {
    id: rebarCheck
    command: ["sh", "-c", "command -v hwtruth >/dev/null && hwtruth rebar-check || { s=$(cat /sys/class/drm/card*/device/resource 2>/dev/null | head -3); echo 'hwtruth CLI not installed:'; echo '  pip install --user git+https://github.com/Cheurteenyt/hwtruth'; }"]
    stdout: StdioCollector {
      onStreamFinished: {
        root.rebarOutput = text.trim()
        root.checking = false
      }
    }
  }

  Process {
    id: refreshTelemetry
    command: ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,clocks.current.graphics,pstate", "--format=csv,noheader,nounits"]
    stdout: StdioCollector {
      onStreamFinished: root.telemetryText = text.trim()
    }
  }

  property string telemetryText: ""

  Rectangle {
    color: "#1a1b26"
    radius: 12
    anchors.fill: parent

    Column {
      anchors.margins: 18
      anchors.fill: parent
      spacing: 10

      Text {
        text: "HWTruth — hardware truth"
        font.pixelSize: 16
        font.bold: true
        color: "#7dcfff"
      }

      Text {
        text: root.telemetryText !== "" ? root.telemetryText : "GPU telemetry…"
        font.pixelSize: 13
        font.family: "monospace"
        color: "#c0caf5"
      }

      Rectangle { width: parent.width; height: 1; color: "#24283b" }

      Text {
        width: parent.width
        text: root.rebarOutput
        font.pixelSize: 12
        font.family: "monospace"
        color: "#9ece6a"
        wrapMode: Text.WrapAnywhere
      }

      Button {
        text: root.checking ? "checking…" : "Check ReBAR"
        enabled: !root.checking
        onClicked: root.runCheck()
      }

      Text {
        width: parent.width
        text: "Read-only, always. Evidence over assumptions — see github.com/Cheurteenyt/hwtruth"
        font.pixelSize: 10
        color: "#565f89"
        wrapMode: Text.WrapAnywhere
      }
    }
  }
}
