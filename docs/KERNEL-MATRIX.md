# Kernel matrix — CVE-2026-98432 remediation

Status as of **2026-10-30**. Scope: the CVE is plain IPv4 TCP, not MPTCP-only;
fixed upstream in **6.12.113** and **6.18.56**.

## Matrix

| Host / target | Running | Newest available | CVE-fix version | Action | State |
|---|---|---|---|---|---|
| Hetzner (OMR host) | `6.12.113+deb13-arm64` | pinned | 6.12.113 | GRUB pinned; re-run `playbook-bonding-servers-hardening.yml` after any OMR update | ✅ done |
| hermes-nvme | `6.12.113` | — | 6.12.113 | none | ✅ done |
| testserver2 | `6.12.113` | — | 6.12.113 | none | ✅ done |
| x280 | `7.0.0-38` | `7.0.0-42.42` | `7.0.0-43.43` **not published** | **wait** for 43.43; do not reboot onto 42.42 | ⏳ blocked |
| cobrador | `7.0.0-38` | `7.0.0-42.42` | `7.0.0-43.43` **not published** | **wait** | ⏳ blocked |
| t440 | `6.8.0-147` | `6.8.0-147.147` | `6.8.0-149.149` **not published** | **wait** | ⏳ blocked |
| dq05 | `6.17.0-41-generic` (Ubuntu 25.10) | `6.17.0-41.41` (current) | vendor advisory needed | `apt-cache` is slow (~44 s, rebuilds its cache) but works; check the 25.10 advisory. Disk is 98% full — free space before any upgrade | ⚠️ unknown |
| t14 (workstation) | `7.0.0-38` (Ubuntu 26.04.1) | `7.0.0-42.42` | `7.0.0-43.43` **not published** | local workstation (T14Gen5); `sshd` is bound to loopback only, access is local — not a fleet blocker | ⏳ blocked |
| E750 | `6.12.94` | OpenWrt 25.12.6 = `6.12.112` | 6.12.113 | 25.12.6 is still one patch short; build 25.12.7/snapshot or patch the kernel; flash blocked by dead serial | ⚠️ blocked |
| MT6000 | `6.18.39` (OMR `v0.64.2-6.18`) | `v0.64.2` and `v0.65-snapshot` both pin the same OpenWrt commit (still `6.18.39`) | 6.18.56 | wait for OMR to bump the OpenWrt pin; do not flash a vulnerable image | ⚠️ blocked |

## Findings (2026-10-30)

- **Ubuntu**: the CVE-fix kernels are still not in the archive. `x280`/`cobrador`
  see `7.0.0-42.42`, `t440` sees `6.8.0-147.147`. Updating now would still leave
  the hosts vulnerable and force a second reboot later — **wait**.
- **OpenWrt**: `25.12.5` ships `6.12.94`; the newer `25.12.6` ships
  `6.12.112`. Neither reaches `6.12.113`. The E750 image in this repo is built
  from 25.12.5 and is therefore still vulnerable.
- **OMR**: the installed `v0.64.2-6.18` uses `6.18.39`; the latest stable is the
  same release. `v0.65-snapshot` **also pins the same OpenWrt commit**
  (`c0e9507c32f5f3729b324fe27308a9a63007f6c0`), so it still ships `6.18.39`.
  There is no OMR build with `6.18.56+` yet; wait for OMR to bump that pin.
- **Ubuntu**: re-checked after `apt-get update` on 2026-10-30 — the candidates
  are still `7.0.0-42.42` and `6.8.0-147.147`. The fix versions are not in the
  archive.
- **dq05**: the earlier "apt-cache hangs" was a timeout artifact. A full run
  takes ~44 s (`real 0m43.777s`) because it rebuilds the package cache from
  154 MB of lists; candidate `6.17.0-41.41` equals the running kernel. The real
  risk is the 98%-full root filesystem (9.8 GB free).
- **t14**: this is the local workstation (`T14Gen5`, 192.168.50.160). `sshd`
  listens only on `127.0.0.1:22`, so `ssh t14` from itself is refused by
  design; all work on it is local. It is not a fleet access outage.
- **Hetzner** is the only host confirmed booting a fixed kernel, and it is
  pinned in GRUB. OMR updates can regenerate GRUB and select the old kernel
  again, so re-run the hardening playbook afterwards.

## Upgrade procedure (when the fixed versions land)

### Ubuntu (x280, cobrador, t440, dq05)

```bash
sudo apt update
apt-cache policy linux-image-generic linux-generic-hwe-24.04
# only proceed when the candidate is 7.0.0-43.43 / 6.8.0-149.149 or newer
sudo apt install --only-upgrade linux-image-generic
sudo reboot
uname -r
```

For dq05 first repair the apt cache (`apt-cache` currently hangs; check
`/var/lib/apt/lists`, locks and disk space).

### E750

```bash
# bump image/build.sh VERSION to a release whose kernel is >= 6.12.113
cd image && ./build.sh
# flash only after the serial console is repaired and the preflight passes
ansible-playbook -i inventory/e750-serial.yml playbook-e750-serial-check.yml
```

### MT6000 / OMR

1. Pick the first OMR release built on `6.18.56+` (check `uname -r` on a test
   unit or the release manifest).
2. Back up `/etc/config` and the OMR state.
3. Sysupgrade, then re-check `uname -r`, MPTCP endpoints and the BSBF uplink.

### Hetzner

```bash
ssh -p 65222 hermes-deploy@167.235.218.44 'uname -r'   # expect 6.12.113
# after any OMR update:
ansible-playbook -i inventory/bonding-servers.yml playbook-bonding-servers-hardening.yml
```

## Verification

- `uname -r` on every host.
- `scripts/cve-2026-98432-check.sh`.
- Hetzner: `ip mp e`, BSBF health, egress `167.235.218.44`.
- E750: `e750-health`, portal 200, `kind 10021`.
- MT6000: MPTCP endpoints + STA uplink.
