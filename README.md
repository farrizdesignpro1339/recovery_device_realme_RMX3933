# TWRP Device Tree for realme Note 60 / RMX3933

This repository contains the TWRP device tree for the following device:

- **realme Note 60** (RMX3933)

## Device Information

| Feature | Specification |
|---|---|
| Device codename | `ussi_arm64` |
| Model | realme Note 60 (RMX3933) |
| SoC | Unisoc T612 (ums9230, 1H10) |
| Board / platform | `ums9230_latte` / `ums9230` |
| Recovery | Team Win Recovery Project (TWRP) |
| Target Android version | Android 16 (SDK 36) |
| Security patch | 2026-08-01 (`BP2A.250605.031.A3`) |
| Kernel | 5.15.149-android13-8-00008-gbe074b05e5af |
| Display | 6.74" 720x1600, 90 Hz, density 320 |
| Storage | 64/128/256 GB — userdata f2fs, logical partitions erofs |
| A/B | yes (virtual A/B, `snapuserd` enabled) |
| Fingerprint | `realme/RMX3933/RE6057:16/BP2A.250605.031.A3/U.R4T2.1785291165:user/release-keys` |

## Boot chain

```
boot.img      64 MB   kernel (arm64 Image @ 0x1000)
init_boot.img  8 MB   first stage ramdisk (first_stage_init + snapuserd_ramdisk, lz4)
vendor_boot   100 MB   second stage ramdisk (generic init + init.recovery.common.rc
                        + 176 vendor modules) + vendor dtb + bootconfig
dtbo.img       8 MB   device tree overlay
vbmeta*.img          AVB descriptors (flags 0x02000000 = hashtree disabled)
```

`boot.img` and `init_boot.img` are kept as stock (stock kernel, first stage and the
first-stage `snapuserd` for the COW partitions). Only the **second stage ramdisk inside
`vendor_boot`** is replaced by TWRP, so the recovery is flashed to `vendor_boot`.

## Features

Expected to work:

- [ ] ADB
- [ ] Display
- [ ] Fastbootd
- [ ] Flashing
- [ ] MTP
- [ ] Sideload
- [ ] USB OTG
- [ ] Touchscreen
- [ ] Decryption of encrypted `/data` (FBE, metadata encryption v3)

Everything is still untested on real hardware — see the checklist below.

## Building

> **Note:** the folder name must match `PRODUCT_DEVICE` (`RMX3933`), because the build
> system locates `BoardConfig.mk` through `device/*/RMX3933/BoardConfig.mk`. All paths
> inside the tree are relative (`$(call my-dir)` / `$(TARGET_DEVICE_DIR)`), so any
> vendor folder works.

Copy the tree into your TWRP source:

```bash
cp -r recovery_device_realme_RMX3933 <twrp-source>/device/realme/RMX3933
cd <twrp-source>
source build/envsetup.sh
lunch twrp_RMX3933-eng
mka recovery
```

Output: `out/target/product/RMX3933/vendor_boot.img`
(no `recovery.img` is produced, `TARGET_NO_RECOVERY := true`).

## Repacking (required step)

The stock `vendor_boot` of this device is **not** packed the AOSP way. The header is
`VNDRBOOT` v4, but the AOSP `dtb_size` / `dtb_addr` / `bootconfig_size` fields are zero
and the bootloader uses its own fields at offset `0x830` instead:

| Offset | Value | Meaning |
|---|---|---|
| 0x81c | 0x100 | - |
| 0x830 | 0x850 | - |
| 0x834 | 137418 | dtb size |
| 0x838 | 0x01f00000 | dtb load address |
| 0x840 | 0x6c | - |
| 0x844 | 1 | - |
| 0x848 | 0x6c | - |
| 0x84c | 35 | bootconfig size |

Physical layout of the stock image:

```
0x000000  header (4096)
0x001000  vendor ramdisk (lz4_legacy)
          dtb (137418 bytes)
          Unisoc info block: u32 ramdisk size, u32 0, u32 1
          bootconfig ("androidboot.hardware=ums9230_latte", 35 bytes)
          AVB footer at the end of the partition
```

`mkbootimg` (AOSP) puts the DTB at `--dtb_offset` and the bootconfig at the end of the
file, which does not match the layout above. `tools/repack_vendorboot.py` fixes that: it
reuses the stock header verbatim (only `vendor_ramdisk_size` is patched) and rebuilds
`header | ramdisk | dtb | unisoc info | bootconfig` exactly like the stock image.

```bash
python3 device/realme/RMX3933/tools/repack_vendorboot.py \
    out/target/product/RMX3933/vendor_boot.img \
    out/target/product/RMX3933/vendor_boot_repacked.img \
    --header device/realme/RMX3933/prebuilt/vendor_boot_header.bin \
    --dtb    device/realme/RMX3933/prebuilt/dtb.img \
    --bootconfig device/realme/RMX3933/bootconfig \
    --partition-size 104857600
```

