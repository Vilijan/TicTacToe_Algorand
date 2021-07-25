from algosdk import logic as algo_logic
from algosdk.future import transaction as algo_txn
from pyteal import compileTeal, Mode

from src.blockchain_utils.network_interaction import NetworkInteraction
from src.blockchain_utils.transaction_repository import ApplicationTransactionRepository, PaymentTransactionRepository
from src.smart_contracts.game_funds_escrow import game_funds_escorw
from src.smart_contracts.tic_tac_toe_asc1 import approval_program, clear_program, AppVariables


class GameEngineService:
    """
    Engine that defines the interaction and initialization of the Tic-Tac-Toe DApp.
    """

    def __init__(self,
                 app_creator_pk,
                 app_creator_address,
                 player_x_pk,
                 player_x_address,
                 player_o_pk,
                 player_o_address):
        self.app_creator_pk = app_creator_pk
        self.app_creator_address = app_creator_address
        self.player_x_pk = player_x_pk
        self.player_x_address = player_x_address
        self.player_o_pk = player_o_pk
        self.player_o_address = player_o_address
        self.teal_version = 4

        self.approval_program_code = approval_program()
        self.clear_program_code = clear_program()

        self.app_id = None
        self.escrow_fund_address = None
        self.escrow_fund_program_bytes = None

    def deploy_application(self, client):
        """
        Creates and sends the transaction to the network that does the initialization of the Tic-Tac-Toe game.
        :param client:
        :return:
        """
        approval_program_compiled = compileTeal(approval_program(),
                                                mode=Mode.Application,
                                                version=self.teal_version)

        clear_program_compiled = compileTeal(clear_program(),
                                             mode=Mode.Application,
                                             version=self.teal_version)

        approval_program_bytes = NetworkInteraction.compile_program(client=client,
                                                                    source_code=approval_program_compiled)

        clear_program_bytes = NetworkInteraction.compile_program(client=client,
                                                                 source_code=clear_program_compiled)

        global_schema = algo_txn.StateSchema(num_uints=AppVariables.number_of_int(),
                                             num_byte_slices=AppVariables.number_of_str())

        local_schema = algo_txn.StateSchema(num_uints=0,
                                            num_byte_slices=0)

        app_transaction = ApplicationTransactionRepository.create_application(client=client,
                                                                              creator_private_key=self.app_creator_pk,
                                                                              approval_program=approval_program_bytes,
                                                                              clear_program=clear_program_bytes,
                                                                              global_schema=global_schema,
                                                                              local_schema=local_schema,
                                                                              app_args=None)

        tx_id = NetworkInteraction.submit_transaction(client,
                                                      transaction=app_transaction,
                                                      log=False)

        transaction_response = client.pending_transaction_info(tx_id)

        self.app_id = transaction_response['application-index']
        print(f'Tic-Tac-Toe application deployed with the application_id: {self.app_id}')

    def start_game(self, client):
        """
        Atomic transfer of 3 transactions:
        - 1. Application call
        - 2. Payment from the Player X address to the Escrow fund address
        - 3. Payment from the Player O address to the Escrow fund address
        :param client:
        :return:
        """
        if self.app_id is None:
            raise ValueError('The application has not been deployed')

        if self.escrow_fund_address is not None or self.escrow_fund_program_bytes is not None:
            raise ValueError('The game has already started!')

        escrow_fund_program_compiled = compileTeal(game_funds_escorw(app_id=self.app_id),
                                                   mode=Mode.Signature,
                                                   version=self.teal_version)

        self.escrow_fund_program_bytes = NetworkInteraction.compile_program(client=client,
                                                                            source_code=escrow_fund_program_compiled)

        self.escrow_fund_address = algo_logic.address(self.escrow_fund_program_bytes)

        player_x_funding_txn = PaymentTransactionRepository.payment(client=client,
                                                                    sender_address=self.player_x_address,
                                                                    receiver_address=self.escrow_fund_address,
                                                                    amount=1000000,
                                                                    sender_private_key=None,
                                                                    sign_transaction=False)

        player_o_funding_txn = PaymentTransactionRepository.payment(client=client,
                                                                    sender_address=self.player_o_address,
                                                                    receiver_address=self.escrow_fund_address,
                                                                    amount=1000000,
                                                                    sender_private_key=None,
                                                                    sign_transaction=False)

        app_args = [
            "SetupPlayers"
        ]

        app_initialization_txn = \
            ApplicationTransactionRepository.call_application(client=client,
                                                              caller_private_key=self.app_creator_pk,
                                                              app_id=self.app_id,
                                                              on_complete=algo_txn.OnComplete.NoOpOC,
                                                              app_args=app_args,
                                                              sign_transaction=False)

        gid = algo_txn.calculate_group_id([app_initialization_txn,
                                           player_x_funding_txn,
                                           player_o_funding_txn])

        app_initialization_txn.group = gid
        player_x_funding_txn.group = gid
        player_o_funding_txn.group = gid

        app_initialization_txn_signed = app_initialization_txn.sign(self.app_creator_pk)
        player_x_funding_txn_signed = player_x_funding_txn.sign(self.player_x_pk)
        player_o_funding_txn_signed = player_o_funding_txn.sign(self.player_o_pk)

        signed_group = [app_initialization_txn_signed,
                        player_x_funding_txn_signed,
                        player_o_funding_txn_signed]

        txid = client.send_transactions(signed_group)

        print(f'Game started with the transaction_id: {txid}')

    def play_action(self, client, player_id: str, action_position: int):
        """
        Application call transaction that performs an action for the specified player at the specified action position.
        :param client:
        :param player_id: "X" or "O"
        :param action_position: action position in the range of [0, 8]
        :return:
        """
        if player_id != "X" and player_id != "O":
            raise ValueError('Invalid player id! The player_id should be X or O.')

        if self.app_id is None:
            raise ValueError('The application has not been deployed')

        app_args = [
            "ActionMove",
            action_position]

        player_pk = self.player_x_pk if player_id == "X" else self.player_o_pk

        app_initialization_txn = \
            ApplicationTransactionRepository.call_application(client=client,
                                                              caller_private_key=player_pk,
                                                              app_id=self.app_id,
                                                              on_complete=algo_txn.OnComplete.NoOpOC,
                                                              app_args=app_args)

        tx_id = NetworkInteraction.submit_transaction(client,
                                                      transaction=app_initialization_txn,
                                                      log=False)

        print(f'{player_id} has been put at position {action_position} in transaction with id: {tx_id}')

    def fund_escrow(self, client):
        """
        Funding the escrow address in order to handle the transactions fees for refunding.
        :param client:
        :return:
        """
        fund_escrow_txn = PaymentTransactionRepository.payment(client=client,
                                                               sender_address=self.app_creator_address,
                                                               receiver_address=self.escrow_fund_address,
                                                               amount=1000000,
                                                               sender_private_key=self.app_creator_pk,
                                                               sign_transaction=True)

        tx_id = NetworkInteraction.submit_transaction(client,
                                                      transaction=fund_escrow_txn,
                                                      log=False)

        print(f'Escrow address has been funded in transaction with id: {tx_id}')

    def win_money_refund(self, client, player_id: str):
        """
        Atomic transfer of 2 transactions:
        1. Application call
        2. Payment from the Escrow account to winner address either PlayerX or PlayerO.
        :param client:
        :param player_id: "X" or "O".
        :return:
        """
        if player_id != "X" and player_id != "O":
            raise ValueError('Invalid player id! The player_id should be X or O.')

        if self.app_id is None:
            raise ValueError('The application has not been deployed')

        player_pk = self.player_x_pk if player_id == "X" else self.player_o_pk
        player_address = self.player_x_address if player_id == "X" else self.player_o_address

        app_args = [
            "MoneyRefund"
        ]

        app_withdraw_call_txn = \
            ApplicationTransactionRepository.call_application(client=client,
                                                              caller_private_key=player_pk,
                                                              app_id=self.app_id,
                                                              on_complete=algo_txn.OnComplete.NoOpOC,
                                                              app_args=app_args,
                                                              sign_transaction=False)

        refund_txn = PaymentTransactionRepository.payment(client=client,
                                                          sender_address=self.escrow_fund_address,
                                                          receiver_address=player_address,
                                                          amount=2000000,
                                                          sender_private_key=None,
                                                          sign_transaction=False)

        gid = algo_txn.calculate_group_id([app_withdraw_call_txn,
                                           refund_txn])

        app_withdraw_call_txn.group = gid
        refund_txn.group = gid

        app_withdraw_call_txn_signed = app_withdraw_call_txn.sign(player_pk)

        refund_txn_logic_signature = algo_txn.LogicSig(self.escrow_fund_program_bytes)
        refund_txn_signed = algo_txn.LogicSigTransaction(refund_txn, refund_txn_logic_signature)

        signed_group = [app_withdraw_call_txn_signed,
                        refund_txn_signed]

        txid = client.send_transactions(signed_group)

        print(f'The winning money have been refunded to the player {player_id} in the transaction with id: {txid}')

    def tie_money_refund(self, client):
        """
        Atomic transfer of 3 transactions:
        1. Application call
        2. Payment from the escrow address to the PlayerX address.
        3. Payment from the escrow address to the PlayerO address.
        :param client:
        :return:
        """
        if self.app_id is None:
            raise ValueError('The application has not been deployed')

        app_args = [
            "MoneyRefund"
        ]

        app_withdraw_call_txn = \
            ApplicationTransactionRepository.call_application(client=client,
                                                              caller_private_key=self.app_creator_pk,
                                                              app_id=self.app_id,
                                                              on_complete=algo_txn.OnComplete.NoOpOC,
                                                              app_args=app_args,
                                                              sign_transaction=False)

        refund_player_x_txn = PaymentTransactionRepository.payment(client=client,
                                                                   sender_address=self.escrow_fund_address,
                                                                   receiver_address=self.player_x_address,
                                                                   amount=1000000,
                                                                   sender_private_key=None,
                                                                   sign_transaction=False)

        refund_player_o_txn = PaymentTransactionRepository.payment(client=client,
                                                                   sender_address=self.escrow_fund_address,
                                                                   receiver_address=self.player_o_address,
                                                                   amount=1000000,
                                                                   sender_private_key=None,
                                                                   sign_transaction=False)

        gid = algo_txn.calculate_group_id([app_withdraw_call_txn,
                                           refund_player_x_txn,
                                           refund_player_o_txn])

        app_withdraw_call_txn.group = gid
        refund_player_x_txn.group = gid
        refund_player_o_txn.group = gid

        app_withdraw_call_txn_signed = app_withdraw_call_txn.sign(self.app_creator_pk)

        refund_player_x_txn_logic_signature = algo_txn.LogicSig(self.escrow_fund_program_bytes)
        refund_player_x_txn_signed = \
            algo_txn.LogicSigTransaction(refund_player_x_txn, refund_player_x_txn_logic_signature)

        refund_player_o_txn_logic_signature = algo_txn.LogicSig(self.escrow_fund_program_bytes)
        refund_player_o_txn_signed = \
            algo_txn.LogicSigTransaction(refund_player_o_txn, refund_player_o_txn_logic_signature)

        signed_group = [app_withdraw_call_txn_signed,
                        refund_player_x_txn_signed,
                        refund_player_o_txn_signed]

        txid = client.send_transactions(signed_group)

        print(f'The initial bet money have been refunded to the players in the transaction with id: {txid}')

