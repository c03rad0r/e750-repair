# BSBF server on a fleet VPS

Status: **live on `hermes-nvme` (23.182.128.219), 2026-10-28.** The server is a
companion to the E750 client in [`BSBF-BONDING.md`](BSBF-BONDING.md).

## Host

| Item | Value |
|---|---|
| Host | `hermes-nvme` (Debian 13, 2 vCPU, 16 GB, 23.182.128.219) |
| Role | `roles/bsbf_server` |
| Playbook | `playbook-bsbf-server.yml` |
| Inventory | `inventory/bsbf-servers.yml` (`[bsbf_servers]`) |
| Client port range | `16384:16400/tcp`, opened in ufw |
| Client rate limit | 50 Mbps (server-side HTB) |

`testserver2` was not used: it is at ~89% disk and load 1.5.

## What the role does

- Pins the upstream `bsbf-resources` commit
  `75a54685b94515a388bd8278a9586f1086f1dcee` and verifies the installer's
  SHA256 (`bc774d…`). The installer's mutable `refs/heads/main` and Xray
  install URLs are rewritten to the pinned commit and Xray `v26.10.21`.
- Installs the BSBF server (`bsbf-add-client`, `bsbf-add-client-api`,
  `bsbf-list-client`, `bsbf-remove-client`, rate limiting) and xray.
- Opens the client port range in ufw.
- Creates the first client with `bsbf-add-client 50` if no credentials are
  persisted, then writes:
  - `/etc/bsbf/client-credentials.json` on the server (0600), and
  - `state/bsbf/hermes-nvme.json` on the controller (0600, gitignored).
- Verifies the client is listed, the port is listening, and the xray instance
  is active.

The UUID/port in `state/bsbf/hermes-nvme.json` are credentials. Never commit
them; pass them to the client playbook with `-e` or load them from OpenBao.

## Debian 13 sysctl caveat

The upstream `bsbf-mptcp-configuration.service` writes
`net.mptcp.syn_retrans_before_tcp_fallback`, which Debian 13's kernel does not
provide, so the unit exits 1. The role installs a systemd drop-in that keeps
the supported settings:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/ip mptcp limits set subflows 8
ExecStart=-/usr/sbin/sysctl net.mptcp.blackhole_timeout=0
```

The `subflows 8` setting is the one the client needs; the missing fallback knob
is not required for this deployment.

## Verification

```bash
ansible-playbook -i inventory/bsbf-servers.yml playbook-bsbf-server.yml
```

The role's assertions cover the client registration, listening socket, and
active xray instance. From the client side, the decisive check is the egress:
the router must exit `23.182.128.219`, not the local WAN IP.

## Firewall

`ufw` is active on the host with 80/443 and the FIPS mesh. The role adds
`16384:16400/tcp`. If the provider has a cloud firewall, the same range must be
opened there; the role cannot see the provider panel.

## Upgrade and uninstall

Re-run the role to upgrade to a new pinned commit. To remove:

```bash
# on the server
sudo /usr/local/src/bsbf/bsbf-server-installer.sh --uninstall
sudo ufw delete allow 16384:16400/tcp
sudo systemctl disable --now bsbf-add-client-api bsbf-mptcp-configuration 2>/dev/null || true
```

The upstream uninstall removes the xray per-client configs and units. Remove
`/etc/bsbf/client-credentials.json` and the controller's
`state/bsbf/hermes-nvme.json` as well.

## Caveats

- **Location:** the host is in Houston; the E750 is in Germany. Measured RTT is
  ~160–170 ms. A European server would be better for latency and single-flow
  throughput.
- **Production relay:** the installer disables the default xray unit and sets
  host-wide MPTCP sysctls. `hermes-nvme` is a fleet relay; the role is
  documented and reversible, but a dedicated VPS or container is cleaner.
- **AGPL-3.0:** BSBF is AGPL; this repository does not vendor the upstream
  scripts. It calls pinned upstream URLs and verifies the installer hash.
