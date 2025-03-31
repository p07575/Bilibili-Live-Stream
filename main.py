import sys
import asyncio
import threading
import url
import os
import json
import vlc
from PyQt5.QtWidgets import QApplication, QMainWindow, QFrame, QDesktopWidget, QTextEdit, QHBoxLayout, QVBoxLayout, QWidget, QPushButton, QSlider, QLineEdit
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QIcon
from bilibili_api import live, user, login, Credential
from bilibili_api.live import LiveRoom, Danmaku
import tkinter as tk
from tkinter import ttk

class DanmuSignals(QObject):
    new_danmu = pyqtSignal(str, str, int)

class Player(QMainWindow):
    def __init__(self, stream_url, room_id, credential):
        super().__init__()
        self.setWindowIcon(QIcon('_internal/favicon.ico'))
        self.setWindowTitle("Bilibili Live Player")
        self.stream_url = stream_url
        self.room_id = room_id
        self.credential = credential
        self.danmu_thread = None
        
        self.resize_to_screen()

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Video frame
        self.video_frame = QFrame(self)
        main_layout.addWidget(self.video_frame, 2)

        # Danmu and controls
        danmu_control_widget = QWidget()
        danmu_control_layout = QVBoxLayout(danmu_control_widget)
        main_layout.addWidget(danmu_control_widget, 1)

        # Danmu display
        self.danmu_display = QTextEdit(self)
        self.danmu_display.setReadOnly(True)
        danmu_control_layout.addWidget(self.danmu_display)

        # Danmu input
        self.danmu_input = QLineEdit(self)
        danmu_control_layout.addWidget(self.danmu_input)

        # Send danmu button
        self.send_danmu_button = QPushButton("Send Danmu")
        self.send_danmu_button.clicked.connect(self.send_danmu)
        danmu_control_layout.addWidget(self.send_danmu_button)

        # Control buttons
        control_layout = QHBoxLayout()

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        control_layout.addWidget(self.volume_slider)

        self.refresh_stream_button = QPushButton("Refresh Stream")
        self.refresh_stream_button.clicked.connect(self.refresh_stream)
        control_layout.addWidget(self.refresh_stream_button)

        self.reset_danmu_button = QPushButton("Reset Danmu")
        self.reset_danmu_button.clicked.connect(self.reset_danmu)
        control_layout.addWidget(self.reset_danmu_button)

        danmu_control_layout.addLayout(control_layout)

        self.setup_player()
        self.setup_danmu()

        self.loop = None

    def setup_player(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        self.media = self.instance.media_new(self.stream_url)
        self.player.set_media(self.media)

        if sys.platform.startswith('linux'):
            self.player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":
            self.player.set_nsobject(int(self.video_frame.winId()))

        self.player.play()

    def setup_danmu(self):
        self.room = live.LiveDanmaku(self.room_id, credential=self.credential)
        self.live_room = LiveRoom(self.room_id, self.credential)

        self.danmu_signals = DanmuSignals()
        self.danmu_signals.new_danmu.connect(self.display_danmu)

        self.start_danmu_thread()

    def start_danmu_thread(self):
        if self.danmu_thread:
            self.stop_danmu_thread()
        self.danmu_thread = threading.Thread(target=self.run_danmu_client, daemon=True)
        self.danmu_thread.start()

    def stop_danmu_thread(self):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.room.disconnect(), self.loop)
            self.danmu_thread.join()
            self.danmu_thread = None

    def resize_to_screen(self):
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())
        screen_size = QDesktopWidget().screenGeometry(screen)
        
        width = int(screen_size.width() * 0.7)
        height = int(screen_size.height() * 0.7)
        self.setGeometry((screen_size.width() - width) // 2,
                         (screen_size.height() - height) // 2,
                         width, height)

    def parse_danmu(self, event):
        data = event['data']
        info = data['info']
        
        username = info[2][1]
        content = info[1]
        color = info[0][3]
        
        return username, content, color

    @property
    def on_danmaku(self):
        @self.room.on('DANMU_MSG')
        async def on_danmaku_handler(event):
            try:
                username, content, color = self.parse_danmu(event)
                self.danmu_signals.new_danmu.emit(username, content, color)
                print(f"\033[33m[DANMU] {username}: {content}\033[0m")
            except Exception as e:
                print(f"\033[31m[ERROR] Error parsing danmaku: {e}\033[0m")
        return on_danmaku_handler

    def display_danmu(self, username, content, color):
        cursor = self.danmu_display.textCursor()
        cursor.movePosition(cursor.End)
        
        # Set username and colon to grey
        username_format = QTextCharFormat()
        username_format.setForeground(QColor(128, 128, 128))  # Grey color
        cursor.setCharFormat(username_format)
        cursor.insertText(f"{username}: ")
        
        # Set content to default black
        content_format = QTextCharFormat()
        content_format.setForeground(QColor(0, 0, 0))  # Black color
        cursor.setCharFormat(content_format)
        cursor.insertText(f"{content}\n")
        
        self.danmu_display.setTextCursor(cursor)
        self.danmu_display.ensureCursorVisible()

    def run_danmu_client(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.on_danmaku  # This line is necessary to register the event handler
        print("\033[32m[INFO] Connecting to danmu room...\033[0m")
        self.loop.run_until_complete(self.room.connect())

    def change_volume(self):
        volume = self.volume_slider.value()
        print(f"Volume changed to: {volume}")
        self.player.audio_set_volume(volume)

    def refresh_stream(self):
        print("Refreshing stream")
        self.player.stop()
        self.media = self.instance.media_new(self.stream_url)
        self.player.set_media(self.media)
        self.player.play()

    def reset_danmu(self):
        print("Resetting danmu")
        self.danmu_display.clear()

    def send_danmu(self):
        danmu_text = self.danmu_input.text()
        if danmu_text:
            asyncio.run_coroutine_threadsafe(self._send_danmu(danmu_text), self.loop)
            self.danmu_input.clear()

    async def _send_danmu(self, text):
        try:
            await self.live_room.send_danmaku(Danmaku(text))
            print(f"\033[32m[SENT] Danmu sent: {text}\033[0m")
        except Exception as e:
            print(f"\033[31m[ERROR] Failed to send danmu: {e}\033[0m")

    def closeEvent(self, event):
        self.stop_danmu_thread()
        super().closeEvent(event)

def create_credential_if_not_exist(credential_file='credential.json'):
    if not os.path.exists(credential_file):
        credential = {
            "sessdata": "",
            "bili_jct": "",
            "buvid3": "",
            "dedeuserid": "",
            "ac_time_value": ""
        }
        with open(credential_file, 'w') as f:
            json.dump(credential, f, indent=4)
        return credential
    else:
        return load_credential(credential_file)

def load_credential(credential_file='credential.json'):
    with open(credential_file, 'r') as f:
        credential = json.load(f)
    return credential

def save_config(credential, config_file='credential.json'):
    config = {
        "sessdata": credential.sessdata,
        "bili_jct": credential.bili_jct,
        "buvid3": credential.buvid3,
        "dedeuserid": credential.dedeuserid,
        "ac_time_value": credential.ac_time_value
    }
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)

