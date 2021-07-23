from pyteal import *


class AppVariables:
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


class AppActions:
    SetupPlayers = Bytes("SetupPlayers")
    ActionMove = Bytes("ActionMove")
    MoneyRefund = Bytes("MoneyRefund")


powers_of_two = [1, 2, 4, 8, 16, 32, 64, 128, 256]

WIN_POSITIONS = [
    (0, 1, 2),  # "XXX******" 448
    (3, 4, 5),  # "***XXX***" 56
    (6, 7, 8),  # "******XXX" 7
    (0, 3, 6),  # "X**X**X**" 292
    (1, 4, 7),  # "*X**X**X*" 146
    (2, 5, 8),  # "**X**X**X" 73
    (0, 4, 8),  # "X***X***X" 273
    (2, 4, 6),  # "**X*X*X**" 84
]

WINING_STATES = [448, 56, 7, 292, 146, 73, 273, 84]


def application_start():
    is_app_initialization = Txn.application_id() == Int(0)

    actions = Cond(
        [Txn.application_args[0] == AppActions.SetupPlayers, initialize_game_state()],
        [And(Txn.application_args[0] == AppActions.ActionMove,
             Global.group_size() == Int(1)), play_action()],
        [Txn.application_args[0] == AppActions.MoneyRefund, money_refund()]
    )

    return If(is_app_initialization, app_initialization_logic(), actions)


def app_initialization_logic():
    return Seq([
        App.globalPut(AppVariables.PlayerXState, DefaultValues.PlayerXState),
        App.globalPut(AppVariables.PlayerOState, DefaultValues.PlayerOState),
        App.globalPut(AppVariables.GameStatus, DefaultValues.GameStatus),
        App.globalPut(AppVariables.BetAmount, DefaultValues.BetAmount),
        Return(Int(1))
    ])


def initialize_game_state():
    """
    This should be an atomic transfer of 3 transactions:
    1. App call
    2. Player X funding the Escrow
    3. Player O funding the Escrow.
    :return:
    """
    player_x_address = App.globalGetEx(Int(0), AppVariables.PlayerXAddress)
    player_o_address = App.globalGetEx(Int(0), AppVariables.PlayerOAddress)

    setup_failed = Seq([
        Return(Int(0))
    ])

    setup_players = Seq([
        Assert(Gtxn[1].receiver() == Gtxn[2].receiver()),
        Assert(Gtxn[1].amount() == App.globalGet(AppVariables.BetAmount)),
        Assert(Gtxn[2].amount() == App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.PlayerXAddress, Gtxn[1].sender()),
        App.globalPut(AppVariables.PlayerOAddress, Gtxn[2].sender()),
        App.globalPut(AppVariables.PlayerTurnAddress, Gtxn[1].sender()),
        App.globalPut(AppVariables.FundsEscrowAddress, Gtxn[1].receiver()),
        # TODO: Define it as a global default variable.
        App.globalPut(AppVariables.ActionTimeout, Global.latest_timestamp() + Int(300)),
        Return(Int(1))
    ])

    return Seq([
        player_x_address,
        player_o_address,
        If(Or(player_x_address.hasValue(), player_o_address.hasValue()), setup_failed, setup_players)
    ])


def has_player_won(state):
    return If(Or(state == Int(WINING_STATES[0]),
                 state == Int(WINING_STATES[1]),
                 state == Int(WINING_STATES[2]),
                 state == Int(WINING_STATES[3]),
                 state == Int(WINING_STATES[4]),
                 state == Int(WINING_STATES[5]),
                 state == Int(WINING_STATES[6]),
                 state == Int(WINING_STATES[7])), Int(1), Int(0))


def is_tie():
    state_x = App.globalGet(AppVariables.PlayerXState)
    state_o = App.globalGet(AppVariables.PlayerOState)
    return Int(511) == BitwiseOr(state_x, state_o)


def play_action():
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


def money_refund():
    """
    If there is a winner this is atomic transfer of 2 transactions:
    1. App call
    2. Escrow -> Winner
    If there is a tie this is atomic transfer of 3 transactions:
    1. App call
    2. Escrow -> Player X
    3. Escrow -> Player O
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
        Assert(Gtxn[1].amount() == Int(2) * App.globalGet(AppVariables.BetAmount))
    ])

    o_withdraw = Seq([
        Assert(Gtxn[1].receiver() == App.globalGet(AppVariables.PlayerOAddress)),
        Assert(Gtxn[1].amount() == Int(2) * App.globalGet(AppVariables.BetAmount))
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
