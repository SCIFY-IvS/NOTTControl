#!/bin/sh
# MACIE GigE direct link on nott-server. Does not touch enp2s0f0 / 10.33.179.136.
set -e

IFACE=enp2s0f1
HOST_CIDR=10.33.179.137/32
PEER_CIDR=10.33.179.135/32

ip link set "$IFACE" up
ip addr flush dev "$IFACE"
ip addr add "$HOST_CIDR" dev "$IFACE"
ip route replace "$PEER_CIDR" dev "$IFACE"
