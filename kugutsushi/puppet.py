#!/usr/bin/env python3
"""
puppet.py — AI傀儡師
GoLのMIDI出力を監視し、密度に応じて自動演奏する即興ロジック。

- GoLのアクティブ音数(density)を計測
- dense (>4音): 傀儡師は発音を減らしスペースを作る
- sparse (<3音): 傀儡師がフィルインで埋める
- スケール: GoLと同じ [60,65,70,76,81,86,91,96] 内で演奏
- GoLが鳴らしていない音程を優先選択
"""

import time
import random
import threading
import rtmidi
from rtmidi.midiutil import open_midiinput

# GoL と傀儡師が共有するスケール (Slendro系, D-minor pentatonic variant)
GOL_SCALE = [60, 65, 70, 76, 81, 86, 91, 96]

CHANNEL_GOL = 0   # ch1 (0-indexed) — GoLの出力チャンネル

class Puppet:
    def __init__(self):
        self.gol_active: set[int] = set()   # GoLが現在鳴らしているノート
        self.my_active: set[int] = set()    # 傀儡師が鳴らしているノート
        self.lock = threading.Lock()

        # 入力: GoL の MIDI を監視
        self.midi_in = rtmidi.MidiIn()
        self.midi_in.set_client_name("Kugutsushi-In")

        # 出力: 仮想ポート "Kugutsushi" → SuperCollider
        self.midi_out = rtmidi.MidiOut()
        self.midi_out.open_virtual_port("Kugutsushi")
        print("[puppet] Virtual MIDI port 'Kugutsushi' opened.")

        # GoL の MIDI ポートを探して接続
        self._connect_gol_input()

        self.running = False

    def _connect_gol_input(self):
        """GoL MIDI ポートを探して接続する。見つからなければ仮想入力で待機。"""
        ports = self.midi_in.get_ports()
        print(f"[puppet] Available MIDI input ports: {ports}")
        gol_port = next(
            (i for i, p in enumerate(ports) if "Game of Life" in p),
            None
        )
        if gol_port is not None:
            self.midi_in.open_port(gol_port)
            print(f"[puppet] Connected to GoL MIDI port: {ports[gol_port]}")
        else:
            # 仮想入力ポートで待機 (テスト用)
            self.midi_in.open_virtual_port("Kugutsushi-Monitor")
            print("[puppet] GoL not found. Opened virtual monitor port.")

        self.midi_in.set_callback(self._on_midi)
        self.midi_in.ignore_types(sysex=True, timing=True, active_sense=True)

    def _on_midi(self, event, data=None):
        """GoL の MIDI イベントを受信して density を更新する。"""
        msg, _ = event
        if len(msg) < 3:
            return
        status, note, vel = msg[0], msg[1], msg[2]
        ch = status & 0x0F
        msg_type = status & 0xF0

        if ch != CHANNEL_GOL:
            return

        with self.lock:
            if msg_type == 0x90 and vel > 0:   # note_on
                self.gol_active.add(note)
            elif msg_type == 0x80 or (msg_type == 0x90 and vel == 0):  # note_off
                self.gol_active.discard(note)

    @property
    def density(self) -> int:
        with self.lock:
            return len(self.gol_active)

    def _gol_active_snapshot(self) -> set[int]:
        with self.lock:
            return set(self.gol_active)

    def _available_notes(self) -> list[int]:
        """GoLが鳴らしていないスケール音を返す。"""
        gol = self._gol_active_snapshot()
        return [n for n in GOL_SCALE if n not in gol]

    def _note_on(self, note: int, vel: int = 64):
        self.midi_out.send_message([0x90, note, vel])  # ch1
        with self.lock:
            self.my_active.add(note)

    def _note_off(self, note: int):
        self.midi_out.send_message([0x80, note, 0])
        with self.lock:
            self.my_active.discard(note)

    def _silence_all(self):
        """現在鳴らしている全音を止める。"""
        with self.lock:
            notes = list(self.my_active)
        for note in notes:
            self._note_off(note)

    def _play_fillin(self, count: int = 2):
        """空きスケール音から count 音選んで短く鳴らす。"""
        available = self._available_notes()
        if not available:
            return
        chosen = random.sample(available, min(count, len(available)))
        dur = random.uniform(0.15, 0.5)
        vel = random.randint(45, 80)
        for note in chosen:
            self._note_on(note, vel)
        time.sleep(dur)
        for note in chosen:
            self._note_off(note)

    def run(self):
        """メインループ: density に応じて演奏/休止を切り替える。"""
        self.running = True
        print("[puppet] Running. Press Ctrl+C to stop.")
        try:
            while self.running:
                d = self.density
                my_count = len(self.my_active)

                if d > 4:
                    # GoLが賑やか → 傀儡師は引いてスペースを作る
                    if my_count > 0:
                        self._silence_all()
                    # ランダムな休止
                    time.sleep(random.uniform(0.3, 1.0))

                elif d < 3:
                    # GoLが閑散 → フィルイン
                    fill_count = random.randint(1, 3)
                    self._play_fillin(fill_count)
                    # フィルイン間の間隔
                    time.sleep(random.uniform(0.2, 0.8))

                else:
                    # 中間 → ゆっくり単音で絡む
                    available = self._available_notes()
                    if available and random.random() < 0.4:
                        note = random.choice(available)
                        vel = random.randint(40, 70)
                        dur = random.uniform(0.2, 0.6)
                        self._note_on(note, vel)
                        time.sleep(dur)
                        self._note_off(note)
                    time.sleep(random.uniform(0.3, 0.9))

        except KeyboardInterrupt:
            print("\n[puppet] Stopping...")
        finally:
            self._silence_all()
            self.midi_in.close_port()
            self.midi_out.close_port()
            print("[puppet] Done.")

def main():
    puppet = Puppet()
    puppet.run()

if __name__ == "__main__":
    main()