def main():
    def start_player():
        cred = create_credential_if_not_exist()

        print(cred['sessdata'])

        room_id = int(room_id_entry.get())
        root.destroy()  # Close the Tkinter window

        loop = asyncio.get_event_loop()
        
        if cred['sessdata'] == "":
            print("\033[33m请登录：\033[0m")
            credential = login.login_with_qrcode()
            print(credential.sessdata)
            print(credential.bili_jct)
            save_config(credential)
            try:
                credential.raise_for_no_bili_jct()
                credential.raise_for_no_sessdata()
            except:
                print("\033[31m登陆失敗。。。\033[0m")
                return
        else:
            credential = Credential(sessdata=cred['sessdata'], bili_jct=cred['bili_jct'], ac_time_value=cred['ac_time_value'], buvid3=cred['buvid3'])
            print(credential.sessdata)
            print(credential.bili_jct)
            try:
                credential.raise_for_no_bili_jct()
                credential.raise_for_no_sessdata()
            except:
                print("\033[31m登陆失敗。。。\033[0m")
                return
            
        user_info = loop.run_until_complete(user.get_self_info(credential))
        print(f"\033[32m歡迎，{user_info['name']}!\033[0m")

        stream_url = url.get_bilibili_live_url(room_id)

        app = QApplication(sys.argv)
        player = Player(stream_url, room_id, credential)
        player.show()

        print("\033[32m[INFO] Starting application...\033[0m")
        sys.exit(app.exec_())

    # Create Tkinter window
    root = tk.Tk()
    root.iconbitmap("_internal/favicon.ico")
    root.title("Bilibili Live Player")
    root.geometry("300x120")

    # Room ID input
    ttk.Label(root, text="Enter Bilibili room ID:").pack(pady=5)
    room_id_entry = ttk.Entry(root)
    room_id_entry.pack(pady=5)

    # Start button
    ttk.Button(root, text="Start Player", command=start_player).pack(pady=10)

    root.mainloop()

if __name__ == '__main__':
    main()