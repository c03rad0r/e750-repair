# E750 access and key management

The E750 is reachable from x280 over its LAN `192.168.8.1/24`. Dropbear is
key-only (`PasswordAuth off`, `RootPasswordAuth off`). The serial console on
x280 is the recovery path.

## Current key layout (2026-10-29)

- `/etc/dropbear/authorized_keys` — the file Dropbear actually uses. Before
  this work it contained **one** key (x280). The operator key from T14 was not
  present, which is why T14 could not SSH to the E750 directly. It now contains
  **two** keys (x280 + T14), mode 0600.
- `/root/.ssh/authorized_keys` — **16** keys, not the Dropbear path. They do
  not grant SSH access by themselves.
- `scripts/e750-backup.sh` backs up both files privately; never commit them.

## Add an operator public key

Copy the public key to the controller x280 (public material only):

```bash
scp ~/.ssh/id_ed25519.pub x280:/tmp/t14.pub
```

Then run the role from x280:

```bash
ssh x280
cd ~/e750-repair
LC_ALL=C.UTF-8 ansible-playbook -i inventory/e750-ssh.yml playbook-e750-access.yml \
  -e '{"e750_authorized_key_files":["/tmp/t14.pub"]}'
```

The role:

- validates that each file looks like an OpenSSH public key;
- appends it via `sort -u` (preserving all existing keys, no duplicates);
- sets `/etc/dropbear/authorized_keys` to mode 0600;
- never reads or writes a private key.

## Verify from T14

```bash
ssh -J x280 -i ~/.ssh/id_ed25519 root@192.168.8.1 \
  'echo ok; wc -l /etc/dropbear/authorized_keys; ls -l /etc/dropbear/authorized_keys'
```

The jump host is x280; the final authentication uses the T14 key that was just
added. The role is idempotent: re-running it does not add duplicates.

## Live verification

From T14, after running the role:

```text
$ ssh -J x280 -i ~/.ssh/id_ed25519 root@192.168.8.1 \
    'echo ok; wc -l < /etc/dropbear/authorized_keys; ls -l /etc/dropbear/authorized_keys'
ok
2
-rw------- 1 root root 204 ... /etc/dropbear/authorized_keys
```

The two public-key fingerprints are in
`evidence/access/2026-10-29_dropbear-keys.txt` (no key material).

### Dropbear host key changed after the reflash

T14's old `known_hosts` entry for `192.168.8.1` was
`SHA256:PRNBlxEgQlhln4+OaVZwdZcYPSrr3S5lRhvxV2BpUeQ`. After the 25.12.5
reflash the E750 presents
`SHA256:wsNmvgQcsnUvHo5kPY2L1qtdtH1Ys5KJSzWG7/WB0fU`, which matches what x280
sees. The stale entry was removed, `known_hosts` was updated, and a backup was
written to `~/.ssh/known_hosts.bak-20261029-e750`. Verify the fingerprint
before accepting a host-key change.

The E750's `ssh-keygen` is Dropbear's `dropbearkey` and does not support
`-lf <authorized_keys>`; copy the public keys to a controller and fingerprint
them there.

## Serial recovery

If SSH is unavailable, the serial console from x280 is the recovery path, but
**the current E750 adapter is not reliable**: the FTDI `BH00DL3M` leg corrupts
every command (the MT6000 `BG046H5F` leg on the same hub is clean). The console
prompt appears, but commands are corrupted; see
[`SERIAL-RELIABILITY.md`](SERIAL-RELIABILITY.md).

Use SSH as the primary access until the adapter/cable is swapped or replaced.
After the swap, verify with:

```bash
python3 scripts/serial-tx-test.py /dev/ttyE750 --count 5   # expect 5/5
python3 scripts/serial-wake.py /dev/ttyE750 id              # expect uid=0
```

The repo's `inventory/hosts.yml` is the serial transport;
`inventory/e750-ssh.yml` is the normal SSH path.

## Security notes

- Public keys only; private keys stay on the operator/controller machines.
- Do not commit `/root/.ssh/authorized_keys` or `/etc/dropbear/authorized_keys`;
  fingerprints are enough evidence.
- The 16 files in `/root/.ssh` should be reconciled separately; Dropbear does
  not read that directory by default.
