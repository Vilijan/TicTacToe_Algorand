import streamlit as st
from src.blockchain_utils.credentials import get_client, get_account_credentials
from src.services.game_engine_service import GameEngineService

client = get_client()

acc_pk, acc_address, _ = get_account_credentials(account_id=4)
player_x_pk, player_x_address, _ = get_account_credentials(account_id=1)
player_o_pk, player_o_address, _ = get_account_credentials(account_id=2)

if "submitted_transactions" not in st.session_state:
    st.session_state.submitted_transactions = []

if "player_turn" not in st.session_state:
    st.session_state.player_turn = "X"

if "game_state" not in st.session_state:
    st.session_state.game_state = ['-'] * 9

if "x_state" not in st.session_state:
    st.session_state.x_state = 0

if "o_state" not in st.session_state:
    st.session_state.o_state = 0

if "game_state" not in st.session_state:
    st.session_state.game_state = ['-'] * 9

if "game_engine" not in st.session_state:
    st.session_state.game_engine = GameEngineService(app_creator_pk=acc_pk,
                                                     app_creator_address=acc_address,
                                                     player_x_pk=player_x_pk,
                                                     player_x_address=player_x_address,
                                                     player_o_pk=player_o_pk,
                                                     player_o_address=player_o_address)

if "is_app_deployed" not in st.session_state:
    st.session_state.is_app_deployed = False

if "is_game_started" not in st.session_state:
    st.session_state.is_game_started = False

st.title("Addresses")
st.write(f"app_creator: {acc_address}")
st.write(f"player_x: {player_x_address}")
st.write(f"player_o: {player_o_address}")

st.title("App deployment")
if st.session_state.is_app_deployed:
    st.write(f"The app is deployed on TestNet with the following app_id: {st.session_state.game_engine.app_id}")
else:
    if st.button("Deploy application"):
        app_deployment_txn_log = st.session_state.game_engine.deploy_application(client)
        st.session_state.submitted_transactions.append(app_deployment_txn_log)
        st.session_state.is_app_deployed = True

st.title("Start of the game")

if st.session_state.is_game_started:
    st.write("The game has already started")
else:
    if st.button("Start game"):
        start_game_txn_log = st.session_state.game_engine.start_game(client)
        st.session_state.submitted_transactions.append(start_game_txn_log)
        st.session_state.is_game_started = True

st.title("Game action")

if st.session_state.player_turn == "X":
    st.warning(f"Current player: {st.session_state.player_turn}")
else:
    st.success(f"Current player: {st.session_state.player_turn}")

mark_position_idx = st.number_input(f'Action position',
                                    value=0,
                                    step=1)


def load_states(indexer, application_id):
    response = indexer.search_applications(application_id=application_id)

    PLAYER_X_STATE_KEY = "UGxheWVyWFN0YXRl"
    PLAYER_O_STATE_KEY = "UGxheWVyT1N0YXRl"

    player_x_state = None
    player_o_state = None

    for global_variable in response['applications'][0]['params']['global-state']:
        if global_variable['key'] == PLAYER_X_STATE_KEY:
            player_x_state = global_variable['value']['uint']

        if global_variable['key'] == PLAYER_O_STATE_KEY:
            player_o_state = global_variable['value']['uint']

    return player_x_state, player_o_state


def get_game_state_as_array(x_int_state, o_int_state):
    x_str = to_binary(x_int_state)
    o_str = to_binary(o_int_state)

    game_state = ['-'] * 9
    for i, (x_mark, o_mark) in enumerate(zip(x_str, o_str)):
        if x_mark == '1':
            game_state[i] = 'X'
        if o_mark == '1':
            game_state[i] = 'O'

    return game_state


def to_binary(integer):
    return format(integer, 'b').zfill(9)


def play_action(action_idx):
    try:
        play_action_txn = st.session_state.game_engine.play_action(client,
                                                                   player_id=st.session_state.player_turn,
                                                                   action_position=action_idx)
    except:
        st.session_state.submitted_transactions.append(f"Rejected transaction. Tried to put "
                                                       f"{st.session_state.player_turn} at {action_idx}")
        return

    st.session_state.game_state[action_idx] = st.session_state.player_turn
    st.session_state.submitted_transactions.append(play_action_txn)
    if st.session_state.player_turn == "X":
        st.session_state.x_state = st.session_state.x_state | (1 << action_idx)
        st.session_state.player_turn = "O"
    else:
        st.session_state.o_state = st.session_state.o_state | (1 << action_idx)
        st.session_state.player_turn = "X"


increment = st.button('Play Action', on_click=play_action,
                      args=(mark_position_idx,))

st.title("Game state")

for i in range(3):
    cols = st.columns(3)
    for j in range(3):
        idx = i * 3 + j
        if st.session_state.game_state[idx] == '-':
            cols[j].info('-')
        elif st.session_state.game_state[idx] == 'X':
            cols[j].warning('X')
        else:
            cols[j].success('O')

st.subheader("Binary states")
st.write(f"x_state: {st.session_state.x_state} == {to_binary(st.session_state.x_state)}")
st.write(f"o_state: {st.session_state.o_state} == {to_binary(st.session_state.o_state)}")

st.title("Submitted transactions")

for txn in st.session_state.submitted_transactions:
    if "Rejected transaction." in txn:
        st.error(txn)
    else:
        st.success(txn)
