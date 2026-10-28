#!/usr/bin/env python3
"""
AC KONDO'S PACMAN — Python arcade port 0.1
Zero-shot full engine: levels 1–256, arcade graphics/audio (procedural, files=off).

Main menu: Play Game · Help · About · Exit
© AC Kondo 1999–2026. Inspired by Namco Pac-Man (1980) arcade.

Run:  python3 utrapacbykondov0.1.py
Requires: pygame-ce (import pygame)
"""

from __future__ import annotations

import array
import math
import random
import sys
from enum import Enum, auto

import pygame

# ---------------------------------------------------------------------------
TITLE = "AC KONDO'S PACMAN"
SUBTITLE = "Python arcade port 0.1"
COPYRIGHT = "© AC Kondo 1999–2026 — All rights reserved"
MAX_LEVEL = 256

TILE = 8
COLS, ROWS = 28, 31  # classic playfield (HUD above)
LOGICAL_W = COLS * TILE          # 224
LOGICAL_H = (ROWS + 5) * TILE    # 288 with HUD
SCALE = 3
FPS = 60

# Colors (arcade CRT-ish)
BLACK = (0, 0, 0)
WALL_BLUE = (33, 33, 255)
DOT = (255, 183, 174)
POWER = (255, 183, 174)
PAC = (255, 255, 0)
BLINKY = (255, 0, 0)
PINKY = (255, 184, 255)
INKY = (0, 255, 255)
CLYDE = (255, 184, 82)
FRIGHT = (33, 33, 255)
FRIGHT_FLASH = (255, 255, 255)
WHITE = (255, 255, 255)
TEXT = (255, 255, 255)
PINK_TXT = (255, 184, 255)
CYAN_TXT = (0, 255, 255)
RED_TXT = (255, 0, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)

# Classic maze — 28 wide, 31 tall. # wall  . pellet  o power  - gate  ' ' empty
# Faithful recreation of Namco Pac-Man maze topology.
MAZE = [
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#.####.#####.##.#####.####.#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#.####.##.########.##.####.#",
    "#......##....##....##......#",
    "######.##### ## #####.######",
    "     #.##### ## #####.#     ",
    "     #.##          ##.#     ",
    "     #.## ###--### ##.#     ",
    "######.## #      # ##.######",
    "      .   #      #   .      ",
    "######.## #      # ##.######",
    "     #.## ######## ##.#     ",
    "     #.##          ##.#     ",
    "     #.## ######## ##.#     ",
    "######.## ######## ##.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#.####.#####.##.#####.####.#",
    "#o..##................##..o#",
    "###.##.##.########.##.##.###",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#.##########.##.##########.#",
    "#.##########.##.##########.#",
    "#..........................#",
    "############################",
]

assert len(MAZE) == ROWS and all(len(r) == COLS for r in MAZE)


class Mode(Enum):
    MENU = auto()
    HELP = auto()
    ABOUT = auto()
    PLAY = auto()
    READY = auto()
    DYING = auto()
    LEVEL_CLEAR = auto()
    GAME_OVER = auto()


class GhostMode(Enum):
    SCATTER = auto()
    CHASE = auto()
    FRIGHTENED = auto()
    EATEN = auto()
    HOUSE = auto()


DIRS = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}
OPP = {"U": "D", "D": "U", "L": "R", "R": "L"}


