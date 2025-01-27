"""
Feeder gateway routes.
"""

from flask import request, jsonify, abort, Blueprint
from flask.wrappers import Response
from marshmallow import ValidationError
from starkware.starknet.services.api.gateway.transaction import InvokeFunction
from starkware.starkware_utils.error_handling import StarkException
from werkzeug.datastructures import MultiDict

from starknet_devnet.state import state
from starknet_devnet.util import custom_int, StarknetDevnetException
from .shared import validate_transaction

feeder_gateway = Blueprint("feeder_gateway", __name__, url_prefix="/feeder_gateway")

def validate_call(data: bytes):
    """Ensure `data` is valid Starknet function call. Returns an `InvokeFunction`."""

    try:
        call_specifications = InvokeFunction.loads(data)
    except (TypeError, ValidationError) as err:
        abort(Response(f"Invalid Starknet function call: {err}", 400))

    return call_specifications

def _check_block_hash(request_args: MultiDict):
    block_hash = request_args.get("blockHash", type=custom_int)
    if block_hash is not None:
        print("Specifying a block by its hash is not supported. All interaction is done with the latest block.")

def _check_block_arguments(block_hash, block_number):
    if block_hash is not None and block_number is not None:
        message = "Ambiguous criteria: only one of (block number, block hash) can be provided."
        abort(Response(message, 500))

@feeder_gateway.route("/is_alive", methods=["GET"])
def is_alive():
    """Health check endpoint."""
    return "Alive!!!"

@feeder_gateway.route("/get_contract_addresses", methods=["GET"])
def get_contract_addresses():
    """Endpoint that returns an object containing the addresses of key system components."""
    return "Not implemented", 501

@feeder_gateway.route("/call_contract", methods=["POST"])
async def call_contract():
    """
    Endpoint for receiving calls (not invokes) of contract functions.
    """

    call_specifications = validate_call(request.data)

    try:
        result_dict = await state.starknet_wrapper.call(call_specifications)
    except StarkException as err:
        # code 400 would make more sense, but alpha returns 500
        abort(Response(err.message, 500))

    return jsonify(result_dict)

@feeder_gateway.route("/get_block", methods=["GET"])
async def get_block():
    """Endpoint for retrieving a block identified by its hash or number."""
    block_hash = request.args.get("blockHash")
    block_number = request.args.get("blockNumber", type=custom_int)

    _check_block_arguments(block_hash, block_number)

    try:
        if block_hash is not None:
            result_dict = state.starknet_wrapper.get_block_by_hash(block_hash)
        else:
            result_dict = state.starknet_wrapper.get_block_by_number(block_number)
    except StarkException as err:
        abort(Response(err.message, 500))

    return jsonify(result_dict)

@feeder_gateway.route("/get_code", methods=["GET"])
def get_code():
    """
    Returns the ABI and bytecode of the contract whose contractAddress is provided.
    """

    _check_block_hash(request.args)

    contract_address = request.args.get("contractAddress", type=custom_int)
    result_dict = state.starknet_wrapper.get_code(contract_address)
    return jsonify(result_dict)

@feeder_gateway.route("/get_full_contract", methods=["GET"])
def get_full_contract():
    """
    Returns the contract definition of the contract whose contractAddress is provided.
    """
    _check_block_hash(request.args)

    contract_address = request.args.get("contractAddress", type=custom_int)

    try:
        result_dict = state.starknet_wrapper.get_full_contract(contract_address)
    except StarknetDevnetException as error:
        # alpha throws 500 for unitialized contracts
        abort(Response(error.message, 500))
    return jsonify(result_dict)

@feeder_gateway.route("/get_storage_at", methods=["GET"])
async def get_storage_at():
    """Endpoint for returning the storage identified by `key` from the contract at """
    _check_block_hash(request.args)

    contract_address = request.args.get("contractAddress", type=custom_int)
    key = request.args.get("key", type=custom_int)

    storage = await state.starknet_wrapper.get_storage_at(contract_address, key)
    return jsonify(storage)

@feeder_gateway.route("/get_transaction_status", methods=["GET"])
def get_transaction_status():
    """
    Returns the status of the transaction identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    ret = state.starknet_wrapper.get_transaction_status(transaction_hash)
    return jsonify(ret)

@feeder_gateway.route("/get_transaction", methods=["GET"])
def get_transaction():
    """
    Returns the transaction identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    ret = state.starknet_wrapper.get_transaction(transaction_hash)
    return jsonify(ret)

@feeder_gateway.route("/get_transaction_receipt", methods=["GET"])
def get_transaction_receipt():
    """
    Returns the transaction receipt identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    ret = state.starknet_wrapper.get_transaction_receipt(transaction_hash)
    return jsonify(ret)

@feeder_gateway.route("/get_transaction_trace", methods=["GET"])
def get_transaction_trace():
    """
    Returns the trace of the transaction identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")

    try:
        transaction_trace = state.starknet_wrapper.get_transaction_trace(transaction_hash)
    except StarkException as err:
        abort(Response(err, 500))

    return jsonify(transaction_trace)

@feeder_gateway.route("/get_state_update", methods=["GET"])
def get_state_update():
    """
    Returns the status update from the block identified by the blockHash argument in the GET request.
    If no block hash was provided it will default to the last block.
    """

    block_hash = request.args.get("blockHash")
    block_number = request.args.get("blockNumber", type=custom_int)

    try:
        state_update = state.starknet_wrapper.get_state_update(block_hash=block_hash, block_number=block_number)
    except StarkException as err:
        abort(Response(err.message, 500))

    return jsonify(state_update)

@feeder_gateway.route("/estimate_fee", methods=["POST"])
async def estimate_fee():
    """Currently a dummy implementation, always returning 0."""
    transaction = validate_transaction(request.data, InvokeFunction)
    try:
        actual_fee = await state.starknet_wrapper.calculate_actual_fee(transaction)
    except StarkException as stark_exception:
        abort(Response(stark_exception.message, 500))

    return jsonify({
        "amount": actual_fee,
        "unit": "wei"
    })
