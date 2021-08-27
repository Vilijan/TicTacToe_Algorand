# Overview

In this solution I describe how you can develop the Tic-Tac-Toe game on the Algorand blockchain. The game logic is implemented as a [Stateful Smart Contract](https://developer.algorand.org/docs/features/asc1/stateful/) using [PyTeal](https://pyteal.readthedocs.io/en/latest/overview.html) while the communication with the network is done using the [py-algorand-sdk](https://github.com/algorand/py-algorand-sdk). 

Two players submit equal amount of algos to an escrow address which marks the start of the game. After this step, the players interchangeably place their marks on the board where the placing mark action is implemented as an application call to the Stateful Smart Contract. In the end whoever player wins the game is able to withdraw the funds submitted to the escrow address, in case of a tie both players are able to withdraw half of the amount submitted to the escrow address.

The goal of this solution is to present a starting point for developers to easily build board games as DApps on the Algorand Blockchain. The idea is that they should be able to change the game logic from Tic-Tac-Toe to whichever board game they prefer like Chess, Connect4, Go or others and deploy it on the network.

# Table of content
- [Overview](#overview)
- [Application architecture](#application-architecture)
- [State representation and transition](#state-representation-and-transition)
- [Tic-Tac-Toe ASC1](#tic-tac-toe-asc1)
    + [Application start](#application-start)
    + [Application initialization logic](#application-initialization-logic)
    + [Setup players](#setup-players)
    + [Action move](#action-move)
    + [Money refund](#money-refund)
- [Escrow fund](#escrow-fund)
- [Game Engine service](#game-engine-service)
  * [Initialization](#initialization)
  * [Application deployment](#application-deployment)
  * [Start game](#start-game)
  * [Play action](#play-action)
  * [Win money refund](#win-money-refund)
  * [Tie money refund](#tie-money-refund)
- [Deployment on TestNet](#deployment-on-testnet)
- [Final thoughts](#final-thoughts)

# Application architecture

The Tic-Tac-Toe decentralized application has two main components:

1. **Smart contracts** - this component contains all of the PyTeal code divided into two submodules:
   - Tic-Tac-Toe ASC1 - this stateful smart contract implements the game logic and defines the interaction between the players and the application. There are 3 possible interactions with this smart contract: starting the game, executing game action and refunding the submitted Algos by the players.
   - Escrow fund - this is a [stateless smart contract](https://developer.algorand.org/docs/features/asc1/stateless/) that holds the funds submitted by the players on game start. This escrow address is linked to the Tic-Tac-Toe ASC1. On game end, the escrow fund is responsible to make the appropriate payment that represents the refunding of the submitted Algos.
2. **Game Engine service** - this is the submodule which is responsible for submitting the right transactions to the network in order to interact with the smart contracts. Those are the following services that are implemented by the game engine:
   - Application deployment - creates the transaction that deploys the Tic-Tac-Toe ASC1 to the network.
   - Start game - submits an [atomic transfer](https://developer.algorand.org/docs/features/atomic_transfers/) of 3 transaction to the network in order to denote the start of the game. 
   - Play action - submits a single application call transaction to the Tic-Tac-Toe ASC1 which executes a move in the game.
   - Win refund - submits an atomic transfer of 2 transactions to the network that refunds the Algos to the winner of the game.
   - Tie refund - submits an atomic transfer of 3 transactions to the network that refunds the Algos to the both players of the game.

All of the mentioned points above as well with the corresponding source code will be explained in more details in the later sections.

# State representation and transition

In order to optimize the state representation and state transitions in the Tic-Tac-Toe DApp I decided to implement them as bitmasks and use [bit manipulations](https://en.wikipedia.org/wiki/Bit_manipulation) for the state transitions. 

The game state is represented as two separate integer variables *state<sub>x</sub>* and *state<sub>o</sub>*. If the *i<sup>th</sup>* bit in the state<sub>x</sub> is on it means that there is a "X" mark at position *i* in the board, while on the other hand if the  *i<sup>th</sup>* bit in the state<sub>o</sub> is active it means that there is a "O" mark at position *i*. The board positions are enumerated from 0 to 8 left to right, top to bottom. The top left position is numbered with 0 while the bottom right position is numbered with 8. The following image describes the state representation of the Tic-Tac-Toe game using two bit masks:

![State representation](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/images/btimask_state.png?raw=true)

On the image above we can see how we have decoupled the original Tic-Tac-Toe game state into two separate integer states using bitmasks.

Once we have decided to represent the game state with this format we can use various bit manipulations in order to do state transitions and checks for terminal states. Here are some examples of some of the state transitions that have been used in the Tic-Tac-Toe ASC1:

- `state_x = state_x | (1 << i)` - placing "X" mark at position *i*. We can achieve this by activating the i<sup>th</sup> bit in the *state_x* variable.
- `valid_move = (state_x & (1 << i)) | (state_o & (1 << i))` - if the *valid_move* variable is equal to 0 it means that the i<sup>th</sup> bit in both of the state variables is not activated which means that the i<sup>th</sup> position is empty in the board. 
- `has_won = (state_x & 7)` - if the *has_won* variable is equal to 7 it means that the player that plays with mark "X" has won the game by populating the first row with 3 "X"es. With this expression we check whether the bits that represent the first row(bits: 0, 1 and 2) are activated. Note that here we do not check whether those bits are 0s in the *state_o* because we need to make sure in our implementation logic that the i<sup>th</sup> bit can be activated in only one of the state variables.
- `is_tie = (state_x | state_y)` - if the *is_tie* variable has value of 511 it means that all of the first 9 bits are activated which then means that the whole game board has been filled. 



# Tic-Tac-Toe ASC1

In this section I will explain in more details the logic behind the PyTeal [source code](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/src/smart_contracts/tic_tac_toe_asc1.py) in the Tic-Tac-Toe ASC1. The application has 9 global variables shown in the code snippet below:

```python
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
```

- **PlayerXState and PlayerOState** - those are integer variables that represent the state of the game board for each of the players. The state representation was described in more details in the previous section.
- **PlayerXAddress and PlayerOAddress** - those variables represent the addresses for each of the players. They are initialized when the start game action is performed.
- **PlayerTurnAddress** - this variable represents the address of the player who needs to place the next mark on the board. The game always starts with the PlayerXAddress and the PlayerTurnAddress is changed on every game action because the players place marks interchangeably. 
- **FundsEscrowAddress** - this variable represents the escrow address who is responsible for holding the funds submitted by the players. This address is initialized on the start game action as well. 
- **BetAmount** - represents the amount of micro algost that each player needs to submit to the escrow address.
- **ActionTimeout** - represents for how many seconds the game will be active on the Algorand blockchain. If the player whose turn it is hasn't played an action in the specified timeout interval the other player will be declared as a winner and will be able to withdraw the funds from the escrow address.
- **GameStatus** - is an integer variable that represents the current status of the game.
  - 0 - means that the game is active and the players are currently interacting with it.
  - 1 - means that the game was won by player X.
  - 2 - means that the game was won by player O.
  - 3 - means that the game ended with a tie.

Some of the global variables can be initialized with defaults values when the first transaction that deploys the applications is executed. On the following image we can see which variables are initialized right away:

```python
class DefaultValues:
    PlayerXState = Int(0)
    PlayerOState = Int(0)
    GameStatus = Int(0)
    BetAmount = Int(1000000)
    GameDurationInSeconds = Int(3600)
```

- **PlayerXState and PlayerOState** - at the beginning of the game there are no marks on the board and that is why all of the bits in both states are turned off.
- **GameStatus** - once we have created the application it becomes available for interactions hence the status 0 described previously.
- **BetAmount** - we fix the bet amount to be 1000000 Micro Algos or 1 Algo. With minimal effort we can change this logic to be dynamic which means that the players can define their own bet amount when performing the setup players action.
- **GameDurationInSeconds** - defines for how many seconds the players can perform actions in the game. We have defined that after the setting up of the players the game will receive action moves for 1 hour.

As mention before there are possible interactions with the Tic-Tac-Toe ASC1:

```python
class AppActions:
    SetupPlayers = Bytes("SetupPlayers")
    ActionMove = Bytes("ActionMove")
    MoneyRefund = Bytes("MoneyRefund")
```

- **SetupPlayers** - this action setups all of the global variables that haven't been initialized and marks the start of the game. This action can be performed only once and it is done through atomic transfer with 3 transactions which will be described in more details later on.
- **ActionMove** - this action performs a single game move which is placing a mark on the board. This is done through an application call to the Tic-Tac-Toe ASC1 where the target position for the mark is passed as an argument. The sender of this transaction should match the PlayerTurnAddress global variable. If we try to place a mark on a already populated position the smart contract should reject that transaction.
- **MoneyRefund** - this action validates the withdraw logic after the game has ended by the players or by a timeout. This action is executed when the Tic-Tac-Toe ASC1 is called with atomic transfer of 2 transaction in case of a win or atomic transfer of 3 transactions in case of a tie.

### Application start

This function represents the start of the Tic-Tac-Toe ASC1 application. Here we decide which action will be executed in the current application call. The specified action should be passed as a string and a first argument to the application call transaction. If we are creating the application for the very first time we are going to initialize the default global variables.

```python
def application_start():
    is_app_initialization = Txn.application_id() == Int(0)

    actions = Cond(
        [Txn.application_args[0] == AppActions.SetupPlayers, initialize_players_logic()],
        [And(Txn.application_args[0] == AppActions.ActionMove,
             Global.group_size() == Int(1)), play_action_logic()],
        [Txn.application_args[0] == AppActions.MoneyRefund, money_refund_logic()]
    )

    return If(is_app_initialization, app_initialization_logic(), actions)
```

### Application initialization logic

With this function we are going to initialize the default global variables.

```python
def app_initialization_logic():
    return Seq([
        App.globalPut(AppVariables.PlayerXState, DefaultValues.PlayerXState),
        App.globalPut(AppVariables.PlayerOState, DefaultValues.PlayerOState),
        App.globalPut(AppVariables.GameStatus, DefaultValues.GameStatus),
        App.globalPut(AppVariables.BetAmount, DefaultValues.BetAmount),
        Return(Int(1))
    ])
```

### Setup players

This function initializes all the other global variables and additionally marks the start of the game. We expect that this logic is performed within an Atomic Transfer of 3 transactions:

1. **Application call transaction** to the smart contract where the first argument passed to the transaction is "SetupPlayers" which denotes that this action should be performed within the application.
2. **Payment transaction** from PlayerX that funds the Escrow account. The address of the sender of this transaction is stored in the PlayerXAddress global variable. Additionally, the amount of the payment transaction should equal to the predefined BetAmount.
3. **Payment transaction** from PlayerO that funds the Escrow account. Similarly, the sender of this transaction is stored in the PlayerOAddress global variable and the amount of the transaction should equal to the BetAmount.

We want to be able to execute this code logic only once because we don't want in the middle of the game to change the players addresses. Additionally, the receiver of both payment transactions should be the same which is the escrow address. We store this address in the FundsEscrowAddress global variable.

```python
def initialize_players_logic():
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
```

### Action move

In order to execute an action, we first must check what is the current state of the game. To decouple the code a little bit, we create two separate functions *has_player_won(state)* and *is_tie()* to check whether the game is in a terminal i.e leaf state. At the end we combine and use those function in the main function responsible for executing an action which is *play_action_logic()* function.

```python
WINING_STATES = [448, 56, 7, 292, 146, 73, 273, 84]

def has_player_won(state):
    return If(Or(BitwiseAnd(state, Int(WINING_STATES[0])) == Int(WINING_STATES[0]),
                 BitwiseAnd(state, Int(WINING_STATES[1])) == Int(WINING_STATES[1]),
                 BitwiseAnd(state, Int(WINING_STATES[2])) == Int(WINING_STATES[2]),
                 BitwiseAnd(state, Int(WINING_STATES[3])) == Int(WINING_STATES[3]),
                 BitwiseAnd(state, Int(WINING_STATES[4])) == Int(WINING_STATES[4]),
                 BitwiseAnd(state, Int(WINING_STATES[5])) == Int(WINING_STATES[5]),
                 BitwiseAnd(state, Int(WINING_STATES[6])) == Int(WINING_STATES[6]),
                 BitwiseAnd(state, Int(WINING_STATES[7])) == Int(WINING_STATES[7])), Int(1), Int(0))
```

In the Tic-Tac-Toe game there are 8 possible winning states. Since we are representing the game state as a bit mask the numbers specified in the *WINNING_STATES* array define the bits that should be activated in each of those terminal states. With the `BitwiseAnd(state, Int(WINING_STATES[0])) == Int(WINING_STATES[0])` operation we are making sure that the required bits are activated in order to match the winning state 448 which is the state where the last row in the board is filled with the same marks. We are performing the same operation for all the other 7 possible winning states. If one of those conditions is true it means that we are in a terminal state. On the image bellow you can see an illustration of one winning state operation check:

![Winning State](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/images/winning_state_sample.png?raw=true)

Just for illustration purposes, the bits that we do not care about in the state variable are marked with "*", they actually will have values either 0 or 1. On the following [link](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/game_states.txt) you can find drawings about the other winning states.

The *is_tie*() function, as it name suggests, checks whether the current state of the game ended up with a tie. To check this, we get all of the activated bits from the states of the both players and see whether this number is equal to 511. The decimal number  511<sub>10</sub> = 111111111<sub>2</sub> which means that all of the places in the board have been filled.

```python
def is_tie():
    state_x = App.globalGet(AppVariables.PlayerXState)
    state_o = App.globalGet(AppVariables.PlayerOState)
    return Int(511) == BitwiseOr(state_x, state_o)
```

Finally we are at a point where we can implement the *play_action_logic()* function which executes a single game action. 

```python
def play_action_logic():
    position_index = Btoi(Txn.application_args[1])

    state_x = App.globalGet(AppVariables.PlayerXState)
    state_o = App.globalGet(AppVariables.PlayerOState)

    game_action = ShiftLeft(Int(1), position_index) # activate the bit at position "position_index"

    player_x_move = Seq([
        App.globalPut(AppVariables.PlayerXState, BitwiseOr(state_x, game_action)), # fill the game_action bit

        If(has_player_won(App.globalGet(AppVariables.PlayerXState)),
           App.globalPut(AppVariables.GameStatus, Int(1))), # update the game status in case of a win

        App.globalPut(AppVariables.PlayerTurnAddress, App.globalGet(AppVariables.PlayerOAddress)), 
    ])

    player_o_move = Seq([
        App.globalPut(AppVariables.PlayerOState, BitwiseOr(state_o, game_action)),

        If(has_player_won(App.globalGet(AppVariables.PlayerOState)),
           App.globalPut(AppVariables.GameStatus, Int(2))),

        App.globalPut(AppVariables.PlayerTurnAddress, App.globalGet(AppVariables.PlayerXAddress)),
    ])

    return Seq([
        Assert(position_index >= Int(0)), # valid position interval
        Assert(position_index <= Int(8)), # valid position interval
        Assert(Global.latest_timestamp() <= App.globalGet(AppVariables.ActionTimeout)), # valid time interval
        Assert(App.globalGet(AppVariables.GameStatus) == DefaultValues.GameStatus), # is game active
        Assert(Txn.sender() == App.globalGet(AppVariables.PlayerTurnAddress)), # valid player
        Assert(And(BitwiseAnd(state_x, game_action) == Int(0),
                   BitwiseAnd(state_o, game_action) == Int(0))), # the i-th position in the board is empty
        Cond(
            [Txn.sender() == App.globalGet(AppVariables.PlayerXAddress), player_x_move],
            [Txn.sender() == App.globalGet(AppVariables.PlayerOAddress), player_o_move],
        ),
        If(is_tie(), App.globalPut(AppVariables.GameStatus, Int(3))), # adjust the status in case of a tie.
        Return(Int(1))
    ])
```

We can summarize the play action function in the following steps and conditions:

- The position index is passed as the second argument to the application call transaction. We convert this argument to an integer, with this we have the index of the position where the mark will be placed. Additionally, we need to make sure that the *position_index* variable is within the allowed range which is between 0 and 8 inclusively. 
- The *game_action* variable represents the bit that needs to be activated when we place a mark at the specified position index. We achieve this by shifting the number 1 by *position_index* places to the left. *Note: The ShiftLeft PyTeal function is only available in TEAL version 4.*
- Before executing the action we need to make sure that the game hasn't ended by timeout i.e we are in the valid gameplay interval. Also, we need to make sure that the player who sent the application transaction has address equal to the one specified in the *PlayerTurnAddress* global variable. On top of that we need to check whether the *GameStatus* global variable has value of 0 which indicates that the game is currently active, the different meaning of the values of this variable were described previously in more details.
- We must check whether the *position_index* position in the board is empty. We achieve this by performing a `BitwiseAnd` operation on both states with the current *game_action* to check whether the *position_index* bit is activated. If the *position_index* bit is not activated in both state variables, it means that there is no mark on that position in the board.
- When we finally perform a player move, we need to make sure that we activate the *position_index* bit in the current player's state. If this action results in a win, we must update the *GameStatus* in order to note that the current player has won the game. In the end we need to change the *PlayerTurnAddress* variable to the address of the other player because the Tic-Tac-Toe game is played interchangeably.
- In a case of a tie, we need to update the GameStus as well in order to note that the current game has ended with a tie.

### Money refund

Up until now we have described how we can start the game with setting up the players and how we can perform an action using an application call transaction on the Tic-Tac-Toe ASC1. The one thing that is left to implement is the money refund at the end of the game, which we do by implementing the *money_refund_logic()* function.

This function handles the logic for refunding the submitted money to the escrow address in case of a winner, tie or timeout termination. If the player whose turn it is, hasn't made a move for the predefined period of time stored in the *ActionTimeout* global variable, the other player is declared as a winner and can withdraw the money. The money can be refunded with one of the following two transactions:

-  In case of a win, the money from the escrow address should be able to be refunded only by the player who won the game. That is why we need to perform an atomic transfer of 2 transactions where the first transaction is an application call to the Tic-Tac-Toe ASC1 which tells the application that we want to refund money, while the second transaction must be a payment transaction from the escrow address to the winner address. The amount refunded to the winner is equal to twice the *BetAmount* global variable.
- In case of a tie, the money from the escrow address should be equally split to both of the players. That is why this logic is executed within an atomic transfer of 3 transactions. The first transaction is an application call to the Tic-Tac-Toe ASC1, the second and the third are payment transactions from the escrow address to the *PlayerXAddress* and *PlayerOAddress*. Both of the payment transactions should have equal amount which is the same as the *BetAmount* global variable.

The code that performs the money refund logic is shown below.

```python
def money_refund_logic():
    has_x_won_by_playing = App.globalGet(AppVariables.GameStatus) == Int(1) # normal win by placing marks
    has_o_won_by_playing = App.globalGet(AppVariables.GameStatus) == Int(2) # normal win by placing marks

    has_x_won_by_timeout = And(App.globalGet(AppVariables.GameStatus) == Int(0),
                               Global.latest_timestamp() > App.globalGet(AppVariables.ActionTimeout),
                               App.globalGet(AppVariables.PlayerTurnAddress) == App.globalGet(
                                   AppVariables.PlayerOAddress)) # win by timeout logic.

    has_o_won_by_timeout = And(App.globalGet(AppVariables.GameStatus) == Int(0),
                               Global.latest_timestamp() > App.globalGet(AppVariables.ActionTimeout),
                               App.globalGet(AppVariables.PlayerTurnAddress) == App.globalGet(
                                   AppVariables.PlayerXAddress)) # win by timeout logic.

    has_x_won = Or(has_x_won_by_playing, has_x_won_by_timeout) # anykind of win
    has_o_won = Or(has_o_won_by_playing, has_o_won_by_timeout) # anykind of win
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
```

With this function we complete the PyTeal logic implementation for the Tic-Tac-Toe smart contract. At the end we just need to declare the approval and the clear programs.

```python
def approval_program():
    return application_start()

def clear_program():
    return Return(Int(1))
```

# Escrow fund

The escrow fund smart contract is a simple stateless smart contract that is linked to the Tic-Tac-Toe ASC1. This contracts initially  receives the funds by both players. After the game end, the escrow fund should be able to sign a payment transaction to the winner of the game, or to sign transactions to both of the players in case of a tie. 

```python
def game_funds_escorw(app_id: int):
    win_refund = Seq([
        Assert(Gtxn[0].application_id() == Int(app_id)),
        Assert(Gtxn[1].fee() <= Int(1000)),
        Assert(Gtxn[1].asset_close_to() == Global.zero_address()),
        Assert(Gtxn[1].rekey_to() == Global.zero_address())
    ])

    tie_refund = Seq([
        Assert(Gtxn[0].application_id() == Int(app_id)),
        Assert(Gtxn[1].fee() <= Int(1000)),
        Assert(Gtxn[1].asset_close_to() == Global.zero_address()),
        Assert(Gtxn[1].rekey_to() == Global.zero_address()),
        Assert(Gtxn[2].fee() <= Int(1000)),
        Assert(Gtxn[2].asset_close_to() == Global.zero_address()),
        Assert(Gtxn[2].rekey_to() == Global.zero_address())
    ])

    return Seq([
        Cond(
            [Global.group_size() == Int(2), win_refund],
            [Global.group_size() == Int(3), tie_refund],
        ),
        Return(Int(1))
    ])
```



# Game Engine service

After we have finished with the implementation of the smart contracts, we need to implement the services that talk to the Algorand network.  The GameEngineService object provides an API for initializing and playing the Tic-Tac-Toe game on the blockchain. The GameEngineService API implements the following methods:

- *init* - initialization of the object, this method receives all of the private keys and addresses for the players.
- *deploy_application* - deploys the Tic-Tac-Toe ASC1 to the network.
- *start_game* - marks the start of the game by sending an atomic transfer of 3 transactions to the network.
- *play_action* - sends a transaction that plays an action in the current instance of the game. This method receives a *player_id* parameter can be either "X" or "O" and a position argument which should be integer between 0 and 8.
- *win_money_refund* - sends an atomic transfer of 2 transactions to the network which refunds the money from the escrow address to the winner of the game. Here we also pass the *player_id* as argument to note which player is the winner.
- *tie_money_refund* - sends an atomic transfer of 3 transactions to the network which refunds the money from the escrow address to both of the players. 
- *fund_escrow* - sends some Algos to the escrow address to handle the fees for the money refund payments.

## Initialization

One instance of the GameEngineService object should represent one game on the blockchain. Within the initializer we need to provide the address of the game creator as well with the addresses of the PlayerX and PlayerO.

```python
class GameEngineService:
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
```

In the initializer we fix the teal version to be 4 because we are using some of its features in the Tic-Tac-Toe ASC1. Additionally, we are loading the *approval_program()* and *clear_program()* from the Tic-Tac-Toe ASC1 that were described previously. 

## Application deployment

Once we have initialized the *GameEngineService*, the first think that we need to do is to deploy the application on the network. We deploy the application by submitting an Application Create Transaction on the network where we sent our teal code generated by the smart contract. 

```python
def deploy_application(self, client):
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

    app_transaction = \
    	ApplicationTransactionRepository.create_application(client=client,
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
```

## Start game

With this method we execute the *SetupPlayers* action in the Tic-Tac-Toe ASC1. Here we create the escrow fund address to which the players need to sent their money. This function should be called only once per game, otherwise the smart contract will reject this atomic transfer.

```python
def start_game(self, client):
    """
    Atomic transfer of 3 transactions:
    - 1. Application call
    - 2. Payment from the Player X address to the Escrow fund address
    - 3. Payment from the Player O address to the Escrow fund address
    """
    if self.app_id is None:
        raise ValueError('The application has not been deployed')

    if self.escrow_fund_address is not None or self.escrow_fund_program_bytes is not None:
        raise ValueError('The game has already started!')

    escrow_fund_program_compiled = compileTeal(game_funds_escorw(app_id=self.app_id),
                                               mode=Mode.Signature,
                                               version=self.teal_version)

    self.escrow_fund_program_bytes = \
    								NetworkInteraction.compile_program(client=client,
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
```

## Play action

Application call transaction that performs an action for the specified player at the specified action position. With this function we are updating the global state of the Tic-Tac-Toe ASC1. The *player_id* argument should be either "X" or "O".

```python
def play_action(self, client, player_id: str, action_position: int):
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
```

## Win money refund

When the game has ended the winner should be able to withdraw the money from the escrow address. This function executes the correct atomic transfer in order for the winner to be able to receive its money. In the *player_id* argument we pass the winner of the game, if we pass the wrong winner the smart contract will reject the withdrawal transaction.

```python
def win_money_refund(self, client, player_id: str):
    """
    Atomic transfer of 2 transactions:
    1. Application call
    2. Payment from the Escrow account to winner address either PlayerX or PlayerO.
    """
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

```

 ## Tie money refund

Similarly like the win money refund function, we need to handle the money refunding in case of a tie. This function executes the correct atomic transfer where the two players receive their initial funded money to the escrow account.

```python
def tie_money_refund(self, client):
    """
    Atomic transfer of 3 transactions:
    1. Application call
    2. Payment from the escrow address to the PlayerX address.
    3. Payment from the escrow address to the PlayerO address.
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
```

# Deployment on TestNet

I prepared a short video where I play a single game using the UI on the Algorand Testnet.

[![Watch the video](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/images/video_bg.png?raw=true)](https://www.youtube.com/watch?v=5FSWJR7fDZY&t=9s&ab_channel=VilijanMonev)

## Final thoughts

If you have made it this far I want to sincerely thank you for reading this solution. I hope that you learned something new and interesting as it was the case for me.

I hope that this solution will help you to build your favorite game on the Algorand Blockchain.