# ---------------------------------------------------------------------------
# Audio — arcade-ish procedural SFX (files=off)
# ---------------------------------------------------------------------------
class AudioEngine:
    def __init__(self):
        self.enabled = True
        self.sr = 22050
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.sr, -16, 1, 512)
            self.sr = pygame.mixer.get_init()[0] or 22050
        except pygame.error:
            self.enabled = False
        self.sfx = {}
        if self.enabled:
            self.sfx["waka"] = self._chirp(420, 520, 0.05, 0.25)
            self.sfx["waka2"] = self._chirp(520, 420, 0.05, 0.25)
            self.sfx["power"] = self._siren(0.35)
            self.sfx["eat_ghost"] = self._sweep(200, 800, 0.25, 0.4)
            self.sfx["death"] = self._death()
            self.sfx["extra"] = self._square(880, 0.08, 0.3)
            self.sfx["fruit"] = self._square(660, 0.1, 0.3)
            self.sfx["start"] = self._jingle()
            self.sfx["credit"] = self._square(1100, 0.04, 0.2)
        self._waka = 0

    def _buf(self, data: array.array) -> pygame.mixer.Sound:
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _square(self, freq, dur, vol):
        n = max(1, int(self.sr * dur))
        amp = int(30000 * vol)
        period = max(1, int(self.sr / max(1.0, freq)))
        half = period // 2
        data = array.array("h", (amp if (i % period) < half else -amp for i in range(n)))
        return self._buf(data)

    def _chirp(self, f0, f1, dur, vol):
        n = max(1, int(self.sr * dur))
        amp = int(26000 * vol)
        data = array.array("h")
        phase = 0.0
        for i in range(n):
            t = i / n
            freq = f0 + (f1 - f0) * t
            phase += 2 * math.pi * freq / self.sr
            v = amp if math.sin(phase) >= 0 else -amp
            data.append(int(v * (1 - 0.3 * t)))
        return self._buf(data)

    def _sweep(self, f0, f1, dur, vol):
        return self._chirp(f0, f1, dur, vol)

    def _siren(self, dur):
        n = max(1, int(self.sr * dur))
        data = array.array("h")
        phase = 0.0
        for i in range(n):
            t = i / n
            freq = 180 + 80 * math.sin(t * math.pi * 8)
            phase += 2 * math.pi * freq / self.sr
            amp = int(18000 * (0.5 + 0.5 * math.sin(t * math.pi)))
            data.append(int(amp * math.sin(phase)))
        return self._buf(data)

    def _death(self):
        n = int(self.sr * 0.9)
        data = array.array("h")
        phase = 0.0
        for i in range(n):
            t = i / n
            freq = 600 * (1 - t) + 40
            phase += 2 * math.pi * freq / self.sr
            amp = int(22000 * (1 - t))
            data.append(int(amp * (1 if math.sin(phase) >= 0 else -1)))
        return self._buf(data)

    def _jingle(self):
        # short start jingle
        parts = []
        for f, d in ((523, 0.1), (659, 0.1), (784, 0.15), (1046, 0.2)):
            n = int(self.sr * d)
            amp = 20000
            period = max(1, int(self.sr / f))
            half = period // 2
            for i in range(n):
                parts.append(amp if (i % period) < half else -amp)
        return self._buf(array.array("h", parts))

    def play(self, name):
        if not self.enabled:
            return
        s = self.sfx.get(name)
        if s:
            s.play()

    def waka(self):
        self._waka ^= 1
        self.play("waka" if self._waka else "waka2")


