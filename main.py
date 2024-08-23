import asyncio
import json
import os
import warnings
from datetime import datetime, timezone
from json import JSONDecodeError

from web3 import Web3, HTTPProvider

from common import *
from logs import *

web3 = Web3(HTTPProvider(os.getenv('RPC_SERVER')))
log_contract = web3.eth.contract(
    os.getenv('LOG_CONTRACT_ADDRESS'),
    abi=json.load(open("./data/abi/{}".format(os.getenv('LOG_CONTRACT_ABI_FILE'))))
)


async def keep_chat_updated(event_filter, poll_interval):
    while True:
        for event in event_filter.get_new_entries():
            output_line(event)
        await asyncio.sleep(poll_interval)


def preload_chat(earliest_block, latest_block):
    event_logs = web3.eth.get_logs({
        "fromBlock": int(earliest_block),
        "toBlock": int(latest_block),
        "topics": ["0x6b81130c485ac9b98332fa40c2e57900867815b0fe1497e1a168caf930fc9c9d"],
        "address": os.getenv('LOG_CONTRACT_ADDRESS')
    })
    warnings.filterwarnings("ignore")
    for log in event_logs:
        output_line(log)


def load_chat(latest_block):
    event_filter = log_contract.events.LogEvent.create_filter(fromBlock=latest_block)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        asyncio.run(keep_chat_updated(event_filter, 2))
    except KeyboardInterrupt:
        pass


def output_line(log):
    try:
        tx_receipt = web3.eth.get_transaction_receipt(log.transactionHash)
        decoded_data = log_contract.events.LogEvent().process_receipt(tx_receipt)
    except Exception as e:
        return
    if decoded_data[0]['args']['Aura'] and decoded_data[0]['args']['Soul']:
        # save latest block number
        room = json.load(open(room_file := "{}/rooms/{}.json".format(os.getenv('DATA_FOLDER'), os.getenv('CHANNEL_NAME')), 'r'))
        room['last_block'] = tx_receipt['blockNumber']
        open(room_file, 'w').write(json.dumps(room))

        # get the block and save it to cache
        block_number = tx_receipt['blockNumber']
        if block_number not in block_cache:
            block_cache[block_number] = web3.eth.get_block(block_number)

        # log the message and output to console
        log_message("VOID", decoded_data[0]['args']['LogLine'])
        timestamp = datetime.fromtimestamp(block_cache[block_number]['timestamp'], tz=timezone.utc)
        print("[{}] {}".format(timestamp.strftime("%Y-%m-%d %H:%M:%S"), decoded_data[0]['args']['LogLine']))


if __name__ == '__main__':
    # create the log and rooms folder if it doesn't exist
    os.makedirs("{}/logs/".format(os.getenv('DATA_FOLDER')), exist_ok=True)
    os.makedirs("{}/rooms/".format(os.getenv('DATA_FOLDER')), exist_ok=True)

    # create the rooms file if it doesn't exist
    try:
        room = json.load(open(room_file := "{}/rooms/{}.json".format(os.getenv('DATA_FOLDER'), os.getenv('CHANNEL_NAME')), 'r'))  # TODO: change this to target an address
    except (JSONDecodeError, FileNotFoundError):
        room = {
            "label": os.getenv('CHANNEL_NAME'),
            "last_block": 0,
            "preloaded": False,
        }
        open(room_file, 'w').write(json.dumps(room))
    log_file = "{}/logs/{}.log".format(os.getenv('DATA_FOLDER'), "VOID")
    # grab the entire log if the log file doesn't exist
    if not room['preloaded']:
        if os.path.exists(log_file):
            os.remove(log_file)
        latest_block = web3.eth.get_block('latest')
        block_cache = {latest_block.number: latest_block}
        earliest_block_number = 21220693
        preload_chat(earliest_block_number, latest_block.number)
        room['preloaded'] = True
        room['last_block'] = latest_block.number
    else:
        # print past log to console
        logs = read_file_to_list(log_file)
        for log in logs:
            print(log)
    open(room_file, 'w').write(json.dumps(room))
    # check for new messages
    load_chat(room['last_block'])
