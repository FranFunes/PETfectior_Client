#!/bin/bash
echo Configuring VPN connection...

mkdir -p /dev/net
mknod /dev/net/tun c 10 200
chmod 600 /dev/net/tun

echo -e "nameserver 10.0.0.2\n$(cat /etc/resolv.conf)" > /etc/resolv.conf
echo Starting VPN connection...

openvpn --config /vpn/PETfectior_client.ovpn --route $SERVER_ADDRESS 255.255.255.255