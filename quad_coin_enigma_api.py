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

from json.decoder import JSONDecodeError

def get_last_transactions(key, ids):

    proc = subprocess.Popen(["curl", "-X", "GET",
                            f"https://block.io/api/v2/get_transactions/?api_key={key}&type=sent"
                            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    output = proc.stdout.read()

    try:
        d = json.loads(output)
    except JSONDecodeError as e:
        print("DECODING JSON HAS FAILED")
        print(output)
        print("DECODING JSON HAS FAILED")

        return 0.0, "NA"

    to_buy_back = 0.0
    if d["data"]["network"]:
        crypto = d["data"]["network"]

        if crypto == "BTC":

            # check top
            txid = d["data"]["txs"][0]["txid"]
            if txid not in ids:
                to_buy_back = float(d["data"]["txs"][0]["total_amount_sent"])

            # check one back
            txid_back = d["data"]["txs"][1]["txid"]
            if txid_back not in ids:
                back_to_buy_back = float(d["data"]["txs"][1]["total_amount_sent"])
                ids.append(txid_back)

                print("*"*50)
                print(f"Also buying back - {txid_back} - {back_to_buy_back}")
                print("*"*50)
                to_buy_back += back_to_buy_back

            return to_buy_back, txid, ids

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
    auth_key = "NA"

    proc = subprocess.Popen(["curl", "--location",
                             "--request", "PUT",
                             "https://api.enigma-securities.io/auth",
                             "--data-urlencode", f"username={user}",
                             "--data-urlencode", f"password={password}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    output = proc.stdout.read()

    try:
        d = json.loads(output)
        auth_key = d["key"]
    except JSONDecodeError as e:
        print("ENIGMA DECODING JSON HAS FAILED")
        print(output)
        print("ENIGMA DECODING JSON HAS FAILED")

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
    ids = []
    batch = 0.0
    enigma_auth = get_enigma_auth(args.username, args.password)
    print(enigma_auth)

    while True:

        with open("output.log", "a+") as out:

            # get current time
            now = datetime.datetime.now()

            # every day at 2am a new auth token will be generated
            if now.hour == 7 and now.minute == 1:
                enigma_auth = get_enigma_auth(args.username, args.password)
                if enigma_auth == "NA":
                    continue

                last_txid = ids[-1]
                ids = []
                ids.append(last_txid)
                print(f'New auth token: {enigma_auth}')
                print("Cleared IDs")
                time.sleep(60)

            to_buy_back, txid, ids = get_last_transactions(args.api_key, ids)

            if txid == "NA":
                time.sleep(5)
                continue

            if txid not in ids:

                ids.append(txid)
                print(ids)

                if to_buy_back < 0.001 and batch < 0.001:
                    batch += to_buy_back
                    print(f'Current buy back (batches) - {batch}')
                    print(f'Current buy back (batches) - {batch}', file=out)
                    out.close()

                else:
                    sum_to_buy = batch + to_buy_back
                    print("="*50)
                    print("-"*50)
                    print(f'BUYING THIS MUCH FROM ENIGMA - {sum_to_buy} - {txid}')
                    print(f'BUYING THIS MUCH FROM ENIGMA - {sum_to_buy} - {txid} - {now}', file=out)
                    print("-"*50)
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

                    out.close()

            ## check every 60 secs
            time.sleep(5)

