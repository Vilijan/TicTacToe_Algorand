import streamlit as st
from src.blockchain_utils.credentials import get_client, get_account_credentials, get_indexer
from src.services.game_engine_service import GameEngineService
import algosdk

client = get_client()
indexer = get_indexer()

acc_pk, acc_address = algosdk.account.generate_account()
player_x_pk, player_x_address = algosdk.account.generate_account()
player_o_pk, player_o_address = algosdk.account.generate_account()

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

if "game_status" not in st.session_state:
    st.session_state.game_status = 0

if "is_app_deployed" not in st.session_state:
    st.session_state.is_app_deployed = False

if "is_game_started" not in st.session_state:
    st.session_state.is_game_started = False

st.title("Addresses")
st.write(f"app_creator: {acc_address}")
st.write(f"player_x: {player_x_address}")
st.write(f"player_o: {player_o_address}")

st.write("You need to fund those accounts on the following link: https://bank.testnet.algorand.network/")


# Step 1: App deployment.

def deploy_application():
    if st.session_state.is_app_deployed:
        return

    app_deployment_txn_log = st.session_state.game_engine.deploy_application(client)
    st.session_state.submitted_transactions.append(app_deployment_txn_log)
    st.session_state.is_app_deployed = True


st.title("Step 1: App deployment")
st.write("In this step we deploy the Tic-Tac-Toe Stateful Smart Contract to the Algorand TestNetwork")

if st.session_state.is_app_deployed:
    st.success(f"The app is deployed on TestNet with the following app_id: {st.session_state.game_engine.app_id}")
else:
    st.error(f"The app is not deployed! Press the button below to deploy the application.")
    _ = st.button("Deploy App", on_click=deploy_application)

# Step 2: Start of the game
st.title("Step 2: Mark the start of the game")
st.write("In this step we make atomic transfer of 3 transactions that marks the start of the game.")


def start_game():
    if st.session_state.is_game_started:
        return

    start_game_txn_log = st.session_state.game_engine.start_game(client)
    st.session_state.submitted_transactions.append(start_game_txn_log)
    st.session_state.is_game_started = True


if st.session_state.is_game_started:
    st.success("The game has started")
else:
    st.error(f"The game has not started! Press the button below to start the game.")
    _ = st.button("Start game", on_click=start_game)

st.title("Step 3: Execute game actions")

if st.session_state.player_turn == "X":
    st.warning(f"Current player: {st.session_state.player_turn}")
else:
    st.success(f"Current player: {st.session_state.player_turn}")

mark_position_idx = st.number_input(f'Action position',
                                    value=0,
                                    step=1)


def to_binary(integer):
    return format(integer, 'b').zfill(9)


def get_game_status(indexer, app_id):
    response = indexer.search_applications(application_id=app_id)
    game_status_key = "R2FtZVN0YXRl"

    for global_variable in response['applications'][0]['params']['global-state']:
        if global_variable['key'] == game_status_key:
            return global_variable['value']['uint']


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


_ = st.button('Play Action', on_click=play_action,
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

# Step 4:

st.title("Step 4: Withdraw funds")


def check_game_status():
    if st.session_state.is_game_started:
        game_status = get_game_status(indexer, app_id=st.session_state.game_engine.app_id)
        st.session_state.game_status = game_status


st.write("Press the button below to use the indexer to query the global state of the application.")
_ = st.button("Check the game status", on_click=check_game_status)


def withdraw_funds(winner):
    if winner is None:
        try:
            fund_escrow_txn = st.session_state.game_engine.fund_escrow(client=client)
            st.session_state.submitted_transactions.append(fund_escrow_txn)

            txn_description = st.session_state.game_engine.tie_money_refund(client)
            st.session_state.submitted_transactions.append(txn_description)
        except:
            st.session_state.submitted_transactions.append("Rejected transaction. Unsuccessful withdrawal.")
    else:
        try:
            fund_escrow_txn = st.session_state.game_engine.fund_escrow(client=client)
            st.session_state.submitted_transactions.append(fund_escrow_txn)

            txn_description = st.session_state.game_engine.win_money_refund(client, player_id=winner)
            st.session_state.submitted_transactions.append(txn_description)
        except:
            st.session_state.submitted_transactions.append("Rejected transaction. Unsuccessful withdrawal.")


if st.session_state.game_status == 0:
    st.write("The game is still active.")
else:
    winner = None
    if st.session_state.game_status == 1:
        st.balloons()
        st.success("Player X won the game.")
        winner = "X"
    elif st.session_state.game_status == 2:
        st.balloons()
        st.success("Player O won the game.")
        winner = "O"
    elif st.session_state.game_status == 3:
        st.warning("The game has ended with a tie.")

    _ = st.button('Withdraw funds', on_click=withdraw_funds,
                  args=(winner,))

st.title("Submitted transactions")

for txn in st.session_state.submitted_transactions:
    if "Rejected transaction." in txn:
        st.error(txn)
    else:
        st.success(txn)
