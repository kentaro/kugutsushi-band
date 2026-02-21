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

## 依存関係

- [lattice](https://github.com/kentaro/lattice) — SuperCollider シンセ (別リポジトリ)
- gol-synth — GoL MIDI firmware (別リポジトリ)
- `python-rtmidi` — 傀儡師の MIDI I/O

## セットアップ (pi02)

```bash
# lattice を clone
git clone https://github.com/kentaro/lattice ~/src/github.com/kentaro/lattice

# kugutsushi-band を clone
git clone https://github.com/kentaro/kugutsushi-band ~/src/github.com/kentaro/kugutsushi-band

# 傀儡師の依存をインストール (uv 推奨)
cd ~/src/github.com/kentaro/kugutsushi-band/kugutsushi
uv pip install -r requirements.txt
```

## 起動

```bash
bash ~/src/github.com/kentaro/kugutsushi-band/bin/start
```

内部で以下を順番に実行:
1. `lattice` (SuperCollider) をバックグラウンド起動
2. 8秒待ってから MIDI ルーティング設定 (`aconnect`)
3. AI傀儡師 (`puppet.py`) をバックグラウンド起動

Ctrl+C で全プロセスを停止。

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
