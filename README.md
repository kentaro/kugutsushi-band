# kugutsushi-band

バンド統合プロジェクト。lattice + gol-synth + AI傀儡師を束ねる。

## 構成

```
gol-synth (Pico)  ──┐
                     ├── aconnect ──► lattice (SuperCollider)
Launchkey Mini ───┐  │                   ↑
                  ├──┘              ←────┘
AI 傀儡師 ────────┘
```

## 演奏方法

### 準備

pi02にSSHしてバンドを起動する:

```bash
ssh kentaro@pi02.local
bash ~/src/github.com/kentaro/kugutsushi-band/bin/start
```

これで以下が自動的に立ち上がる:
1. **lattice** (SuperCollider) — 音を出すシンセ
2. **AI傀儡師** (puppet.py) — GoLの演奏に反応して即興する
3. **MIDIルーティング** — 全デバイスをSuperColliderに接続

### 演奏

| 入力 | 何が起きるか |
|------|------------|
| **Launchkey 鍵盤** | ピアノ音色で演奏 (ch1) |
| **Launchkey パッド下段** | ローファイドラム: Kick / Snare / HiHat / OpenHH |
| **Launchkey パッド上段左** | ローファイ 808キック ×3 (ピッチ違い) |
| **Launchkey パッド上段右** | Clap / Perc ×4 / FX ×4 |
| **Launchkey ノブ 1-7** | Cutoff / Resonance / Attack / Release / Reverb / Detune / LFO |
| **Launchkey ノブ 8** | マスターボリューム |
| **Launchkey Modストリップ** | ビブラート / デチューン |
| **Launchkey ピッチベンド** | ±2半音 |
| **gol-synth** | Game of Life の生死がMIDI音に (ch0-7) |
| **AI傀儡師** | GoLの密度を見て自動的にフィルイン |

### 停止

`Ctrl+C` で全プロセスを停止。

### lattice単体で使う場合

```bash
bash ~/src/github.com/kentaro/lattice/bin/lattice
```

gol-synthやAI傀儡師なしでも、Launchkey単体で楽器として使える。

## 依存関係

- [lattice](https://github.com/kentaro/lattice) — SuperCollider シンセ (別リポジトリ)
- gol-synth — GoL MIDI firmware (別リポジトリ)
- `python-rtmidi` — 傀儡師の MIDI I/O

## セットアップ (pi02)

```bash
# lattice を clone
git clone git@github.com:kentaro/lattice.git ~/src/github.com/kentaro/lattice

# kugutsushi-band を clone
git clone git@github.com:kentaro/kugutsushi-band.git ~/src/github.com/kentaro/kugutsushi-band

# 傀儡師の依存をインストール
cd ~/src/github.com/kentaro/kugutsushi-band/kugutsushi
python3 -m venv .venv
.venv/bin/pip install python-rtmidi
```

## AI傀儡師のロジック

GoLのアクティブ音数 (density) に応じて演奏スタイルを変える:

| GoL density | 傀儡師の動作 |
|------------|------------|
| > 4音 (dense) | 発音を止めてスペースを作る |
| < 3音 (sparse) | フィルインで1〜3音埋める |
| 3〜4音 (中間) | ゆっくり単音で絡む |

- スケール: `[60, 65, 70, 76, 81, 86, 91, 96]` (GoLと共有)
- GoLが鳴らしていない音程を優先

## ディレクトリ構成

```
kugutsushi-band/
├── bin/
│   └── start               # マスター起動スクリプト
├── routing/
│   └── connect.sh          # aconnect MIDI ルーティング
└── kugutsushi/
    ├── puppet.py            # AI傀儡師 即興ロジック
    └── requirements.txt     # python-rtmidi
```
