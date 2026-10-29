"""Network administration commands are denied unless host freedom is on."""

from __future__ import annotations

from .common import class_pattern

LABEL = "network administration"

BODY = (
    r"iptables(?:-save|-restore)?|ip6tables(?:-save|-restore)?|nft|nftables|"
    r"firewall-cmd|ufw|pfctl|"
    r"ip|ifconfig|ipconfig|netsh|route|arp|iw|iwconfig|ethtool|"
    r"ss|netstat|tcpdump|tshark|conntrack|nmap|traceroute|tracepath|"
    r"ping|dig|nslookup|host|"
    r"Get-NetTCPConnection|Get-NetIPAddress|Get-NetAdapter"
)

PATTERN = class_pattern(BODY)
