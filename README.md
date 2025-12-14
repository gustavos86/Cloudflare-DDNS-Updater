# Cloudflare-DDNS-Updater
Python script that keeps monitoring the Public IP of the local host and updates a DNS A Record in Cloudflare if necessary

This is a fork of:
- https://medium.com/@js_9757/build-your-own-dynamic-dns-with-cloudflare-and-python-in-minutes-40a786919657
- https://gist.github.com/fivesecde/33a8320949e4ac11fddab9b62e59e629

## Files

- cloudflare_ddns.py
- .env
- requirements.txt
- cloudflare-ddns.service
- cloudflare-ddns.timer

## Instructions

Populate .env file

```
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ZONE_ID=
CLOUDFLARE_RECORD_NAME=
```

Copy files to the systemd folder

```
sudo cp cloudflare-ddns.service /etc/systemd/system/.
sudo cp cloudflare-ddns.timer /etc/systemd/system/.
```

Enable systemd

NOTE: Do NOT enable the service directly — only the timer.

```
sudo systemctl daemon-reload
sudo systemctl enable cloudflare-ddns.timer
sudo systemctl start cloudflare-ddns.timer
```

Monitor for errors

```
sudo journalctl -u cloudflare-ddns -p err
tail -f cloudflare-ddns.log
