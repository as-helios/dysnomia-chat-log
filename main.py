import asyncio
import json
import re
import sys
import time
import warnings
from datetime import datetime, timezone
from json import JSONDecodeError

from web3 import Web3
from web3.exceptions import BlockNotFound
from web3_multi_provider import FallbackProvider

from common import *
from logs import *

warnings.filterwarnings("ignore")
web3 = Web3(FallbackProvider(json.loads(os.getenv('RPC_SERVER'))))
log_contract = web3.eth.contract(
    os.getenv('LOG_CONTRACT_ADDRESS'),
    abi=json.load(open("./data/abi/{}".format(os.getenv('LOG_CONTRACT_ABI_FILE'))))
)
block_cache = {}


async def keep_chat_updated(event_filter, poll_interval):
    while True:
        for event in event_filter.get_new_entries():
            output_line(event)
        await asyncio.sleep(poll_interval)


def preload_chat(earliest_block, latest_block):
    event_logs = web3.eth.get_logs({
        "fromBlock": int(earliest_block),
        "toBlock": int(latest_block),
        "topics": [os.getenv('LOG_TOPIC')],
        "address": os.getenv('LOG_CONTRACT_ADDRESS')
    })
    for log in event_logs:
        output_line(log)


def load_chat(latest_block):
    event_filter = web3.eth.filter({
        "fromBlock": int(latest_block),
        "topics": [os.getenv('LOG_TOPIC')],
        "address": os.getenv('LOG_CONTRACT_ADDRESS')
    })
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(keep_chat_updated(event_filter, 2))


def output_line(event):
    try:
        tx_receipt = web3.eth.get_transaction_receipt(event.transactionHash)
        decoded_data = log_contract.events.LogEvent().process_receipt(tx_receipt)
    except Exception as e:
        logging.error(e)
        return
    if decoded_data[0]['args']['Aura'] and decoded_data[0]['args']['Soul']:
        # get the block and save it to cache
        block_number = tx_receipt['blockNumber']
        if block_number not in block_cache:
            attempts = 3
            block_cache[block_number] = None
            while attempts > 0:
                try:
                    block_cache[block_number] = web3.eth.get_block(block_number)
                except BlockNotFound:
                    attempts = attempts - 1
                    time.sleep(3)
                    continue
                else:
                    break
            if not block_cache[block_number]:
                raise Exception("Could not get block {}".format(block_number))

        # log the message and output to console
        message = "{}:{} {}".format(decoded_data[0]['args']['Soul'], decoded_data[0]['args']['Aura'], decoded_data[0]['args']['LogLine'])
        log_message(os.getenv('CHANNEL_NAME'), message)
        timestamp = datetime.fromtimestamp(block_cache[block_number]['timestamp'], tz=timezone.utc)
        print("[{}] {}".format(timestamp.strftime("%Y-%m-%d %H:%M:%S"), message if os.getenv('SHOW_AURA_AND_SOUL') != '0' else decoded_data[0]['args']['LogLine']))

        # save latest block number
        room = json.load(open(room_file := "{}/rooms/{}.json".format(os.getenv('DATA_FOLDER'), os.getenv('CHANNEL_NAME')), 'r'))
        room['last_block'] = tx_receipt['blockNumber']
        open(room_file, 'w').write(json.dumps(room))


if __name__ == '__main__':
    while True:
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
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
            latest_block = web3.eth.get_block('latest')
            if not room['preloaded']:
                if os.path.exists(log_file):
                    os.remove(log_file)
                block_cache[latest_block.number] = latest_block
                start_block_number = os.getenv('START_BLOCK')
                preload_chat(start_block_number, latest_block.number)
                room['preloaded'] = True
            else:
                # print past log to console
                logs = read_file_to_list(log_file)
                for i, log in enumerate(logs):
                    if os.getenv('SHOW_AURA_AND_SOUL') != '0':
                        print(log)
                    else:
                        match = re.match(r'^.*( [\d]+:[\d]+) .*$', log)
                        if match:
                            print(log.replace(match.group(1), ''))
                preload_chat(room['last_block'], latest_block.number)
            room['last_block'] = latest_block.number
            open(room_file, 'w').write(json.dumps(room))
            # check for new messages
            load_chat(room['last_block'])
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(3)
            logging.error(e)
