
# 1) Smart summary (what happened & why it works now)

* **Symptom:** You couldn’t connect to PostgreSQL on `mail.ajcloudsolutions.com:5432` from your PC (`telnet 44.201.109.108 5432` failed).
* **What we verified:**

  * DNS & EC2 were fine.
  * PostgreSQL was running and **listening on 0.0.0.0:5432 and [::]:5432**.
  * Security Group/NACL allowed the traffic.
* **Root cause:** The **host firewall (nftables)** had a **catch-all drop rule** that executed **before** any rule allowing port **5432**. So SYN packets arrived at the instance, but the server never replied (seen in `tcpdump` as repeated inbound SYN with no SYN-ACK).
* **Fix:** Add an nftables rule to **accept TCP dport 5432** and place it **above the drop rule**. We made it persistent by updating `/etc/nftables.conf` and reloading nftables.
* **Optional hardening:** Restrict 5432 to **your IP only**, or use an **SSH tunnel** instead of leaving 5432 open to the internet.

---

# 2) Commands used (what, how, why)

### A) Diagnose networking & service

```bash
# Show listeners (verify Postgres is bound to 0.0.0.0 / ::)
sudo ss -tulpen | grep 5432
```

*Why:* Confirms PostgreSQL is listening on external interfaces, not just localhost.

```bash
# Watch traffic on 5432 (while you attempt to connect from your PC)
sudo tcpdump -nni any port 5432
```

*Why:* If you see inbound SYNs but no SYN-ACK replies, something on the host (firewall) is dropping it.

### B) Check / adjust reverse path filter (asymmetric routing safety)

```bash
cat /proc/sys/net/ipv4/conf/{all,default,ens5}/rp_filter
sudo sysctl -w net.ipv4.conf.all.rp_filter=2
sudo sysctl -w net.ipv4.conf.default.rp_filter=2
sudo sysctl -w net.ipv4.conf.ens5.rp_filter=2
```

*Why:* `rp_filter=2` (loose mode) avoids dropping valid replies on AWS public/private NAT paths.

Make it permanent:

```bash
sudo bash -c 'cat >> /etc/sysctl.conf <<EOF

# Allow AWS public<->private NAT reply paths
net.ipv4.conf.all.rp_filter=2
net.ipv4.conf.default.rp_filter=2
EOF'
sudo sysctl -p
```

### C) nftables (firewall) — inspect & edit rules

```bash
# See tables & chains
sudo nft list tables
sudo nft list table inet filter
sudo nft list chain inet filter input
```

*Why:* Learn current rule order; find any final “drop everything else” rule.

```bash
# List with handles (exact deletion)
sudo nft --handle list chain inet filter input
# Delete by handle if needed
sudo nft delete rule inet filter input handle <HANDLE_NUMBER>
```

*Why:* nftables requires handle numbers for deleting specific rules.

**Add allow rule (quick CLI):**

```bash
# Allow all (testing)
sudo nft insert rule inet filter input position 1 tcp dport 5432 accept
# or restrict to your IP (safer)
sudo nft insert rule inet filter input position 1 ip saddr <YOUR_PUBLIC_IP> tcp dport 5432 accept
```

*Why:* Ensure the accept rule is **before** the drop.

**Persist current rules:**

```bash
sudo sh -c 'nft list ruleset > /etc/nftables.conf'
sudo systemctl restart nftables
```

*Why:* Save & reload so the rules survive reboot.

**Edit file directly (cleanest):**

```bash
sudo nano /etc/nftables.conf
# (paste a clean table with 5432 allow above drop)
sudo nft -f /etc/nftables.conf
sudo systemctl restart nftables
```

*Why:* Ensures the exact order you want; easier than juggling handles.

### D) Test from Windows

```powershell
# Basic reachability
telnet 44.201.109.108 5432

# Or detailed test
Test-NetConnection 44.201.109.108 -Port 5432 -InformationLevel Detailed
```

*Why:* Confirms remote TCP connectivity.

