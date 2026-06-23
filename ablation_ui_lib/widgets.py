from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        master,
        text: str,
        command=None,
        width: int = 150,
        height: int = 34,
        radius: int = 12,
        normal_bg: str = "#2e7d32",
        normal_fg: str = "white",
        hover_bg: str = "#256628",
        press_bg: str = "#1e5a22",
        border_color: str = "#1f5e26",
        disabled_bg: str = "#c7c7c7",
        disabled_fg: str = "#7a7a7a",
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT,
            cursor="hand2",
            bg=self._detect_parent_bg(master),
        )
        self._text = text
        self._command = command
        self._radius = radius
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._palette = {
            "normal_bg": normal_bg,
            "normal_fg": normal_fg,
            "hover_bg": hover_bg,
            "press_bg": press_bg,
            "border_color": border_color,
            "disabled_bg": disabled_bg,
            "disabled_fg": disabled_fg,
        }

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    @staticmethod
    def _mix_colors(base: str, target: str, ratio: float) -> str:
        def _rgb(hex_color: str) -> tuple[int, int, int]:
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

        br, bg, bb = _rgb(base)
        tr, tg, tb = _rgb(target)
        r = int(br + (tr - br) * ratio)
        g = int(bg + (tg - bg) * ratio)
        b = int(bb + (tb - bb) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _detect_parent_bg(master) -> str:
        try:
            bg = master.cget("background")
            if bg:
                return bg
        except Exception:
            pass
        return "#f0f0f0"

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._pressed = False
        self._hover = False if not enabled else self._hover
        self.config(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def set_palette(self, **kwargs) -> None:
        self._palette.update(kwargs)
        self._draw()

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, **kwargs):
        points = [
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _draw(self) -> None:
        self.delete("all")
        w = int(self.cget("width"))
        h = int(self.cget("height"))

        if not self._enabled:
            fill = self._palette["disabled_bg"]
            fg = self._palette["disabled_fg"]
            shadow = self._mix_colors(fill, "#ffffff", 0.18)
        elif self._pressed:
            fill = self._palette["press_bg"]
            fg = self._palette["normal_fg"]
            shadow = self._mix_colors(fill, "#000000", 0.12)
        elif self._hover:
            fill = self._palette["hover_bg"]
            fg = self._palette["normal_fg"]
            shadow = self._mix_colors(fill, "#000000", 0.08)
        else:
            fill = self._palette["normal_bg"]
            fg = self._palette["normal_fg"]
            shadow = self._mix_colors(fill, "#000000", 0.06)

        self._rounded_rect(
            2,
            3,
            w - 2,
            h - 1,
            self._radius,
            fill=shadow,
            outline=shadow,
            width=1,
        )

        self._rounded_rect(
            1,
            1,
            w - 2,
            h - 3,
            self._radius,
            fill=fill,
            outline=self._palette["border_color"],
            width=1,
        )
        font = tkfont.nametofont("TkDefaultFont").copy()
        font.configure(weight="bold", size=max(int(font.cget("size")), 9))
        self.create_text(
            w // 2,
            (h // 2) - 1,
            text=self._text,
            fill=fg,
            font=font,
        )

    def _on_enter(self, _event) -> None:
        if not self._enabled:
            return
        self._hover = True
        self._draw()

    def _on_leave(self, _event) -> None:
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event) -> None:
        if not self._enabled:
            return
        self._pressed = True
        self._draw()

    def _on_release(self, event) -> None:
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if not was_pressed:
            return
        x, y = event.x, event.y
        if 0 <= x <= int(self.cget("width")) and 0 <= y <= int(self.cget("height")):
            if callable(self._command):
                self._command()
