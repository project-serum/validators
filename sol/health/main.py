import logging
import socket
import time
import traceback
from functools import wraps
from pathlib import Path
from typing import Union, Tuple, Optional, Dict

import gevent
import jsonpickle
import requests
from flask import Flask
from flask import jsonify
from gevent.pywsgi import WSGIServer

app = Flask('health.main')
logger = logging.getLogger('health.main')

PORT = 9090
ENDPOINTS = {
    'local': 'http://localhost:8899',
    'mainnet': 'http://vip-api.mainnet-beta.solana.com',
    'cluster': 'https://solana-api.projectserum.com',
}
UNHEALTHY_BLOCKHEIGHT_DIFF = 15
DATA_DIR = 'data'
UPSTREAM_DOWN_TOLERANCE_SECONDS = 30

_last_successful_trusted_fetch = 0


def serve_flask_app(app: Flask, port: int, allow_remote_connections: bool = False,
                    allow_multiple_listeners: bool = False):
    listener: Union[socket.socket, Tuple[str, int]]
    hostname = '' if allow_remote_connections else 'localhost'
    listener = (hostname, port)
    if allow_multiple_listeners:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        listener.bind((hostname, port))
        listener.listen()
    server = WSGIServer(listener, app)
    server.serve_forever()


def api_endpoint(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
            return jsonify({'status': 'OK',
                            'result': result})
        except Exception as e:
            logger.warning('Error in handler %s', f, exc_info=True)
            return jsonify({'status': 'Error',
                            'error': repr(e),
                            'pickled_exception': jsonpickle.encode(e),
                            'traceback': traceback.format_exc()}), 500
    return wrapped


@app.route('/status')
@api_endpoint
def get_validator_status():
    return get_all_slots()


@app.route('/health')
@api_endpoint
def get_health_status():
    global _last_successful_trusted_fetch
    slots = get_all_slots()
    logger.info(f'slots: {slots}')

    local = slots['local']
    upstream_height = max([v for k, v in slots.items() if k != 'local'])
    if upstream_height == 0 and _last_successful_trusted_fetch < time.time() - UPSTREAM_DOWN_TOLERANCE_SECONDS:
        raise Exception(
            f'Both upstreams have been returning errors for more than {UPSTREAM_DOWN_TOLERANCE_SECONDS} seconds'
        )
    elif upstream_height > 0:
        _last_successful_trusted_fetch = time.time()

    behind = upstream_height - local
    if behind < 0:
        logger.info(f'Local block height is greater than upstreams. '
                    f'Current block height: {local}, '
                    f'Upstream block height: {upstream_height}')
    unhealthy_blockheight_diff = load_data_file_locally('unhealthy_block_threshold') or UNHEALTHY_BLOCKHEIGHT_DIFF
    if behind > int(unhealthy_blockheight_diff):
        raise Exception(f'Local validator is behind trusted validator by more than {unhealthy_blockheight_diff} blocks.')
    return slots


def load_data_file_locally(filename: str, mode='r') -> Optional[str]:
    file_path = Path(DATA_DIR) / filename
    if file_path.exists():
        with file_path.open(mode=mode) as f:
            return f.read()
    return None


def get_all_slots() -> Dict[str, int]:
    futures = {k: gevent.spawn(get_slot, v) for k, v in ENDPOINTS.items()}
    return {k: v.get() for k, v in futures.items()}


def get_slot(url: str) -> int:
    try:
        return get_epoch_info(url)['result']['absoluteSlot']
    except Exception as e:
        logger.info(f'Received error fetching blockheight from {url}')
        logger.info(e)
        return 0


def get_epoch_info(url: str):
    res = requests.post(
        url,
        json={
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getEpochInfo',
            'params': [{'commitment': 'single'}],
        },
        timeout=1,
    )
    res.raise_for_status()
    return res.json()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve_flask_app(
        app, PORT, allow_remote_connections=True, allow_multiple_listeners=True
    )
