#!/bin/bash
# connect.sh — MIDI ルーティング設定
# gol-synth + Launchkey + 傀儡師 → SuperCollider (lattice)

set -e

echo "[routing] Setting up MIDI connections..."

# SuperCollider が起動するまでポートが現れない場合があるので少し待つ
wait_for_port() {
    local name="$1"
    local max_wait=30
    local elapsed=0
    while ! aconnect -l | grep -q "$name"; do
        if [ $elapsed -ge $max_wait ]; then
            echo "[routing] WARNING: Port '$name' not found after ${max_wait}s, skipping."
            return 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    echo "[routing] Found port: $name"
    return 0
}

# SuperCollider を待つ (必須)
wait_for_port "SuperCollider" || { echo "[routing] ERROR: SuperCollider port not found."; exit 1; }

# gol-synth → lattice
if aconnect -l | grep -q "Game of Life MIDI"; then
    aconnect 'Game of Life MIDI':0 'SuperCollider':0
    echo "[routing] gol-synth → SuperCollider"
else
    echo "[routing] INFO: gol-synth not connected, skipping."
fi

# Launchkey Mini MK4 25 → lattice
if aconnect -l | grep -q "Launchkey Mini MK4 25"; then
    aconnect 'Launchkey Mini MK4 25':0 'SuperCollider':0
    echo "[routing] Launchkey → SuperCollider"
else
    echo "[routing] INFO: Launchkey not connected, skipping."
fi

# 傀儡師 仮想ポート → lattice (傀儡師起動後に接続)
wait_for_port() {
    local name="$1"
    local max_wait=15
    local elapsed=0
    while ! aconnect -l | grep -q "$name"; do
        if [ $elapsed -ge $max_wait ]; then
            return 1
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 0
}

if wait_for_port "Kugutsushi"; then
    aconnect 'Kugutsushi':0 'SuperCollider':0
    echo "[routing] Kugutsushi → SuperCollider"
else
    echo "[routing] INFO: Kugutsushi port not ready, skipping."
fi

echo "[routing] MIDI routing complete."
aconnect -l