## Flashing

```bash
adb reboot bootloader
fastboot flash --disable-verity --disable-verification vendor_boot \
    out/target/product/RMX3933/vendor_boot_repacked.img
fastboot reboot recovery
```

`--disable-verity --disable-verification` is required: the stock `vendor_boot` carries an
AVB footer and hash that will never match a rebuilt image.

## Repository layout

```
ussi_arm64/
├── BoardConfig.mk                TWRP build config (vendor_boot, AVB, display, TWRP options)
├── device.mk                     packages (Unisoc bootctrl, erofs tools, fastbootd, virtual A/B)
├── twrp_RMX3933.mk               product makefile (lunch: twrp_RMX3933-*)
├── AndroidProducts.mk            product list + COMMON_LUNCH_CHOICES
├── Android.mk / Android.bp       device tree scaffolding
├── vendorsetup.sh                add_lunch_combo
├── system.prop / vendor.prop     recovery properties (USB, fastbootd)
├── bootconfig                    "androidboot.hardware=ums9230_latte" (same as stock)
├── prebuilt/
│   ├── dtb.img                   vendor dtb from the stock vendor_boot
│   └── vendor_boot_header.bin    stock vendor_boot header (4096 bytes, repack template)
├── tools/repack_vendorboot.py    AOSP layout -> realme vendor_boot layout
└── recovery/root/                files injected into the TWRP ramdisk
    ├── init.recovery.ums9230_latte.rc   device init (imports init.recovery.common.rc)
    ├── init.recovery.ums9230_1h10.rc    fallback when ro.hardware is the SoC variant
    ├── init.recovery.common.rc          Unisoc common init (stock, USB block removed)
    ├── init.recovery.usb.rc             TWRP style configfs USB (adb/mtp/fastboot)
    ├── ueventd.ums9230_latte.rc         device permissions
    ├── ueventd.ums9230_1h10.rc
    ├── snapuserd.rc                     required for virtual A/B (COW)
    ├── servicemanager.recovery.rc
    ├── android.hardware.boot-service.default_recovery.rc
    ├── vendor.sprd.hardware.boot-service.default_recovery.rc
    ├── first_stage_ramdisk/fstab.ums9230_latte   identical to stock
    ├── lib/modules/                      176 vendor modules + modules.load.recovery
    └── system/etc/recovery.fstab         built from the stock /etc/fstab.ums9230_latte
```

## Recovery fstab

`recovery/root/system/etc/recovery.fstab` is derived from the stock
`/etc/fstab.ums9230_latte` (extracted from the vendor partition) and uses the device-first
format `<device> <mount point> <fs type> <fs options> <twrp flags>`:

- logical partitions use the partition name as device plus the `logical` flag, so TWRP
  takes them from the super partition through fs_mgr (needs TWRP 14.1+; on older TWRP the
  entries are skipped and the partitions are auto-discovered from `/dev/block/by-name`)
- the stock mount options are kept, including `fileencryption=` and
  `keydirectory=/metadata/vold/metadata_encryption` for FBE `/data`
- extra partitions: `blackbox`, `my_preload`, `opporeserve`, `cache` (f2fs/ext4),
  SD card (mmcblk1) and USB OTG

## Troubleshooting

1. **Reboot loop / hang at logo** — check the ramdisk compression. Stock uses
   `lz4_legacy`; if the intermediate image uses modern lz4, use the legacy format.
2. **Stuck logo** — verify `bootconfig` and `prebuilt/dtb.img` still match the stock
   (they are byte identical to the stock dump).
3. **Missing partitions in TWRP** — compare `recovery/root/system/etc/recovery.fstab` with
   `adb shell ls -l /dev/block/by-name/` (`cache`/`rescue`/`prodnv` differ between storage
   variants).
4. **Touch / audio / charging not working** — the vendor modules are in
   `recovery/root/lib/modules/`, loaded in the order of the stock
   `modules.load.recovery` (via `TW_LOAD_VENDOR_MODULES`).
5. **`/data` cannot be decrypted** — `TW_USE_FSCRYPT_POLICY := 2` (Android 13+). Check
   `TW_INCLUDE_CRYPTO_FBE` and the policy version if it still fails.

## Disclaimer

This project is provided for development and testing purposes. Flashing recovery images or
modifying device partitions can cause data loss or prevent the device from booting. Keep a
backup of important data and verify the exact device variant before flashing.

## Credits

- [Team Win Recovery Project](https://twrp.me/)
- Android Open Source Project
- realme for the Note 60 hardware
- Unisoc for the platform and kernel sources
- Contributors to the device tree and related open-source projects
