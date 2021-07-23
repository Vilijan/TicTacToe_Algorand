from pyteal import *


class AppVariables:
    """
    All the possible global variables in the application.

    State representation:
    GameBoard = "X-00----X"

    X-0
    0--
    --X

    """

    GameBoard = "GameBoard"

    PlayerOAddress = "PlayerOAddress"
    PlayerXAddress = "PlayerXAddress"
    BetAmount = "BetAmount"
    ActionTimeout = "ActionTimeout"

    WinnerAddress = "WinnerAddress"
    PlayerTurn = "PlayerTurn"

    @classmethod
    def number_of_int(cls):
        # ActionTimeout, IsGameActive
        return 2

    @classmethod
    def number_of_str(cls):
        return 5


class DefaultValues:
    """
    The default values for the global variables initialized on the transaction that creates the application.
    """
    GameBoard = "---------"
    PlayerTurn = "X"
    WinnerAddress = ""


WIN_POSITIONS = [
    (0, 1, 2),  # "XXX******"
    (3, 4, 5),  # "***XXX***"
    (6, 7, 8),  # "******XXX"
    (0, 3, 6),  # "X**X**X**"
    (1, 4, 7),  # "*X**X**X*"
    (2, 5, 8),  # "**X**X**X"
    (0, 4, 8),  # "X***X***X"
    (2, 4, 6),  # "**X*X*X**"

]


def retrieve_state_substring(pos1, pos2, pos3):
    """
    Retrieves the characters at pos1, pos2 and pos3 from the global state string and concatenates them
    into a new string.
    :param pos1: index of the first char
    :param pos2: index of the second char
    :param pos3: index of the third char
    :return:
    """
    state = App.globalGet(Bytes(AppVariables.GameBoard))

    return Concat(
        Substring(state, Int(pos1), Int(pos1 + 1)),
        Substring(state, Int(pos2), Int(pos2 + 1)),
        Substring(state, Int(pos3), Int(pos3 + 1)),
    )


def has_player_won(player_target_string: str):
    """
    Checks whether specific player has won the game. We do this by obtaining all the possible combination
    of winning states. If one of those winning states matches the player_target_string passed as argument,
    it means that we have a winner.
    :param player_target_string: We pass the winning target string for each player. "XXX" for player X or
    "OOO" for player O.
    :return: 1 if there is a winner, otherwise 0.
    """
    pattern_1 = retrieve_state_substring(WIN_POSITIONS[0][0], WIN_POSITIONS[0][1], WIN_POSITIONS[0][2])
    pattern_2 = retrieve_state_substring(WIN_POSITIONS[1][0], WIN_POSITIONS[1][1], WIN_POSITIONS[1][2])
    pattern_3 = retrieve_state_substring(WIN_POSITIONS[2][0], WIN_POSITIONS[2][1], WIN_POSITIONS[2][2])
    pattern_4 = retrieve_state_substring(WIN_POSITIONS[3][0], WIN_POSITIONS[3][1], WIN_POSITIONS[3][2])
    pattern_5 = retrieve_state_substring(WIN_POSITIONS[4][0], WIN_POSITIONS[4][1], WIN_POSITIONS[4][2])
    pattern_6 = retrieve_state_substring(WIN_POSITIONS[5][0], WIN_POSITIONS[5][1], WIN_POSITIONS[5][2])
    pattern_7 = retrieve_state_substring(WIN_POSITIONS[6][0], WIN_POSITIONS[6][1], WIN_POSITIONS[6][2])
    pattern_8 = retrieve_state_substring(WIN_POSITIONS[7][0], WIN_POSITIONS[7][1], WIN_POSITIONS[7][2])

    return If(Or(pattern_1 == Bytes(player_target_string),
                 pattern_2 == Bytes(player_target_string),
                 pattern_3 == Bytes(player_target_string),
                 pattern_4 == Bytes(player_target_string),
                 pattern_5 == Bytes(player_target_string),
                 pattern_6 == Bytes(player_target_string),
                 pattern_7 == Bytes(player_target_string),
                 pattern_8 == Bytes(player_target_string)), Int(1), Int(0))


def update_game_on_win():
    """
    With this function we check whether we have a winner. If there is a winner we update the
    global state of the WinnerAddress variable to match the winner player address. If we don't have
    a winner this function doesn't change anything.
    :return: Returns code logic that updates the winning state if there is a winner.
    """
    has_player_X_won = has_player_won("XXX") == Int(1)
    has_player_O_won = has_player_won("OOO") == Int(1)

    player_X_address = App.globalGet(Bytes(AppVariables.PlayerXAddress))
    player_O_address = App.globalGet(Bytes(AppVariables.PlayerOAddress))

    update_winner_address_logic = Cond(
        [has_player_X_won, App.globalPut(Bytes(AppVariables.WinnerAddress), player_X_address)],
        [has_player_O_won, App.globalPut(Bytes(AppVariables.WinnerAddress), player_O_address)],
        [Int(1), App.globalPut(Bytes(AppVariables.WinnerAddress), Bytes(DefaultValues.WinnerAddress))]
    )

    return update_winner_address_logic


