#!/usr/bin/env python3

import logging
import os
from logging.handlers import RotatingFileHandler
import dns.resolver
import requests
import time
import sys

# ========================
# Rate limiting / API safety
# ========================

RATE_LIMIT_FILE = ".last_run"
MIN_SECONDS_BETWEEN_RUNS = 55  # Cloudflare-safe (1 request/min)

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

def __rate_limit():
    now = time.time()

    if os.path.exists(RATE_LIMIT_FILE):
        with open(RATE_LIMIT_FILE, "r") as f:
            last_run = float(f.read().strip() or 0)

        if now - last_run < MIN_SECONDS_BETWEEN_RUNS:
            logging.info("rate limit hit — skipping execution")
            sys.exit(0)

    with open(RATE_LIMIT_FILE, "w") as f:
        f.write(str(now))

# ========================
# Global configuration
# ========================

CONST_USER_AGENT = "fivsec-dyndns-cloudflare-agent"

LOG_FILE_PATH = "cloudflare-ddns.log"
LOG_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 3  # number of rotated logs to keep

# ========================
# Logging configuration
# ========================

log_dir = os.path.dirname(os.path.abspath(LOG_FILE_PATH))
os.makedirs(log_dir, exist_ok=True)

# Create the log file if it does not exist
if not os.path.exists(LOG_FILE_PATH):
    open(LOG_FILE_PATH, "a").close()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=LOG_MAX_SIZE_BYTES,
    backupCount=LOG_BACKUP_COUNT
)

formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)

# ========================
# DNS / Cloudflare logic
# ========================

def __get_public_ip():
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ['208.67.222.222']

    try:
        answer = resolver.resolve('myip.opendns.com', 'A')
        for rdata in answer:
            return rdata.to_text()
    except Exception as e:
        logging.error(f"Error resolving public IP: {e}")
        return None


def __get_cloudflare_dns_records():
    logging.info("getting cloudflare dns records")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                f"https://api.cloudflare.com/client/v4/zones/{os.getenv('CLOUDFLARE_ZONE_ID')}/dns_records",
                headers={
                    "Authorization": f"Bearer {os.getenv('CLOUDFLARE_API_TOKEN')}",
                    "Content-Type": "application/json",
                    "User-Agent": CONST_USER_AGENT
                },
                params={
                    "type": "A",
                    "name": os.getenv("CLOUDFLARE_RECORD_NAME")
                },
                timeout=10
            )

            if response.status_code == 200:
                return response.json()

            logging.error(f"Cloudflare API error: {response.text}")

        except Exception as e:
            logging.error(f"attempt {attempt} failed: {e}")

        time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    sys.exit(1)


def __update_cloudflare_dns_record(record_id, ip_address, name):
    try:
        logging.info(f"updating cloudflare dns record {record_id} to {ip_address}")

        response = requests.put(
            f"https://api.cloudflare.com/client/v4/zones/{os.getenv('CLOUDFLARE_ZONE_ID')}/dns_records/{record_id}",
            headers={
                "Authorization": f"Bearer {os.getenv('CLOUDFLARE_API_TOKEN')}",
                "Content-Type": "application/json",
                "User-Agent": CONST_USER_AGENT
            },
            json={
                "type": "A",
                "name": name,
                "content": ip_address,
                "ttl": 1,
                "proxied": False
            },
            timeout=10
        )

        if response.status_code == 200:
            logging.info(f"cloudflare dns record {record_id} updated to {ip_address}")
            return response.json()

        logging.error(f"Error updating cloudflare dns record: {response.text}")
        return None

    except Exception as e:
        logging.error(f"Error updating cloudflare dns record: {e}")
        return None


def main():
    logging.info("executing dyndns agent")

    __rate_limit()

    public_ip_address = __get_public_ip()
    if not public_ip_address:
        logging.error("public IP address could not be determined")
        return

    records = __get_cloudflare_dns_records()
    if not records or "result" not in records:
        logging.error("no DNS records returned from Cloudflare")
        return

    for record in records["result"]:
        record_dict = dict(record)

        if record_dict.get("type") == "A":
            logging.info(f"checking record {record_dict.get('name')}")

            if (
                record_dict.get("name") == os.getenv('CLOUDFLARE_RECORD_NAME')
                and record_dict.get("content") != public_ip_address
            ):
                logging.info(
                    f"updating record {record_dict.get('name')} "
                    f"from {record_dict.get('content')} to {public_ip_address}"
                )
                __update_cloudflare_dns_record(
                    record_id=record_dict.get("id"),
                    ip_address=public_ip_address,
                    name=record_dict.get("name")
                )
            elif record_dict.get("name") == os.getenv('CLOUDFLARE_RECORD_NAME'):
                logging.info(f"record {record_dict.get('name')} is already up to date")
            else:
                logging.info(f"record {record_dict.get('name')} is not the record we want to update")


if __name__ == "__main__":
    main()