# ---------------------------------------------------------------------------
# Level tables (arcade-inspired, extended to 256)
# ---------------------------------------------------------------------------
def level_params(level: int) -> dict:
    """Difficulty curve for levels 1..256."""
    lv = max(1, min(MAX_LEVEL, level))
    # Pac speeds (px/sec in logical space); ghosts relative
    if lv == 1:
        pac, ghost, fright_t = 75, 70, 6.0
    elif lv < 5:
        pac, ghost, fright_t = 80, 75, 5.0
    elif lv < 21:
        pac, ghost, fright_t = 85, 80, max(3.0, 5.0 - (lv - 5) * 0.15)
    elif lv < 100:
        pac, ghost, fright_t = 88, 85, max(1.5, 3.0 - (lv - 21) * 0.02)
    else:
        pac, ghost, fright_t = 90, min(92, 86 + (lv - 100) * 0.02), max(0.5, 1.5 - (lv - 100) * 0.005)

    flash = min(5, max(1, int(fright_t)))
    # Cruise Elroy thresholds (dots remaining)
    elroy1 = max(5, 20 - lv // 4)
    elroy2 = max(3, elroy1 // 2)
    fruit = ("CHERRY", "STRAWBERRY", "ORANGE", "APPLE", "MELON", "GALAXIAN",
             "BELL", "KEY")[min(7, (lv - 1) % 8 if lv < 8 else 7 if lv >= 13 else (lv - 1))]
    # Map fruit by arcade table roughly
    fruit_table = [
        "CHERRY", "STRAWBERRY", "ORANGE", "ORANGE", "APPLE", "APPLE",
        "MELON", "MELON", "GALAXIAN", "GALAXIAN", "BELL", "BELL", "KEY",
    ]
    fruit = fruit_table[min(len(fruit_table) - 1, lv - 1)] if lv <= 13 else "KEY"
    fruit_score = {
        "CHERRY": 100, "STRAWBERRY": 300, "ORANGE": 500, "APPLE": 700,
        "MELON": 1000, "GALAXIAN": 2000, "BELL": 3000, "KEY": 5000,
    }[fruit]
    return {
        "pac_speed": pac,
        "ghost_speed": ghost,
        "fright_speed": max(40, ghost * 0.55),
        "tunnel_speed": ghost * 0.5,
        "fright_time": fright_t,
        "flash": flash,
        "elroy1": elroy1,
        "elroy2": elroy2,
        "fruit": fruit,
        "fruit_score": fruit_score,
        "scatter_chase": _scatter_chase_pattern(lv),
    }


def _scatter_chase_pattern(lv: int):
    # Seconds: scatter, chase, scatter, chase, ... then infinite chase
    if lv == 1:
        return [7, 20, 7, 20, 5, 20, 5, 9999]
    if lv < 5:
        return [7, 20, 7, 20, 5, 1033, 0.01, 9999]
    return [5, 20, 5, 20, 5, 1037, 0.01, 9999]


# ---------------------------------------------------------------------------
# Maze helpers
# ---------------------------------------------------------------------------
def is_wall(c: str) -> bool:
    return c == "#"


def tile_at(maze, tx, ty):
    if ty < 0 or ty >= ROWS or tx < 0 or tx >= COLS:
        return "#"
    return maze[ty][tx]


def passable(maze, tx, ty, allow_gate=False):
    c = tile_at(maze, tx, ty)
    if c == "#":
        return False
    if c == "-" and not allow_gate:
        return False
    return True


# ---------------------------------------------------------------------------
# Actors
# ---------------------------------------------------------------------------
class Pacman:
    def __init__(self):
        self.x = 14 * TILE
        self.y = 23 * TILE + TILE // 2
        self.dir = "L"
        self.next_dir = "L"
        self.mouth = 0.0
        self.alive = True

    @property
    def tile(self):
        return int(self.x // TILE), int(self.y // TILE)

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 4, int(self.y) - 4, 8, 8)


class Ghost:
    def __init__(self, name, color, home, scatter_target):
        self.name = name
        self.color = color
        self.home = home  # tile spawn
        self.scatter = scatter_target
        self.x = home[0] * TILE + TILE // 2
        self.y = home[1] * TILE + TILE // 2
        self.dir = "L"
        self.mode = GhostMode.HOUSE
        self.frightened_t = 0.0
        self.house_timer = 0.0
        self.eaten = False

    @property
    def tile(self):
        return int(self.x // TILE), int(self.y // TILE)

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - 4, int(self.y) - 4, 8, 8)

    def reset(self, released=False):
        self.x = self.home[0] * TILE + TILE // 2
        self.y = self.home[1] * TILE + TILE // 2
        self.dir = "U" if self.name != "blinky" else "L"
        self.mode = GhostMode.SCATTER if released or self.name == "blinky" else GhostMode.HOUSE
        self.frightened_t = 0.0
        self.eaten = False


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{TITLE} — {SUBTITLE}")
        self.screen = pygame.display.set_mode((LOGICAL_W * SCALE, LOGICAL_H * SCALE))
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
        self.audio = AudioEngine()
        self.font = pygame.font.SysFont("Courier", 12, bold=True)
        self.font_sm = pygame.font.SysFont("Courier", 10, bold=True)
        self.font_lg = pygame.font.SysFont("Courier", 18, bold=True)
        self.mode = Mode.MENU
        self.menu_i = 0
        self.menu_items = ["PLAY GAME", "HELP", "ABOUT", "EXIT"]
        self.score = 0
        self.hi = 0
        self.lives = 3
        self.level = 1
        self.maze = [list(r) for r in MAZE]
        self.pac = Pacman()
        self.ghosts = self._make_ghosts()
        self.dots_left = 0
        self.ghost_combo = 0
        self.fruit = None
        self.fruit_t = 0.0
        self.dots_eaten = 0
        self.ready_t = 0.0
        self.dying_t = 0.0
        self.clear_t = 0.0
        self.wave_t = 0.0
        self.wave_i = 0
        self.params = level_params(1)
        self.flash = False
        self.frame = 0
        self._count_dots()

    def _make_ghosts(self):
        return [
            Ghost("blinky", BLINKY, (14, 11), (25, 0)),
            Ghost("pinky", PINKY, (14, 14), (2, 0)),
            Ghost("inky", INKY, (12, 14), (27, 30)),
            Ghost("clyde", CLYDE, (16, 14), (0, 30)),
        ]

    def _count_dots(self):
        self.dots_left = sum(1 for row in self.maze for c in row if c in ".o")

    def start_level(self, level: int, full_reset=False):
        self.level = max(1, min(MAX_LEVEL, level))
        self.params = level_params(self.level)
        self.maze = [list(r) for r in MAZE]
        self._count_dots()
        self.pac = Pacman()
        self.ghosts = self._make_ghosts()
        self.ghosts[0].mode = GhostMode.SCATTER  # Blinky out
        self.ghosts[0].y = 11 * TILE + TILE // 2
        self.ghosts[1].house_timer = 0.0
        self.ghosts[2].house_timer = 1.0
        self.ghosts[3].house_timer = 2.0
        self.ghost_combo = 0
        self.fruit = None
        self.fruit_t = 0.0
        self.dots_eaten = 0
        self.wave_t = 0.0
        self.wave_i = 0
        self.mode = Mode.READY
        self.ready_t = 2.2
        if full_reset:
            self.score = 0
            self.lives = 3
        self.audio.play("start")

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.frame += 1
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self._quit()
                elif ev.type == pygame.KEYDOWN:
                    self._key(ev.key)
            self._update(dt)
            self._draw()
            scaled = pygame.transform.scale(self.canvas, self.screen.get_size())
            self.screen.blit(scaled, (0, 0))
            pygame.display.flip()

    def _quit(self):
        pygame.quit()
        sys.exit(0)

    def _key(self, key):
        if self.mode == Mode.MENU:
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_i = (self.menu_i - 1) % len(self.menu_items)
                self.audio.play("credit")
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_i = (self.menu_i + 1) % len(self.menu_items)
                self.audio.play("credit")
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._menu_select()
            elif key == pygame.K_ESCAPE:
                self._quit()
        elif self.mode in (Mode.HELP, Mode.ABOUT):
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.mode = Mode.MENU
        elif self.mode == Mode.GAME_OVER:
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.mode = Mode.MENU
        elif self.mode in (Mode.PLAY, Mode.READY):
            if key == pygame.K_ESCAPE:
                self.mode = Mode.MENU
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.pac.next_dir = "L"
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.pac.next_dir = "R"
            elif key in (pygame.K_UP, pygame.K_w):
                self.pac.next_dir = "U"
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.pac.next_dir = "D"
        elif self.mode == Mode.LEVEL_CLEAR:
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                nxt = self.level + 1
                if nxt > MAX_LEVEL:
                    self.mode = Mode.GAME_OVER
                    self.message = "ALL 256 LEVELS CLEARED!"
                else:
                    self.start_level(nxt)

    def _menu_select(self):
        item = self.menu_items[self.menu_i]
        if item == "PLAY GAME":
            self.start_level(1, full_reset=True)
        elif item == "HELP":
            self.mode = Mode.HELP
        elif item == "ABOUT":
            self.mode = Mode.ABOUT
        elif item == "EXIT":
            self._quit()

    # ------------------------------------------------------------------ update
    def _update(self, dt):
        if self.mode == Mode.READY:
            self.ready_t -= dt
            if self.ready_t <= 0:
                self.mode = Mode.PLAY
            return
        if self.mode == Mode.DYING:
            self.dying_t -= dt
            if self.dying_t <= 0:
                if self.lives <= 0:
                    self.hi = max(self.hi, self.score)
                    self.mode = Mode.GAME_OVER
                else:
                    self._reset_positions()
                    self.mode = Mode.READY
                    self.ready_t = 2.0
            return
        if self.mode == Mode.LEVEL_CLEAR:
            self.clear_t -= dt
            return
        if self.mode != Mode.PLAY:
            return

        self._update_modes(dt)
        self._move_pac(dt)
        self._move_ghosts(dt)
        self._collisions()
        self._fruit_tick(dt)
        self.pac.mouth += dt * 12

    def _reset_positions(self):
        self.pac = Pacman()
        for i, g in enumerate(self.ghosts):
            g.reset(released=(i == 0))
            if i == 0:
                g.y = 11 * TILE + TILE // 2
                g.mode = GhostMode.SCATTER
            else:
                g.house_timer = i * 0.8
                g.mode = GhostMode.HOUSE
        self.fruit = None

    def _update_modes(self, dt):
        # Scatter/chase wave timer (skip while any frightened)
        if any(g.mode == GhostMode.FRIGHTENED for g in self.ghosts):
            for g in self.ghosts:
                if g.mode == GhostMode.FRIGHTENED:
                    g.frightened_t -= dt
                    if g.frightened_t <= 0:
                        g.mode = GhostMode.CHASE if self.wave_i % 2 else GhostMode.SCATTER
            self.flash = any(
                g.mode == GhostMode.FRIGHTENED and 0 < g.frightened_t < self.params["flash"]
                and int(g.frightened_t * 6) % 2 == 0
                for g in self.ghosts
            )
            return

        pattern = self.params["scatter_chase"]
        self.wave_t += dt
        dur = pattern[min(self.wave_i, len(pattern) - 1)]
        if self.wave_t >= dur:
            self.wave_t = 0.0
            self.wave_i = min(self.wave_i + 1, len(pattern) - 1)
            chase = self.wave_i % 2 == 1
            for g in self.ghosts:
                if g.mode in (GhostMode.SCATTER, GhostMode.CHASE):
                    g.mode = GhostMode.CHASE if chase else GhostMode.SCATTER
                    g.dir = OPP.get(g.dir, g.dir)  # reverse on mode change

        # Release from house (dot counters + timers, arcade-inspired)
        release_dots = {"blinky": 0, "pinky": 0, "inky": 30, "clyde": 60}
        for g in self.ghosts:
            if g.mode == GhostMode.HOUSE:
                g.house_timer -= dt
                need = release_dots.get(g.name, 0)
                if g.house_timer <= 0 and self.dots_eaten >= need:
                    g.mode = GhostMode.SCATTER
                    g.y = 11 * TILE + TILE // 2
                    g.x = 14 * TILE
                    g.dir = "L"

    def _center_snap(self, actor):
        tx, ty = int(actor.x // TILE), int(actor.y // TILE)
        cx, cy = tx * TILE + TILE // 2, ty * TILE + TILE // 2
        return abs(actor.x - cx) < 1.2 and abs(actor.y - cy) < 1.2, cx, cy, tx, ty

    def _move_pac(self, dt):
        speed = self.params["pac_speed"]
        # Tunnel slowdown optional — keep full for arcade feel on pac
        centered, cx, cy, tx, ty = self._center_snap(self.pac)
        if centered:
            self.pac.x, self.pac.y = cx, cy
            nd = self.pac.next_dir
            dx, dy = DIRS[nd]
            if passable(self.maze, tx + dx, ty + dy):
                self.pac.dir = nd
            dx, dy = DIRS[self.pac.dir]
            if not passable(self.maze, tx + dx, ty + dy):
                return  # blocked

        dx, dy = DIRS[self.pac.dir]
        self.pac.x += dx * speed * dt
        self.pac.y += dy * speed * dt

        # Tunnel wrap
        if self.pac.x < -TILE:
            self.pac.x = LOGICAL_W + TILE // 2
        elif self.pac.x > LOGICAL_W + TILE:
            self.pac.x = -TILE // 2

        # Eat pellets at tile center
        centered, cx, cy, tx, ty = self._center_snap(self.pac)
        if centered:
            cell = self.maze[ty][tx]
            if cell == ".":
                self.maze[ty][tx] = " "
                self.score += 10
                self.dots_left -= 1
                self.dots_eaten += 1
                self.audio.waka()
                self._check_fruit_spawn()
            elif cell == "o":
                self.maze[ty][tx] = " "
                self.score += 50
                self.dots_left -= 1
                self.dots_eaten += 1
                self._frighten()
                self.audio.play("power")
            if self.dots_left <= 0:
                self.mode = Mode.LEVEL_CLEAR
                self.clear_t = 2.5
                self.hi = max(self.hi, self.score)

    def _check_fruit_spawn(self):
        if self.dots_eaten in (70, 170) and self.fruit is None:
            self.fruit = {"name": self.params["fruit"], "score": self.params["fruit_score"]}
            self.fruit_t = 9.0

    def _fruit_tick(self, dt):
        if self.fruit:
            self.fruit_t -= dt
            if self.fruit_t <= 0:
                self.fruit = None

    def _frighten(self):
        self.ghost_combo = 0
        t = self.params["fright_time"]
        for g in self.ghosts:
            if g.mode != GhostMode.EATEN and g.mode != GhostMode.HOUSE:
                g.mode = GhostMode.FRIGHTENED
                g.frightened_t = t
                g.dir = OPP.get(g.dir, g.dir)

    def _ghost_target(self, g: Ghost):
        px, py = self.pac.tile
        pdx, pdy = DIRS[self.pac.dir]
        if g.mode == GhostMode.EATEN:
            return (14, 14)
        if g.mode == GhostMode.FRIGHTENED:
            return (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
        if g.mode == GhostMode.SCATTER:
            return g.scatter
        # CHASE personalities
        if g.name == "blinky":
            return (px, py)
        if g.name == "pinky":
            return (px + pdx * 4, py + pdy * 4)
        if g.name == "inky":
            bx, by = self.ghosts[0].tile
            ax, ay = px + pdx * 2, py + pdy * 2
            return (ax + (ax - bx), ay + (ay - by))
        # clyde: chase if far, scatter if near
        dist = abs(g.tile[0] - px) + abs(g.tile[1] - py)
        return (px, py) if dist > 8 else g.scatter

    def _move_ghosts(self, dt):
        for g in self.ghosts:
            if g.mode == GhostMode.HOUSE:
                # bob in house
                g.y = 14 * TILE + TILE // 2 + math.sin(self.frame * 0.1 + hash(g.name) % 7) * 2
                continue

            speed = self.params["ghost_speed"]
            if g.mode == GhostMode.FRIGHTENED:
                speed = self.params["fright_speed"]
            elif g.mode == GhostMode.EATEN:
                speed = 140
            # Elroy
            if g.name == "blinky" and g.mode == GhostMode.CHASE:
                if self.dots_left <= self.params["elroy2"]:
                    speed *= 1.15
                elif self.dots_left <= self.params["elroy1"]:
                    speed *= 1.08
            # Tunnel
            tx, ty = g.tile
            if tile_at(self.maze, tx, ty) == " " and (tx <= 0 or tx >= COLS - 1 or ty == 14 and (tx < 6 or tx > 21)):
                if ty == 14 and (tx < 5 or tx > 22):
                    speed = self.params["tunnel_speed"]

            centered, cx, cy, tx, ty = self._center_snap(g)
            if centered:
                g.x, g.y = float(cx), float(cy)
                if g.mode == GhostMode.EATEN and (tx, ty) == (14, 14):
                    g.mode = GhostMode.HOUSE
                    g.house_timer = 0.8
                    g.home = (14, 14)
                    continue
                target = self._ghost_target(g)
                options = []
                for d, (dx, dy) in DIRS.items():
                    if d == OPP[g.dir]:
                        continue
                    nx, ny = tx + dx, ty + dy
                    if passable(self.maze, nx, ny, allow_gate=(g.mode == GhostMode.EATEN)):
                        # distance to target
                        dist = (nx - target[0]) ** 2 + (ny - target[1]) ** 2
                        options.append((dist, d))
                if not options:
                    # reverse only choice
                    g.dir = OPP[g.dir]
                else:
                    if g.mode == GhostMode.FRIGHTENED:
                        g.dir = random.choice(options)[1]
                    else:
                        options.sort()
                        g.dir = options[0][1]

            dx, dy = DIRS[g.dir]
            g.x += dx * speed * dt
            g.y += dy * speed * dt
            if g.x < -TILE:
                g.x = LOGICAL_W + TILE // 2
            elif g.x > LOGICAL_W + TILE:
                g.x = -TILE // 2

    def _collisions(self):
        # Fruit
        if self.fruit:
            fx, fy = 14 * TILE, 17 * TILE + TILE // 2
            if abs(self.pac.x - fx) < 6 and abs(self.pac.y - fy) < 6:
                self.score += self.fruit["score"]
                self.audio.play("fruit")
                self.fruit = None
                if self.score >= 10000 and self.lives < 5:
                    # extra life once-ish
                    pass

        # Ghosts
        for g in self.ghosts:
            if abs(self.pac.x - g.x) < 6 and abs(self.pac.y - g.y) < 6:
                if g.mode == GhostMode.FRIGHTENED:
                    g.mode = GhostMode.EATEN
                    self.ghost_combo = min(self.ghost_combo + 1, 4)
                    pts = (200, 400, 800, 1600)[self.ghost_combo - 1]
                    self.score += pts
                    self.audio.play("eat_ghost")
                elif g.mode not in (GhostMode.EATEN, GhostMode.HOUSE):
                    self._pac_die()
                    return

        # Extra life every 10k
        # (simple check)
        if not hasattr(self, "_life_awarded"):
            self._life_awarded = 0
        while self.score >= (self._life_awarded + 1) * 10000:
            self._life_awarded += 1
            self.lives += 1
            self.audio.play("extra")

    def _pac_die(self):
        self.lives -= 1
        self.mode = Mode.DYING
        self.dying_t = 1.6
        self.audio.play("death")
        self.fruit = None

    # ------------------------------------------------------------------ draw
    def _draw(self):
        self.canvas.fill(BLACK)
        if self.mode == Mode.MENU:
            self._draw_menu()
        elif self.mode == Mode.HELP:
            self._draw_help()
        elif self.mode == Mode.ABOUT:
            self._draw_about()
        else:
            self._draw_hud()
            self._draw_maze()
            self._draw_actors()
            if self.mode == Mode.READY:
                self._center("READY!", 14 * TILE, YELLOW)
            elif self.mode == Mode.DYING:
                self._draw_death_anim()
            elif self.mode == Mode.LEVEL_CLEAR:
                self._center(f"LEVEL {self.level} CLEAR", 13 * TILE, GREEN)
                if self.level < MAX_LEVEL:
                    self._center("PRESS ENTER", 15 * TILE, WHITE)
                else:
                    self._center("256 COMPLETE!", 15 * TILE, PINK_TXT)
            elif self.mode == Mode.GAME_OVER:
                self._center("GAME OVER", 13 * TILE, RED_TXT)
                self._center("PRESS ENTER", 15 * TILE, WHITE)

    def _draw_menu(self):
        self._center(TITLE, 40, YELLOW)
        self._center(SUBTITLE, 58, CYAN_TXT)
        self._center("1 – 256 LEVELS", 78, PINK_TXT)
        # demo pac
        self._draw_pac_icon(LOGICAL_W // 2, 110, self.frame / 8)
        y0 = 140
        for i, item in enumerate(self.menu_items):
            col = YELLOW if i == self.menu_i else WHITE
            prefix = "> " if i == self.menu_i else "  "
            self._center(prefix + item, y0 + i * 18, col)
        self._center(COPYRIGHT, LOGICAL_H - 24, (120, 120, 120))
        self._center("ARROWS SELECT · ENTER CONFIRM", LOGICAL_H - 40, (160, 160, 160))

    def _draw_help(self):
        self._center("HELP", 24, YELLOW)
        lines = [
            "ARROW KEYS / WASD — MOVE",
            "EAT ALL DOTS TO CLEAR LEVEL",
            "POWER PELLET: EAT GHOSTS",
            "BLINKY PINKY INKY CLYDE",
            "LEVELS 1 TO 256 — SPEED UP",
            "ESC — MENU",
            "",
            "PRESS ENTER TO RETURN",
        ]
        for i, line in enumerate(lines):
            self._center(line, 60 + i * 16, WHITE if line else BLACK)
        self._center(COPYRIGHT, LOGICAL_H - 20, (100, 100, 100))

    def _draw_about(self):
        self._center("ABOUT", 24, YELLOW)
        lines = [
            TITLE,
            SUBTITLE,
            "",
            "ARCADE-STYLE PAC-MAN ENGINE",
            "PROCEDURAL GRAPHICS + AUDIO",
            "FILES = OFF",
            f"MAX LEVEL: {MAX_LEVEL}",
            "",
            COPYRIGHT,
            "",
            "PRESS ENTER TO RETURN",
        ]
        for i, line in enumerate(lines):
            self._center(line, 55 + i * 14, CYAN_TXT if i == 0 else WHITE)
        self._center("NOT AFFILIATED WITH BANDAI NAMCO", LOGICAL_H - 20, (90, 90, 90))

    def _draw_hud(self):
        s = self.font_sm.render(f"1UP  {self.score:06d}", True, WHITE)
        self.canvas.blit(s, (8, 2))
        h = self.font_sm.render(f"HI  {self.hi:06d}", True, WHITE)
        self.canvas.blit(h, (LOGICAL_W // 2 - h.get_width() // 2, 2))
        lv = self.font_sm.render(f"LV{self.level:03d}", True, PINK_TXT)
        self.canvas.blit(lv, (LOGICAL_W - 48, 2))
        # lives
        for i in range(max(0, self.lives - 1)):
            self._draw_pac_icon(12 + i * 14, LOGICAL_H - 10, 2.0)

    def _draw_maze(self):
        oy = 3 * TILE  # HUD offset
        for ty, row in enumerate(self.maze):
            for tx, c in enumerate(row):
                x, y = tx * TILE, ty * TILE + oy
                if c == "#":
                    pygame.draw.rect(self.canvas, WALL_BLUE, (x, y, TILE, TILE), 1)
                elif c == ".":
                    pygame.draw.rect(self.canvas, DOT, (x + 3, y + 3, 2, 2))
                elif c == "o":
                    if (self.frame // 10) % 2 == 0:
                        pygame.draw.circle(self.canvas, POWER, (x + 4, y + 4), 3)
                elif c == "-":
                    pygame.draw.line(self.canvas, PINK_TXT, (x, y + 4), (x + TILE, y + 4), 2)

    def _draw_actors(self):
        oy = 3 * TILE
        # fruit
        if self.fruit:
            fx, fy = 14 * TILE, 17 * TILE + TILE // 2 + oy
            pygame.draw.circle(self.canvas, RED_TXT, (fx, int(fy)), 4)
            pygame.draw.circle(self.canvas, GREEN, (fx, int(fy) - 4), 2)

        # ghosts
        for g in self.ghosts:
            self._draw_ghost(g, oy)

        # pac
        if self.mode != Mode.DYING:
            self._draw_pac(self.pac.x, self.pac.y + oy, self.pac.dir, self.pac.mouth)

    def _draw_pac(self, x, y, direction, mouth_phase):
        ang = {"R": 0, "D": 90, "L": 180, "U": 270}[direction]
        mouth = 25 + 25 * abs(math.sin(mouth_phase))
        rect = pygame.Rect(int(x) - 6, int(y) - 6, 12, 12)
        pygame.draw.circle(self.canvas, PAC, (int(x), int(y)), 6)
        # mouth wedge
        pts = [(int(x), int(y))]
        for a in (ang - mouth, ang + mouth):
            rad = math.radians(a)
            pts.append((int(x + 7 * math.cos(rad)), int(y + 7 * math.sin(rad))))
        pygame.draw.polygon(self.canvas, BLACK, pts)

    def _draw_pac_icon(self, x, y, phase):
        pygame.draw.circle(self.canvas, PAC, (int(x), int(y)), 5)
        mouth = 30 + 20 * abs(math.sin(phase))
        pts = [(int(x), int(y))]
        for a in (-mouth, mouth):
            rad = math.radians(a)
            pts.append((int(x + 6 * math.cos(rad)), int(y + 6 * math.sin(rad))))
        pygame.draw.polygon(self.canvas, BLACK, pts)

    def _draw_ghost(self, g: Ghost, oy):
        x, y = int(g.x), int(g.y + oy)
        if g.mode == GhostMode.EATEN:
            # eyes only
            pygame.draw.circle(self.canvas, WHITE, (x - 2, y - 1), 2)
            pygame.draw.circle(self.canvas, WHITE, (x + 2, y - 1), 2)
            pygame.draw.circle(self.canvas, WALL_BLUE, (x - 2, y - 1), 1)
            pygame.draw.circle(self.canvas, WALL_BLUE, (x + 2, y - 1), 1)
            return
        col = g.color
        if g.mode == GhostMode.FRIGHTENED:
            col = FRIGHT_FLASH if self.flash else FRIGHT
        # body
        pygame.draw.circle(self.canvas, col, (x, y - 1), 6)
        pygame.draw.rect(self.canvas, col, (x - 6, y - 1, 12, 7))
        # skirt
        for i in range(4):
            pygame.draw.circle(self.canvas, col, (x - 4 + i * 3, y + 6), 2)
        # eyes
        if g.mode != GhostMode.FRIGHTENED:
            pygame.draw.circle(self.canvas, WHITE, (x - 2, y - 2), 2)
            pygame.draw.circle(self.canvas, WHITE, (x + 2, y - 2), 2)
            ox, oy2 = DIRS[g.dir]
            pygame.draw.circle(self.canvas, WALL_BLUE, (x - 2 + ox, y - 2 + oy2), 1)
            pygame.draw.circle(self.canvas, WALL_BLUE, (x + 2 + ox, y - 2 + oy2), 1)
        else:
            pygame.draw.rect(self.canvas, WHITE, (x - 3, y - 2, 2, 2))
            pygame.draw.rect(self.canvas, WHITE, (x + 1, y - 2, 2, 2))

    def _draw_death_anim(self):
        oy = 3 * TILE
        t = 1.0 - max(0.0, self.dying_t) / 1.6
        # shrinking pac
        r = max(1, int(6 * (1 - t)))
        pygame.draw.circle(self.canvas, PAC, (int(self.pac.x), int(self.pac.y + oy)), r)

    def _center(self, text, y, color):
        surf = self.font.render(text, True, color)
        self.canvas.blit(surf, ((LOGICAL_W - surf.get_width()) // 2, int(y)))


def main():
    print(TITLE)
    print(SUBTITLE)
    print(COPYRIGHT)
    print(f"Levels 1–{MAX_LEVEL} | pygame-ce | files=off")
    Game().run()


if __name__ == "__main__":
    main()
