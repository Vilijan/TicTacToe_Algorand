from pyteal import *


class AppVariables:
    """
    All the variables available in the global state of the application.
    """
    PlayerXState = Bytes("PlayerXState")
    PlayerOState = Bytes("PlayerOState")

    PlayerOAddress = Bytes("PlayerOAddress")
    PlayerXAddress = Bytes("PlayerXAddress")
    PlayerTurnAddress = Bytes("PlayerTurnAddress")
    FundsEscrowAddress = Bytes("FundsEscrowAddress")

    BetAmount = Bytes("BetAmount")
    ActionTimeout = Bytes("ActionTimeout")
    GameStatus = Bytes("GameState")

    @classmethod
    def number_of_int(cls):
        return 5

    @classmethod
    def number_of_str(cls):
        return 4


class DefaultValues:
    """
    The default values for the global variables initialized on the transaction that creates the application.
    """
    PlayerXState = Int(0)
    PlayerOState = Int(0)
    GameStatus = Int(0)
    BetAmount = Int(1000000)
    GameDurationInSeconds = Int(3600)


class AppActions:
    """
    Available actions in the tic-tac-toe application.
    """
    SetupPlayers = Bytes("SetupPlayers")
    ActionMove = Bytes("ActionMove")
    MoneyRefund = Bytes("MoneyRefund")


WINING_STATES = [448, 56, 7, 292, 146, 73, 273, 84]


def application_start():
    """
    This function represents the start of the application. Here we decide which action will be executed in the current
    application call. If we are creating the application for the very first time we are going to initialize some
    of the global values with their appropriate default values.
    """
    is_app_initialization = Txn.application_id() == Int(0)

    actions = Cond(
        [Txn.application_args[0] == AppActions.SetupPlayers, initialize_players_logic()],
        [And(Txn.application_args[0] == AppActions.ActionMove,
             Global.group_size() == Int(1)), play_action_logic()],
        [Txn.application_args[0] == AppActions.MoneyRefund, money_refund_logic()]
    )

    return If(is_app_initialization, app_initialization_logic(), actions)


def app_initialization_logic():
    """
    Initialization of the default global variables.
    """
    return Seq([
        App.globalPut(AppVariables.PlayerXState, DefaultValues.PlayerXState),
        App.globalPut(AppVariables.PlayerOState, DefaultValues.PlayerOState),
        App.globalPut(AppVariables.GameStatus, DefaultValues.GameStatus),
        App.globalPut(AppVariables.BetAmount, DefaultValues.BetAmount),
        Return(Int(1))
    ])


def initialize_players_logic():
    """
    This function initializes all the other global variables. The end of the execution of this function defines the game
    start. We expect that this logic is performed within an Atomic Transfer of 3 transactions:
    1. Application Call with the appropriate application action argument.
    2. Payment transaction from Player X that funds the Escrow account. The address of this sender is represents the
    PlayerX address.
    3. Payment transaction from Player O that funds the Escrow account. The address of this sender is represents the
    PlayerO address.
    :return:
    """
    player_x_address = App.globalGetEx(Int(0), AppVariables.PlayerXAddress)
    player_o_address = App.globalGetEx(Int(0), AppVariables.PlayerOAddress)

    setup_failed = Seq([
        Return(Int(0))
    ])

    setup_players = Seq([
        Assert(Gtxn[1].type_enum() == TxnType.Payment),
        Assert(Gtxn[2].type_enum() == TxnType.Payment),
        Assert(Gtxn[1].receiver() == Gtxn[2].receiver()),
        Assert(Gtxn[1].amount() == App.globalGet(AppVariables.BetAmount)),
        Assert(Gtxn[2].amount() == App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.PlayerXAddress, Gtxn[1].sender()),
        App.globalPut(AppVariables.PlayerOAddress, Gtxn[2].sender()),
        App.globalPut(AppVariables.PlayerTurnAddress, Gtxn[1].sender()),
        App.globalPut(AppVariables.FundsEscrowAddress, Gtxn[1].receiver()),
        App.globalPut(AppVariables.ActionTimeout, Global.latest_timestamp() + DefaultValues.GameDurationInSeconds),
        Return(Int(1))
    ])

    return Seq([
        player_x_address,
        player_o_address,
        If(Or(player_x_address.hasValue(), player_o_address.hasValue()), setup_failed, setup_players)
    ])