def is_valid_action(pos):
    """
    This function validates whether we can execute action on the pos index in the state variable.
    We need to make sure that:
    - The pos index has values between [0, 8].
    - The character at the pos index is empty which is indicated with '-'.
    :param pos: index of the potential position for placing a mark.
    :return: Bool variable indicating whether we can execute action at the given position index.
    """
    state = App.globalGet(Bytes(AppVariables.GameBoard))
    target_position = Substring(state, pos, pos + Int(1))

    return And(
        pos >= Int(0),
        pos <= Int(8),
        target_position == Bytes("-")
    )


# actions are from 0-8 starting from top left corner to the bottom right.
def update_state(pos, player_mark):
    """
    Updates the current game state with placing the player_mark on the pos index position.
    :param pos: position index where the new mark should be placed.
    :param player_mark: The type of mark that should be placed, either 'X' or 'O'.
    :return: Returns the code that updates the new state.
    """
    state = App.globalGet(Bytes(AppVariables.GameBoard))  # [0-8] 9 total

    larger_state = Concat(
        Bytes("-"),
        state,
        Bytes("-")
    )  # [0-10] 11 total

    new_larger_state = Concat(
        Substring(larger_state, Int(0), pos + Int(1)),
        player_mark,
        Substring(larger_state, pos + Int(2), Int(11)),
    )

    new_state = Substring(new_larger_state, Int(1), Int(10))

    return App.globalPut(Bytes(AppVariables.GameBoard), new_state)


def play_action(pos, player_mark):
    """
    Places the specified player_mark on the board i.e state at the position with index pos. The action is executed
    if the following criteria is met:
    1. the game is activate - there is no winning state on the board i.e the winning address is still the default one.
    2. valid turn - the right player is placing the mark.
    3. valid mark - a valid mark is being placed on the board, either "X" or "O".
    4. valid action - a valid action is performed, meaning the the pos value is in the correct interval [0, 8] and the
    board is empty at the pos index.
    :param pos: position index for placing the mark.
    :param player_mark: mark type either "X" or "O".
    :return:
    """
    winner_address = App.globalGet(Bytes(AppVariables.WinnerAddress))

    player_X_address = App.globalGetEx(Int(0), Bytes(AppVariables.PlayerXAddress))
    player_O_address = App.globalGetEx(Int(0), Bytes(AppVariables.PlayerOAddress))

    is_game_active = winner_address == Bytes(DefaultValues.WinnerAddress)

    valid_mark = Or(player_mark == Bytes("X"),
                    player_mark == Bytes("O"))

    current_player_turn = App.globalGet(Bytes(AppVariables.PlayerTurn))
    valid_turn = current_player_turn == player_mark

    valid_action = is_valid_action(pos=pos)

    can_execute_action = And(is_game_active,
                             valid_turn,
                             valid_mark,
                             valid_action)

    game_logic = Seq([
        update_state(pos=pos, player_mark=player_mark),
        update_game_on_win(),
        If(current_player_turn == Bytes("X"),
           App.globalPut(Bytes(AppVariables.PlayerTurn), Bytes("O")),
           App.globalPut(Bytes(AppVariables.PlayerTurn), Bytes("X")))
    ])
    # TODO: We should handle the tie situation in this function.
    return Seq([
        player_X_address,
        player_O_address,
        If(And(player_X_address.hasValue(),
               player_O_address.hasValue(),
               can_execute_action), game_logic, Return(Int(0)))

    ])


def perform_action():
    return Seq([
        play_action(pos=Btoi(Txn.application_args[0]),
                    player_mark=Txn.application_args[1]),


        Return(Int(1))
    ])

#
# def application_start():
#     is_app_initialization = Txn.application_id() == Int(0)
#     are_actions_used = Txn.on_completion() == OnComplete.NoOp
#
#     return If(is_app_initialization, app_initialization_logic(),
#               If(are_actions_used, perform_action(), Return(Int(0))))


def application_start():
    return Seq([
        App.globalPut(Bytes(AppVariables.GameBoard), Bytes(DefaultValues.GameBoard)),
        App.globalPut(Bytes(AppVariables.WinnerAddress), Bytes(DefaultValues.WinnerAddress)),
        App.globalPut(Bytes(AppVariables.PlayerTurn), Bytes(DefaultValues.PlayerTurn)),
        # TODO: Those need to be removed.
        App.globalPut(Bytes(AppVariables.PlayerOAddress), Bytes("O")),
        App.globalPut(Bytes(AppVariables.PlayerXAddress), Bytes("X")),
        play_action(pos=Int(0),
                    player_mark=Bytes("X")),
        App.globalPut(Bytes("temp_x"), Bytes("X--------")),
        Return(Int(1))
    ])



def clear_program():
    return Return(Int(1))




