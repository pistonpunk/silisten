import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Window {
    id: root
    visible: false
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: root.demo ? "#ffffff" : "transparent"
    width: 660

    property bool demo: demoMode
    property string demoStatus: "listening"
    property string demoText: ""
    property string demoClock: "0:00"
    property string status: demo ? demoStatus : backend.status
    property int lastReveal: -1
    property int lastHide: -1
    property real revealProgress: 0
    property var levels: []
    property real demoPhase: 0

    Timer {
        id: script
        running: root.demo
        interval: 100
        repeat: true
        property real elapsed: 0
        onTriggered: {
            elapsed += 0.1
            const cycle = elapsed % 10.5
            if (cycle < 3.6) {
                root.demoStatus = "listening"
                root.demoClock = "0:0" + Math.min(9, Math.floor(cycle) + 1)
                root.demoText = ""
            } else if (cycle < 5.4) {
                root.demoStatus = "thinking"
            } else {
                root.demoStatus = "done"
                root.demoText = "Speaker 1: Ship it Monday? The build passed everything.\n\nSpeaker 2: Monday. I'll write the release notes tonight."
            }
        }
    }
    property bool settingsOpen: false

    readonly property bool listening: status === "listening"
    readonly property bool thinking: status === "thinking"
    readonly property bool failed: status === "error"
    readonly property bool showingResult: !listening && !thinking && !failed

    height: panel.implicitHeight + (root.demo ? 56 : 0)

    onStatusChanged: levels = []
    Connections {
        target: backend
        function onChanged() {
            if (backend.levels.length > 0)
                root.levels = backend.levels.slice(-600)
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

    Component.onCompleted: if (root.demo) root.visible = true

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
        anchors.leftMargin: root.demo ? 28 : 0
        anchors.rightMargin: root.demo ? 28 : 0
        anchors.bottomMargin: root.demo ? 28 : 0
        implicitHeight: content.implicitHeight + 44
        color: "#000000"
        radius: 28
        opacity: revealProgress
        transform: Translate {
            y: (1 - revealProgress) * 40
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 28
            color: "#000000"
            visible: !root.demo
        }

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.margins: 20
            spacing: 10

            RowLayout {
                Layout.fillWidth: true

                Label {
                    text: root.settingsOpen ? "Settings"
                        : root.demo ? (root.demoStatus === "listening" ? "Listening"
                                     : root.demoStatus === "thinking" ? "Transcribing"
                                     : root.demoStatus === "done" ? "Transcription" : "Silisten")
                        : backend.title
                    color: "#f5f5f7"
                    font.pixelSize: 27
                    font.weight: Font.DemiBold
                    font.letterSpacing: -0.6
                    Layout.fillWidth: true
                }

                Button {

                    HoverHandler { cursorShape: Qt.PointingHandCursor }

                    scale: down ? 0.97 : 1.0

                    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
                    display: AbstractButton.IconOnly
                    icon.name: "emblem-system-symbolic"
                    icon.width: 18
                    icon.height: 18
                    icon.color: root.settingsOpen ? "#ffffff" : "#c9c9cf"
                    implicitWidth: 40
                    implicitHeight: 40
                    background: Rectangle {
                        radius: height / 2
                        color: parent.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)

                    
                            Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    onClicked: root.settingsOpen = !root.settingsOpen
                }

                Button {

                    HoverHandler { cursorShape: Qt.PointingHandCursor }

                    scale: down ? 0.97 : 1.0

                    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
                    display: AbstractButton.IconOnly
                    icon.name: "window-close-symbolic"
                    icon.width: 16
                    icon.height: 16
                    icon.color: "#c9c9cf"
                    implicitWidth: 40
                    implicitHeight: 40
                    background: Rectangle {
                        radius: height / 2
                        color: parent.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)

                    
                            Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    onClicked: root.visible = false
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                ColumnLayout {
                    opacity: (root.listening && !root.settingsOpen) ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 130; easing.type: Easing.OutQuad } }
                    visible: root.listening && !root.settingsOpen
                    spacing: 12
                    Label {
                        text: root.demo ? root.demoClock : backend.timerText
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
                            const ph = root.demoPhase
                            for (let i = 0; i < bars; i++) {
                                let v = 0
                                if (root.demo) {
                                    const noise = (n) => {
                                        const x = Math.sin(n * 127.1 + 311.7) * 43758.5453
                                        return x - Math.floor(x)
                                    }
                                    const tick = Math.floor(ph * 26)
                                    const envelope = 0.25 + 0.75 * Math.max(0, Math.sin(ph * 0.8 + 1.1))
                                    const body = noise(i * 2.7 + tick * 0.61)
                                    const shaped = Math.pow(body, 2.1)
                                    const spike = noise(i * 0.9 + tick * 1.37) > 0.94 ? 0.45 : 0.0
                                    v = Math.min(1, envelope * (shaped + spike))
                                } else if (data.length > 0) {
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

                            HoverHandler { cursorShape: Qt.PointingHandCursor }

                            scale: down ? 0.97 : 1.0

                            Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
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

                            
                                    Behavior on color { ColorAnimation { duration: 120 } }
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

                            
                                    Behavior on color { ColorAnimation { duration: 120 } }
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

                            
                                    Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.thinking && !root.settingsOpen
                    spacing: 10
                    Label {
                        text: root.demo ? "Turning your voice into text" : backend.subtitle
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
                            function hueRgb(h) {
                                const i = Math.floor(h * 6), f = h * 6 - i
                                const q = 1 - f, t = f
                                const m = [ [1, t, 0], [q, 1, 0], [0, 1, t], [0, q, 1], [t, 0, 1], [1, 0, q] ][i % 6]
                                return "rgb(" + Math.round(m[0] * 255) + "," + Math.round(m[1] * 255) + "," + Math.round(m[2] * 255) + ")"
                            }
                            for (let i = 0; i <= 24; i++) {
                                const t = i / 24
                                const hue = (phase + t * 0.85) % 1
                                ctx.fillStyle = hueRgb(hue)
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
                    visible: root.settingsOpen
                    spacing: 12

                    Label {
                        text: "Speech model"
                        color: "#8e8e93"
                        font.pixelSize: 14
                    }

                    ComboBox {
                        id: modelBox
                        Layout.fillWidth: true
                        implicitHeight: 42
                        font.pixelSize: 15
                        model: backend.speechModels
                        textRole: "label"
                        valueRole: "name"
                        onActivated: backend.setSpeechModel(currentValue)
                        Component.onCompleted: {
                            const idx = indexOfValue(backend.speechModel)
                            currentIndex = idx >= 0 ? idx : 0
                        }
                        Connections {
                            target: backend
                            function onChanged() {
                                const idx = modelBox.indexOfValue(backend.speechModel)
                                if (idx >= 0 && idx !== modelBox.currentIndex)
                                    modelBox.currentIndex = idx
                            }
                        }
                        contentItem: Text {
                            leftPadding: 16
                            rightPadding: 34
                            text: {
                                const row = modelBox.model[modelBox.currentIndex]
                                if (!row) return ""
                                return row.label + (row.installed ? "" : "  (downloads on first use)")
                            }
                            color: "#d8d8dc"
                            font: modelBox.font
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }
                        indicator: Text {
                            x: modelBox.width - width - 14
                            y: (modelBox.height - height) / 2
                            text: "\u2304"
                            color: "#8e8e93"
                            font.pixelSize: 16
                        }
                        background: Rectangle {
                            radius: height / 2
                            color: modelBox.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.10)

                        
                                Behavior on color { ColorAnimation { duration: 120 } }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Label speakers"
                            color: "#f5f5f7"
                            font.pixelSize: 15
                            Layout.fillWidth: true
                        }
                        Switch {
                            checked: backend.diarization
                            onToggled: backend.setDiarization(checked)
                        }
                    }

                    Label {
                        text: "Models download on demand. Run `silisten models` in a terminal to see what is installed."
                        color: "#6e6e73"
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
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
                    visible: root.showingResult && !root.settingsOpen
                    spacing: 12

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(transcript.contentHeight + 10, 330)
                        clip: true

                        TextArea {
                            id: transcript
                            text: (root.demo ? root.demoText : backend.text).length ? (root.demo ? root.demoText : backend.text) : "No speech detected. Try again."
                            readOnly: true
                            selectByMouse: true
                            selectionColor: "#3a5fb8"
                            selectedTextColor: "#ffffff"
                            wrapMode: TextArea.Wrap
                            color: (root.demo ? root.demoText : backend.text).length ? "#f5f5f7" : "#6e6e73"
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

                            HoverHandler { cursorShape: Qt.PointingHandCursor }

                            scale: down ? 0.97 : 1.0

                            Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
                            display: AbstractButton.IconOnly
                            icon.name: "edit-copy-symbolic"
                            icon.width: 22
                            icon.height: 22
                            icon.color: "#000000"
                            implicitWidth: 54
                            implicitHeight: 42
                            enabled: (root.demo ? root.demoText : backend.text).length > 0
                            opacity: enabled ? 1 : 0.4
                            background: Rectangle {
                                radius: height / 2
                                color: parent.hovered ? "#ffffff" : "#f5f5f7"

                            
                                    Behavior on color { ColorAnimation { duration: 120 } }
                            }
                            onClicked: {
                                textCopied.text = root.demo ? root.demoText : backend.text
                                textCopied.selectAll()
                                textCopied.copy()
                            }
                        }

                        Button {

                            HoverHandler { cursorShape: Qt.PointingHandCursor }

                            scale: down ? 0.97 : 1.0

                            Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
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

                            
                                    Behavior on color { ColorAnimation { duration: 120 } }
                            }
                            onClicked: backend.startRecording(true)
                        }

                        Item { Layout.fillWidth: true }

                        Button {

                            HoverHandler { cursorShape: Qt.PointingHandCursor }

                            scale: down ? 0.97 : 1.0

                            Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
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

                            
                                    Behavior on color { ColorAnimation { duration: 120 } }
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
