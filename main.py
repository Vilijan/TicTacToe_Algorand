from algosdk import logic as algo_logic
from algosdk.future import transaction as algo_txn
from pyteal import compileTeal, Mode

from src.blockchain_utils.credentials import get_client, get_account_credentials
from src.blockchain_utils.network_interaction import NetworkInteraction
from src.blockchain_utils.transaction_repository import ApplicationTransactionRepository, PaymentTransactionRepository
from src.smart_contracts.tic_tac_toe_asc1 import approval_program, clear_program, AppVariables
from src.smart_contracts.game_funds_escrow import game_funds_escorw

TEAL_VERSION = 4

client = get_client()

acc_pk, acc_address, _ = get_account_credentials(account_id=3)

# App deployment.

approval_program_compiled = compileTeal(approval_program(),
                                        mode=Mode.Application,
                                        version=TEAL_VERSION)

clear_program_compiled = compileTeal(clear_program(),
                                     mode=Mode.Application,
                                     version=TEAL_VERSION)

approval_program_bytes = NetworkInteraction.compile_program(client=client,
                                                            source_code=approval_program_compiled)

clear_program_bytes = NetworkInteraction.compile_program(client=client,
                                                         source_code=clear_program_compiled)

global_schema = algo_txn.StateSchema(num_uints=AppVariables.number_of_int(),
                                     num_byte_slices=AppVariables.number_of_str())

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

# Escrow initialization

escrow_fund_program_compiled = compileTeal(game_funds_escorw(app_id=app_id),
                                           mode=Mode.Signature,
                                           version=TEAL_VERSION)

escrow_fund_program_bytes = NetworkInteraction.compile_program(client=client,
                                                               source_code=escrow_fund_program_compiled)

escrow_address = algo_logic.address(escrow_fund_program_bytes)

print(escrow_address)

# Game state initialization

player_x_pk, player_x_address, _ = get_account_credentials(account_id=1)
player_o_pk, player_o_address, _ = get_account_credentials(account_id=2)

player_x_funding = PaymentTransactionRepository.payment(client=client,
                                                        sender_address=player_x_address,
                                                        receiver_address=escrow_address,
                                                        amount=1000000,
                                                        sender_private_key=None,
                                                        sign_transaction=False)

player_o_funding = PaymentTransactionRepository.payment(client=client,
                                                        sender_address=player_o_address,
                                                        receiver_address=escrow_address,
                                                        amount=1000000,
                                                        sender_private_key=None,
                                                        sign_transaction=False)

app_args = [
    "SetupPlayers"
]

app_initialization_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                           caller_private_key=acc_pk,
                                                                           app_id=app_id,
                                                                           on_complete=algo_txn.OnComplete.NoOpOC,
                                                                           app_args=app_args,
                                                                           sign_transaction=False)

gid = algo_txn.calculate_group_id([app_initialization_txn,
                                   player_x_funding,
                                   player_o_funding])

app_initialization_txn.group = gid
player_x_funding.group = gid
player_o_funding.group = gid

app_initialization_txn_signed = app_initialization_txn.sign(acc_pk)
player_x_funding_signed = player_x_funding.sign(player_x_pk)
player_o_funding_signed = player_o_funding.sign(player_o_pk)

signed_group = [app_initialization_txn_signed,
                player_x_funding_signed,
                player_o_funding_signed]

txid = client.send_transactions(signed_group)

print(tx_id)

# Execute action player x

app_args = [
    "ActionMove",
    3]

app_initialization_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                           caller_private_key=player_x_pk,
                                                                           app_id=app_id,
                                                                           on_complete=algo_txn.OnComplete.NoOpOC,
                                                                           app_args=app_args)

tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=app_initialization_txn)
#
# # execute action player o
#

app_args = [
    "ActionMove",
    5]

app_initialization_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                           caller_private_key=player_o_pk,
                                                                           app_id=app_id,
                                                                           on_complete=algo_txn.OnComplete.NoOpOC,
                                                                           app_args=app_args)

tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=app_initialization_txn)

# Fund escrow

fund_escrow_txn = PaymentTransactionRepository.payment(client=client,
                                                       sender_address=acc_address,
                                                       receiver_address="XB2STLOEO7VQIB3AZUWCDAFW5Z43Y7GJYNKVFHEMQHX7QAQ3GFMBUKAJ7E",
                                                       amount=100000,
                                                       sender_private_key=acc_pk,
                                                       sign_transaction=True)

tx_id = NetworkInteraction.submit_transaction(client,
                                              transaction=fund_escrow_txn)

# Withdraw money


app_args = [
    "MoneyRefund"
]

app_withdraw_call_txn = ApplicationTransactionRepository.call_application(client=client,
                                                                          caller_private_key=player_x_pk,
                                                                          app_id=app_id,
                                                                          on_complete=algo_txn.OnComplete.NoOpOC,
                                                                          app_args=app_args,
                                                                          sign_transaction=False)

refund_txn = PaymentTransactionRepository.payment(client=client,
                                                  sender_address=escrow_address,
                                                  receiver_address=player_x_address,
                                                  amount=2000000,
                                                  sender_private_key=None,
                                                  sign_transaction=False)

gid = algo_txn.calculate_group_id([app_withdraw_call_txn,
                                   refund_txn])


app_withdraw_call_txn.group = gid
refund_txn.group = gid


app_withdraw_call_txn_signed = app_withdraw_call_txn.sign(player_x_pk)

refund_txn_logic_signature = algo_txn.LogicSig(escrow_fund_program_bytes)
refund_txn_signed = algo_txn.LogicSigTransaction(refund_txn, refund_txn_logic_signature)


signed_group = [app_withdraw_call_txn_signed,
                refund_txn_signed]

txid = client.send_transactions(signed_group)

print(tx_id)
