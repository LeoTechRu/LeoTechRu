# v2rayA Codex Recovery

Canonical source:

- Health script: `/int/tools/codex/bin/v2raya-codex-health.sh`
- v2rayA core hook source: `/int/tools/codex/bin/v2raya-core-hook-remove-quic.sh`
- Runtime health unit: `/etc/systemd/system/v2raya-codex-health.service`
- Runtime health timer: `/etc/systemd/system/v2raya-codex-health.timer`

## Symptom

Codex on `dev@vds.intdata.pro` must reach external network targets through local v2ray/v2rayA proxies:

- HTTP proxy: `http://127.0.0.1:20171`
- SOCKS proxy: `socks5h://127.0.0.1:20170`

The incident symptom was:

```text
unexpected status 403 Forbidden
url: https://chatgpt.com/backend-api/codex/responses
cf-ray: ...-DME
```

That means the Codex route reached Cloudflare from a blocked or wrong egress path, not from the expected v2ray route.

## Root Cause Seen On 2026-04-23

`snap.v2raya.v2raya.service` was `active`, but the v2ray core process was absent and ports `20170/20171` were not listening. v2rayA logs showed v2ray core `5.28.0` panicking in QUIC sniffing:

```text
github.com/v2fly/v2ray-core/v5/common/protocol/quic.SniffQUIC
panic: runtime error
exit status 2
```

The wrapper service stayed active, so normal `Restart=on-failure` did not repair the core.

## Runtime Wiring

The health script installs the tracked core-hook source into snap-visible runtime storage:

```text
/var/snap/v2raya/current/etc/core-hook-remove-quic.sh
```

Then it enforces this v2rayA systemd drop-in:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/snap run v2raya --core-hook /var/snap/v2raya/current/etc/core-hook-remove-quic.sh
```

It also enforces the Codex user-service proxy environment:

```ini
[Service]
Environment=HTTP_PROXY=http://127.0.0.1:20171
Environment=HTTPS_PROXY=http://127.0.0.1:20171
Environment=ALL_PROXY=socks5h://127.0.0.1:20170
Environment=NO_PROXY=127.0.0.1,localhost,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
ExecStartPre=/bin/sh -c 'curl -fsS --max-time 20 --proxy http://127.0.0.1:20171 https://chatgpt.com/cdn-cgi/trace >/dev/null'
```

## Manual Check

Run:

```sh
sudo /int/tools/codex/bin/v2raya-codex-health.sh
systemctl status v2raya-codex-health.timer --no-pager
systemctl status snap.v2raya.v2raya.service --no-pager
ss -ltnp | grep -E ':(20170|20171|20172)\b'
curl -k -fsS --proxy http://127.0.0.1:20171 https://chatgpt.com/cdn-cgi/trace | sed -n '1,12p'
curl -k -sS -o /dev/null -w '%{http_code}\n' --proxy http://127.0.0.1:20171 -I https://chatgpt.com/backend-api/codex/responses
```

Expected:

- v2ray core is running;
- ports `127.0.0.1:20170`, `127.0.0.1:20171`, and `127.0.0.1:20172` are listening;
- Cloudflare trace shows the proxied egress path;
- `HEAD /backend-api/codex/responses` returns `405`, not the incident `403`.

## Codex Environment Check

Run:

```sh
for pid in $(pgrep -u agents -f 'codex.*app-server|node .*codex app-server'); do
  echo "pid=$pid"
  tr '\0' '\n' < /proc/$pid/environ | grep -E '^(HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY)='
done
```

Expected:

```text
HTTP_PROXY=http://127.0.0.1:20171
HTTPS_PROXY=http://127.0.0.1:20171
ALL_PROXY=socks5h://127.0.0.1:20170
```

## Notes

- Do not place runbooks in `/home/agents` or hidden Codex state.
- Do not use `/usr/local/sbin` as the source of truth for this recovery logic.
- Runtime copies under `/var/snap/**` and systemd drop-ins under `/etc/systemd/**` are host-local installed state, not canonical source.
