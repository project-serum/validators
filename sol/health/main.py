import logging
import socket
import traceback
from functools import wraps
from pathlib import Path
from typing import Union, Tuple, Optional

import jsonpickle
import requests
from flask import Flask
from flask import jsonify
from gevent.pywsgi import WSGIServer

app = Flask('health.main')
logger = logging.getLogger('health.main')

PORT = 9090
TRUSTED_VALIDATOR_ENDPOINT = 'http://vip-api.mainnet-beta.solana.com'
LOCAL_VALIDATOR_ENDPOINT = 'http://localhost:8899'
UNHEALTHY_BLOCKHEIGHT_DIFF = 15
DATA_DIR = 'data'


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


@app.route('/')
@api_endpoint
def get_status():
    return f'Hello from {socket.gethostname()}.'


@app.route('/status')
@api_endpoint
def get_validator_status():
    local = get_epoch_info(LOCAL_VALIDATOR_ENDPOINT)['result']['blockHeight']
    trusted = get_epoch_info(TRUSTED_VALIDATOR_ENDPOINT)['result']['blockHeight']
    return {
        'local': local,
        'trusted': trusted
    }


@app.route('/health')
@api_endpoint
def get_health_status():
    local = get_epoch_info(LOCAL_VALIDATOR_ENDPOINT)['result']['blockHeight']
    trusted = get_epoch_info(TRUSTED_VALIDATOR_ENDPOINT)['result']['blockHeight']
    diff = trusted - local
    if diff < 0:
        logger.info(f'Local block height is greater than trusted validator. '
                    f'Current block height: {local}, '
                    f'Trusted block height: {trusted}')
    behind = max(0, diff)
    unhealthy_blockheight_diff = load_data_file_locally('unhealthy_block_threshold') or UNHEALTHY_BLOCKHEIGHT_DIFF
    if behind > int(unhealthy_blockheight_diff):
        raise Exception(f'Local validator is behind trusted validator by more than {unhealthy_blockheight_diff} blocks.')
    return {
        'local': local,
        'trusted': trusted
    }


def load_data_file_locally(filename: str, mode='r') -> Optional[str]:
    file_path = Path(DATA_DIR) / filename
    if file_path.exists():
        with file_path.open(mode=mode) as f:
            return f.read()
    return None


def get_epoch_info(url: str):
    res = requests.post(
        url,
        headers={
            'Content-Type': 'application/json'
        },
        json={"jsonrpc":"2.0", "id":1, "method":"getEpochInfo", "params":[]}
    )
    res.raise_for_status()
    return res.json()


if __name__ == '__main__':
    serve_flask_app(
        app, PORT, allow_remote_connections=True, allow_multiple_listeners=True
    )
