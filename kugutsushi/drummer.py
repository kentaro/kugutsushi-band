#!/usr/bin/env python3
"""
drummer.py — AI傀儡師ドラムデーモン

起動したまま待機。/tmp/drum.cmd を監視して即応答。
- echo start > /tmp/drum.cmd  → 演奏開始
- echo stop  > /tmp/drum.cmd  → 演奏停止

即興ロジック:
- GoLの密度変化でリアルタイムにパターンを崩す
- 4小節ごとにパターンチェンジ
- 突発的なアクセント・ゴースト・ずらしを入れる
- フィルインは「溜めてから崩す」タイミングで
"""

import rtmidi, time, random, threading, os

KICK=36; SNARE=37; HIHAT=38; OPEN_HH=39; LOFIKICK=40; CLAP=43; PERC=44; PERC2=45
CH=9
CMD_FILE = "/tmp/drum.cmd"
BEAT     = 0.8        # BPM75
SIXTEENTH = BEAT / 4
SWING_R   = SIXTEENTH * 0.18

KICK_PATTERNS = [
    [1,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0],  # 基本
    [1,0,0,0, 0,0,0,0, 1,0,0,1, 0,0,0,0],  # 3拍半追加
    [1,0,0,0, 0,0,1,0, 1,0,0,0, 0,0,0,0],  # 2拍前追加
    [1,0,0,1, 0,0,0,0, 1,0,0,0, 0,0,0,0],  # 1拍半追加
    [1,0,0,0, 0,0,0,0, 0,0,1,0, 1,0,0,0],  # 3拍ずらし
    [1,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,1,0],  # 4拍前キック
]
SNARE_PATTERNS = [
    [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0],  # 基本
    [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,1,0],  # 4拍半追加
    [0,0,0,0, 1,0,0,1, 0,0,0,0, 1,0,0,0],  # 2拍半追加
    [0,0,0,0, 0,0,1,0, 0,0,0,0, 1,0,0,0],  # 2拍後ろに
    [0,0,1,0, 1,0,0,0, 0,0,0,0, 1,0,0,0],  # 前にゴースト
]
HH_PATTERNS = [
    [1,1,1,1, 1,1,1,1, 1,1,1,1, 1,1,1,1],  # 16分全部
    [1,1,1,0, 1,0,1,1, 1,1,0,1, 1,0,1,1],  # たかたかA
    [1,0,1,1, 1,1,1,0, 1,0,1,1, 1,1,0,1],  # たかたかB
    [1,0,1,0, 1,1,1,0, 1,0,1,0, 1,1,0,1],  # 8分+アクセント
    [1,1,0,1, 1,0,1,1, 0,1,1,0, 1,1,0,1],  # シャッフル強め
]
FILL_PATTERNS = [
    [0,0,0,0, 0,0,0,0, 1,1,1,1, 1,1,1,1],  # 後半ドコドコ
    [0,0,0,0, 0,0,1,1, 0,1,1,0, 1,1,1,1],  # だんだん増える
    [0,0,0,0, 0,0,0,0, 0,1,0,1, 1,0,1,1],  # スネア連打
]