### E) Optional: SSH tunnel (no public 5432 exposure)

```bash
# From your PC
ssh -L 5432:localhost:5432 ubuntu@mail.ajcloudsolutions.com
```

*Why:* Safest way to administer Postgres remotely; keeps 5432 closed to the Internet.

---

# 3) Step-by-step (do this order next time)

**Step 0 — AWS checks (console)**

* Security Group inbound: allow **TCP 5432** (ideally from **your IP only**).
* NACLs: if customized, allow inbound **5432** and outbound **ephemeral 1024–65535**.
  *(Default NACL usually allows all.)*

**Step 1 — Verify PostgreSQL is listening**

```bash
sudo ss -tulpen | grep 5432
```

* If only `127.0.0.1:5432`, set Postgres to listen externally:

  * Edit `postgresql.conf`: `listen_addresses = '*'`
  * Edit `pg_hba.conf`: `host all all <YOUR_IP>/32 md5`
  * Restart: `sudo systemctl restart postgresql`
* Recheck the `ss` output.

**Step 2 — rp_filter (AWS-friendly)**

```bash
sudo sysctl -w net.ipv4.conf.all.rp_filter=2
sudo sysctl -w net.ipv4.conf.default.rp_filter=2
sudo bash -c 'grep -q rp_filter /etc/sysctl.conf || echo -e "\nnet.ipv4.conf.all.rp_filter=2\nnet.ipv4.conf.default.rp_filter=2" >> /etc/sysctl.conf'
sudo sysctl -p
```

**Step 3 — Fix nftables rule order**

* Open `/etc/nftables.conf` and make sure **accept 5432** is **above** the drop. Minimal working input chain example:

```nft
table inet filter {
  chain input {
    type filter hook input priority filter; policy accept;
    tcp dport 5432 accept                         # <= must be above drop
    iif "lo" accept
    ct state established,related accept
    tcp dport {22,25,80,443,465,587,993,995,110,143} accept
    counter packets 0 bytes 0 drop
  }
}
```

* Apply & restart:

```bash
sudo nft -f /etc/nftables.conf
sudo systemctl restart nftables
```

**Step 4 — Test live traffic**

```bash
sudo tcpdump -nni any port 5432    # on server
```

```powershell
telnet 44.201.109.108 5432         # from your PC
```

* You should see inbound SYN **and** outbound SYN-ACK. If connected, `telnet` goes blank.

**Step 5 — Harden**

* Restrict 5432 to **your IP** in nftables:

```bash
# Replace the wide-open 5432 rule with:
ip saddr <YOUR_PUBLIC_IP> tcp dport 5432 accept
sudo nft -f /etc/nftables.conf
sudo systemctl restart nftables
```

* Optionally close 5432 publicly and use **SSH tunnel** instead (safer).

---

## Quick copy/paste: final nftables block (safe & tidy)

```nft
table inet filter {
  chain input {
    type filter hook input priority filter; policy accept;

    # PostgreSQL (restrict to your IP if you want)
    tcp dport 5432 accept
    # e.g. ip saddr 92.253.30.180 tcp dport 5432 accept

    # Loopback & established
    iif "lo" accept
    ct state established,related accept

    # Mail/Web/SSH
    tcp dport {22,25,80,443,465,587,993,995,110,143} accept

    # (ICMP rules optional – keep if you use them)
    ip protocol icmp icmp type { destination-unreachable, echo-request, router-advertisement, router-solicitation, time-exceeded, parameter-problem } accept
    ip6 nexthdr ipv6-icmp icmpv6 type { destination-unreachable, packet-too-big, time-exceeded, parameter-problem, echo-request, nd-router-solicit, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert } accept

    # Drop everything else
    counter packets 0 bytes 0 drop
  }

  chain output {
    type filter hook output priority filter; policy accept;
  }

  chain forward {
    type filter hook forward priority filter; policy drop;
  }
}
```

If you want, I can tailor this block to **only** your current public IP for 5432 and tighten any ports you’re not using.
