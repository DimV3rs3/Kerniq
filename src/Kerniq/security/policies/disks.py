"""Disk and hardware inspection is denied unless host freedom is on."""

from __future__ import annotations

from .common import class_pattern

LABEL = "disks and hardware"

BODY = (
    r"lscpu|lsmem|lsblk|lsusb|lspci|dmidecode|dmesg|sysctl|"
    r"mount|umount|findmnt|df|blkid|fdisk|parted|diskpart|losetup"
)

PATTERN = class_pattern(BODY)