class Drummer:
    def __init__(self):
        self.out = rtmidi.MidiOut()
        sc_idx = next(i for i, p in enumerate(self.out.get_ports())
                      if 'SuperCollider' in p and 'in0' in p)
        self.out.open_port(sc_idx)

        self.inp = rtmidi.MidiIn()
        in_ports = self.inp.get_ports()
        gol_idx = next((i for i, p in enumerate(in_ports) if 'Game of Life' in p), None)
        if gol_idx is not None:
            self.inp.open_port(gol_idx)
        else:
            self.inp.open_virtual_port("gol-monitor")
        self.inp.set_callback(self._on_gol)
        self.inp.ignore_types(sysex=True, timing=True, active_sense=True)

        self.active = set()
        self.lock = threading.Lock()
        self.playing = False
        self.bar = 0

        # 前回密度（急変を検知して即興する）
        self.prev_density = 0
        self.energy = 0.5  # 0.0(静) ~ 1.0(激しい)

    def _on_gol(self, event, data=None):
        msg, _ = event
        if len(msg) < 3: return
        s, n, v = msg[0], msg[1], msg[2]
        with self.lock:
            if (s & 0xF0) == 0x90 and v > 0: self.active.add(n)
            else: self.active.discard(n)

    def density(self):
        with self.lock: return len(self.active)

    def hit(self, note, vel_base, vel_range=10):
        vel = max(1, min(127, vel_base + random.randint(-vel_range, vel_range)))
        self.out.send_message([0x90|CH, int(note), int(vel)])
        threading.Timer(0.04, lambda: self.out.send_message([0x80|CH, int(note), 0])).start()

    def silence(self):
        for ch in range(16):
            self.out.send_message([0xB0|ch, 123, 0])

    def play_bar(self):
        t0 = time.perf_counter()
        d = self.density()

        # エネルギー更新（密度変化に追従）
        target_energy = min(1.0, d / 6.0)
        self.energy = self.energy * 0.7 + target_energy * 0.3

        minimal = self.energy > 0.7
        fill = self.energy < 0.2 and random.random() < 0.5

        # GoL密度が急変したら即座にパターンチェンジ
        density_jump = abs(d - self.prev_density) > 3
        self.prev_density = d

        if self.bar % 4 == 0 or density_jump:
            self.kick_pat  = random.choice(KICK_PATTERNS)
            self.snare_pat = random.choice(SNARE_PATTERNS)
            self.hh_pat    = random.choice(HH_PATTERNS)

        is_fill_bar = (self.bar % 4 == 3) and not minimal
        fill_pat = random.choice(FILL_PATTERNS) if is_fill_bar else None

        for i in range(16):
            if not self.playing: return

            step_t = t0 + i * SIXTEENTH
            swing_offset = SWING_R if i % 2 == 1 else 0
            now = time.perf_counter()
            wait = step_t + swing_offset - now
            if wait > 0: time.sleep(wait)

            # 即興的なゴーストノート（確率でベロシティ極小のスネア）
            ghost = random.random() < (0.15 * (1 - self.energy))

            if is_fill_bar and fill_pat and fill_pat[i]:
                self.hit(SNARE, 100, vel_range=8)
                if i % 2 == 0: self.hit(PERC, 75)
            else:
                if self.kick_pat[i]:
                    self.hit(KICK, 105)
                if self.snare_pat[i]:
                    vel = 88 if i not in [4,12] else 92
                    self.hit(SNARE, vel)
                elif ghost and i not in [0,8]:
                    self.hit(SNARE, 28, vel_range=5)  # ゴーストノート

            # ハイハット
            if minimal:
                if i % 2 == 0: self.hit(HIHAT, 58, vel_range=8)
            elif self.hh_pat[i]:
                vel = 72 if i % 4 == 0 else (58 if i % 2 == 0 else 44)
                self.hit(HIHAT, vel, vel_range=8)

            # オープンハイハット
            if i == 14 and not minimal and random.random() < 0.2:
                self.hit(OPEN_HH, 70)

            # 突発クラップ（GoLが静かなとき）
            if fill and i in [4, 12]:
                self.hit(CLAP, 75)

        self.bar += 1
        elapsed = time.perf_counter() - t0
        drift = BEAT * 4 - elapsed
        if drift > 0.001: time.sleep(drift)

    def run(self):
        # CMD_FILEを初期化
        with open(CMD_FILE, 'w') as f: f.write("stop\n")
        print("[drummer] 待機中... echo start > /tmp/drum.cmd で開始", flush=True)

        while True:
            # コマンド読み取り
            try:
                with open(CMD_FILE, 'r') as f:
                    cmd = f.read().strip()
            except: cmd = "stop"

            if cmd == "start" and not self.playing:
                self.playing = True
                self.bar = 0
                self.energy = 0.5
                print("[drummer] 演奏開始", flush=True)
            elif cmd == "stop" and self.playing:
                self.playing = False
                self.silence()
                print("[drummer] 停止", flush=True)

            if self.playing:
                self.play_bar()
            else:
                time.sleep(0.05)

if __name__ == "__main__":
    d = Drummer()
    d.run()
