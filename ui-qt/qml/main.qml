import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Window {
    id: root
    visible: false
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    width: 660

    property string status: backend.status
    property int lastReveal: -1
    property int lastHide: -1
    property real revealProgress: 0
    property var levels: []

    readonly property bool listening: status === "listening"
    readonly property bool thinking: status === "thinking"
    readonly property bool failed: status === "error"
    readonly property bool showingResult: !listening && !thinking && !failed

    height: panel.implicitHeight

    onStatusChanged: levels = []
    Connections {
        target: backend
        function onChanged() {
            if (backend.levels.length > 0)
                root.levels = backend.levels
            if (root.lastHide !== -1 && backend.hideRequest !== root.lastHide) {
                root.lastHide = backend.hideRequest
                root.visible = false
            } else if (root.lastHide === -1) {
                root.lastHide = backend.hideRequest
            }
            if (backend.reveal !== root.lastReveal) {
                if (root.lastReveal !== -1) {
                    root.visible = true
                    entrance.restart()
                }
                root.lastReveal = backend.reveal
            }
            backend.visible = root.visible
        }
    }

    onVisibleChanged: backend.visible = visible

    NumberAnimation {
        id: entrance
        target: root
        property: "revealProgress"
        from: 0
        to: 1
        duration: 260
        easing.type: Easing.OutBack
        easing.overshoot: 1.15
    }

    FileDialog {
        id: fileDialog
        title: "Transcribe audio or video"
        nameFilters: ["Audio and video (*.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac *.mp4 *.mkv *.webm *.mov *.avi *.m4v)"]
        onAccepted: backend.upload(selectedFile)
    }

    Rectangle {
        id: panel
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        implicitHeight: content.implicitHeight + 44
        color: "#000000"
        radius: 28
        topLeftRadius: 28
        topRightRadius: 28
        bottomLeftRadius: 0
        bottomRightRadius: 0
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.10)
        opacity: revealProgress
        transform: Translate {
            y: (1 - revealProgress) * 40
        }

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10

            RowLayout {
                Layout.fillWidth: true

                Label {
                    text: backend.title
                    color: "#f5f5f7"
                    font.pixelSize: 27
                    font.weight: Font.DemiBold
                    font.letterSpacing: -0.6
                    Layout.fillWidth: true
                }

                Button {
                    text: "✕"
                    flat: false
                    implicitWidth: 40
                    implicitHeight: 40
                    font.pixelSize: 14
                    contentItem: Text {
                        text: parent.text
                        color: "#c9c9cf"
                        font: parent.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: height / 2
                        color: parent.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)
                    }
                    onClicked: root.visible = false
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                ColumnLayout {
                    visible: root.listening
                    spacing: 12
                    Label {
                        text: backend.timerText
                        color: "#f5f5f7"
                        font.pixelSize: 46
                        font.weight: Font.Medium
                        font.letterSpacing: -1.4
                    }

                    Canvas {
                        id: wave
                        Layout.fillWidth: true
                        Layout.preferredHeight: 76
                        onPaint: {
                            const ctx = getContext("2d")
                            ctx.reset()
                            const bars = 110
                            const gap = 3
                            const bw = (width - gap * (bars - 1)) / bars
                            const mid = height / 2
                            ctx.fillStyle = "#f5f5f7"
                            const data = root.levels
                            for (let i = 0; i < bars; i++) {
                                let v = 0
                                if (data.length > 0) {
                                    const from = Math.floor((i / bars) * data.length)
                                    const to = Math.max(from + 1, Math.floor(((i + 1) / bars) * data.length))
                                    let sum = 0, n = 0
                                    for (let j = from; j < to && j < data.length; j++) { sum += data[j]; n++ }
                                    v = n ? sum / n : 0
                                }
                                const h = Math.max(3, Math.min(76, Math.pow(v, 0.7) * 76 * 1.9 + 3))
                                const x = i * (bw + gap)
                                ctx.fillRect(x, mid - h / 2, bw, h)
                            }
                        }
                        Connections {
                            target: root
                            function onLevelsChanged() { wave.requestPaint() }
                        }
                        Component.onCompleted: requestPaint()
                    }

                    RowLayout {
                        spacing: 10
                        Layout.fillWidth: true

                        Button {
                            text: "Done"
                            implicitHeight: 42
                            implicitWidth: 92
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            contentItem: Text {
                                text: parent.text
                                color: "#000000"
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 21
                                color: parent.hovered ? "#ffffff" : "#f5f5f7"
                            }
                            onClicked: backend.stopRecording()
                        }

                        Item { Layout.fillWidth: true }

                        ComboBox {
                            id: micBox
                            implicitWidth: 268
                            implicitHeight: 42
                            model: backend.sources
                            textRole: "label"
                            valueRole: "id"
                            font.pixelSize: 15
                            onActivated: backend.setInputDevice(currentValue)
                            Component.onCompleted: {
                                const idx = indexOfValue(backend.inputDevice)
                                currentIndex = idx >= 0 ? idx : -1
                            }
                            Connections {
                                target: backend
                                function onChanged() {
                                    const idx = micBox.indexOfValue(backend.inputDevice)
                                    if (idx >= 0 && idx !== micBox.currentIndex)
                                        micBox.currentIndex = idx
                                }
                            }
                            contentItem: Text {
                                leftPadding: 16
                                rightPadding: 34
                                text: micBox.displayText
                                color: "#d8d8dc"
                                font: micBox.font
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                            indicator: Text {
                                x: micBox.width - width - 14
                                y: (micBox.height - height) / 2
                                text: "⌄"
                                color: "#8e8e93"
                                font.pixelSize: 16
                            }
                            background: Rectangle {
                                radius: height / 2
                                color: micBox.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.10)
                            }
                        }

                        ComboBox {
                            id: langBox
                            implicitWidth: 170
                            implicitHeight: 42
                            model: backend.languages
                            textRole: "name"
                            valueRole: "code"
                            font.pixelSize: 15
                            onActivated: backend.setLanguage(currentValue)
                            Component.onCompleted: {
                                const idx = indexOfValue(backend.language)
                                currentIndex = idx >= 0 ? idx : 0
                            }
                            Connections {
                                target: backend
                                function onChanged() {
                                    const code = backend.language || ""
                                    const idx = langBox.indexOfValue(code)
                                    if (idx >= 0 && idx !== langBox.currentIndex)
                                        langBox.currentIndex = idx
                                }
                            }
                            contentItem: Text {
                                leftPadding: 16
                                rightPadding: 34
                                text: langBox.displayText
                                color: "#d8d8dc"
                                font: langBox.font
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                            indicator: Text {
                                x: langBox.width - width - 14
                                y: (langBox.height - height) / 2
                                text: "⌄"
                                color: "#8e8e93"
                                font.pixelSize: 16
                            }
                            background: Rectangle {
                                radius: height / 2
                                color: langBox.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.10)
                            }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.thinking
                    spacing: 10
                    Label {
                        text: backend.subtitle
                        color: "#8e8e93"
                        font.pixelSize: 15
                    }
                    Canvas {
                        id: loadBar
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        property real phase: 0
                        onPaint: {
                            const ctx = getContext("2d")
                            ctx.reset()
                            const r = height / 2
                            ctx.fillStyle = "rgba(255,255,255,0.10)"
                            ctx.fillRect(0, 0, width, height)
                            ctx.save()
                            for (let i = 0; i <= 24; i++) {
                                const t = i / 24
                                const hue = (phase + t * 0.85) % 1
                                ctx.fillStyle = "hsl(" + (hue * 360) + ", 62%, 60%)"
                                ctx.fillRect((t - 0.045) * width, 0, width / 24 + 2, height)
                            }
                            const sheenX = ((phase * 2.4) % 1) * (width + 200) - 200
                            const grad = ctx.createLinearGradient(sheenX, 0, sheenX + 200, 0)
                            grad.addColorStop(0, "rgba(255,255,255,0)")
                            grad.addColorStop(0.5, "rgba(255,255,255,0.55)")
                            grad.addColorStop(1, "rgba(255,255,255,0)")
                            ctx.fillStyle = grad
                            ctx.fillRect(0, 0, width, height)
                            ctx.restore()
                        }
                        Timer {
                            interval: 16
                            running: root.thinking
                            repeat: true
                            onTriggered: { loadBar.phase = (loadBar.phase + 0.006) % 1; loadBar.requestPaint() }
                        }
                        onWidthChanged: requestPaint()
                        Component.onCompleted: requestPaint()
                    }
                }

                ColumnLayout {
                    visible: root.failed
                    spacing: 8
                    Label {
                        text: backend.error || "Something went wrong."
                        color: "#ff6961"
                        font.pixelSize: 18
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Press Esc to dismiss."
                        color: "#8e8e93"
                        font.pixelSize: 14
                    }
                }

                ColumnLayout {
                    visible: root.showingResult
                    spacing: 12

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(transcript.contentHeight + 10, 330)
                        clip: true

                        TextArea {
                            id: transcript
                            text: backend.text.length ? backend.text : "No speech detected. Try again."
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextArea.Wrap
                            color: backend.text.length ? "#f5f5f7" : "#6e6e73"
                            font.pixelSize: 18
                            background: null
                            leftPadding: 0
                            rightPadding: 8
                        }
                    }

                    RowLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        Button {
                            display: AbstractButton.IconOnly
                            icon.name: "edit-copy-symbolic"
                            icon.width: 22
                            icon.height: 22
                            icon.color: "#000000"
                            implicitWidth: 54
                            implicitHeight: 42
                            enabled: backend.text.length > 0
                            opacity: enabled ? 1 : 0.4
                            background: Rectangle {
                                radius: height / 2
                                color: parent.hovered ? "#ffffff" : "#f5f5f7"
                            }
                            onClicked: {
                                textCopied.text = backend.text
                                textCopied.selectAll()
                                textCopied.copy()
                            }
                        }

                        Button {
                            text: "Talk more"
                            implicitHeight: 42
                            implicitWidth: 110
                            font.pixelSize: 15
                            font.weight: Font.Medium
                            contentItem: Text {
                                text: parent.text
                                color: "#f5f5f7"
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: height / 2
                                color: parent.hovered ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(1, 1, 1, 0.10)
                            }
                            onClicked: backend.startRecording(true)
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            display: AbstractButton.IconOnly
                            icon.name: "document-open-symbolic"
                            icon.width: 22
                            icon.height: 22
                            icon.color: "#f5f5f7"
                            implicitWidth: 54
                            implicitHeight: 42
                            background: Rectangle {
                                radius: height / 2
                                color: parent.hovered ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(1, 1, 1, 0.10)
                            }
                            onClicked: fileDialog.open()
                        }
                    }
                }
            }
        }
    }

    TextEdit {
        id: textCopied
        visible: false
    }

    Shortcut {
        sequence: "Escape"
        onActivated: root.visible = false
    }
}