def has_player_won(state):
    """
    Checks whether the passed state as an argument is a winning state. There are 8 possible winning states in which
    a specific pattern of bits needs to be activated.
    :param state:
    :return:
    """
    return If(Or(BitwiseAnd(state, Int(WINING_STATES[0])) == Int(WINING_STATES[0]),
                 BitwiseAnd(state, Int(WINING_STATES[1])) == Int(WINING_STATES[1]),
                 BitwiseAnd(state, Int(WINING_STATES[2])) == Int(WINING_STATES[2]),
                 BitwiseAnd(state, Int(WINING_STATES[3])) == Int(WINING_STATES[3]),
                 BitwiseAnd(state, Int(WINING_STATES[4])) == Int(WINING_STATES[4]),
                 BitwiseAnd(state, Int(WINING_STATES[5])) == Int(WINING_STATES[5]),
                 BitwiseAnd(state, Int(WINING_STATES[6])) == Int(WINING_STATES[6]),
                 BitwiseAnd(state, Int(WINING_STATES[7])) == Int(WINING_STATES[7])), Int(1), Int(0))


def is_tie():
    """
    Checks whether the game has ended with a tie. Tie state is represented with the number 511 which is the number where
    the first 9 bits are active.
    :return:
    """
    state_x = App.globalGet(AppVariables.PlayerXState)
    state_o = App.globalGet(AppVariables.PlayerOState)
    return Int(511) == BitwiseOr(state_x, state_o)


def play_action_logic():
    """
    Executes an action for the current player in the game and accordingly updates the state of the game. The action
    is passed as an argument to the application call.
    :return:
    """
    position_index = Int(8) - Btoi(Txn.application_args[1])

    state_x = App.globalGet(AppVariables.PlayerXState)
    state_o = App.globalGet(AppVariables.PlayerOState)

    game_action = ShiftLeft(Int(1), position_index)

    player_x_move = Seq([
        App.globalPut(AppVariables.PlayerXState, BitwiseOr(state_x, game_action)),

        If(has_player_won(App.globalGet(AppVariables.PlayerXState)),
           App.globalPut(AppVariables.GameStatus, Int(1))),

        App.globalPut(AppVariables.PlayerTurnAddress, App.globalGet(AppVariables.PlayerOAddress)),
    ])

    player_o_move = Seq([
        App.globalPut(AppVariables.PlayerOState, BitwiseOr(state_o, game_action)),

        If(has_player_won(App.globalGet(AppVariables.PlayerOState)),
           App.globalPut(AppVariables.GameStatus, Int(2))),

        App.globalPut(AppVariables.PlayerTurnAddress, App.globalGet(AppVariables.PlayerXAddress)),
    ])

    return Seq([
        Assert(position_index >= Int(0)),
        Assert(position_index <= Int(8)),
        Assert(Global.latest_timestamp() <= App.globalGet(AppVariables.ActionTimeout)),
        Assert(App.globalGet(AppVariables.GameStatus) == DefaultValues.GameStatus),
        Assert(Txn.sender() == App.globalGet(AppVariables.PlayerTurnAddress)),
        Assert(And(BitwiseAnd(state_x, game_action) == Int(0),
                   BitwiseAnd(state_o, game_action) == Int(0))),
        Cond(
            [Txn.sender() == App.globalGet(AppVariables.PlayerXAddress), player_x_move],
            [Txn.sender() == App.globalGet(AppVariables.PlayerOAddress), player_o_move],
        ),
        If(is_tie(), App.globalPut(AppVariables.GameStatus, Int(3))),
        Return(Int(1))
    ])


