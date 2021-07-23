from algosdk.encoding import decode_address
from algosdk.future import transaction as algo_txn
from pyteal import compileTeal, Mode

from src.blockchain_utils.credentials import get_client, get_account_credentials
from src.blockchain_utils.network_interaction import NetworkInteraction
from src.blockchain_utils.transaction_repository import ApplicationTransactionRepository
from src.smart_contracts.different_state_asc1 import approval_program, clear_program

client = get_client()

acc_pk, acc_address, _ = get_account_credentials(account_id=4)

# App deployment.

approval_program_compiled = compileTeal(approval_program(),
                                        mode=Mode.Application,
                                        version=3)

clear_program_compiled = compileTeal(clear_program(),
                                     mode=Mode.Application,
                                     version=3)

approval_program_bytes = NetworkInteraction.compile_program(client=client,
                                                            source_code=approval_program_compiled)

clear_program_bytes = NetworkInteraction.compile_program(client=client,
                                                         source_code=clear_program_compiled)

global_schema = algo_txn.StateSchema(num_uints=5,
                                     num_byte_slices=5)

local_schema = algo_txn.StateSchema(num_uints=0,
                                    num_byte_slices=0)

app_transaction = ApplicationTransactionRepository.create_application(client=client,
                                                                      creator_private_key=acc_pk,
                                                                      approval_program=approval_program_bytes,
                                                                      clear_program=clear_program_bytes,
                                                                      global_schema=global_schema,
                                                                      local_schema=local_schema,
                                                                      app_args=None)
tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=app_transaction)

transaction_response = client.pending_transaction_info(tx_id)
app_id = transaction_response['application-index']

print(app_id)

# Game state initialization

player_x_pk, player_x_address, _ = get_account_credentials(account_id=1)
player_o_pk, player_o_address, _ = get_account_credentials(account_id=2)

app_args = [
    "SetupPlayers",
    decode_address(player_x_address),
    decode_address(player_o_address)]

app_initialization_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                           caller_private_key=acc_pk,
                                                                           app_id=app_id,
                                                                           on_complete=algo_txn.OnComplete.NoOpOC,
                                                                           app_args=app_args)

tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=app_initialization_txn)

print(tx_id)

# Execute action player x

app_args = [
    "ActionMove",
    6]

app_initialization_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                           caller_private_key=player_x_pk,
                                                                           app_id=app_id,
                                                                           on_complete=algo_txn.OnComplete.NoOpOC,
                                                                           app_args=app_args)

tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=app_initialization_txn)

# execute action player o

app_args = [
    "ActionMove",
    8]

app_initialization_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                           caller_private_key=player_o_pk,
                                                                           app_id=app_id,
                                                                           on_complete=algo_txn.OnComplete.NoOpOC,
                                                                           app_args=app_args)

tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=app_initialization_txn)

