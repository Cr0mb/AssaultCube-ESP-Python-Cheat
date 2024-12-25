import ctypes
from ctypes import wintypes, c_int, c_float, c_char, c_byte, Structure, byref
from pymem import Pymem
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt
import sys

class Pointer:
    player_count = 0x18AC0C
    entity_list = 0x18AC04
    local_player = 0x18AC00
    view_matrix = 0x17DFD0

class Vec2(Structure):
    _fields_ = [
        ("x", c_float),
        ("y", c_float)
    ]

class Vec2_int(Structure):
    _fields_ = [
        ("x", c_int),
        ("y", c_int)
    ]

class Vec3(Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
        ('z', c_float)
    ]

class Entity(Structure):
    _fields_ = [
        ("", 0x4 * c_byte),
        ("pos", Vec3),
        ("", 0xDC * c_byte),
        ("health", c_int),
        ("", 0x115 * c_byte),
        ("name", 0x50 * c_char),
        ("", 0xB7 * c_byte),
        ("team", c_int)
    ]

class WINDOWINFO(Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('rcWindow', wintypes.RECT),
        ('rcClient', wintypes.RECT),
        ('dwStyle', wintypes.DWORD),
        ('dwExStyle', wintypes.DWORD),
        ('dwWindowStatus', wintypes.DWORD),
        ('cxWindowBorders', wintypes.UINT),
        ('cyWindowBorders', wintypes.UINT),
        ('atomWindowType', wintypes.ATOM),
        ('wCreatorVersion', wintypes.WORD),
    ]

def get_window_info(title):
    hwnd = ctypes.windll.user32.FindWindowA(0, ctypes.c_char_p(title.encode()))
    win_info = WINDOWINFO()
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowInfo(hwnd, byref(win_info))
    ctypes.windll.user32.GetClientRect(hwnd, byref(rect))
    return (win_info.rcClient.left, win_info.rcClient.top, rect.right, rect.bottom)

def world_to_screen(matrix, pos, screen_width, screen_height):
    clip = Vec3()
    ndc = Vec2()

    clip.z = pos.x * matrix[3] + pos.y * matrix[7] + pos.z * matrix[11] + matrix[15]
    if clip.z < 0.2:
        raise IOError("WTS: Out of bounds")
    clip.x = pos.x * matrix[0] + pos.y * matrix[4] + pos.z * matrix[8] + matrix[12]
    clip.y = pos.x * matrix[1] + pos.y * matrix[5] + pos.z * matrix[9] + matrix[13]
    ndc.x = clip.x / clip.z
    ndc.y = clip.y / clip.z

    result_x = int((ndc.x + 1) * (screen_width / 2))
    result_y = int((1 - ndc.y) * (screen_height / 2))

    return result_x, result_y

class Overlay(QtWidgets.QWidget):
    def __init__(self, game_window):
        super().__init__()
        self.game_window = game_window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(*self.game_window)
        self.proc = Pymem("ac_client.exe")
        self.base = self.proc.base_address
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 14))
        painter.drawText(10, 20, f"FPS: {int(1000 / self.timer.interval())}")

        painter.drawText(10, 40, "GHax by Cr0mb")

        try:
            matrix = self.proc.read_ctype(self.base + Pointer.view_matrix, (16 * c_float)())[:]
            player_count = self.proc.read_int(self.base + Pointer.player_count)

            painter.drawText(10, 60, f"Total Players: {player_count}")

            if player_count > 1:
                ents = self.proc.read_ctype(self.proc.read_int(self.base + Pointer.entity_list), (player_count * c_int)())[1:]
                for ent_addr in ents:
                    ent_obj = self.proc.read_ctype(ent_addr, Entity())
                    if ent_obj.health > 0:
                        try:
                            screen_width = self.width()
                            screen_height = self.height()
                            head_pos = world_to_screen(matrix, Vec3(ent_obj.pos.x, ent_obj.pos.y, ent_obj.pos.z + 0.5), screen_width, screen_height)
                            feet_pos = world_to_screen(matrix, Vec3(ent_obj.pos.x, ent_obj.pos.y, ent_obj.pos.z - 4.5), screen_width, screen_height)
                        except:
                            continue

                        box_height = int(feet_pos[1] - head_pos[1])
                        box_width = int(box_height // 3)
                        box_x = int(head_pos[0] - box_width // 2)
                        box_y = int(head_pos[1])

                        painter.setBrush(QColor(128, 128, 128, 128))
                        painter.setPen(Qt.NoPen)
                        painter.drawRect(box_x, box_y, box_width, box_height)

                        painter.setBrush(Qt.NoBrush)
                        painter.setPen(QColor("blue") if ent_obj.team else QColor("red"))
                        painter.drawRect(box_x, box_y, box_width, box_height)

                        health_height = int(box_height * (ent_obj.health / 100.0))
                        painter.setBrush(QColor("green"))
                        painter.drawRect(box_x - 6, box_y + (box_height - health_height), 4, health_height)

                        painter.setPen(QColor("white"))
                        painter.drawText(box_x, box_y - 10, ent_obj.name.decode('utf-8'))
                        painter.drawText(box_x + 40, box_y + box_height // 2, f"HP: {ent_obj.health}")

                        painter.setPen(QColor("orange"))
                        screen_center = (screen_width // 2, screen_height // 1)
                        painter.drawLine(screen_center[0], screen_center[1], feet_pos[0], feet_pos[1])
        except Exception as e:
            painter.setPen(QColor("red"))
            painter.drawText(10, 80, f"Error: {str(e)}")

    def closeEvent(self, event):
        self.timer.stop()
        self.proc.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    game_window = get_window_info("AssaultCube")
    overlay = Overlay(game_window)
    
    def on_quit():
        overlay.close()

    app.aboutToQuit.connect(on_quit)
    overlay.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()