def money_refund_logic():
    """
    This function handles the logic for refunding the money in case of a winner, tie or timeout termination. If the
    player whose turn it is hasn't made a move for the predefined period of time, the other player is declared as a
    winner and can withdraw the money.
    This action logic should be performed using an Atomic Transfer of 2 transactions in case of a winner or using an
    Atomic Transfer of 3 transactions in case of a tie.
    If there is a winner the Atomic Transfer should have the following 2 transactions:
    1. Application Call with the appropriate application action argument.
    2. Payment from the Escrow to the Winner Address with a amount equal to the 2 * BetAmount.
    If there is a tie the Atomic Transfer should have the following 3 transactions:
    1. Application Call with the appropriate application action argument.
    2. Payment from the Escrow to the PlayerX's Address with a amount equal to the BetAmount.
    3. Payment from the Escrow to the PlayerO's Address with a amount equal to the BetAmount.
    :return:
    """
    has_x_won_by_playing = App.globalGet(AppVariables.GameStatus) == Int(1)
    has_o_won_by_playing = App.globalGet(AppVariables.GameStatus) == Int(2)

    has_x_won_by_timeout = And(App.globalGet(AppVariables.GameStatus) == Int(0),
                               Global.latest_timestamp() > App.globalGet(AppVariables.ActionTimeout),
                               App.globalGet(AppVariables.PlayerTurnAddress) == App.globalGet(
                                   AppVariables.PlayerOAddress))

    has_o_won_by_timeout = And(App.globalGet(AppVariables.GameStatus) == Int(0),
                               Global.latest_timestamp() > App.globalGet(AppVariables.ActionTimeout),
                               App.globalGet(AppVariables.PlayerTurnAddress) == App.globalGet(
                                   AppVariables.PlayerXAddress))

    x_state = App.globalGet(AppVariables.PlayerXState)
    o_state = App.globalGet(AppVariables.PlayerOState)
    game_started = And(x_state != Int(0),
                       o_state != Int(0))

    has_x_won = And(Or(has_x_won_by_playing, has_x_won_by_timeout), game_started)
    has_o_won = And(Or(has_o_won_by_playing, has_o_won_by_timeout), game_started)
    game_is_tie = App.globalGet(AppVariables.GameStatus) == Int(3)

    x_withdraw = Seq([
        Assert(Gtxn[1].receiver() == App.globalGet(AppVariables.PlayerXAddress)),
        Assert(Gtxn[1].amount() == Int(2) * App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.GameStatus, Int(1))
    ])

    o_withdraw = Seq([
        Assert(Gtxn[1].receiver() == App.globalGet(AppVariables.PlayerOAddress)),
        Assert(Gtxn[1].amount() == Int(2) * App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.GameStatus, Int(2))
    ])

    tie_withdraw = Seq([
        Assert(Gtxn[1].receiver() == App.globalGet(AppVariables.PlayerXAddress)),
        Assert(Gtxn[1].amount() == App.globalGet(AppVariables.BetAmount)),
        Assert(Gtxn[2].type_enum() == TxnType.Payment),
        Assert(Gtxn[2].sender() == App.globalGet(AppVariables.FundsEscrowAddress)),
        Assert(Gtxn[2].receiver() == App.globalGet(AppVariables.PlayerOAddress)),
        Assert(Gtxn[2].amount() == App.globalGet(AppVariables.BetAmount))
    ])

    return Seq([
        Assert(Gtxn[1].type_enum() == TxnType.Payment),
        Assert(Gtxn[1].sender() == App.globalGet(AppVariables.FundsEscrowAddress)),
        Cond(
            [has_x_won, x_withdraw],
            [has_o_won, o_withdraw],
            [game_is_tie, tie_withdraw]
        ),
        Return(Int(1))
    ])


def approval_program():
    return application_start()


def clear_program():
    return Return(Int(1))
