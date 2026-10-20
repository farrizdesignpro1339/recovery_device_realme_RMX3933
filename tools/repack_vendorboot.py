#!/usr/bin/env python3
"""
Repack a vendor_boot image for realme Note 60 (RMX3933, Unisoc ums9230_latte).

Kenapa perlu repack?
-------------------
Vendor_boot stock device ini tidak dipack dengan cara AOSP:

    header (4096) | vendor ramdisk (lz4_legacy) | dtb | bootconfig | nol

Header v4-nya punya dtb_size / dtb_addr / bootconfig_size = 0 (field AOSP),
yang dipakai bootloader Instead field Unisoc sendiri di offset 0x830:

    0x81c : 0x100
    0x830 : 0x850
    0x834 : ukuran dtb        (137418)
    0x838 : alamat load dtb   (0x01f00000)
    0x840 : 0x6c
    0x844 : 0x1
    0x848 : 0x6c
    0x84c : ukuran bootconfig (35)

mkbootimg AOSP menaruh dtb di --dtb_offset dan bootconfig di akhir file,
jadi hasilnya tidak sama dengan layout di atas. Script ini mengubah output
mkbootimg/TWRP supaya identik dengan layout stock:

  - header dipakai ulang dari prebuilt/vendor_boot_header.bin (file stock),
    jadi semua field Unisoc tetap valid (dtb & bootconfig tidak berubah)
  - hanya vendor_ramdisk_size (offset 0x18) yang di-patch sesuai ramdisk baru
  - ramdisk, dtb, dan bootconfig disusun persis seperti stock

Pemakaian:
    ./tools/repack_vendorboot.py <vendor_boot.img> <out.img> \
        --header prebuilt/vendor_boot_header.bin \
        --dtb prebuilt/dtb.img \
        --bootconfig bootconfig \
        [--partition-size 104857600]

Data stock (realme Note 60, RMX3933):
    header      : VNDRBOOT, v4, page_size 4096, kernel_addr 0x8000,
                  ramdisk_addr 0x5400000,
                  cmdline "console=ttyS1,115200n8 bootconfig bootconfig"
    ramdisk     : lz4_legacy, 38510337 bytes, mulai 0x1000
    dtb         : 137418 bytes, mulai 0x24bb000
    bootconfig  : "androidboot.hardware=ums9230_latte\\n" (35 bytes),
                  mulai 0x24de000
"""

import argparse
import struct
import sys

VENDOR_BOOT_MAGIC = b"VNDRBOOT"
CMDLINE_LEN = 1536
HEADER_SIZE = 4096

# offset field di header v4
OFF_HEADER_VERSION = 8
OFF_PAGE_SIZE = 12
OFF_KERNEL_ADDR = 16
OFF_RAMDISK_ADDR = 20
OFF_RAMDISK_SIZE = 24
OFF_CMDLINE = 28


def parse_header(data):
    if data[:8] != VENDOR_BOOT_MAGIC:
        raise SystemExit("bukan vendor_boot (magic salah)")
    version, page_size, kernel_addr, ramdisk_addr, ramdisk_size = struct.unpack_from(
        "<5I", data, OFF_HEADER_VERSION
    )
    cmdline = data[OFF_CMDLINE : OFF_CMDLINE + CMDLINE_LEN].split(b"\0")[0].decode(
        errors="replace"
    )
    return {
        "version": version,
        "page_size": page_size,
        "kernel_addr": kernel_addr,
        "ramdisk_addr": ramdisk_addr,
        "ramdisk_size": ramdisk_size,
        "cmdline": cmdline,
    }


def patch_header(template, ramdisk_size, cmdline=None):
    hdr = bytearray(template)
    struct.pack_into("<I", hdr, OFF_RAMDISK_SIZE, ramdisk_size)
    if cmdline is not None:
        raw = cmdline.encode()
        hdr[OFF_CMDLINE : OFF_CMDLINE + CMDLINE_LEN] = b"\0" * CMDLINE_LEN
        hdr[OFF_CMDLINE : OFF_CMDLINE + len(raw)] = raw
    return bytes(hdr)


def align(buf, page):
    return buf + b"\0" * ((-len(buf)) % page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="vendor_boot.img hasil build TWRP (layout AOSP)")
    ap.add_argument("output", help="vendor_boot.img output (layout realme)")
    ap.add_argument(
        "--header",
        default="prebuilt/vendor_boot_header.bin",
        help="header 4096 byte dari vendor_boot stock",
    )
    ap.add_argument("--dtb", default="prebuilt/dtb.img", help="vendor dtb")
    ap.add_argument("--bootconfig", default="bootconfig", help="file bootconfig")
    ap.add_argument("--cmdline", default=None, help="override cmdline header")
    ap.add_argument(
        "--partition-size",
        type=int,
        default=0,
        help="pad output dengan nol sampai ukuran ini (mis. 104857600)",
    )
    args = ap.parse_args()

    data = open(args.input, "rb").read()
    src = parse_header(data)

    page = src["page_size"]
    ramdisk = data[page : page + src["ramdisk_size"]]
    if len(ramdisk) != src["ramdisk_size"]:
        raise SystemExit("vendor ramdisk terpotong di file input")

    template = open(args.header, "rb").read()
    if len(template) != HEADER_SIZE:
        raise SystemExit("header template harus %d byte" % HEADER_SIZE)

    dtb = open(args.dtb, "rb").read()
    bootconfig = open(args.bootconfig, "rb").read()

    cmdline = args.cmdline if args.cmdline is not None else src["cmdline"]

    out = bytearray(patch_header(template, len(ramdisk), cmdline))
    ramdisk_off = len(out)
    out += ramdisk
    out = bytearray(align(bytes(out), page))
    dtb_off = len(out)
    out += dtb
    out = bytearray(align(bytes(out), page))
    # blok info Unisoc setelah dtb: u32 ukuran vendor ramdisk, u32 0, u32 flag(1)
    meta_off = len(out)
    out += struct.pack("<III", len(ramdisk), 0, 1)
    out = bytearray(align(bytes(out), page))
    bc_off = len(out)
    out += bootconfig
    out = bytearray(align(bytes(out), page))

    if args.partition_size and len(out) < args.partition_size:
        out += b"\0" * (args.partition_size - len(out))

    open(args.output, "wb").write(out)

    print("wrote %s (%d byte)" % (args.output, len(out)))
    print("  header     : %s (dari %s)" % (cmdline, args.header))
    print("  ramdisk    : %d byte @ 0x%x" % (len(ramdisk), ramdisk_off))
    print("  dtb        : %d byte @ 0x%x" % (len(dtb), dtb_off))
    print("  meta       : @ 0x%x (ramdisk_size + flag)" % meta_off)
    print("  bootconfig : %d byte @ 0x%x" % (len(bootconfig), bc_off))


if __name__ == "__main__":
    main()
