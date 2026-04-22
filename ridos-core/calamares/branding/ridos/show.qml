/* RIDOS-Core — show.qml
   Place at: /etc/calamares/branding/ridos/show.qml
   Slideshow shown while files are being copied during installation.
*/

import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {
    id: presentation

    Timer {
        interval: 5000
        running: presentation.activatedInCalamares
        repeat:  true
        onTriggered: presentation.goToNextSlide()
    }

    // ── Slide 1 — Welcome ──────────────────────────────────────────────
    Slide {
        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            color: "#1a1a2e"

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Welcome to RIDOS-Core"
                    color: "#00d4aa"
                    font.pixelSize: 32
                    font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "A fast, stable Debian-based OS built for you."
                    color: "#e0e0e0"
                    font.pixelSize: 16
                }
            }
        }
    }

    // ── Slide 2 — Performance ─────────────────────────────────────────
    Slide {
        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            color: "#1a1a2e"

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Built for Performance"
                    color: "#00d4aa"
                    font.pixelSize: 32
                    font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "RIDOS-Core 1.0 Nova runs on Debian Bookworm\nwith a lightweight, optimized base."
                    color: "#e0e0e0"
                    font.pixelSize: 16
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

    // ── Slide 3 — Almost Done ─────────────────────────────────────────
    Slide {
        anchors.fill: parent

        Rectangle {
            anchors.fill: parent
            color: "#1a1a2e"

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Almost There..."
                    color: "#00d4aa"
                    font.pixelSize: 32
                    font.bold: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Setting up your system.\nThis will only take a few more minutes."
                    color: "#e0e0e0"
                    font.pixelSize: 16
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
