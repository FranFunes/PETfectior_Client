#!/bin/bash
echo Configuring VPN connection...

mkdir -p /dev/net
mknod /dev/net/tun c 10 200
chmod 600 /dev/net/tun

echo Starting VPN connection...
openvpn --config /vpn/PETfectior_client1.ovpn --route $SERVER_ADDRESS 255.255.255.255