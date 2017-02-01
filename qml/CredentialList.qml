import QtQuick 2.6
import QtQuick.Controls 1.4
import QtQuick.Layouts 1.1
import QtQuick.Controls.Styles 1.4

Column {
    id: column1
    property var device
    width: 300
    height: 400
    property int margin: width / 30
    property int expiration: 0
    property var credentials: device.credentials
    onCredentialsChanged: {
        updateExpiration()
        console.log(JSON.stringify(credentials))
    }

    ColumnLayout {

        ProgressBar {
            id: bar
            maximumValue: 30
            minimumValue: 0

            style: ProgressBarStyle {
                progress: Rectangle {
                    color: "#83d714"
                }
                background: Rectangle {
                    radius: 2
                    color: "lightgray"
                    border.color: "gray"
                    border.width: 0
                    implicitWidth: 300
                    implicitHeight: 10
                }
            }

            Timer {
                interval: 100
                repeat: true
                running: true
                triggeredOnStart: true
                onTriggered: {
                    var timeLeft = expiration - (Date.now() / 1000)
                    if (timeLeft <= 0 && bar.value > 0) {
                        device.refresh()
                    }
                    bar.value = timeLeft
                }
            }
        }

        Repeater {
            model: credentials

            Rectangle {
                height: 65
                color: "#f1bde5"
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.left: parent.left
                anchors.leftMargin: 10
                Column {
                    anchors.verticalCenter: parent.verticalCenter

                        Text {
                            visible: modelData.issuer !== undefined
                            text: qsTr('') + modelData.issuer
                            font.pointSize: 13
                        }
                        Text {
                            visible: modelData.code != null
                            text: qsTr('') + modelData.code
                            font.family: "Verdana"
                            font.pointSize: 22
                        }
                        Text {
                            text: qsTr('') + modelData.name
                            font.pointSize: 13
                        }
                    }

            }
        }
    }

    function updateExpiration() {
        var maxExpiration = 0
        if (credentials !== null) {
            for (var i = 0; i < credentials.length; i++) {
                var exp = credentials[i].expiration
                if (exp !== null && exp > maxExpiration) {
                    maxExpiration = exp
                }
            }
            expiration = maxExpiration
        }
    }
}