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

# Gmail API utils
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# for encoding/decoding messages in base64
from base64 import urlsafe_b64decode, urlsafe_b64encode

# for dealing with attachement MIME types
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from mimetypes import guess_type as guess_mime_type

# Request all access (permission to read/send/receive emails, manage the inbox, and more)
SCOPES = ['https://mail.google.com/']

def gmail_authenticate(gcredentials):
    creds = None
    # the file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials availablle, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(gcredentials, SCOPES)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def search_messages(service, query):
    result = service.users().messages().list(userId='me',q=query).execute()
    messages = [ ]
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me',q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages

# utility functions
def get_size_format(b, factor=1024, suffix="B"):
    """
    Scale bytes to its proper byte format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"


def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

def parse_parts(service, parts, folder_name):
    """
    Utility function that parses the content of an email partition
    """
    if parts:
        for part in parts:
            filename = part.get("filename")
            mimeType = part.get("mimeType")
            body = part.get("body")
            data = body.get("data")
            file_size = body.get("size")
            part_headers = part.get("headers")
            if part.get("parts"):
                # recursively call this function when we see that a part
                # has parts inside
                parse_parts(service, part.get("parts"), folder_name)
            if mimeType == "text/plain":
                # if the email part is text plain
                if data:
                    text = urlsafe_b64decode(data).decode()
                    text = text.strip().split()
                    if "BTC" in text:
                        btc_index = text.index('BTC')
                        btc = text[btc_index-1]
                        print(f'Bitcoin to buy back: {btc}')
                        return btc
                    #elif "ETH" in text:
                    #    eth_index = text.index('ETH')
                    #    eth = text[eth_index-1]
                    #    print(f'Ethereum to buy back: {eth}')
                    #    return eth
    return 0.00

def read_message(service, message_id):
    """
    This function takes Gmail API `service` and the given `message_id` and does the following:
        - Downloads the content of the email
        - Prints email basic information (To, From, Subject & Date) and plain/text parts
        - Creates a folder for each email based on the subject
        - Downloads text/html content (if available) and saves it under the folder created as index.html
        - Downloads any file that is attached to the email and saves it in the folder created
    """
    msg = service.users().messages().get(userId='me', id=message_id['id'], format='full').execute()
    # parts can be the message body, or attachments
    payload = msg['payload']
    headers = payload.get("headers")
    parts = payload.get("parts")
    folder_name = "email"
    if headers:
        # this section prints email basic info & creates a folder for the email
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name == 'From':
                # we print the From address
                print("From:", value)
            if name == "To":
                # we print the To address
                print("To:", value)
            if name == "Subject":
                print("Subject:", value)
            if name == "Date":
                # we print the date when the message was sent
                print("Date:", value)
    to_buy_back = parse_parts(service, parts, folder_name)
    print("="*50)

    return float(to_buy_back)

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
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--google-creds')

    args = parser.parse_args()

    # initalize ids and auth token
    ids = {}
    batch = 0.0
    enigma_auth = get_enigma_auth(args.username, args.password)
    print(enigma_auth)

    while True:

        # get the Gmail API service
        service = gmail_authenticate(args.google_creds)

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

        print(ids)

        results = search_messages(service, "robot@generalbytes.com")
        uniq_id = results[0]['id'].encode('utf-8')
        if uniq_id not in ids:
            hashid = hashlib.sha256(uniq_id)
            ids[uniq_id] = hashid
            last_id = uniq_id

            to_buy_back = read_message(service, results[0])
            """
            EndPoint:
            https://api.enigma-securities.io/

            # get a quote
            curl --location --request GET 'https://sandbox.rest-api.enigma-securities.io/product/'

            # buy
            curl \
            --location --request POST 'https://api.enigma-securities.io/trade' \
            -H 'Authorization:{key}' \
            --form 'type=MKT' \
            --form 'side=BUY' \
            --form 'product_id=2' \
            --form 'quantity=1'
            """
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

            print("FOUND NEW EMAIL")
            print(ids)
            print()

        ## check every 30 secs
        time.sleep(30)
