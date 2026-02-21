#!/usr/bin/env python3
"""
puppet.py — AI傀儡師 (ドラマー)
GoLのMIDI出力を監視し、密度に応じてローファイヒップホップのビートを叩く。

- dense (>4音): シンプルなビートに絞る / 休む
- sparse (<3音): フィルインやバリエーションを増やす
- 中間: 基本ビートをキープ
"""

import time
import random
import threading
import rtmidi

# ─── ドラムマッピング (lattice の ch10 パッド割り当て) ───────────────────
KICK = 36
SNARE = 37
HIHAT = 38
OPENHAT = 39
LOFI_KICK_L = 40
LOFI_KICK_M = 41
LOFI_KICK_H = 42
CLAP = 43
PERC1 = 44
PERC2 = 45

CH_DRUM = 9  # ch10 (0-indexed)
CHANNEL_GOL = 0  # GoLの出力チャンネル

# ─── BPM ──────────────────────────────────────────────────────────────────
BPM = 78  # ローファイヒップホップの典型テンポ
BEAT = 60.0 / BPM  # 1拍の秒数
SIXTEENTH = BEAT / 4


class Puppet:
    def __init__(self):
        self.gol_active: set[int] = set()
        self.lock = threading.Lock()

        # 入力: GoL の MIDI を監視
        self.midi_in = rtmidi.MidiIn()
        self.midi_in.set_client_name("Kugutsushi-In")

        # 出力: 仮想ポート "Kugutsushi" → SuperCollider
        self.midi_out = rtmidi.MidiOut()
        self.midi_out.open_virtual_port("Kugutsushi")
        print("[puppet] Virtual MIDI port 'Kugutsushi' opened.")

        self._connect_gol_input()
        self.running = False
        self.bar = 0  # 現在の小節数

    def _connect_gol_input(self):
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
            self.midi_in.open_virtual_port("Kugutsushi-Monitor")
            print("[puppet] GoL not found. Opened virtual monitor port.")

        self.midi_in.set_callback(self._on_midi)
        self.midi_in.ignore_types(sysex=True, timing=True, active_sense=True)

    def _on_midi(self, event, data=None):
        msg, _ = event
        if len(msg) < 3:
            return
        status, note, vel = msg[0], msg[1], msg[2]
        ch = status & 0x0F
        msg_type = status & 0xF0
        if ch != CHANNEL_GOL:
            return
        with self.lock:
            if msg_type == 0x90 and vel > 0:
                self.gol_active.add(note)
            elif msg_type == 0x80 or (msg_type == 0x90 and vel == 0):
                self.gol_active.discard(note)

    @property
    def density(self) -> int:
        with self.lock:
            return len(self.gol_active)

    def _hit(self, note: int, vel: int = 80):
        """ドラムを1回叩く (ch10)"""
        self.midi_out.send_message([0x99, note, vel])
        # ドラムは打楽器なので即座にnote_off
        self.midi_out.send_message([0x89, note, 0])

    def _humanize(self, vel: int, amount: int = 15) -> int:
        """ベロシティに揺らぎを加える"""
        return max(30, min(120, vel + random.randint(-amount, amount)))

    def _swing_delay(self, step: int) -> float:
        """偶数ステップにスウィング感 (裏拍を少し遅らせる)"""
        if step % 2 == 1:
            return SIXTEENTH * random.uniform(0.05, 0.15)
        return 0

    def _play_basic_beat(self, step: int):
        """基本ビート: kick-hat-snare-hat パターン"""
        # step: 0-15 (16ステップ = 1小節)
        vel_kick = self._humanize(90)
        vel_snare = self._humanize(85)
        vel_hat = self._humanize(50)

        # キック: 1拍目 + 3拍目の手前
        if step == 0:
            self._hit(KICK, vel_kick)
        elif step == 6:
            self._hit(LOFI_KICK_M, self._humanize(70))
        elif step == 10 and random.random() < 0.3:
            self._hit(KICK, self._humanize(60))

        # スネア: 2拍目 + 4拍目
        if step == 4:
            self._hit(SNARE, vel_snare)
        elif step == 12:
            self._hit(SNARE, vel_snare)

        # ハイハット: 8分音符
        if step % 2 == 0:
            self._hit(HIHAT, vel_hat)
        elif random.random() < 0.3:
            # ゴーストハット
            self._hit(HIHAT, self._humanize(30, 5))

    def _play_sparse_beat(self, step: int):
        """GoLが静かなとき: フィルインやバリエーション多め"""
        self._play_basic_beat(step)

        # 追加のフィルイン要素
        if step == 14 and random.random() < 0.5:
            self._hit(CLAP, self._humanize(65))
        if step == 15 and random.random() < 0.4:
            self._hit(LOFI_KICK_L, self._humanize(55))
        if step in (13, 14, 15) and random.random() < 0.3:
            self._hit(random.choice([PERC1, PERC2]), self._humanize(45))
        # オープンハット
        if step == 8 and random.random() < 0.4:
            self._hit(OPENHAT, self._humanize(55))

    def _play_dense_beat(self, step: int):
        """GoLが賑やかなとき: シンプルに引く"""
        vel_hat = self._humanize(35, 5)

        # キックとスネアだけ最低限
        if step == 0:
            self._hit(KICK, self._humanize(70))
        if step == 4 or step == 12:
            self._hit(SNARE, self._humanize(60))

        # ハイハットは4拍のみ
        if step % 4 == 0:
            self._hit(HIHAT, vel_hat)

    def run(self):
        self.running = True
        print(f"[puppet] Drummer mode. BPM={BPM}. Press Ctrl+C to stop.")
        try:
            while self.running:
                d = self.density
                for step in range(16):
                    if not self.running:
                        break

                    swing = self._swing_delay(step)
                    if swing > 0:
                        time.sleep(swing)

                    if d > 4:
                        self._play_dense_beat(step)
                    elif d < 3:
                        self._play_sparse_beat(step)
                    else:
                        self._play_basic_beat(step)

                    # density を定期的に更新
                    if step % 4 == 0:
                        d = self.density

                    time.sleep(SIXTEENTH - swing)

                self.bar += 1

        except KeyboardInterrupt:
            print("\n[puppet] Stopping...")
        finally:
            self.midi_in.close_port()
            self.midi_out.close_port()
            print("[puppet] Done.")


def main():
    puppet = Puppet()
    puppet.run()

if __name__ == "__main__":
    main()
