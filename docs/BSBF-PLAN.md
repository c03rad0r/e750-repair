# BSBF bonding — implementation plan and tracker

Status: **implemented and live on the bench unit, 2026-10-28.**
Server IaC is in this repository because the `hermes-orchestration` GitHub
remote is not reachable from this environment; the role is self-contained and
can be moved later.

## Decisions

- [x] Server repo: this repository (`felixfelix-bot/e750-repair`), role
      `bsbf_server`.
- [x] Server host: `hermes-nvme` (Debian 13, 23.182.128.219). `testserver2`
      was rejected at ~89% disk / load 1.5.
- [x] Client repo: fork `c03rad0r/e750-repair`, branch `pr/bsbf-bonding`.
- [x] Topology: `eth0` = LAN `192.168.8.1/24`; `phy1-sta0` = WAN (2.4 GHz STA
      to `hermes-lan`); `wwan0` = WAN (Aldi Talk 4G, MBIM).
- [x] WiFi is primary (metric 9); 4G is backup (metric 13) and listed in
      `/etc/bsbf/bsbf-mptcp-subflow-backup`.
- [x] No vendoring: pinned upstream commit + installer SHA256; Xray pinned.
- [x] Credentials are not committed; `state/bsbf/*.json` is gitignored.

## Done

- [x] Server role `roles/bsbf_server`, playbook, inventory, group vars.
- [x] Pinned BSBF commit `75a5468…` and installer SHA256.
- [x] Pinned Xray `v26.10.21` / install-script commit `e42df6a…`.
- [x] ufw `16384:16400/tcp`; client port 16384; 50 Mbps HTB limit.
- [x] Client created; credentials in `state/bsbf/hermes-nvme.json` (0600).
- [x] Debian 13 `bsbf-mptcp-configuration` drop-in (removes the missing
      `syn_retrans_before_tcp_fallback` sysctl).
- [x] Client role `roles/bsbf` + `roles/verify_bsbf` + playbook + inventory.
- [x] MBIM packages + `/dev/cdc-wdm0`; APN `internet.eplus.de`; 4G up.
- [x] Site patches: MPTCP probe bypass, `1.1.1.1` connectivity target,
      endpoint retry, nft cold-boot hook.
- [x] Live verification: both endpoints, 4G backup, tproxy, xray, status,
      egress `23.182.128.219`.
- [x] Throughput: BSBF STA-only ~22 Mbps; 4G backup does not degrade it.
- [x] Failover: STA down → 4G carries traffic at ~0.52 Mbps, egress stays the
      server; STA restored → primary endpoint returns.
- [x] Contract tests (`tests/test_bsbf_contract.py`), syntax checks, docs,
      evidence.
- [x] Cold-boot persistence: table pre-created, endpoints re-added, xray
      starts, egress verified after reboot.

## Remaining / follow-up

- [ ] Open and merge the PR from `c03rad0r/e750-repair:pr/bsbf-bonding`.
- [ ] Decide whether to move the server to a European VPS. Houston adds
      ~160–170 ms; it does not break the STA path but limits single-flow
      throughput.
- [ ] Improve the 4G link (plan/throttle, antenna, position). If it becomes
      faster than the STA, remove `wwan0` from the backup file and re-test
      aggregation.
- [ ] Automate the client UUID/port into OpenBao instead of the controller
      `state/bsbf` file.
- [ ] Move the server role into `hermes-orchestration` when its GitHub remote
      is reachable, keeping the client role here.
- [ ] Consider a non-nested WiFi path (`StarGate`/`c03rad0r`) for a clean
      two-ISP measurement; `hermes-lan` is behind the MT6000 OMR tunnel.
- [ ] The 5 GHz QCA9887 radio repair remains unsolved; see `STATUS.md`.
- [ ] Monitor 4G data usage; it is metered and only used on failover.

## Rollback

- Client: `bsbf-bonding --disable`; restore `/etc/config/network`; keep
  `inventory/hosts.yml` (serial) available.
- Server: `bsbf-server-installer.sh --uninstall`; `ufw delete allow
  16384:16400/tcp`; remove the client credentials.
