#! /usr/bin/env python3

import os
import pickle
import hashlib
import time
import argparse
import requests
import subprocess
import json
import datetime
import socket
import ssl

# for encoding/decoding messages in base64
from base64 import urlsafe_b64decode, urlsafe_b64encode

# set socket timeout to 10 secs
socket.setdefaulttimeout(8)

def get_last_transactions(key):

    proc = subprocess.Popen(["curl", "-X", "GET",
                            f"https://block.io/api/v2/get_transactions/?api_key={key}&type=sent"
                            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    output = proc.stdout.read()
    #print(output)
    d = json.loads(output)
    if d["data"]["network"]:
        crypto = d["data"]["network"]

        if crypto == "BTC":
            txid = d["data"]["txs"][0]["txid"]
            to_buy_back = float(d["data"]["txs"][0]["total_amount_sent"])

            return to_buy_back, txid

    return 0.0, "NA"

def get_enigma_auth(user, password):
    """
    headers = {
    'Content-type': 'application/json',
    }

    data = '{"text":"Hello, World!"}'

    response = requests.post('https://hooks.slack.com/services/asdfasdfasdf', headers=headers, data=data)

    curl --location --request PUT 'https://sandbox.rest-api.enigma-securities.io/auth' \
    --data-urlencode 'username=client_sandbox' \
    --data-urlencode 'password=saQidf_8'
    """
    proc = subprocess.Popen(["curl", "--location",
                             "--request", "PUT",
                             "https://api.enigma-securities.io/auth",
                             "--data-urlencode", f"username={user}",
                             "--data-urlencode", f"password={password}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    output = proc.stdout.read()
    d = json.loads(output)
    auth_key = d["key"]

    return auth_key

#------------------------------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Gmail web scraper/Enigma API integration')

    parser.add_argument('--version', action='version', version='%(prog)s 0.1')
    parser.add_argument('--api-key')
    parser.add_argument('--username')
    parser.add_argument('--password')

    args = parser.parse_args()

    # initalize ids and auth token
    ids = {}
    batch = 0.0
    enigma_auth = get_enigma_auth(args.username, args.password)
    print(enigma_auth)

    while True:

        try:
            # get current time
            now = datetime.datetime.now()

            # every day at 2am a new auth token will be generated
            if now.hour == 2 and now.minute == 1:
                enigma_auth = get_enigma_auth(args.username, args.password)
                last_hash = ids[last_id]
                ids = {}
                ids[last_id] = last_hash
                print(f'New auth token: {enigma_auth}')
                print("Cleared IDs")

            to_buy_back, txid = get_last_transactions(args.api_key)

            if txid not in ids:
                ids[txid] = txid
                last_id = txid
                print(ids)

                if to_buy_back < 0.001 and batch < 0.001:
                    batch += to_buy_back
                    print(f'Current buy back (batches) - {batch}')

                else:
                    sum_to_buy = batch + to_buy_back
                    print("="*50)
                    print(f'BUYING THIS MUCH FROM ENIGMA - {sum_to_buy}')
                    proc = subprocess.Popen(["curl", "--location",
                                            "--request", "POST",
                                            "https://api.enigma-securities.io/trade",
                                            "-H", f"Authorization:{enigma_auth}",
                                            "--form", "type=MKT",
                                            "--form", "side=BUY",
                                            "--form", "product_id=2",
                                            "--form", f"quantity={sum_to_buy}",
                                            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    output = proc.stdout.read()
                    print(output)
                    print("="*50)
                    batch = 0.0

        except socket.timeout:
            print("SOCKET TIMEOUT TRYING AGAIN")
        except ssl.SSLError as err:
            print("SSL ERROR TRYING AGAIN")

        ## check every 30 secs
        time.sleep(30)

